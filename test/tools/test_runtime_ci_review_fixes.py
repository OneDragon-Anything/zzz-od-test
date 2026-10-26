"""覆盖发布包选择、下载凭据与兼容性检查子进程的审查修复。"""
import ast
import importlib.util
import io
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import ModuleType

import pytest


def _load_script(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[3] / 'tools' / 'ci' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load_script('check_runtime_compatibility')
ASSETS = _load_script('prepare_release_assets')


def _release(tag: str, assets: list[dict] | None = None, **flags: bool) -> dict:
    return {'tag_name': tag, 'assets': assets or [], **flags}


def _asset(url: str = 'https://api.github.com/assets/1') -> dict:
    return {'name': CHECKER.ASSET_NAME, 'url': url}


def test_latest_release_skips_drafts_and_prereleases(monkeypatch: pytest.MonkeyPatch) -> None:
    data = [None, _release('draft', [_asset()], draft=True),
            _release('beta', [_asset()], prerelease=True), _release('new', [_asset()]),
            _release('old', [_asset('https://api.github.com/assets/old')])]
    monkeypatch.setattr(CHECKER, '_fetch_json', lambda *args: data)
    assert CHECKER._latest_stable_release('token') == ('new', _asset()['url'])


@pytest.mark.parametrize('assets', [[], [_asset('')], [{'name': 'other.zip', 'url': 'https://example.com'}]])
def test_latest_release_does_not_fall_back(monkeypatch: pytest.MonkeyPatch, assets: list[dict]) -> None:
    monkeypatch.setattr(CHECKER, '_fetch_json', lambda *args: [_release('new', assets), _release('old', [_asset()])])
    with pytest.raises(RuntimeError, match='最新正式版 new 没有找到'):
        CHECKER._latest_stable_release('token')


def test_no_stable_release_has_distinct_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, '_fetch_json', lambda *args: [_release('beta', prerelease=True)])
    with pytest.raises(RuntimeError, match='没有正式版'):
        CHECKER._latest_stable_release('token')


def test_malformed_latest_release_does_not_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CHECKER, '_fetch_json', lambda *args: [{'tag_name': 'new', 'assets': None}, _release('old', [_asset()])])
    with pytest.raises(RuntimeError, match='标签或资产列表无效'):
        CHECKER._latest_stable_release('token')


@pytest.mark.parametrize('module', [CHECKER, ASSETS], ids=['checker', 'release_assets'])
@pytest.mark.parametrize('source,target,keeps_token', [
    ('https://api.github.com/asset', 'https://release-assets.githubusercontent.com/file', False),
    ('https://api.github.com/asset', 'https://API.GITHUB.COM/another', True),
    ('https://api.github.com/asset', 'https://api.github.com:443/another', True),
    ('https://api.github.com:443/asset', 'https://api.github.com/another', True),
    ('https://api.github.com/asset', 'https://api.github.com:8443/another', False),
    ('https://api.github.com:8443/asset', 'https://api.github.com/another', False),
    ('https://api.github.com/asset', 'https://api.github.com:0/another', False),
    ('http://api.github.com/asset', 'https://api.github.com/another', False),
    ('http://api.github.com/asset', 'http://api.github.com:80/another', True),
    ('http://api.github.com:80/asset', 'http://api.github.com/another', True),
])
def test_redirect_authorization(module: ModuleType, source: str, target: str, keeps_token: bool) -> None:
    original = urllib.request.Request(source, headers={
        'Authorization': 'Bearer test-only', 'Accept': 'application/octet-stream',
    })
    handler = module._DownloadRedirectHandler()
    if source.startswith('https://') and target.startswith('http://'):
        with pytest.raises(module.urllib.error.HTTPError):
            handler.redirect_request(original, None, 302, 'Found', {}, target)
        return
    redirected = handler.redirect_request(original, None, 302, 'Found', {}, target)
    assert redirected is not None
    assert redirected.get_header('Authorization') == ('Bearer test-only' if keeps_token else None)
    assert redirected.get_header('Accept') == 'application/octet-stream'
    assert original.get_header('Authorization') == 'Bearer test-only'


