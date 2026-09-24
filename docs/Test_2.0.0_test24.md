# 2.0.0-test.24：多显示器区域一致性与框选界面

本版在 test.23 源码上修复屏幕坐标、采集与预览一致性。主程序版本为 `2.0.0-test.24`，项目元数据为 `2.0.0.dev24`，独立预览为 `0.2.2-test`。使用根目录 [Start.cmd](../Start.cmd)；[Start.md](../Start.md) 是启动说明。

## 用户可见变化

- 框选使用深色屏幕快照、青绿色边框、明亮选区、角标和中心标记；显示屏编号、分辨率、选区物理像素位置与尺寸。松开后可点“使用此区域／重新选择／取消”，也支持 Enter／R／Esc。提示与确认卡限制在真实显示器内，窄屏按钮自动纵排。
- 框选快照只在内存中保留，关闭后释放；它不是实时分析画面。仅打开框选器时，在前后两次桌面提交之间留出最多 250 ms 的剩余等待，减少主窗口隐藏动画残影；实时采集没有新增等待。
- 主程序和独立预览使用同一个物理像素坐标实现。支持左侧／上方副屏的负坐标以及跨屏矩形，显示器之间没有屏幕的部分保持黑色，不挤压或移动已有像素。
- 分析预览分别标出实际采集位置／尺寸与分析处理尺寸。缩小处理或界面留黑边不会改变选区，也不会再次裁剪。
- 实时分析或视频导出期间锁定区域和来源控件；停止后可修改。如果程序方式改变输入，停止原任务并废弃旧参考及排队预览，防止新设置对应旧画面。
- 坐标输入暂时为空、只有负号或尺寸无效时，保存其他设置但保留上一组完整区域。启动前校验，越界、只框到显示器空隙或小于 16×16 会提示重新选择。鼠标框选最小为 24×24。
- 显示器断开、排列或分辨率改变后，采集检测到桌面几何变化会停止并提示；不会默默改抓主屏。重新框选后再启动。

## 原因与代码位置

旧主框选把整个虚拟桌面宽高除以 Tk 主屏尺寸当作缩放倍率。多屏布局和缩放混在一起后，X、Y 甚至会被应用不同倍数。旧 `ScreenRegion.normalized()` 又把负坐标夹到零，导致左／上副屏选区偏向主屏。

- `src/osr_screen_tcode/screen_geometry.py`：在 Tk 创建前启用每显示器 DPI 感知；原生枚举实际屏幕矩形，鼠标与窗口使用有符号物理坐标。采集线程单独进入并恢复 DPI 上下文，不再修改 MSS 的全局实现。
- `capture.py`：严格校验矩形而不平移／缩放；验证返回帧大小；每 0.5 秒核对几何布局，屏幕空隙显式置黑。
- `region_selector.py`：主程序与 Lab 共用的框选、内存快照、跨屏投影、按钮、清理及双语文本。
- `app.py`：启动时在界面线程确定完整采集快照，工作线程直接使用；输入变化清预览与参考、锁定运行中的编辑、完整区域原子保存；开始确认、语言等弹窗与提示按所在显示器定位。
- `integrated_preview.py`：明确区分采集矩形与分析尺寸；沿用同帧成对预览。
- `visual_pipeline.py`、`Pose-Preview-Lab/preview.py`：极细长画面等比缩小时短边至少保留 1 像素，避免 OpenCV 的零尺寸错误。v1 的最小处理边不再分别拉伸宽高；修改压缩滑块会重建旧帧参考，防止两帧尺寸不同导致分析中止。

处理最长边默认仍是 640。没有调整 v1/v2/Pose 的运动识别核心、最终行程倍率、TCode、模拟器或录制算法。极细区域虽然能完整显示，仍可能缺少运动特征；会报告缺测，不捏造运动。

## 验证记录

- 主程序通过隔离入口 `python tests/run_tests.py -v`：**345 项全部通过，442.480 秒**；测试结束核对个人配置未变化。
- 独立预览完整检查：**38 项全部通过，0.352 秒**。覆盖选区取消、切换来源清旧帧、工作线程精确矩形、极细区域及原骨架稳定处理。
- 主程序中英文 `Start.cmd --smoke --language zh/en` 与 Lab `Start.cmd --smoke` 均正常启动并退出；没有安装依赖。
- 模拟器最终指令检查通过：动画不能覆盖经过最终倍率与限制后的指令。
- 单独运行最终生产代码 Log only 读屏 8 秒：**304 次统计更新**，正常停止、工作线程退出，无采集或界面回调错误。最后一次统计约为采集 64.95 FPS／分析 67.66 FPS／输入年龄 8.83 ms；这些来自各自滚动统计窗口，不能解读为每秒分析帧数超过实际新采集帧数，也不是所有设备的性能保证。
- 所有图形启动与实际读屏检查串行执行，没有与完整测试争用采集。核对配置使用用户确认更新后的文件，后续指纹一直一致。

