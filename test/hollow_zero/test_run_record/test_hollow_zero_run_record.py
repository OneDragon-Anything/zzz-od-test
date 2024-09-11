import test
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.utils import os_utils
from zzz_od.application.hollow_zero.hollow_zero_config import HollowZeroExtraTask
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.call_for_support import CallForSupport


class TestHollowZeroRunRecord(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_run_status_under_now(self):
        """
        测试当前显示状态的正确性
        """
        self.ctx.hollow_zero_config.weekly_plan_times = 2
        self.ctx.hollow_zero_config.daily_plan_times = 1

        # 先设置成功
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)

        # 上周运行的 已经完成
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -7)
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status_under_now)

        # 昨天运行的 每日次数已经完成
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -1)
        self.ctx.hollow_zero_record.weekly_run_times = 1
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 每日次数已经完成
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 1
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 但每天次数不满
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 1
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 但每周次数满了 但业绩没满
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 每周次数满了 每天次数满了 但业绩没满
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 每周次数满了 业绩也满了
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 每周次数满了 周期奖励未满
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 每周次数满了 每天次数满了 周期奖励未满
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status_under_now)

        # 今天运行的 每周次数满了 周期奖励已满
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = True
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status_under_now)

    def test_check_and_update_status(self):
        """
        测试更新状态的正确性
        """
        self.ctx.hollow_zero_config.weekly_plan_times = 2
        self.ctx.hollow_zero_config.daily_plan_times = 1

        # 上周运行的 已经完成
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -7)
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = True
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(0, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(False, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status)

        # 昨天运行的 每日次数已经完成
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -1)
        self.ctx.hollow_zero_record.weekly_run_times = 1
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(1, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(False, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每日次数已经完成
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 1
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(1, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(1, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(False, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 但每天次数不满
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 1
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(1, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(False, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每周次数满了 但业绩没满
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(2, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(False, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每周次数满了 每天次数满了 但业绩没满
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = False
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(2, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(1, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(False, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每周次数满了 业绩也满了
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(2, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(True, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每周次数满了 周期奖励未满
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(2, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(True, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_WAIT, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每周次数满了 每天次数满了 周期奖励未满
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 1
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = False
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(2, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(1, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(True, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(False, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status)

        # 今天运行的 每周次数满了 周期奖励已满
        self.ctx.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        self.ctx.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        self.ctx.hollow_zero_record.dt = os_utils.get_dt()
        self.ctx.hollow_zero_record.weekly_run_times = 2
        self.ctx.hollow_zero_record.daily_run_times = 0
        self.ctx.hollow_zero_record.no_eval_point = True
        self.ctx.hollow_zero_record.period_reward_complete = True
        self.ctx.hollow_zero_record.check_and_update_status()
        self.assertEqual(2, self.ctx.hollow_zero_record.weekly_run_times)
        self.assertEqual(0, self.ctx.hollow_zero_record.daily_run_times)
        self.assertEqual(True, self.ctx.hollow_zero_record.no_eval_point)
        self.assertEqual(True, self.ctx.hollow_zero_record.period_reward_complete)
        self.assertEqual(AppRunRecord.STATUS_SUCCESS, self.ctx.hollow_zero_record.run_status)