@pytest.mark.parametrize('module', [CHECKER, ASSETS], ids=['checker', 'release_assets'])
def test_redirect_without_authorization_allows_https_downgrade(module: ModuleType) -> None:
    original = urllib.request.Request('https://api.github.com/asset')
    redirected = module._DownloadRedirectHandler().redirect_request(
        original, None, 302, 'Found', {}, 'http://api.github.com/asset',
    )
    assert redirected is not None
    assert redirected.get_header('Authorization') is None


@pytest.mark.parametrize('module', [CHECKER, ASSETS], ids=['checker', 'release_assets'])
def test_download_uses_redirect_handler(module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: int) -> io.BytesIO:
            calls.append((request, timeout))
            return io.BytesIO(b'asset-content')

    def build_opener(handler: object) -> Opener:
        assert isinstance(handler, module._DownloadRedirectHandler)
        return Opener()

    monkeypatch.setattr(module.urllib.request, 'build_opener', build_opener)
    destination = tmp_path / 'asset.zip'
    module._download('https://api.github.com/asset', destination, token='test-only')
    assert destination.read_bytes() == b'asset-content'
    assert calls[0][0].get_header('Authorization') == 'Bearer test-only'


def test_bootstrap_keeps_dll_handle_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap = tmp_path / 'bootstrap.py'
    CHECKER._write_bootstrap(bootstrap, tmp_path, tmp_path / 'PYZ.pyz', tmp_path, tmp_path, tmp_path / 'manifest.py')
    tree = ast.parse(bootstrap.read_text(encoding='utf-8'))
    handle_assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                             and isinstance(node.value, ast.Call)
                             and isinstance(node.value.func, ast.Attribute)
                             and node.value.func.attr == 'add_dll_directory')
    assert isinstance(handle_assignment.targets[0], ast.Name)
    assert handle_assignment.targets[0].id == 'dll_directory_handle'
    alive = []

    class Handle:
        def __init__(self) -> None:
            alive.append(True)

        def __del__(self) -> None:
            alive.pop()

    import os
    monkeypatch.setattr(os, 'add_dll_directory', lambda path: Handle(), raising=False)
    namespace = {'os': os, 'RUNTIME_DIR': tmp_path}
    exec(compile(ast.Module(body=[handle_assignment], type_ignores=[]), '<bootstrap>', 'exec'), namespace)
    assert alive == [True]
    assert isinstance(namespace['dll_directory_handle'], Handle)


def test_runtime_environment_enables_utf8(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = tmp_path / 'runtime'
    runtime_dir = runtime / '.runtime'
    runtime_dir.mkdir(parents=True)
    for name in ['python311.dll', 'base_library.zip']:
        (runtime_dir / name).touch()
    (runtime / 'OneDragon-RuntimeLauncher.exe').touch()
    monkeypatch.setattr(CHECKER, '_extract_pyz', lambda *args: 1)
    monkeypatch.setattr(CHECKER, '_extract_bootstrap_modules', lambda *args: None)
    captured = {}

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(CHECKER.subprocess, 'run', run)
    CHECKER._check_with_runtime(runtime, tmp_path, tmp_path / 'target.py', tmp_path)
    environment = captured['env']
    assert environment['PYTHONUTF8'] == '1'
    assert environment['PATH'] == str(runtime_dir)
    assert environment['PYTHONPATH'] == environment['PYTHONHOME'] == ''
    assert environment['PYTHONDONTWRITEBYTECODE'] == '1'
    assert 'SYSTEMROOT' in environment


def test_utf8_stderr_contains_chinese() -> None:
    import os
    process = subprocess.run(
        [sys.executable, '-c', "import sys; sys.stderr.write('中文警告')"],
        env={**os.environ, 'PYTHONUTF8': '1'}, capture_output=True, check=True,
    )
    assert process.stderr.decode('utf-8') == '中文警告'
