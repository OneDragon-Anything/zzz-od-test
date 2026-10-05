"""正式应用接收真实容器恢复结果，并沿已有节点继续或失败结算。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from test.harness.bagel_container import phases, prepare
from test.harness.fixture_controller import enter_running_state, reset_running_state

if TYPE_CHECKING:
    from test.conftest import TestContext

    from zzz_od.application.bagel.bagel_config import BagelConfig
    from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

pytestmark = pytest.mark.usefixtures('no_round_wait')


@pytest.mark.parametrize('succeeds', [False, True])
def test_formal_app_routes_real_container_result(
    test_context: TestContext, monkeypatch: pytest.MonkeyPatch, succeeds: bool,
    config: BagelConfig, record: BagelRunRecord,
) -> None:
    """真实恢复结果可到达正式应用失败结算；局部成功不增加整体失败次数。"""
    from zzz_od.application.bagel.bagel_app import BagelApp

    prompt, _, panel = phases('box')
    controller, flow_op, _ = prepare(test_context, monkeypatch, 'box', [
        {**prompt, 'on': 'f'}, {**prompt, 'on': 'f'}, {**prompt, 'on': 'f'},
        panel if succeeds else prompt,
    ])
    factory = MagicMock(return_value=flow_op)
    monkeypatch.setattr('zzz_od.application.bagel.bagel_app.BagelRunFlow', factory)
    app = BagelApp(test_context, config, record)
    app.matched_map_id = 'janus_high_b'
    app.flow_snapshot = {'janus_high_b': flow_op.flow}
    app.defeat_rounds = 2
    app._init_network()
    app._current_node = app._node_map['执行局内流程']
    enter_running_state(test_context)
    try:
        result = app.run_flow()
        assert factory.call_args.kwargs['continuous_safe_unlock'] is True
        next_node = app._get_next_node(result)
        assert next_node.cn == ('结算仓库' if succeeds else '失败局退出')
        assert app.defeat_rounds == 2 and app.success_rounds == 0
        assert len([e for e in controller.trace if e[0] == 'f']) == 3
        if not succeeds:
            assert result.status == flow_op.STATUS_CONTAINER_FAILED
            assert result.data == '容器开箱交互已达3次上限'
    finally:
        reset_running_state(test_context, app)
