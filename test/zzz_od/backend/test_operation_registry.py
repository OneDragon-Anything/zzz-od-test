"""operation 扫描 / op_id 解析 / args 校验的单元测试。

测试使用 MagicMock 伪造 ZContext(扫描纯反射,不依赖真实游戏/模型)。
扫描会真实 import 主仓 operation/hollow_zero 承载包下的模块,以验证三重过滤与容错。
"""

import importlib
from unittest.mock import MagicMock

import pytest

from zzz_od.backend.operation_registry import (
    coerce_dataclass_params,
    describe_operation,
    resolve_op_class,
    scan_operations,
    validate_args,
)


@pytest.fixture
def mock_ctx() -> MagicMock:
    """mock ZContext:扫描纯反射,ctx 仅作 API 占位。"""
    return MagicMock(name='ZContext')


# ---------- scan_operations ----------

def test_scan_includes_known_ops(mock_ctx: MagicMock) -> None:
    """扫描应包含 OpenAndEnterGame(operation 包)与 HollowRunner(hollow_zero 承载包)。"""
    result = scan_operations(mock_ctx, refresh=True)
    op_ids = [o.op_id for o in result.operations]
    # operation 承载包下的裸 Operation 子类
    assert 'zzz_od.operation.enter_game.open_and_enter_game.OpenAndEnterGame' in op_ids
    # hollow_zero 承载包下的 ZOperation 子类(跨承载包)
    assert any(i.endswith('.HollowRunner') for i in op_ids)


def test_scan_includes_concrete_hollow_event_ops(mock_ctx: MagicMock) -> None:
    """DropResonium/DropResonium2 是具体可运行 op(继承 DropResoniumBase 但非 Application),应出现。"""
    result = scan_operations(mock_ctx, refresh=True)
    class_names = {o.class_name for o in result.operations}
    assert 'DropResonium' in class_names
    assert 'DropResonium2' in class_names


def test_scan_excludes_application_subclasses_and_bases(mock_ctx: MagicMock) -> None:
    """排除:Application 子类(RedemptionCodeApp 等)+ 显式抽象基类 + *Base 后缀。"""
    result = scan_operations(mock_ctx, refresh=True)
    class_names = {o.class_name for o in result.operations}

    # 显式抽象/中间基类不出现
    for base in ('Operation', 'Application', 'ZOperation', 'ZApplication',
                 'OneDragonApp', 'GroupApplication'):
        assert base not in class_names, f'基类 {base} 不应出现'
    # *Base 后缀启发式兜底(DropResoniumBase 在 hollow_zero/event/drop_resonium.py)
    assert 'DropResoniumBase' not in class_names
    # Application 子类不出现(RedemptionCodeApp 在 application/,本就不扫;再断言一次)
    assert 'RedemptionCodeApp' not in class_names


