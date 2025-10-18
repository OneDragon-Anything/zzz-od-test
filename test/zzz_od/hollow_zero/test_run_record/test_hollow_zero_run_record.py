from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.utils import os_utils
from test.conftest import TestContext
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import HollowZeroExtraTask


class TestWitheredDomainRunRecord:

    def test_run_status_under_now(self, test_context: TestContext):
        """
        测试当前显示状态的正确性
        """
        config = test_context.run_context.get_config(
            app_id=withered_domain_const.APP_ID,
            instance_idx=test_context.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        run_record = test_context.run_context.get_run_record(
            app_id=withered_domain_const.APP_ID,
            instance_idx=test_context.current_instance_idx,
        )

        config.weekly_plan_times = 2
        config.daily_plan_times = 1

        # 先设置成功
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)

        # 上周运行的 已经完成
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -7)
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == run_record.run_status_under_now

        # 昨天运行的 每日次数已经完成
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -1)
        run_record.weekly_run_times = 1
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == run_record.run_status_under_now

        # 今天运行的 每日次数已经完成
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 1
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status_under_now

        # 今天运行的 但每天次数不满
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 1
        run_record.daily_run_times = 0
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == run_record.run_status_under_now

        # 今天运行的 但每周次数满了 但业绩没满
        config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == run_record.run_status_under_now

        # 今天运行的 每周次数满了 每天次数满了 但业绩没满
        config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status_under_now

        # 今天运行的 每周次数满了 业绩也满了
        config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = True
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status_under_now

        # 今天运行的 每周次数满了 周期奖励未满
        config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = True
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_WAIT == run_record.run_status_under_now

        # 今天运行的 每周次数满了 每天次数满了 周期奖励未满
        config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 1
        run_record.no_eval_point = True
        run_record.period_reward_complete = False
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status_under_now

        # 今天运行的 每周次数满了 周期奖励已满
        config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = True
        run_record.period_reward_complete = True
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status_under_now

    def test_check_and_update_status(self, test_context: TestContext):
        """
        测试更新状态的正确性
        """
        config = test_context.run_context.get_config(
            app_id=withered_domain_const.APP_ID,
            instance_idx=test_context.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        run_record = test_context.run_context.get_run_record(
            app_id=withered_domain_const.APP_ID,
            instance_idx=test_context.current_instance_idx,
        )

        config.weekly_plan_times = 2
        config.daily_plan_times = 1

        # 上周运行的 已经完成
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -7)
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 1
        run_record.no_eval_point = True
        run_record.period_reward_complete = True
        run_record.check_and_update_status()
        assert 0 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert False == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == run_record.run_status

        # 昨天运行的 每日次数已经完成
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.add_dt_offset(os_utils.get_dt(), -1)
        run_record.weekly_run_times = 1
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 1 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert False == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == run_record.run_status

        # 今天运行的 每日次数已经完成
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 1
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 1 == run_record.weekly_run_times
        assert 1 == run_record.daily_run_times
        assert False == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status

        # 今天运行的 但每天次数不满
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.NONE.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 1
        run_record.daily_run_times = 0
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 1 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert False == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == run_record.run_status

        # 今天运行的 每周次数满了 但业绩没满
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 2 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert False == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == run_record.run_status

        # 今天运行的 每周次数满了 每天次数满了 但业绩没满
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 1
        run_record.no_eval_point = False
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 2 == run_record.weekly_run_times
        assert 1 == run_record.daily_run_times
        assert False == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status

        # 今天运行的 每周次数满了 业绩也满了
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.EVA_POINT.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = True
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 2 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert True == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status

        # 今天运行的 每周次数满了 周期奖励未满
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = True
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 2 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert True == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_WAIT == run_record.run_status

        # 今天运行的 每周次数满了 每天次数满了 周期奖励未满
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 1
        run_record.no_eval_point = True
        run_record.period_reward_complete = False
        run_record.check_and_update_status()
        assert 2 == run_record.weekly_run_times
        assert 1 == run_record.daily_run_times
        assert True == run_record.no_eval_point
        assert False == run_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status

        # 今天运行的 每周次数满了 周期奖励已满
        run_record.update_status(AppRunRecord.STATUS_SUCCESS, only_status=True)
        config.extra_task = HollowZeroExtraTask.PERIOD_REWARD.value.value
        run_record.dt = os_utils.get_dt()
        run_record.weekly_run_times = 2
        run_record.daily_run_times = 0
        run_record.no_eval_point = True
        run_record.period_reward_complete = True
        run_record.check_and_update_status()
        assert 2 == run_record.weekly_run_times
        assert 0 == run_record.daily_run_times
        assert True == run_record.no_eval_point
        assert True == run_record.period_reward_complete
        assert AppRunRecord.STATUS_SUCCESS == run_record.run_status