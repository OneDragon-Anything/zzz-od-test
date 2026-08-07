"""测试 src 损坏时的健康检查与恢复逻辑（launcher/src_recovery.py）。"""

import shutil
import sys
import time
import zipfile
from pathlib import Path

import pytest

from one_dragon.launcher import src_recovery as src_recovery_module
from one_dragon.launcher.src_recovery import (
    SRC_REQUIRED_RELATIVE_PATHS,
    _backup_src_dir,
    _check_downloaded_manifest_compatible,
    _extract_src_members,
    _get_manifest_path_in_zip,
    _recover_src_from_zip,
    download_latest_version,
    is_src_healthy,
    recover_from_embedded_src,
)


def _make_src_tree(root: Path) -> None:
    """构造一个结构完整的假 src/ 目录。"""
    for relative_path in SRC_REQUIRED_RELATIVE_PATHS:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# fake source\n', encoding='utf-8')


def _make_src_zip(zip_path: Path, root: Path) -> None:
    """把假 src/ 目录打包成条目带 src/ 前缀的 zip。"""
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            zf.write(path, f'src/{path.relative_to(root).as_posix()}')


class TestIsSrcHealthy:
    """健康检查。"""

    def test_healthy_src(self, tmp_path: Path) -> None:
        _make_src_tree(tmp_path / 'src')
        healthy, reason = is_src_healthy(tmp_path / 'src')
        assert healthy
        assert reason == ''

    def test_missing_src(self, tmp_path: Path) -> None:
        healthy, reason = is_src_healthy(tmp_path / 'not_exists')
        assert not healthy
        assert 'src 目录不存在' in reason

    def test_partial_src(self, tmp_path: Path) -> None:
        src = tmp_path / 'src'
        src.mkdir()
        (src / 'one_dragon').mkdir()
        healthy, reason = is_src_healthy(src)
        assert not healthy
        assert '缺少关键文件' in reason

    def test_empty_file_counts_as_damaged(self, tmp_path: Path) -> None:
        src = tmp_path / 'src'
        for relative_path in SRC_REQUIRED_RELATIVE_PATHS:
            path = src / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('', encoding='utf-8')
        healthy, _ = is_src_healthy(src)
        assert not healthy


class TestBackupSrcDir:
    """损坏 src 的备份。"""

    def test_backup_existing(self, tmp_path: Path) -> None:
        src = tmp_path / 'src'
        src.mkdir()
        (src / 'marker.txt').write_text('x', encoding='utf-8')

        backup_dir, error = _backup_src_dir(src)
        assert error == ''
        assert backup_dir is not None
        assert backup_dir.name.startswith('src.corrupted.')
        assert (backup_dir / 'marker.txt').is_file()
        assert not src.exists()

    def test_backup_missing_src(self, tmp_path: Path) -> None:
        src = tmp_path / 'src'
        backup_dir, error = _backup_src_dir(src)
        assert error == ''
        assert backup_dir is None

    def test_backup_unique_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 固定时间戳，确保撞上与 _backup_src_dir 相同名称的已有备份，走到加后缀分支
        monkeypatch.setattr(time, 'strftime', lambda _fmt: '20250101_000000')
        src = tmp_path / 'src'
        src.mkdir()
        occupied = tmp_path / 'src.corrupted.20250101_000000'
        occupied.mkdir()
        (occupied / 'keep.txt').write_text('x', encoding='utf-8')

        backup_dir, error = _backup_src_dir(src)
        assert error == ''
        assert backup_dir is not None
        assert backup_dir.name.startswith('src.corrupted.20250101_000000.')
        assert backup_dir != occupied
        assert (occupied / 'keep.txt').is_file(), '重名时不应覆盖已有备份'