def test_scan_import_failure_tolerant(mock_ctx: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """单模块 import 失败不中断扫描,记入 failures,已知 op 仍出现。"""
    real_import = importlib.import_module

    def flaky_import(name: str):  # noqa: ANN202
        if name == 'zzz_od.operation.map_transport':
            raise RuntimeError('模拟 import 失败')
        return real_import(name)

    monkeypatch.setattr(
        'zzz_od.backend.operation_registry.importlib.import_module', flaky_import
    )
    result = scan_operations(mock_ctx, refresh=True)
    # 失败被记录
    assert any('map_transport' in f for f in result.failures)
    # 扫描未中断,其它 op 仍出现
    op_ids = [o.op_id for o in result.operations]
    assert 'zzz_od.operation.enter_game.open_and_enter_game.OpenAndEnterGame' in op_ids


def test_scan_caches_and_refresh(mock_ctx: MagicMock) -> None:
    """无 refresh 时复用缓存(同一对象);refresh=True 重扫。"""
    r1 = scan_operations(mock_ctx, refresh=True)
    r2 = scan_operations(mock_ctx)  # 命中缓存
    assert r1 is r2
    r3 = scan_operations(mock_ctx, refresh=True)  # 强制重扫
    # 内容一致(op_id 集合相同),对象可不同
    assert {o.op_id for o in r1.operations} == {o.op_id for o in r3.operations}


def test_scan_op_info_fields(mock_ctx: MagicMock) -> None:
    """OperationInfo 含 op_id/class_name/module/params 字段。"""
    result = scan_operations(mock_ctx, refresh=True)
    transport = next(
        (o for o in result.operations
         if o.class_name == 'MapTransport'), None,
    )
    assert transport is not None
    assert transport.op_id == 'zzz_od.operation.map_transport.MapTransport'
    assert transport.module == 'zzz_od.operation.map_transport'
    # 参数反射(self/ctx 剔除):area_name / tp_name
    param_names = [p.name for p in transport.params]
    assert param_names == ['area_name', 'tp_name']
    assert all(p.required for p in transport.params)
    assert all(p.json_serializable for p in transport.params)


# ---------- resolve_op_class ----------

def test_resolve_known_op() -> None:
    """解析已知 operation 类。"""
    cls = resolve_op_class('zzz_od.operation.enter_game.open_and_enter_game.OpenAndEnterGame')
    assert cls.__name__ == 'OpenAndEnterGame'


def test_resolve_rejects_non_operation() -> None:
    """解析非 Operation 类(如 dataclass ChargePlanItem)应 raise。"""
    with pytest.raises(ValueError):
        resolve_op_class('zzz_od.application.charge_plan.charge_plan_config.ChargePlanItem')


def test_resolve_rejects_rexport() -> None:
    """__module__ 守卫:re-export 进来的类(op_id 不指向定义模块)应 raise。"""
    # OpenGame 被 open_and_enter_game 模块 import 进来,但定义在 open_game 模块
    with pytest.raises(ValueError):
        resolve_op_class('zzz_od.operation.enter_game.open_and_enter_game.OpenGame')


def test_resolve_rejects_bad_format() -> None:
    """op_id 不含 . 时 raise。"""
    with pytest.raises(ValueError):
        resolve_op_class('NotAClass')


# ---------- validate_args ----------

def test_validate_args_accepts_simple(mock_ctx: MagicMock) -> None:
    """MapTransport 提齐全的标量参数 → None(通过)。"""
    from zzz_od.operation.map_transport import MapTransport
    assert validate_args(MapTransport, {'area_name': '六分街', 'tp_name': '黑糖工作室'}) is None


def test_validate_args_rejects_missing_required(mock_ctx: MagicMock) -> None:
    """必填参数缺失 → 返错误描述。"""
    from zzz_od.operation.map_transport import MapTransport
    err = validate_args(MapTransport, {'area_name': '六分街'})
    assert err is not None
    assert 'tp_name' in err


def test_validate_args_coercible_dataclass(mock_ctx: MagicMock) -> None:
    """NotoriousHunt 必填 plan: ChargePlanItem(@dataclass+from_dict)→ 缺参拒;传 dict 接受(可反序列化)。"""
    from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
    # 缺必填 → 拒
    err_missing = validate_args(NotoriousHunt, {})
    assert err_missing is not None
    assert 'plan' in err_missing
    # 传 dict → 接受(coercible:实例化前用 from_dict 反序列化)
    assert validate_args(NotoriousHunt, {'plan': {'mission_type_name': 'x'}}) is None


def test_validate_args_coercible_requires_dict(mock_ctx: MagicMock) -> None:
    """coercible 参数(ChargePlanItem)值必须是 dict;标量/列表/None 拒绝(否则绕过 coerce,错误类型进 op 构造)。"""
    from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
    for bad in ([], '字符串', None, 42):
        err = validate_args(NotoriousHunt, {'plan': bad})
        assert err is not None, f'{bad!r} 应被拒'
        assert 'plan' in err
        assert 'dict' in err


def test_validate_args_accepts_no_extra_params(mock_ctx: MagicMock) -> None:
    """只有 ctx 参数的 op(如 OpenAndEnterGame),空 args → None。"""
    from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
    assert validate_args(OpenAndEnterGame, {}) is None


# ---------- coerce_dataclass_params ----------

def test_coerce_dataclass_params_converts_dict() -> None:
    """@dataclass+from_dict 参数的 dict 值 → 反序列化为实例。"""
    from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
    from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
    coerced = coerce_dataclass_params(
        NotoriousHunt, {'plan': {'category_name': '恶名狩猎', 'plan_times': 2}},
    )
    assert isinstance(coerced['plan'], ChargePlanItem)
    assert coerced['plan'].category_name == '恶名狩猎'
    assert coerced['plan'].plan_times == 2


def test_coerce_dataclass_params_passthrough_non_dict() -> None:
    """非 coercible 参数原样保留;返回新 dict(不就地改入参)。"""
    from zzz_od.operation.map_transport import MapTransport
    args = {'area_name': '六分街', 'tp_name': '黑糖工作室'}
    coerced = coerce_dataclass_params(MapTransport, args)
    # 标量参数原样
    assert coerced == args
    # 不就地改入参(返回新 dict)
    assert coerced is not args


# ---------- describe_operation ----------

def test_describe_operation_reflects_params(mock_ctx: MagicMock) -> None:
    """describe_operation 纯反射参数 schema,标 json_serializable。"""
    info = describe_operation(mock_ctx, 'zzz_od.operation.map_transport.MapTransport')
    assert info['op_id'] == 'zzz_od.operation.map_transport.MapTransport'
    assert info['class_name'] == 'MapTransport'
    param_names = [p['name'] for p in info['params']]
    assert param_names == ['area_name', 'tp_name']
    # 标量参数 json_serializable=True
    assert all(p['json_serializable'] for p in info['params'])
    # 全必填且可序列化 → debuggable=True
    assert info['debuggable'] is True


def test_describe_operation_marks_coercible_param(mock_ctx: MagicMock) -> None:
    """@dataclass+from_dict 参数(ChargePlanItem)标 json_serializable=False、coercible=True、debuggable=True。"""
    info = describe_operation(
        mock_ctx, 'zzz_od.operation.compendium.notorious_hunt.NotoriousHunt',
    )
    plan = next(p for p in info['params'] if p['name'] == 'plan')
    assert plan['required'] is True
    assert plan['json_serializable'] is False
    assert plan['coercible'] is True
    # coercible 参数可从 dict 传 → debuggable=True
    assert info['debuggable'] is True
