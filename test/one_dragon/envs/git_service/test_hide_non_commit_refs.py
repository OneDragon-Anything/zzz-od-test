from pathlib import Path

import pygit2
import pytest
from pygit2 import Repository

from one_dragon.envs.git_service import _hide_non_commit_refs, _restore_hidden_refs


def _make_commit(repo: pygit2.Repository, msg: str, parent=None):
    """在仓库里创建一个 commit 并指向 refs/heads/main。"""
    blob = repo.create_blob(f'content-{msg}'.encode())
    tree_builder = repo.TreeBuilder()
    tree_builder.insert('a.txt', blob, pygit2.enums.FileMode.BLOB)
    tree = tree_builder.write()
    sig = pygit2.Signature('test', 'test@test')
    parents = [parent] if parent is not None else []
    return repo.create_commit('refs/heads/main', sig, sig, msg, tree, parents)


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Repository, Repository, str]:
    """远端仓库(main 领先) + 正式仓库(main 落后 + 指向 tree 的 Codex 引用) + 临时 fetch 仓库。

    临时仓库通过 alternates 共享正式仓库的对象目录，
    对齐 git_service 实际导入 fetch 结果时的环境。
    """
    remote_dir = tmp_path / 'remote'
    remote_repo = pygit2.init_repository(str(remote_dir), bare=True)
    _make_commit(remote_repo, 'first')
    remote_main = _make_commit(remote_repo, 'second',
                               remote_repo.references['refs/heads/main'].target)

    user_dir = tmp_path / 'user'
    user_repo = pygit2.init_repository(str(user_dir), bare=True)
    local_c = _make_commit(user_repo, 'local-old')
    codex_tree = user_repo.get(local_c).tree.id
    # 模拟 Codex CLI 留下的指向 tree 对象的引用
    user_repo.references.create('refs/codex/turn-diffs/checkpoints/x', codex_tree)

    temp_dir = tmp_path / 'temp'
    temp_repo = pygit2.init_repository(str(temp_dir), bare=True)
    temp_repo.remotes.create('origin', str(remote_dir))
    temp_repo.remotes['origin'].fetch(refspecs=['+refs/heads/main:refs/heads/main'])
    alternates = temp_dir / 'objects' / 'info' / 'alternates'
    alternates.parent.mkdir(parents=True, exist_ok=True)
    alternates.write_text(str(user_dir / 'objects'), encoding='utf-8')

    return Repository(str(user_dir)), remote_repo, str(temp_dir)


def test_local_fetch_fails_with_non_commit_ref(repos) -> None:
    """复现：正式仓库有指向 tree 的引用时 本地导入 fetch 报 object is not a committish。"""
    user_repo, _, temp_dir = repos
    user_repo.remotes.create('origin', temp_dir)
    user_repo.config['remote.origin.tagopt'] = '--no-tags'
    with pytest.raises(ValueError, match='committish'):
        user_repo.remotes['origin'].fetch(
            refspecs=['+refs/heads/main:refs/remotes/origin/main'])


def test_hide_refs_allows_fetch_and_restores(repos) -> None:
    """隐藏非 commit 引用后 fetch 成功 且引用与对象完整恢复。"""
    user_repo, remote_repo, temp_dir = repos
    codex_tree = user_repo.references['refs/codex/turn-diffs/checkpoints/x'].target

    user_repo.remotes.create('origin', temp_dir)
    user_repo.config['remote.origin.tagopt'] = '--no-tags'

    hidden_refs: list[tuple[str, object]] = []
    try:
        _hide_non_commit_refs(user_repo, hidden_refs)
        assert [name for name, _ in hidden_refs] == ['refs/codex/turn-diffs/checkpoints/x']
        user_repo.remotes['origin'].fetch(
            refspecs=['+refs/heads/main:refs/remotes/origin/main'])
        remote_main = remote_repo.references['refs/heads/main'].target
        assert str(user_repo.references['refs/remotes/origin/main'].target) == str(remote_main)
    finally:
        _restore_hidden_refs(user_repo, hidden_refs)

    refs_after = list(user_repo.references)
    assert 'refs/codex/turn-diffs/checkpoints/x' in refs_after
    assert str(user_repo.references['refs/codex/turn-diffs/checkpoints/x'].target) == str(codex_tree)
    # 引用指向的对象仍在对象库中
    assert user_repo[codex_tree].type_str == 'tree'


def test_hide_refs_keeps_normal_refs(tmp_path: Path) -> None:
    """正常引用(分支/附注标签)不会被隐藏。"""
    repo = pygit2.init_repository(str(tmp_path / 'normal'), bare=True)
    commit = _make_commit(repo, 'base')
    sig = pygit2.Signature('test', 'test@test')
    # 附注标签指向 commit 不应被隐藏
    repo.create_tag('v1', commit, pygit2.enums.ObjectType.COMMIT, sig, 'note')

    hidden_refs: list[tuple[str, object]] = []
    _hide_non_commit_refs(repo, hidden_refs)

    assert hidden_refs == []
    assert 'refs/heads/main' in list(repo.references)
    assert 'refs/tags/v1' in list(repo.references)