class TestExtractSrcMembers:
    """从 zip 解压 src/ 条目。"""

    def test_extract_normal(self, tmp_path: Path) -> None:
        fake_src = tmp_path / 'fake_src'
        _make_src_tree(fake_src)
        zip_path = tmp_path / 'src.zip'
        _make_src_zip(zip_path, fake_src)

        install_dir = tmp_path / 'install'
        install_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            count = _extract_src_members(zf, install_dir)

        assert count > 0
        assert (install_dir / 'src' / 'one_dragon' / 'envs' / 'git_service.py').is_file()

    def test_extract_zip_slip_rejected(self, tmp_path: Path) -> None:
        zip_path = tmp_path / 'evil.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('src/../../evil.txt', 'boom')

        install_dir = tmp_path / 'install'
        install_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf, pytest.raises(ValueError, match='非法路径'):
            _extract_src_members(zf, install_dir)


class TestRecoverFromZip:
    """恢复流程（备份 + 解压）。"""

    def test_recover_success_with_backup(self, tmp_path: Path) -> None:
        fake_src = tmp_path / 'fake_src'
        _make_src_tree(fake_src)
        zip_path = tmp_path / 'src.zip'
        _make_src_zip(zip_path, fake_src)

        install_dir = tmp_path / 'install'
        install_dir.mkdir()
        src_dir = install_dir / 'src'
        src_dir.mkdir()
        (src_dir / 'damaged.txt').write_text('x', encoding='utf-8')

        progress_log: list[tuple[float, str]] = []
        success, message = _recover_src_from_zip(
            zip_path, src_dir, '内置代码', lambda p, m: progress_log.append((p, m))
        )
        assert success
        assert '已恢复内置代码' in message
        assert '备份' in message
        assert (src_dir / 'one_dragon' / 'envs' / 'git_service.py').is_file()
        backups = list(install_dir.glob('src.corrupted.*'))
        assert len(backups) == 1
        assert (backups[0] / 'damaged.txt').is_file()

    def test_recover_missing_src_no_backup(self, tmp_path: Path) -> None:
        fake_src = tmp_path / 'fake_src'
        _make_src_tree(fake_src)
        zip_path = tmp_path / 'src.zip'
        _make_src_zip(zip_path, fake_src)

        install_dir = tmp_path / 'install'
        install_dir.mkdir()
        src_dir = install_dir / 'src'

        success, message = _recover_src_from_zip(zip_path, src_dir, '内置代码')
        assert success
        assert '备份' not in message
        assert (src_dir / 'one_dragon' / 'envs' / 'git_service.py').is_file()

    def test_recover_corrupted_zip(self, tmp_path: Path) -> None:
        zip_path = tmp_path / 'broken.zip'
        zip_path.write_bytes(b'not a zip')

        install_dir = tmp_path / 'install'
        install_dir.mkdir()
        src_dir = install_dir / 'src'
        src_dir.mkdir()

        success, message = _recover_src_from_zip(zip_path, src_dir, '内置代码')
        assert not success
        assert '解压内置代码失败' in message


class TestRecoverFromEmbedded:
    """从内嵌源码包恢复。"""

    def test_embedded_zip_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        success, message = recover_from_embedded_src(tmp_path / 'src')
        assert not success
        assert '未找到内嵌源码包' in message


