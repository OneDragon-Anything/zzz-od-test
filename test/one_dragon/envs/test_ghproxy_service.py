"""测试 GhProxyService 的代理候选线路生成。"""

from types import SimpleNamespace

from one_dragon.envs.ghproxy_service import GhProxyService


def create_service(gh_proxy_url: str) -> GhProxyService:
    env_config = SimpleNamespace(gh_proxy_url=gh_proxy_url)
    return GhProxyService(env_config)


def test_candidates_prioritize_last_success_line() -> None:
    service = create_service('https://proxy.example')

    assert service.get_proxy_candidates() == [
        'https://proxy.example',
        'https://ghfast.top',
        'https://gh-proxy.com',
        'https://ghproxy.net',
        'https://ghp.ci',
    ]


def test_candidates_deduplicate_builtin_last_line() -> None:
    service = create_service('https://ghproxy.net')

    assert service.get_proxy_candidates() == [
        'https://ghproxy.net',
        'https://ghfast.top',
        'https://gh-proxy.com',
        'https://ghp.ci',
    ]


def test_candidates_ignore_blank_last_line() -> None:
    service = create_service('   ')

    assert service.get_proxy_candidates() == [
        'https://ghfast.top',
        'https://gh-proxy.com',
        'https://ghproxy.net',
        'https://ghp.ci',
    ]
