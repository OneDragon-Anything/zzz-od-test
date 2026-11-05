"""tools/ci/get_version.py 的版本号计算。"""

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[3] / 'tools' / 'ci' / 'get_version.py'
spec = importlib.util.spec_from_file_location('get_version_tool', MODULE_PATH)
get_version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(get_version)


class TestNextVersion:

    def test_no_tag_starts_from_initial_beta(self) -> None:
        assert get_version.next_version(None) == 'v0.1.0-beta.1'

    def test_beta_tag_increments(self) -> None:
        assert get_version.next_version('v2.5.2-beta.3') == 'v2.5.2-beta.4'

    def test_stable_tag_starts_new_beta(self) -> None:
        # 稳定版之后从补丁号 +1 开始新的 beta 序列
        assert get_version.next_version('v2.5.2') == 'v2.5.3-beta.1'


class TestVersionSort:

    def test_stable_sorts_after_its_beta(self) -> None:
        # v2.6.0 比 v2.6.0-beta.2 新，递增应该继续在 v2.6.0 上算
        tags = sorted(
            ['v2.6.0-beta.2', 'v2.6.0'],
            key=get_version._version_sort_key,
            reverse=True,
        )
        assert tags[0] == 'v2.6.0'

    def test_unknown_tag_sorts_last(self) -> None:
        assert get_version._version_sort_key('not-a-tag') < get_version._version_sort_key('v0.0.1')


class TestResolveVersion:

    def test_manual_version_input_is_used(self) -> None:
        assert get_version.resolve_version(
            github_ref='refs/heads/main',
            create_release=True,
            version_input='v2.6.0',
            remote_tags=['v2.5.2'],
            short_hash='abc123',
            pr_number=None,
        ) == 'v2.6.0'

    def test_manual_beta_version_input_is_used(self) -> None:
        assert get_version.resolve_version(
            github_ref='refs/heads/main',
            create_release=True,
            version_input='v2.6.0-beta.1',
            remote_tags=[],
            short_hash='abc123',
            pr_number=None,
        ) == 'v2.6.0-beta.1'

    def test_invalid_manual_version_raises(self) -> None:
        with pytest.raises(ValueError):
            get_version.resolve_version(
                github_ref='refs/heads/main',
                create_release=True,
                version_input='2.6.0',
                remote_tags=[],
                short_hash='abc123',
                pr_number=None,
            )

    def test_version_input_ignored_without_create_release(self) -> None:
        # 只构建不发版时不该被手填版本号卡住
        assert get_version.resolve_version(
            github_ref='refs/heads/main',
            create_release=False,
            version_input='2.6.0',
            remote_tags=[],
            short_hash='abc123',
            pr_number=None,
        ) == 'dev+abc123'

    def test_manual_release_auto_increments_from_latest_tag(self) -> None:
        assert get_version.resolve_version(
            github_ref='refs/heads/main',
            create_release=True,
            version_input='',
            remote_tags=['v2.5.2-beta.3', 'v2.4.0'],
            short_hash='abc123',
            pr_number=None,
        ) == 'v2.5.2-beta.4'

    def test_tag_ref_reuses_tag(self) -> None:
        assert get_version.resolve_version(
            github_ref='refs/tags/v2.6.0',
            create_release=True,
            version_input='',
            remote_tags=['v2.6.0'],
            short_hash='abc123',
            pr_number=None,
        ) == 'v2.6.0'

    def test_tag_ref_ignores_mismatched_input(self) -> None:
        # 补发版必须用当前 ref 的 tag，不能让产物挂到别的已有 tag 上
        assert get_version.resolve_version(
            github_ref='refs/tags/v2.6.0',
            create_release=True,
            version_input='v2.5.0',
            remote_tags=['v2.5.0'],
            short_hash='abc123',
            pr_number=None,
        ) == 'v2.6.0'

    def test_pr_build_version(self) -> None:
        assert get_version.resolve_version(
            github_ref='refs/pull/3003/merge',
            create_release=False,
            version_input='',
            remote_tags=[],
            short_hash='abc123',
            pr_number='3003',
        ) == 'pr3003+abc123'

    def test_dev_build_version(self) -> None:
        assert get_version.resolve_version(
            github_ref='refs/heads/main',
            create_release=False,
            version_input='',
            remote_tags=[],
            short_hash='abc123',
            pr_number=None,
        ) == 'dev+abc123'


class TestTagExistsOnRemote:

    def test_exact_ref_match(self, monkeypatch) -> None:
        calls: list[list[str]] = []

        class Result:
            returncode = 0
            stdout = 'abc123\trefs/tags/v2.6.0\n'

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return Result()

        monkeypatch.setattr(get_version.subprocess, 'run', fake_run)

        assert get_version.tag_exists_on_remote('v2.6.0') is True
        assert 'refs/tags/v2.6.0' in calls[0]

    def test_no_match(self, monkeypatch) -> None:
        class Result:
            returncode = 0
            stdout = ''

        monkeypatch.setattr(get_version.subprocess, 'run', lambda *a, **k: Result())

        assert get_version.tag_exists_on_remote('v2.6.0') is False

    def test_ls_remote_failure_raises(self, monkeypatch) -> None:
        class Result:
            returncode = 128
            stdout = ''

        monkeypatch.setattr(get_version.subprocess, 'run', lambda *a, **k: Result())

        with pytest.raises(RuntimeError):
            get_version.tag_exists_on_remote('v2.6.0')