class TestManifestCompatibility:
    """下载包的模块清单兼容校验。"""

    def _write_meipass_manifest(self, tmp_path: Path, content: bytes) -> None:
        (tmp_path / 'module_manifest.py').write_bytes(content)

    def _make_download_zip(self, tmp_path: Path, manifest: bytes) -> Path:
        zip_path = tmp_path / 'download.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('src/deploy/module_manifest.py', manifest)
            zf.writestr('src/config/project.yml', 'manifest_path: deploy/module_manifest.py\n')
        return zip_path

    def test_same_manifest_compatible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest = b'import sys\nif not getattr(sys, "frozen", False):\n    pass\n'
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        self._write_meipass_manifest(tmp_path, manifest)
        zip_path = self._make_download_zip(tmp_path, manifest)

        compatible, message = _check_downloaded_manifest_compatible(zip_path)
        assert compatible
        assert message == ''

    def test_crlf_normalized_compatible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest = b'import sys\nif not getattr(sys, "frozen", False):\n    pass\n'
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        self._write_meipass_manifest(tmp_path, manifest.replace(b'\n', b'\r\n'))
        zip_path = self._make_download_zip(tmp_path, manifest)

        compatible, _ = _check_downloaded_manifest_compatible(zip_path)
        assert compatible

    def test_diff_manifest_incompatible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        local_manifest = b'import sys\nif not getattr(sys, "frozen", False):\n    pass\n'
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        self._write_meipass_manifest(tmp_path, local_manifest)
        zip_path = self._make_download_zip(tmp_path, local_manifest + b'# changed\n')

        compatible, message = _check_downloaded_manifest_compatible(zip_path)
        assert not compatible
        assert '更新' in message

    def test_bad_zip_returns_incompatible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 下载文件不是合法 zip（如 HTML 错误页）时，应返回明确的失败提示而非抛异常
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        self._write_meipass_manifest(tmp_path, b'local manifest')
        broken_zip = tmp_path / 'broken.zip'
        broken_zip.write_bytes(b'<html>error page</html>')

        compatible, message = _check_downloaded_manifest_compatible(broken_zip)
        assert not compatible
        assert '损坏' in message

    def test_no_local_manifest_skips(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        zip_path = self._make_download_zip(tmp_path, b'whatever')

        compatible, _ = _check_downloaded_manifest_compatible(zip_path)
        assert compatible

    def test_manifest_path_read_from_project_yml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        self._write_meipass_manifest(tmp_path, b'local')
        zip_path = tmp_path / 'download.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('src/config/project.yml', 'manifest_path: deploy/other_manifest.py\n')
            zf.writestr('src/deploy/other_manifest.py', b'local')

        with zipfile.ZipFile(zip_path) as zf:
            assert _get_manifest_path_in_zip(zf) == 'deploy/other_manifest.py'
        compatible, _ = _check_downloaded_manifest_compatible(zip_path)
        assert compatible


class TestDownloadLatest:
    """下载最新版本（mock 网络与文件操作）。"""

    def test_download_config_incomplete(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # project.yml 存在但缺必需键（如 github_homepage）时，应视为配置无效
        meipass = tmp_path / 'meipass'
        project_yml = meipass / 'resources' / 'config' / 'project.yml'
        project_yml.parent.mkdir(parents=True)
        project_yml.write_text('project_name: "FakeDragon"\n', encoding='utf-8')
        monkeypatch.setattr(sys, '_MEIPASS', str(meipass), raising=False)

        success, message = download_latest_version(tmp_path / 'src')
        assert not success
        assert '无法读取项目配置' in message

    def test_download_config_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
        success, message = download_latest_version(tmp_path / 'src')
        assert not success
        assert '无法读取项目配置' in message

    def test_download_manifest_incompatible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 构造 project.yml + 本地清单 + 兼容校验失败的下载 zip
        meipass = tmp_path / 'meipass'
        project_yml = meipass / 'resources' / 'config' / 'project.yml'
        project_yml.parent.mkdir(parents=True)
        project_yml.write_text(
            'project_name: "FakeDragon"\n'
            'github_homepage: "https://github.example/FakeDragon"\n',
            encoding='utf-8',
        )
        (meipass / 'module_manifest.py').write_bytes(b'local manifest')
        monkeypatch.setattr(sys, '_MEIPASS', str(meipass), raising=False)

        download_zip = tmp_path / 'download.zip'
        with zipfile.ZipFile(download_zip, 'w') as zf:
            zf.writestr('src/deploy/module_manifest.py', b'remote manifest')
            zf.writestr('src/config/project.yml', 'manifest_path: deploy/module_manifest.py\n')

        def fake_download(url: str, dest_path: Path, proxy: str | None, callback=None) -> None:
            assert 'FakeDragon-WithRuntime.zip' in url
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(download_zip, dest_path)

        monkeypatch.setattr(src_recovery_module, '_download_file', fake_download)

        src_dir = tmp_path / 'install' / 'src'
        success, message = download_latest_version(src_dir)
        assert not success
        assert '不兼容' in message or '更新' in message
        assert not src_dir.exists(), '不兼容时不应恢复 src'
