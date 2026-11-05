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
