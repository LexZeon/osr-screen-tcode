# 0.2.2-test - 2026-09-24

- 与主程序共用物理桌面坐标、DPI 初始化及多显示器框选组件；保留左侧/上方显示器的负坐标，支持跨显示器矩形。
- 独立工作线程复用经过区域检查的屏幕采集；无效/断开的屏幕区域拒绝读取，桌面间隙保留黑色，不移动选区。
- 确认新区域清除旧画面与参考，取消保留原选择；运行中先停止再框选。
- 开始新来源前清除旧预览，防止新视频加载失败时保留旧来源画面；模型/区域预检失败或取消仍保留原画面。状态栏分开屏幕采集坐标/尺寸与实际分析尺寸，视频不显示屏幕坐标。
- 极细长区域缩小后短边至少 1 像素；默认最长边 640、完整等比例显示和原分析算法不变。
- 本目录复用上一级源码屏幕组件，不导入主界面、设备模块或主软件个人设置。需与上一级源码一起保留。
- Share physical desktop geometry and multi-monitor selection, preserve negative coordinates, validate capture regions, and clear stale previews after selection. Keep at least one pixel on very thin resized edges. Analysis and local settings remain independent; no device output is added.
- Clear the previous image before starting a new source, while retaining it on cancelled/failed prechecks. Distinguish physical screen capture coordinates and dimensions from processing dimensions; videos show only processing dimensions.

# 0.2.1-test - 2026-09-05

- 保留四项可选稳定处理及 0.2.0 用户勾选状态，不改变连续画面的微抖平滑参数。
- 32x24 缩略图检测明显画面突变；多人点整体大幅跳变、超过 0.2 秒帧间隔或尺寸变化时清空跟踪历史。
- 切镜头后使用当前有效观测，不保留上一镜头的预测骨架；隐藏明显拉长的缺失端点和越界预测。
- RTM 状态新增帧间隔、重置次数，以及视频文件因追赶播放时间跳过的帧数。屏幕源不推测丢帧数量。
- Preserve stabilization for continuous shots; reset stale history on discontinuities, hide implausible stale endpoints, and show frame-gap/reset/video-skip diagnostics. Main application unchanged.

# 0.2.0-test - 2026-09-05

- 默认原始 RTM 结果，四项处理关闭；旧版设置首次迁移为关闭，此后记住用户选择。
- 微抖平滑只作用于处理画面中不超过 3 像素的变化；更大位移直接跟随。
- 实验处理修正光流锚点、重复卡尔曼修正、持续拒绝后的重捕获，以及严重滞后时回到观测。
- 增加独立的画面运动、画面运动 v2 预览模式，无需模型；不是主软件混合分析算法。
- 增加相对参考的画面左右/上下/尺度观测与最近 8 秒图表。尺度不代表真实深度。
- 增加 320/480/640/960/1280 最长边选项，默认 640，实时生效、等比例、不放大小图。
- 增加图像观测和分辨率测试；主软件、设备输出和脚本算法未改。
- Raw RTM defaults, optional micro smoothing, experimental stabilization recovery fixes, standalone translation/scale visualization, and live processing-resolution selection. No main-app integration.

# 0.1.0-test - 2026-09-05

- 新增独立原始/稳定骨架对比预览，无设备和脚本输出。
- 可选异常过滤、光流、卡尔曼及轻平滑；去重时间戳、短时预测过期。
- 中英双语界面、屏幕区域/视频输入、本地独立设置及 Start.cmd。
- Added standalone raw/stabilized pose comparison, optional rejection/flow/Kalman/smoothing, local settings and source launcher. Main application unchanged.
