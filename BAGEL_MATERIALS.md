# 贝果素材：用途、来源与缺口

统一规则见主仓[素材归档规范](../docs/develop/zzz/screenshot_archive.md)。本文维护用途、来源和缺口，不重复记录统一规则。

| 素材 | 权威记录 | 已知限制 |
| --- | --- | --- |
| 历史归档与安全箱锁图标来源 | [历史像素来源](screens/bagel_archive.json) | 部分有损解码后改为无损编码；锁图标有裁剪矩形和处理记录，可重建 |
| 搜查面板录像、开关过渡帧 | [过渡来源](screens/贝果-局内/搜查面板过渡/来源.json) | 源录像标识、摘要、帧率、帧号和账号标识（UID）遮挡区域已记录；帧来自录像解码 |
| 七档投资与金币故障图 | [金额来源](screens/贝果-入场确认/金额识别对照/来源.json) | 记录归档摘要和来源分类。录像代表帧缺精确帧号；独立PNG故障图缺原文件标识，不能挂到金额录像名下 |
| 角标参考图与运行模板 | 主仓[画面缺口](../docs/game/screens/贝果计划.md#角标来源与裁剪缺口) | 完整裁剪、缩放和居中参数尚缺，不能用识别格心冒充裁剪矩形 |
| 两张发布底图 | 主仓[地图来源限制](../docs/develop/zzz/application/bagel_fixed_map.md#当前发布资源的来源与限制) | 缺完整源素材对应关系，当前无法按原采集过程重建 |
| 历史4K缩放图 | [画面归档](screens/)与[物品识别测试](test/zzz_od/application/bagel/bagel_item_vision/test_identify.py) | 仅是历史缩放样本，不能称原生1080p |
| 金额框线图和局部品质样本 | [金额说明](screens/贝果-入场确认/金额识别对照/README.md)与[品质测试](test/zzz_od/application/bagel/bagel_item_vision/test_identify.py) | 说明图、局部图保留当前尺寸，不套整屏限制 |
| 201×201定位图 | [定位数据](test/zzz_od/application/bagel/bagel_fixed_map/data/)与主仓[地图说明](../docs/develop/zzz/application/bagel_fixed_map.md) | 局部参考图，不是整屏 |
| 测试运行时合成图 | `test/harness/` 的合成函数及具体场景 | 包括锁格、数值变化、遮挡和位移，不代表实机发生过该完整过程 |

相近故障帧、连续帧与有损/无损对照保留各自用途。静态搜索不到引用不能作为删除依据。

## 审核边界

图片解码、尺寸检查、文件摘要和模板重建只能验证对应的文件属性。逐图视觉审核 UID、外部来源链接可用性及缺失源录像的补采尚未完成；静态检查不能替代这些工作。
