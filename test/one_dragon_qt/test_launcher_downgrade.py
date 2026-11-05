"""启动器不支持降级：目标版本低于当前版本时不提供下载。"""

from one_dragon.envs.update_service import is_launcher_downgrade


class TestIsLauncherDowngrade:

    def test_target_lower(self) -> None:
        assert is_launcher_downgrade('v2.6.0', 'v2.5.1') is True

    def test_target_higher(self) -> None:
        assert is_launcher_downgrade('v2.5.1', 'v2.6.0') is False

    def test_same_version(self) -> None:
        assert is_launcher_downgrade('v2.6.0', 'v2.6.0') is False

    def test_not_installed(self) -> None:
        assert is_launcher_downgrade('', 'v2.6.0') is False

    def test_unknown_target(self) -> None:
        assert is_launcher_downgrade('v2.6.0', 'latest') is False

    def test_bad_version_text(self) -> None:
        assert is_launcher_downgrade('v2.6.0', 'beta') is False
