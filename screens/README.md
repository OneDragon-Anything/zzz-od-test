# 游戏画面截图存档(webp q90)

按 `<screen_name>/<state>.webp` 组织,镜像 `docs/game/screens/`。用途:测试 fixtures(conftest 的 `load_screen`/`mock_screen`)+ 文档溯源。

## 格式约定
- **webp q90**(有损,~100-150KB/张;已验 13 打开游戏子态识别无损,conf 损耗 <0.006)。
- **角标模板来源例外**:贝果 `仓库角标完整-20260930`、`装备角标完整-20260930`、`电子保险箱满箱对换失败-20260930` 从原生 PNG 转为无损 WebP，保留裁模板所需的原始像素；裁剪矩形见主仓 `docs/game/screens/贝果计划.md`「格子」。
- **贝果精度敏感样本**:定位、细文字 OCR、物品格变化等原 PNG 样本使用无损 WebP，转换后逐像素核对一致；不对这些样本施加有损压缩。同名 WebP 已被测试使用时，不重复保留无引用的 PNG 副本。
- **品质压缩对照**:`武备箱红底金图案-20260921-无损.webp` 保留原始像素，与同名不带「无损」后缀的有损版本共同验证品质识别，二者均为测试输入。
- **1080p 原生**(同 screen_info `pc_rect` 坐标,**不缩放**——喂 offline analyze/流程测试时坐标才对得上)。
- 文件名 = 子态可读名(如 `ready.webp`、`账号密码登录.webp`)。
- **UID 打码**:右下 UID 区域涂色(对齐 `controller.fill_uid_black`),防账号信息随 fixture 外泄;识别不依赖 UID,打码无损识别。

## 已归档
- `贝果-备战/`：`clear_loadout_carried`、`clear_loadout_empty`、`clear_loadout_tools_only`、`clear_loadout_second_weapon_stored`、`clear_loadout_weapon_detail`、`clear_loadout_equipment_detail`、`clear_loadout_item_detail`、`clear_loadout_dense_inventory`、`clear_loadout_dense_detail`、`preset_two`，用于启动清空的携带读数、槽位、详情与预设画面参考。
- `贝果-仓库/`：`clear_loadout_backpack_carried`、`clear_loadout_prepare_warehouse_empty`、`clear_carried_six_before`、`clear_carried_six_animation`，用于批量转存、携带数量与图标动画回归。
- 上述启动清空图均为原生 1080p 并已遮挡 UID。用于携带读数、槽位和图标变化回归的画面采用无损 WebP；仅作画面参考的 `clear_loadout_dense_detail` 与 `preset_two` 采用 WebP q90。详情及动画帧只用于对应状态，不作为稳定主画面或连续实机流程证据。裁模板使用原始 PNG，有损归档不能作为原图。具体画面事实见主仓 `docs/game/screens/贝果计划.md`「启动清空相关画面」。
- `贝果-局内/电子保险箱交互-HUD错字-20260930.webp`：原生1080p失败截图，无损 WebP 并遮挡 UID，保留 `UPROAR` 被识别成 `IPROAR` 的像素，用于交互前 HUD 容错回归。
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
- `贝果-仓库/`:仓库角标完整-20260930、装备角标完整-20260930(角标模板来源与类型识别回归)。
- `贝果-局内/`:电子保险箱满箱对换失败-20260930(贵重物品角标来源；失败截图归档不等于对换已修复)。
- `3D地图/`:默认(传送枢纽;选传送点/前往待补)

> `警告_游戏前详阅` 用下划线(screen_name `警告:游戏前详阅` 带冒号,Windows 目录名非法)。

## 待补(TODO)
(游戏启动链路 + 邮件/兑换码/驱动盘拆解 已齐;后续其他玩法截图按需补充)
