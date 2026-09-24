from types import SimpleNamespace

from one_dragon.envs.python_service import PythonService


def create_python_service(uv_path: str) -> PythonService:
    """
    构造只用于 uv_check_sync_status 的服务，UV 未装分支不触碰其余依赖
    """
    return PythonService(None, SimpleNamespace(uv_path=uv_path), None)


def test_check_sync_status_returns_false_when_uv_path_empty() -> None:
    """
    首次安装时 UV 路径为空，不应执行命令（避免空路径报 WinError 87），
    直接视为未同步交由安装流程先装 UV
    """
    service = create_python_service('')

    assert service.uv_check_sync_status() is False


def test_check_sync_status_returns_false_when_uv_path_missing(tmp_path) -> None:
    """
    UV 配置路径指向不存在的文件时同样视为未同步
    """
    missing_path = str(tmp_path / 'not_exist' / 'uv.exe')
    service = create_python_service(missing_path)

    assert service.uv_check_sync_status() is False
