from pathlib import Path

from one_dragon.envs.download_service import DownloadService


class FakeDownloadService(DownloadService):
    """用可编程的下载行为替代真实网络。"""

    def __init__(self, fail_times: int, monkeypatch_unzip=None):
        super().__init__(None, None)
        self.fail_times = fail_times
        self.download_calls = 0
        self._monkeypatch_unzip = monkeypatch_unzip

    def download_env_file(self, file_name: str, save_file_path: str,
                          progress_callback=None) -> bool:
        self.download_calls += 1
        if self.download_calls <= self.fail_times:
            # 模拟下载失败时残留不完整文件
            Path(save_file_path).write_bytes(b'partial')
            return False
        Path(save_file_path).write_bytes(b'PK\x03\x04fake-zip')
        return True


def test_download_failure_retries(monkeypatch, tmp_path: Path) -> None:
    """下载失败应纳入重试 全部次数耗尽后才返回 False。"""
    service = FakeDownloadService(fail_times=2)
    ok = service.download_and_extract_env_file(
        'env.zip', str(tmp_path / 'temp'), str(tmp_path / 'extract'), retry_count=2)

    assert not ok
    assert service.download_calls == 2


def test_download_failure_then_success(monkeypatch, tmp_path: Path) -> None:
    """第 1 次下载失败后重试成功。"""
    monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file',
                        lambda src, dst: True)
    service = FakeDownloadService(fail_times=1)
    ok = service.download_and_extract_env_file(
        'env.zip', str(tmp_path / 'temp'), str(tmp_path / 'extract'), retry_count=2)

    assert ok
    assert service.download_calls == 2


def test_corrupt_zip_still_redownloads(monkeypatch, tmp_path: Path) -> None:
    """损坏 zip 删除重下的既有语义保持。"""
    service = FakeDownloadService(fail_times=0)
    monkeypatch.setattr('one_dragon.envs.download_service.file_utils.unzip_file',
                        lambda src, dst: service.download_calls >= 2)
    ok = service.download_and_extract_env_file(
        'env.zip', str(tmp_path / 'temp'), str(tmp_path / 'extract'), retry_count=2)

    assert ok
    assert service.download_calls == 2
