"""GitHub 代理线路的候选顺序、探测与记录。"""
from types import SimpleNamespace

import pytest

from one_dragon.envs.ghproxy_service import GhProxyService


class _FakeEnvConfig:
    """只带代理相关字段的 EnvConfig 替身。"""

    def __init__(self, current: str = 'https://first.example', last: str = '') -> None:
        self.gh_proxy_url: str = current
        self.last_gh_proxy_url: str = last


def _create_service(
    current: str = 'https://first.example',
    last: str = '',
    builtin: tuple[str, ...] = ('https://first.example', 'https://second.example', 'https://third.example'),
) -> tuple[GhProxyService, _FakeEnvConfig]:
    env_config = _FakeEnvConfig(current, last)
    repo_config = SimpleNamespace(gh_proxy_urls=builtin)
    return GhProxyService(env_config, repo_config), env_config


class TestCandidateOrder:

    def test_current_then_last_success_then_builtin(self) -> None:
        service, _ = _create_service(current='https://custom.example', last='https://second.example')

        assert service.get_candidate_urls() == [
            'https://custom.example',
            'https://second.example',
            'https://first.example',
            'https://third.example',
        ]

    def test_duplicates_are_removed(self) -> None:
        service, _ = _create_service(current='https://first.example', last='https://first.example/')

        assert service.get_candidate_urls() == [
            'https://first.example',
            'https://second.example',
            'https://third.example',
        ]

    def test_trailing_slash_is_normalized(self) -> None:
        service, _ = _create_service(current='https://first.example/', last='')

        assert service.get_candidate_urls()[0] == 'https://first.example'

    def test_empty_current_url_is_ignored(self) -> None:
        service, _ = _create_service(current='', last='')

        assert service.get_candidate_urls() == [
            'https://first.example',
            'https://second.example',
            'https://third.example',
        ]


class TestUpdateProxyUrl:

    def test_first_available_line_is_recorded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, env_config = _create_service()
        checked: list[str] = []

        def fake_check(url: str) -> bool:
            checked.append(url)
            return url == 'https://second.example'

        monkeypatch.setattr(service, 'check_url', fake_check)

        assert service.update_proxy_url() is True
        assert checked == ['https://first.example', 'https://second.example']
        assert env_config.gh_proxy_url == 'https://second.example'
        assert env_config.last_gh_proxy_url == 'https://second.example'

    def test_all_lines_unavailable_keeps_current(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, env_config = _create_service()

        monkeypatch.setattr(service, 'check_url', lambda url: False)

        assert service.update_proxy_url() is False
        assert env_config.gh_proxy_url == 'https://first.example'
        assert env_config.last_gh_proxy_url == ''

    def test_each_line_is_probed_only_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service(last='https://second.example')
        checked: list[str] = []

        def fake_check(url: str) -> bool:
            checked.append(url)
            return False

        monkeypatch.setattr(service, 'check_url', fake_check)

        service.update_proxy_url()
        assert checked == [
            'https://first.example',
            'https://second.example',
            'https://third.example',
        ]


class TestCheckUrl:

    def test_ok_response_is_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service()

        class _Response:
            status_code = 200

            def iter_content(self, chunk_size: int):
                yield b'[project]\nname = "ZenlessZoneZero-OneDragon"\n'

            def close(self) -> None:
                pass

        monkeypatch.setattr(
            'one_dragon.envs.ghproxy_service.requests.get',
            lambda url, timeout, stream: _Response(),
        )

        assert service.check_url('https://first.example') is True

    def test_html_challenge_page_is_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service()

        class _Response:
            status_code = 200

            def iter_content(self, chunk_size: int):
                yield b'<!DOCTYPE html><html><body>checking your browser</body></html>'

            def close(self) -> None:
                pass

        monkeypatch.setattr(
            'one_dragon.envs.ghproxy_service.requests.get',
            lambda url, timeout, stream: _Response(),
        )

        assert service.check_url('https://first.example') is False

    def test_error_status_is_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service()

        class _Response:
            status_code = 502

            def iter_content(self, chunk_size: int):
                return iter(())

            def close(self) -> None:
                pass

        monkeypatch.setattr(
            'one_dragon.envs.ghproxy_service.requests.get',
            lambda url, timeout, stream: _Response(),
        )

        assert service.check_url('https://first.example') is False

    def test_exception_is_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service, _ = _create_service()

        def raise_error(url: str, timeout: int, stream: bool):
            raise ConnectionError('boom')

        monkeypatch.setattr('one_dragon.envs.ghproxy_service.requests.get', raise_error)

        assert service.check_url('https://first.example') is False


class TestRememberSuccess:

    def test_remember_success_updates_both_fields(self) -> None:
        service, env_config = _create_service()

        service.remember_success('https://third.example/')

        assert env_config.gh_proxy_url == 'https://third.example'
        assert env_config.last_gh_proxy_url == 'https://third.example'

    def test_remember_success_by_url_finds_prefix(self) -> None:
        service, env_config = _create_service()

        matched = service.remember_success_by_url(
            'https://second.example/https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon.git'
        )

        assert matched == 'https://second.example'
        assert env_config.last_gh_proxy_url == 'https://second.example'

    def test_remember_success_by_url_ignores_unknown_prefix(self) -> None:
        service, env_config = _create_service()

        assert service.remember_success_by_url('https://github.com/a/b.git') is None
        assert env_config.last_gh_proxy_url == ''


class TestFailedLines:

    def test_mark_failed_puts_line_behind(self) -> None:
        service, _ = _create_service()

        service.mark_failed('https://first.example/')

        assert service.get_candidate_urls() == [
            'https://second.example',
            'https://third.example',
            'https://first.example',
        ]

    def test_all_lines_marked_failed_falls_back_to_full_list(self) -> None:
        service, _ = _create_service()

        for url in ('https://first.example', 'https://second.example', 'https://third.example'):
            service.mark_failed(url)

        assert service.get_candidate_urls() == [
            'https://first.example',
            'https://second.example',
            'https://third.example',
        ]

    def test_remember_success_clears_failed_mark(self) -> None:
        service, _ = _create_service()
        service.mark_failed('https://second.example')

        service.remember_success('https://second.example')

        assert service.get_candidate_urls()[0] == 'https://second.example'

    def test_remember_success_by_url_prefers_longest_prefix(self) -> None:
        service, env_config = _create_service(
            current='https://proxy.example',
            builtin=('https://proxy.example', 'https://proxy.example/working'),
        )

        matched = service.remember_success_by_url(
            'https://proxy.example/working/https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon.git'
        )

        assert matched == 'https://proxy.example/working'
        assert env_config.last_gh_proxy_url == 'https://proxy.example/working'