本机显示器为主屏 2560×1440／100%，右侧竖屏 2160×3840／150%，虚拟桌面 4720×3840。没有更改 Windows 的显示设置。

原生鼠标拖拽校验使用临时合成色块窗口，避免记录用户桌面：主屏 `(1600,400,600,600)` 与副屏 `(2710,600,900,750)` 的实际帧尺寸及四角色块均匹配。查看了中英文框选卡及主程序成对预览。原生观察工具不能直接绑定无标题边框的窗口，因此视觉和鼠标校验临时加了诊断窗口边框，并保持客户区原点／宽高完全相同；产品仍为无边框遮罩。

随后使用**未改动的产品无边框组件**补验：实际窗口及 Canvas 原点、宽高等于完整物理桌面；隐藏父窗口后的快照采样未留下窗口残影。模拟物理鼠标端点进入正常确认回调，跨屏区域 `(2400,1200,600,600)` 实际采集为 600×600，主屏／副屏／空隙／副屏四点像素全部符合预期，空隙为纯黑。组件回调检查与上方真实鼠标拖拽分别验证，不混为同一项。

早期校验中，窗口刚创建时 Canvas 为 1×1；正常事件循环推进后为完整桌面尺寸，这是尚未处理布局事件的测试时机问题。探针已验证提前请求 geometry 并不能改善，因此未向定位函数加入可重入的 Tk `update()`。另一轮临时测试脚本选错 Notebook 子控件导致预览检查报错，已修正测试脚本；一次鼠标停留在采样点附近时该点颜色不符，可能受鼠标效果影响，移到确认按钮后复验四点全部匹配。失败尝试不计为通过。早期窗口快照确有隐藏动画残影，加入一次性桌面提交及短暂等待后，上述最终产品组件复验通过。

设置核对中发现起始快照后配置文件被保存；用户随后明确更正为操作过 OSR。保留用户更新后的配置，后续测试以该文件为核对基线，不把整个开发期间的指纹变化归因于测试，也不覆盖用户操作。

## 边界与复测

实际双屏检查覆盖本机 100%＋150% 组合及跨屏空隙；负原点和其他排列由自动回归覆盖，没有实际重排显示器。远程桌面、特殊显示驱动、HDR／受保护视频和异常缓慢的系统动画仍需当地复测。打开框选器时的桌面提交及短暂等待不能保证所有桌面会话或自定义动画都已完成。

屏幕截图是当前可见画面；若软件窗口覆盖选区，实时分析也会读取该窗口。请把操作窗口移出选区。非常窄的区域、模糊、遮挡和复杂主体的识别限制仍按 test.23；尺度不是实际深度。

未连接真实设备，没有验证机械臂关节映射、逆运动学、碰撞检测或反馈；未安装依赖、打包、提交或推送，未改正式仓库、旧发布包和 PoseBridge Lab。

## 参考与使用范围

实现依据 Windows 与 MSS 的公开接口自行编写，没有复制第三方项目代码或新增依赖：

- [Microsoft：虚拟屏幕和负坐标](https://learn.microsoft.com/en-us/windows/win32/gdi/the-virtual-screen)
- [Microsoft：每显示器 DPI 感知](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext)
- [Microsoft：DwmFlush 的提交边界](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmflush)
- [MSS API](https://python-mss.readthedocs.io/latest/api.html)

## English

Test.24 unifies selection, screen capture and analysis previews in signed physical desktop pixels. A shared dark snapshot picker highlights the selected area, shows display/region dimensions, and supports Use / Retry / Cancel plus Enter / R / Esc. Narrow-display panels stay within the real monitor. The temporary snapshot is kept only in memory; live capture resumes after closing the picker.

Per-monitor DPI awareness is established before Tk. Capture owns its thread DPI context and immutable region; negative coordinates are preserved, gaps are black, out-of-desktop rectangles are rejected, and geometry changes stop capture instead of silently moving it. Input edits invalidate queued old previews; invalid partial entries preserve the last complete saved rectangle. Capture geometry and analysis size are shown separately. Extreme aspect ratios retain the whole frame; v1 compression changes reset frame history.

The default processing edge remains 640. Tracking, output scaling, TCode and simulator algorithms are unchanged. Final validation passed 345 isolated host tests, 38 Lab tests, Chinese/English startup, Lab startup, final-command simulator validation and a live Log-only run with 304 statistics updates and orderly worker exit. Local physical checks use the existing 100% landscape and 150% portrait screens, including an actual cross-screen capture with a black desktop gap; negative origins and other layouts are covered synthetically. See the validation section for failed diagnostic attempts and test-harness limits. No hardware verification, dependency installation, packaging, commit or push was performed.
