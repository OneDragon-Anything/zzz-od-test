# 游戏画面截图存档(webp q90)

按 `<screen_name>/<state>.webp` 组织,镜像 `docs/game/screens/`。用途:测试 fixtures(conftest 的 `load_screen`/`mock_screen`)+ 文档溯源。

## 格式约定
- **webp q90**(有损,~100-150KB/张;已验 13 打开游戏子态识别无损,conf 损耗 <0.006)。
- **1080p 原生**(同 screen_info `pc_rect` 坐标,**不缩放**——喂 offline analyze/流程测试时坐标才对得上)。
- 文件名 = 子态可读名(如 `ready.webp`、`账号密码登录.webp`)。
- **UID 打码**:右下 UID 区域涂色(对齐 `controller.fill_uid_black`),防账号信息随 fixture 外泄;识别不依赖 UID,打码无损识别。

## 已归档
- `打开游戏/`:ready、loading、退出登录弹窗、账号确认、账号确认-下拉、验证码登录、扫码登录、扫码成功、账号密码登录、选区服、登录服务器中、登录成功(12)
- `加载画面/`:港口工厂旧址(lore tip 代表帧)
- `大世界/`:普通(`大世界-普通` 变体,OpenAndEnterGame 流程测试终态)
- `米哈游启动页/`、`警告_游戏前详阅/`、`绝区零标题页/`:默认(游戏启动序列三页,`游戏启动.md` 相关)
- `邮件/`:列表(无可领)、列表-有可领、确认弹窗(email app 有/无可领两场景测试 fixture)
- `菜单/`:菜单(邮件返回 + BackToNormalWorld fixture)
- `菜单-更多功能/`:默认(功能入口枢纽 fixture)
- `兑换码输入/`:默认(redemption_code 输入态)
- `仓库-驱动仓库/`:默认(驱动盘管理,音擎 TAB-驱动盘)
- `仓库-驱动仓库-驱动盘拆解/`:默认、快速选择(drive_disc_dismantle;拆解确认待补)
- `快捷手册-日常/`:默认(engagement_reward 今日活跃度;领取弹窗待补)
- `丽都城募/`:默认、成长任务(city_fund 大月卡;5 tab)
- `报刊亭/`:默认、刮态(scratch_card;嗷呜对话/确认待补)

> `警告_游戏前详阅` 用下划线(screen_name `警告:游戏前详阅` 带冒号,Windows 目录名非法)。

## 待补(TODO)
(游戏启动链路 + 邮件/兑换码/驱动盘拆解 已齐;后续其他玩法截图按需补充)
