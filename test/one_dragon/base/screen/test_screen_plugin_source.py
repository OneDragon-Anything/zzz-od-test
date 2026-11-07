"""ScreenContext 插件画面来源、from_memory 语义与 SCREEN_INFO_DIR 的回归测试。

不依赖 TestContext/镜像资源：直接构造 ScreenContext + tmp_path 假 yml + 假来源回调。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml

from one_dragon.base.operation.application.application_factory_manager import (
    SCREEN_INFO_DIR,
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.plugin_info import PluginInfo, PluginSource
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.base.screen.screen_loader import ScreenContext
from one_dragon.utils import os_utils


@pytest.fixture()
def work_dir(tmp_path: Path):
    original = os_utils.get_work_dir()
    os_utils.set_work_dir(tmp_path)
    screen_dir = tmp_path / 'assets' / 'game_data' / 'screen_info'
    screen_dir.mkdir(parents=True)
    try:
        yield tmp_path, screen_dir
    finally:
        os_utils.set_work_dir(original)


def _screen(screen_id: str, screen_name: str, app_id: str | None = None,
            area_list: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        'screen_id': screen_id,
        'screen_name': screen_name,
        'area_list': area_list if area_list is not None else [],
    }
    if app_id is not None:
        data['app_id'] = app_id
    return data


def _dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')


def _make_ctx(screen_dir: Path, plugin_dirs: list[tuple[Path, str]]) -> ScreenContext:
    _dump(screen_dir / 'global.yml', _screen('id_global', 'global_screen'))
    ctx = ScreenContext()
    sources = list(plugin_dirs)
    ctx.set_extra_screen_source(lambda: list(sources))
    return ctx


def test_plugin_screens_survive_all_reload_modes(work_dir) -> None:
    """① 四种 reload（init/from_memory/from_separated_files/refresh）后插件画面保留、app_id 正确。"""
    tmp, screen_dir = work_dir
    plugin_dir = tmp / 'plugin_screens'
    _dump(plugin_dir / 'plugin.yml', _screen('id_plugin', 'plugin_screen'))
    ctx = _make_ctx(screen_dir, [(plugin_dir, 'bagel')])

    assert ctx.reload(from_separated_files=True) is True
    assert ctx.screen_info_map['plugin_screen'].app_id == 'bagel'

    ctx.save(reload_after_save=False)  # 生成 _od_merged.yml
    # init 默认走合并文件 reload，必须真正执行并成功
    assert ctx.reload() is True
    assert ctx.screen_info_map['plugin_screen'].app_id == 'bagel'
    assert 'global_screen' in ctx.screen_info_map

    assert ctx.reload(from_memory=True) is True
    assert ctx.screen_info_map['plugin_screen'].app_id == 'bagel'
    assert ctx._extra_screen_ids == {'id_plugin'}

    assert ctx.reload_extra_screens() is True  # refresh
    assert ctx.screen_info_map['plugin_screen'].app_id == 'bagel'


def test_plugin_uninstall_disappears_after_non_memory_reload(work_dir) -> None:
    """② 回调不再返回插件目录 → 非内存重建后插件画面消失，base 保留。"""
    tmp, screen_dir = work_dir
    plugin_dir = tmp / 'plugin_screens'
    _dump(plugin_dir / 'plugin.yml', _screen('id_plugin', 'plugin_screen'))
    sources: list[tuple[Path, str]] = [(plugin_dir, 'bagel')]
    ctx = ScreenContext()
    ctx.set_extra_screen_source(lambda: list(sources))
    _dump(screen_dir / 'global.yml', _screen('id_global', 'global_screen'))
    assert ctx.reload(from_separated_files=True) is True
    assert 'plugin_screen' in ctx.screen_info_map

    sources.clear()
    assert ctx.reload_extra_screens() is True
    assert 'plugin_screen' not in ctx.screen_info_map
    assert 'global_screen' in ctx.screen_info_map
    assert ctx._extra_screen_ids == set()

    assert ctx.reload(from_separated_files=True) is True
    assert 'plugin_screen' not in ctx.screen_info_map


def test_conflicts_and_bad_plugin_yaml_are_skipped(work_dir) -> None:
    """③ base 同名/同 id 跳过，坏 YAML / 缺 pc_rect 跳过，其它画面正常。"""
    tmp, screen_dir = work_dir
    plugin_dir = tmp / 'plugin_screens'
    _dump(screen_dir / 'base_name.yml', _screen('base_1', 'base_screen'))
    _dump(screen_dir / 'base_id.yml', _screen('dup_id', 'base_screen_2'))
    _dump(plugin_dir / 'name_conflict.yml', _screen('plugin_1', 'base_screen'))
    _dump(plugin_dir / 'id_conflict.yml', _screen('dup_id', 'plugin_screen_2'))
    (plugin_dir / 'bad_syntax.yml').write_text('screen_id: [unclosed\n', encoding='utf-8')
    _dump(plugin_dir / 'bad_area.yml', _screen(
        'bad_area', 'bad_area_screen',
        area_list=[{'area_name': 'broken'}],
    ))
    _dump(plugin_dir / 'good.yml', _screen('good_id', 'good_screen'))
    ctx = _make_ctx(screen_dir, [(plugin_dir, 'bagel')])

    assert ctx.reload(from_separated_files=True) is True
    assert 'base_screen' in ctx.screen_info_map
    assert 'base_screen_2' in ctx.screen_info_map
    assert 'good_screen' in ctx.screen_info_map
    assert ctx.screen_info_map['good_screen'].app_id == 'bagel'
    assert 'plugin_screen_2' not in ctx.screen_info_map
    assert 'bad_area_screen' not in ctx.screen_info_map
    assert 'base_screen' in ctx.screen_info_map  # base 未被插件覆盖


def test_from_memory_keeps_save_edit_without_reading_disk(work_dir, monkeypatch) -> None:
    """④ 改插件画面名后 save_screen → from_memory 不重读磁盘也生效。"""
    tmp, screen_dir = work_dir
    plugin_dir = tmp / 'plugin_screens'
    plugin_file = plugin_dir / 'plugin.yml'
    _dump(plugin_file, _screen('id_plugin', 'plugin_screen'))
    ctx = _make_ctx(screen_dir, [(plugin_dir, 'bagel')])
    assert ctx.reload(from_separated_files=True) is True

    edited = ctx.get_screen('plugin_screen', copy=True)
    edited.screen_name = 'plugin_screen_renamed'
    ctx.save_screen(edited)

    def _must_not_call(*args, **kwargs):
        raise AssertionError('from_memory 不应重读插件目录')

    monkeypatch.setattr(ctx, '_build_extras', _must_not_call)
    assert ctx.reload(from_memory=True) is True
    assert 'plugin_screen_renamed' in ctx.screen_info_map
    assert 'plugin_screen' not in ctx.screen_info_map
    assert ctx._extra_screen_ids == {'id_plugin'}


def test_from_memory_never_reads_plugin_dirs(work_dir, monkeypatch) -> None:
    """⑤ from_memory 全程不读插件目录（_build_extras 计数为 0）。"""
    tmp, screen_dir = work_dir
    plugin_dir = tmp / 'plugin_screens'
    _dump(plugin_dir / 'plugin.yml', _screen('id_plugin', 'plugin_screen'))
    ctx = _make_ctx(screen_dir, [(plugin_dir, 'bagel')])
    assert ctx.reload(from_separated_files=True) is True

    calls: list[int] = []
    original = ctx._build_extras

    def _counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(ctx, '_build_extras', _counting)
    assert ctx.reload(from_memory=True) is True
    assert calls == []


def _make_plugin_ctx(work_dir) -> tuple[ScreenContext, Path, Path, Path]:
    tmp, screen_dir = work_dir
    _dump(screen_dir / 'base.yml', _screen('id_base', 'base_screen'))
    dir_a = tmp / 'plugin_a'
    dir_b = tmp / 'plugin_b'
    _dump(dir_a / 'plugin_a.yml', _screen('id_plugin_a', 'plugin_a'))
    _dump(dir_b / 'plugin_b.yml', _screen('id_plugin_b', 'plugin_b'))
    ctx = ScreenContext()
    ctx.set_extra_screen_source(lambda: [(dir_a, 'app_a'), (dir_b, 'app_b')])
    assert ctx.reload(from_separated_files=True) is True
    return ctx, dir_a, dir_b, screen_dir


@pytest.mark.parametrize(('new_id', 'new_name'), [
    ('id_base', 'plugin_a'),        # F1: 插件 id 改成 base 的 id
    ('id_plugin_a', 'base_screen'),  # F2: 插件 name 改成 base 的 name
    ('id_plugin_b', 'plugin_a'),     # F3: 改成另一个插件的 id
])
def test_plugin_screen_edit_cannot_steal_other_screen(work_dir, monkeypatch, new_id, new_name) -> None:
    """P1 F1/F2/F3：插件画面改成 base/其它插件的 id 或 name → warning + 拒绝保存。"""
    from one_dragon.base.screen import screen_loader as loader_module

    ctx, dir_a, _dir_b, _screen_dir = _make_plugin_ctx(work_dir)
    warnings: list[str] = []
    monkeypatch.setattr(
        loader_module.log, 'warning',
        lambda message, *args, **kwargs: warnings.append(message % args),
    )

    edited = ctx.get_screen('plugin_a', copy=True)
    edited.screen_id = new_id
    edited.screen_name = new_name
    ctx.save_screen(edited)

    assert any('不能改成其它画面' in message for message in warnings), warnings
    assert ctx.screen_info_map['base_screen'].screen_id == 'id_base'
    assert ctx.screen_info_map['plugin_a'].screen_id == 'id_plugin_a'
    assert ctx.screen_info_map['plugin_b'].screen_id == 'id_plugin_b'
    assert any(path.suffix == '.yml' for path in dir_a.iterdir())
    saved = yaml.safe_load((dir_a / 'plugin_a.yml').read_text(encoding='utf-8'))
    assert saved['screen_id'] == 'id_plugin_a'
    assert saved['screen_name'] == 'plugin_a'


def test_reload_logs_external_caller_and_internal_debug(work_dir) -> None:
    """维护者第 5 点：外部调用 info 带模块名，save 内部 from_memory 重载走 debug。"""
    import logging

    from one_dragon.base.screen import screen_loader as loader_module

    _tmp, screen_dir = work_dir
    _dump(screen_dir / 'global.yml', _screen('id_global', 'global_screen'))
    ctx = ScreenContext()
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = CaptureHandler()
    logger = loader_module.log
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        assert ctx.reload(from_separated_files=True) is True
        reload_records = [r for r in records if '画面重载 caller=' in r.getMessage()]
        assert any(
            r.levelno == logging.INFO and __name__ in r.getMessage()
            for r in reload_records
        ), [r.getMessage() for r in reload_records]

        records.clear()
        ctx.save(reload_after_save=True)  # save 内部触发 from_memory 重载
        reload_records = [r for r in records if '画面重载 caller=' in r.getMessage()]
        assert any(
            r.levelno == logging.DEBUG and 'caller=screen_loader.save' in r.getMessage()
            for r in reload_records
        ), [r.getMessage() for r in reload_records]
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


def _read_dir(const: Any, attr: str, default: str = 'screen_info') -> str:
    return ApplicationFactoryManager._read_relative_dir(const, 'app', attr, default)


def test_screen_info_dir_const_validation(tmp_path: Path) -> None:
    """⑥ SCREEN_INFO_DIR：默认/自定义/空串/.. /绝对路径/C:foo/非 str/'.' 校验。"""
    assert _read_dir(SimpleNamespace(), 'SCREEN_INFO_DIR', SCREEN_INFO_DIR) == 'screen_info'
    assert _read_dir(SimpleNamespace(SCREEN_INFO_DIR='custom_screens'), 'SCREEN_INFO_DIR') == 'custom_screens'
    assert _read_dir(SimpleNamespace(SCREEN_INFO_DIR=''), 'SCREEN_INFO_DIR') == ''
    assert _read_dir(SimpleNamespace(SCREEN_INFO_DIR='  screens  '), 'SCREEN_INFO_DIR') == 'screens'

    bad_values = ['..', '../outside', '.', './', str(tmp_path / 'absolute')]
    if os.name == 'nt':
        bad_values.extend(['C:foo', '\\outside'])
    for bad in bad_values:
        with pytest.raises(ImportError):
            _read_dir(SimpleNamespace(SCREEN_INFO_DIR=bad), 'SCREEN_INFO_DIR')

    with pytest.raises(ImportError):
        _read_dir(SimpleNamespace(SCREEN_INFO_DIR=123), 'SCREEN_INFO_DIR')

    # KEY_SIM_DIR 共用同一套校验
    assert _read_dir(SimpleNamespace(KEY_SIM_DIR='key_sim'), 'KEY_SIM_DIR', '') == 'key_sim'
    with pytest.raises(ImportError):
        _read_dir(SimpleNamespace(KEY_SIM_DIR='..'), 'KEY_SIM_DIR', '')


_FACTORY_SOURCE = '''
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from . import const


class PluginFactory(ApplicationFactory):
    def __init__(self, ctx):
        ApplicationFactory.__init__(self, const)

    def create_application(self, instance_idx, group_id):
        return None

    def create_config(self, instance_idx, group_id):
        return None
'''


def _write_plugin(plugins_dir: Path, app_id: str, extra_const: str = '') -> Path:
    plugin_dir = plugins_dir / app_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / '__init__.py').write_text('', encoding='utf-8')
    (plugin_dir / 'const.py').write_text(
        f'APP_ID = "{app_id}"\nAPP_NAME = "{app_id}"\n'
        f'DEFAULT_GROUP = False\nNEED_NOTIFY = False\n{extra_const}',
        encoding='utf-8',
    )
    (plugin_dir / 'factory.py').write_text(_FACTORY_SOURCE, encoding='utf-8')
    return plugin_dir


def _discover(plugins_dir: Path) -> ApplicationFactoryManager:
    manager = ApplicationFactoryManager(
        cast(Any, object()), [(plugins_dir, PluginSource.THIRD_PARTY)],
    )
    manager.discover_factories()
    return manager


def test_bad_screen_info_dir_marks_scan_failure_but_others_load(tmp_path: Path) -> None:
    """⑥续 非法 SCREEN_INFO_DIR 只记 scan_failures，不中断其它插件扫描。"""
    plugins_dir = tmp_path / 'plugins'
    _write_plugin(plugins_dir, 'bad_screen_dir', extra_const='SCREEN_INFO_DIR = ".."\n')
    _write_plugin(plugins_dir, 'good_plugin')

    manager = _discover(plugins_dir)
    assert manager.get_plugin_info('bad_screen_dir') is None
    assert manager.get_plugin_info('good_plugin') is not None
    good_info = manager.get_plugin_info('good_plugin')
    assert good_info is not None and good_info.screen_info_dir == 'screen_info'
    assert len(manager.scan_failures) == 1
    assert 'SCREEN_INFO_DIR' in manager.scan_failures[0][1]


def test_manual_and_callback_same_dir_loads_once(work_dir) -> None:
    """⑦ 手工注入与回调同目录 → 只加载一份，app_id 以回调为准。"""
    tmp, screen_dir = work_dir
    plugin_dir = tmp / 'plugin_screens'
    _dump(plugin_dir / 'plugin.yml', _screen('id_plugin', 'plugin_screen'))
    ctx = _make_ctx(screen_dir, [(plugin_dir, 'callback_app')])

    assert ctx.load_extra_screen_dir(str(plugin_dir), 'manual_app') is True
    assert ctx.reload(from_separated_files=True) is True

    screens = [s for s in ctx.screen_info_list if s.screen_id == 'id_plugin']
    assert len(screens) == 1
    assert screens[0].app_id == 'callback_app'
    assert ctx._extra_screen_ids == {'id_plugin'}


@pytest.mark.parametrize('bad_value', ['..', '.', './', 'C:outside'])
def test_bad_relative_dir_values_raise(bad_value: str) -> None:
    """⑥续2 参数化覆盖几类越界目录名。"""
    if os.name != 'nt' and bad_value.startswith('C:'):
        pytest.skip('盘符形态仅 Windows 可构造')
    with pytest.raises(ImportError):
        _read_dir(SimpleNamespace(SCREEN_INFO_DIR=bad_value), 'SCREEN_INFO_DIR')


def test_plugin_info_default_screen_info_dir(tmp_path: Path) -> None:
    """PluginInfo 默认 screen_info_dir 为 'screen_info'。"""
    info = PluginInfo(app_id='a', app_name='a', default_group=False)
    assert info.screen_info_dir == 'screen_info'
    assert info.plugin_dir is None or isinstance(info.plugin_dir, Path)


# ---------- commit 1: goto_list 过滤 ----------


def test_goto_list_filters_invalid_elements() -> None:
    """goto_list 非 str / 空串元素被过滤，正常元素保留且 to_dict 不变。"""
    area = ScreenArea(
        area_name='a', screen_name='s',
        goto_list=['ok', 1, '', None],  # type: ignore[list-item]
    )
    assert area.goto_list == ['ok']
    assert area.to_dict()['goto_list'] == ['ok']


@pytest.mark.parametrize('bad_value', ['not-a-list', 1, {'a': 1}, None])
def test_goto_list_invalid_container_becomes_empty(bad_value) -> None:
    area = ScreenArea(area_name='a', screen_name='s', goto_list=bad_value)
    assert area.goto_list == []


def test_init_screen_route_skips_bad_goto_elements(work_dir) -> None:
    """init_screen_route 对运行时塞入的坏 goto 元素不抛错。"""
    _tmp, screen_dir = work_dir
    _dump(screen_dir / 'global.yml', _screen(
        'id_global', 'global_screen',
        area_list=[{
            'area_name': 'a', 'pc_rect': [1, 2, 3, 4], 'text': 'x',
            'goto_list': ['global_screen'],
        }],
    ))
    ctx = ScreenContext()
    assert ctx.reload(from_separated_files=True) is True
    area = ctx.get_screen('global_screen').area_list[0]
    area.goto_list = [123, 'global_screen']  # type: ignore[list-item]
    ctx.init_screen_route()  # 不应抛错
    assert ctx.screen_route_map['global_screen']['global_screen'].can_go


# ---------- commit 2: save/delete 返回 bool、写盘顺序 ----------


def test_plugin_screen_rename_success(work_dir) -> None:
    """正常唯一改名：新文件写成功、旧文件删除、内存更新。"""
    ctx, dir_a, _dir_b, _tmp = _make_plugin_ctx(work_dir)
    edited = ctx.get_screen('plugin_a', copy=True)
    edited.screen_id = 'id_plugin_a2'
    edited.screen_name = 'plugin_a2'

    assert ctx.save_screen(edited) is True
    assert (dir_a / 'id_plugin_a2.yml').exists()
    assert not (dir_a / 'plugin_a.yml').exists()
    assert ctx.screen_info_map['plugin_a2'].screen_id == 'id_plugin_a2'
    assert ctx._extra_screen_paths['id_plugin_a2'] == dir_a / 'id_plugin_a2.yml'


def test_plugin_screen_rename_invalid_id_keeps_old_file(work_dir) -> None:
    """非法 id（含路径分隔符）→ False，旧 yml 与内存都保留。"""
    ctx, dir_a, _dir_b, _tmp = _make_plugin_ctx(work_dir)
    edited = ctx.get_screen('plugin_a', copy=True)
    edited.screen_id = 'bad/id'

    assert ctx.save_screen(edited) is False
    assert (dir_a / 'plugin_a.yml').exists()
    assert ctx.screen_info_map['plugin_a'].screen_id == 'id_plugin_a'
    saved = yaml.safe_load((dir_a / 'plugin_a.yml').read_text(encoding='utf-8'))
    assert saved['screen_id'] == 'id_plugin_a'


def test_plugin_screen_write_oserror_keeps_old_state(work_dir, monkeypatch) -> None:
    """写盘 OSError → False，旧文件与内存保持原样，临时文件清理。"""
    from one_dragon.base.screen import screen_loader as loader_module

    ctx, dir_a, _dir_b, _tmp = _make_plugin_ctx(work_dir)
    before = (dir_a / 'plugin_a.yml').read_text(encoding='utf-8')
    edited = ctx.get_screen('plugin_a', copy=True)
    edited.screen_name = 'plugin_a_renamed'

    def _boom(*args, **kwargs):
        raise OSError('disk full')

    monkeypatch.setattr(loader_module.os, 'replace', _boom)
    assert ctx.save_screen(edited) is False
    assert (dir_a / 'plugin_a.yml').read_text(encoding='utf-8') == before
    assert ctx.screen_info_map['plugin_a'].screen_name == 'plugin_a'
    assert list(dir_a.glob('.*.tmp')) == []


def test_delete_screen_failure_keeps_memory(work_dir) -> None:
    """删除插件文件失败（只读）→ False，内存与路由不变。"""
    ctx, dir_a, _dir_b, _tmp = _make_plugin_ctx(work_dir)
    file_path = dir_a / 'plugin_a.yml'
    before_names = set(ctx.screen_info_map)
    file_path.chmod(stat.S_IREAD)
    try:
        assert ctx.delete_screen('id_plugin_a') is False
    finally:
        file_path.chmod(stat.S_IWRITE)
    assert file_path.exists()
    assert set(ctx.screen_info_map) == before_names
    assert 'id_plugin_a' in ctx._extra_screen_ids


# ---------- commit 3: backend 消费返回值 ----------


def test_backend_area_save_failure_returns_false(work_dir, monkeypatch) -> None:
    """backend 保存失败时返回 success=False，不再误报成功。"""
    from unittest.mock import MagicMock

    from zzz_od.backend.backend_context import ZzzBackendContext

    _tmp, screen_dir = work_dir
    _dump(screen_dir / 'global.yml', _screen('id_global', 'global_screen'))
    loader = ScreenContext()
    assert loader.reload(from_separated_files=True) is True

    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.screen_loader = loader
    ctx.template_loader = MagicMock()
    backend = ZzzBackendContext(ctx)

    monkeypatch.setattr(loader, 'save_screen', lambda screen_info: False)
    result = backend.upsert_screen_area('global_screen', 'area_a', [1, 2, 3, 4], text='x')
    assert result['success'] is False
    assert '保存失败' in result['error']
    result = backend.delete_screen_area('global_screen', 'area_a')
    assert result['success'] is False
    assert '保存失败' in result['error']


# ---------- commit 4: init 失败通知 ----------


def test_init_reload_failure_dispatches_notify() -> None:
    """init 的 reload 失败分支复用 ContextNotifyEvent 链路。"""
    from one_dragon.base.operation import one_dragon_context as context_module

    source = Path(context_module.__file__).read_text(encoding='utf-8')
    assert 'if not self.screen_loader.reload():' in source
    assert "ContextNotifyEvent.error('画面配置'" in source
    assert 'ready_for_application = True' in source


# ---------- 终审 P1：base 之间冲突 / 目标文件占用 ----------


def _make_base_pair_ctx(work_dir) -> tuple[ScreenContext, Path]:
    _tmp, screen_dir = work_dir
    _dump(screen_dir / 'id_a.yml', _screen('id_a', 'base_a'))
    _dump(screen_dir / 'id_b.yml', _screen('id_b', 'base_b'))
    ctx = ScreenContext()
    assert ctx.reload(from_separated_files=True) is True
    return ctx, screen_dir


@pytest.mark.parametrize(('new_id', 'new_name'), [
    ('id_b', 'base_a'),  # 改 id 撞 B
    ('id_a', 'base_b'),  # 改 name 撞 B
])
def test_base_rename_conflicts_with_other_base(work_dir, monkeypatch, new_id, new_name) -> None:
    """base 画面改名撞另一 base 的 id/name → False，A/B 与文件都保持原样。"""
    from one_dragon.base.screen import screen_loader as loader_module

    ctx, screen_dir = _make_base_pair_ctx(work_dir)
    file_a_before = (screen_dir / 'id_a.yml').read_bytes()
    file_b_before = (screen_dir / 'id_b.yml').read_bytes()
    warnings: list[str] = []
    monkeypatch.setattr(
        loader_module.log, 'warning',
        lambda message, *args, **kwargs: warnings.append(message % args),
    )

    edited = ctx.get_screen('base_a', copy=True)
    edited.screen_id = new_id
    edited.screen_name = new_name
    assert ctx.save_screen(edited) is False

    assert any('不能改成其它基础画面' in message for message in warnings), warnings
    assert ctx.screen_info_map['base_a'].screen_id == 'id_a'
    assert ctx.screen_info_map['base_b'].screen_id == 'id_b'
    assert (screen_dir / 'id_a.yml').read_bytes() == file_a_before
    assert (screen_dir / 'id_b.yml').read_bytes() == file_b_before


def test_new_base_screen_conflicts_with_other_base(work_dir) -> None:
    """新建 base 撞已有 base 的 id/name → False，已有画面不受影响。"""
    ctx, _screen_dir = _make_base_pair_ctx(work_dir)

    for new_id, new_name in (('id_b', 'new_screen'), ('id_new', 'base_b')):
        new_info = ScreenInfo({})  # 与 devtools 新建一致：old_screen_id 为空
        new_info.screen_id = new_id
        new_info.screen_name = new_name
        assert ctx.save_screen(new_info) is False

    assert ctx.screen_info_map['base_a'].screen_id == 'id_a'
    assert ctx.screen_info_map['base_b'].screen_id == 'id_b'
    assert 'new_screen' not in ctx.screen_info_map


def test_base_rename_success_regression(work_dir) -> None:
    """base 正常唯一改名仍成功：新文件写入、旧文件删除、内存更新。"""
    ctx, screen_dir = _make_base_pair_ctx(work_dir)
    edited = ctx.get_screen('base_a', copy=True)
    edited.screen_id = 'id_a2'
    edited.screen_name = 'base_a2'

    assert ctx.save_screen(edited) is True
    assert (screen_dir / 'id_a2.yml').exists()
    assert not (screen_dir / 'id_a.yml').exists()
    assert ctx.screen_info_map['base_a2'].screen_id == 'id_a2'
    assert ctx.screen_info_map['base_b'].screen_id == 'id_b'


def test_plugin_rename_target_file_occupied(work_dir) -> None:
    """插件画面改成 other（other.yml 已存在）→ False，两个 yml 内容都不变。"""
    tmp, screen_dir = work_dir
    _dump(screen_dir / 'global.yml', _screen('id_global', 'global_screen'))
    plugin_dir = tmp / 'plugin_screens'
    p_file = plugin_dir / 'p.yml'
    other_file = plugin_dir / 'other.yml'
    _dump(p_file, _screen('id_plugin', 'plugin_screen'))
    _dump(other_file, _screen('id_other', 'other_screen'))
    ctx = ScreenContext()
    ctx.set_extra_screen_source(lambda: [(plugin_dir, 'app')])
    assert ctx.reload(from_separated_files=True) is True

    p_before = p_file.read_bytes()
    other_before = other_file.read_bytes()
    edited = ctx.get_screen('plugin_screen', copy=True)
    edited.screen_id = 'other'  # 目标 other.yml 已被 id_other 使用
    assert ctx.save_screen(edited) is False

    assert p_file.read_bytes() == p_before
    assert other_file.read_bytes() == other_before
    assert ctx.screen_info_map['plugin_screen'].screen_id == 'id_plugin'
    assert ctx.screen_info_map['other_screen'].screen_id == 'id_other'
    assert ctx._extra_screen_ids == {'id_plugin', 'id_other'}


def test_base_new_screen_target_file_occupied(work_dir) -> None:
    """新建 base 时目标 yml 已存在（未被加载的孤儿文件）→ False，孤儿文件不变。"""
    ctx, screen_dir = _make_base_pair_ctx(work_dir)
    orphan = screen_dir / 'id_new.yml'
    _dump(orphan, _screen('id_other', 'orphan_screen'))
    orphan_before = orphan.read_bytes()

    new_info = ScreenInfo({'screen_id': 'id_new', 'screen_name': 'new_screen'})
    assert ctx.save_screen(new_info) is False

    assert orphan.read_bytes() == orphan_before
    assert 'new_screen' not in ctx.screen_info_map
    assert ctx.screen_info_map['base_a'].screen_id == 'id_a'

