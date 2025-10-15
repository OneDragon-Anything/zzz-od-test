from test.conftest import TestContext

from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.utils import os_utils
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import HollowZeroExtraTask


class TestWitheredDomainRunRecord:

    def test_run_status_under_now(self, test_context: TestContext):
        """
        测试当前显示状态的正确性
        """
        test_context.hollow_zero_config.weekly_plan_times = 2
        test_context.hollow_zero_config.daily_plan_times = 1

        # 先设置成功
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)

        # 上周运行的 已经完成
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -7)
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status_under_now

        # 昨天运行的 每日次数已经完成
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -1)
        test_context.hollow_zero_record.weekly_run_times = 1
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 每日次数已经完成
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 1
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 但每天次数不满
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 1
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 但每周次数满了 但业绩没满
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 每周次数满了 每天次数满了 但业绩没满
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 每周次数满了 业绩也满了
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 每周次数满了 周期奖励未满
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 每周次数满了 每天次数满了 周期奖励未满
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status_under_now

        # 今天运行的 每周次数满了 周期奖励已满
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = True
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status_under_now

    def test_check_and_update_status(self, test_context: TestContext):
        """
        测试更新状态的正确性
        """
        test_context.hollow_zero_config.weekly_plan_times = 2
        test_context.hollow_zero_config.daily_plan_times = 1

        # 上周运行的 已经完成
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -7)
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = True
        test_context.hollow_zero_record.check_and_update_status()
        assert 0 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert False == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status

        # 昨天运行的 每日次数已经完成
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -1)
        test_context.hollow_zero_record.weekly_run_times = 1
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 1 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert False == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status

        # 今天运行的 每日次数已经完成
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 1
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 1 == test_context.hollow_zero_record.weekly_run_times
        assert 1 == test_context.hollow_zero_record.daily_run_times
        assert False == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status

        # 今天运行的 但每天次数不满
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.NONE.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 1
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 1 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert False == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status

        # 今天运行的 每周次数满了 但业绩没满
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 2 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert False == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status

        # 今天运行的 每周次数满了 每天次数满了 但业绩没满
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = False
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 2 == test_context.hollow_zero_record.weekly_run_times
        assert 1 == test_context.hollow_zero_record.daily_run_times
        assert False == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status

        # 今天运行的 每周次数满了 业绩也满了
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 2 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert True == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status

        # 今天运行的 每周次数满了 周期奖励未满
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 2 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert True == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == test_context.hollow_zero_record.run_status

        # 今天运行的 每周次数满了 每天次数满了 周期奖励未满
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 1
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = False
        test_context.hollow_zero_record.check_and_update_status()
        assert 2 == test_context.hollow_zero_record.weekly_run_times
        assert 1 == test_context.hollow_zero_record.daily_run_times
        assert True == test_context.hollow_zero_record.no_eval_point
        assert False == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status

        # 今天运行的 每周次数满了 周期奖励已满
        test_context.hollow_zero_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        test_context.hollow_zero_config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        test_context.hollow_zero_record.dt = os_utils.get_dt()
        test_context.hollow_zero_record.weekly_run_times = 2
        test_context.hollow_zero_record.daily_run_times = 0
        test_context.hollow_zero_record.no_eval_point = True
        test_context.hollow_zero_record.period_reward_complete = True
        test_context.hollow_zero_record.check_and_update_status()
        assert 2 == test_context.hollow_zero_record.weekly_run_times
        assert 0 == test_context.hollow_zero_record.daily_run_times
        assert True == test_context.hollow_zero_record.no_eval_point
        assert True == test_context.hollow_zero_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == test_context.hollow_zero_record.run_status