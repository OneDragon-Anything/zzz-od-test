# 一条龙测试仓

将本仓放到主仓根目录，目录名为 `zzz-od-test`。从主仓根目录运行测试，环境准备见[主仓测试说明](../docs/develop/testing/README.md)。

贝果日常检查使用：

```powershell
uv run --no-sync --env-file .env python zzz-od-test/run_bagel_tests.py fast
```

完整回归、全仓检查、覆盖范围和计时要求见主仓[贝果测试入口](../docs/develop/testing/bagel.md)。当前覆盖与限制见[覆盖说明](BAGEL_COVERAGE.md)，素材来源缺口见[素材记录](BAGEL_MATERIALS.md)。
