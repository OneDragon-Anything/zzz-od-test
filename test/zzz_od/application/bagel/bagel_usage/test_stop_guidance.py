"""不同停止原因不能相互冒充。"""
import pytest

from zzz_od.application.bagel.bagel_usage import stop_guidance


@pytest.mark.parametrize('status,include,exclude', [
    ('仓库已满且安全箱仍有物资，禁止批量出售', '安全箱仍有物品', '结算完成'),
    ('结算后仓库已满（280/280）', '安全箱已空', '安全箱仍有物品'),
    ('仅部分入仓，安全箱 2 -> 1 格', '停止重复点击', '已完成结算'),
    ('整体重试已用 0/0，已完成仓库结算，停止自动重开', '当前停在结算仓库', '正在重开'),
    ('本局失败：定位失败；入仓或清理失败：异常', '请先处理上述原因', '已完成结算'),
    ('未知入场确认', '请检查现场', '自动重试'),
    ('异常', '请检查现场', '已完成结算'),
    ('连续 3 局安全箱为空，未计成功，停止自动重开', '完成返回流程', '正在重开'),
])
def test_stop_guidance(status: str, include: str, exclude: str) -> None:
    """提示只解释已确定的结果。"""
    text = stop_guidance(status)
    assert include in text
    assert exclude not in text
