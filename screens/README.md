# 游戏画面截图存档(webp q90)

按 `<screen_name>/<state>.webp` 组织,镜像 `docs/game/screens/`。用途:测试 fixtures(conftest 的 `load_screen`/`mock_screen`)+ 文档溯源。

## 格式约定
- **webp q90**(有损,~100-150KB/张;已验 13 打开游戏子态识别无损,conf 损耗 <0.006)。
- **1080p 原生**(同 screen_info `pc_rect` 坐标,**不缩放**——喂 offline analyze/流程测试时坐标才对得上)。
- 文件名 = 子态可读名(如 `ready.webp`、`账号密码登录.webp`)。

## 已归档
- `打开游戏/`:ready、loading、退出登录弹窗、账号确认、账号确认-下拉、验证码登录、扫码登录、扫码成功、账号密码登录、选区服、登录服务器中、登录成功(12)
- `加载画面/`:港口工厂旧址(lore tip 代表帧)
- `大世界/`:普通(`大世界-普通` 变体,OpenAndEnterGame 流程测试终态)
- `米哈游启动页/`、`警告_游戏前详阅/`、`绝区零标题页/`:默认(游戏启动序列三页,`游戏启动.md` 相关)

> `警告_游戏前详阅` 用下划线(screen_name `警告:游戏前详阅` 带冒号,Windows 目录名非法)。

## 待补(TODO)
(登录游戏 / 游戏启动 相关已齐;后续其他玩法截图按需补充)
