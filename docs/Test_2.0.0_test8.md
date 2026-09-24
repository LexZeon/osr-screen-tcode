# 2.0.0-test.8 / Local source test

本轮修正 v2 把运镜当作主运动、明确往复却输出行程短的问题；将混合分析 1/v2 实际使用的参考显示在分析画面内；将 **RTM Pose 2D 的 L0 基础输出幅度改为原来的 5 倍**。只更新测试源码，双击根目录 [Start.cmd](../Start.cmd) 运行。[Start.md](../Start.md) 提供操作步骤。

This update adds camera-relative v2 analysis and stroke calibration, shows the actual hybrid measurement references in the preview, and multiplies **RTM Pose 2D base L0 output by five**. Run the root **Start.cmd**. Existing preview, settings and simulator behavior from [test.7](Test_2.0.0_test7.md) remain.

## 在画面内看实际参考 / Actual references in the image

进入 **分析预览**，选择混合分析 1 或 v2 后开始。右侧画面显示实际测量依据，左侧在画面区域内显示说明：

- **黄框／十字**：本帧实际采用的局部区域与区域中心。不是人体检测框。
- **绿点／箭头**：实际参与测量的采样点和运动。v1 取自身原有运动掩膜／ROI 内的光流；v2 显示扣除背景运动后的局部运动。点多时仅抽样显示，计算仍使用完整有效点集。
- **蓝点（v2）**：实际参与运镜估计的背景参考点。
- 说明列出采用的上下／左右／尺度变化；v2 另显示背景变化、主方向权重、往复参考跨度与识别校准倍率。**分析 L0 是最终输出倍率之前的值**；实际指令仍看输出监视或 3D 模拟器。
- “参考不足”“只有背景运动”“跟踪参考区域”等状态会直接显示。短暂转向停顿保留参考，不把该帧当成新的运动。**重设参考**会清除跟踪与往复历史，v1/v2 都生效。

说明文字使用界面语言。移除了 v1 原来按输出值画的整幅横线，避免将其误认为识别参考；其 L0 核心数值保持不变。

Yellow marks the actual selected image region; green marks sampled motion used for analysis. V2 blue points are the background reference actually used to estimate camera motion. These are image features, not a person detector. The in-image notes distinguish camera movement, measured movement, direction weights, stroke calibration and analysis L0 before final output gains. Recalibrate clears tracking history in both hybrid versions. V1's numerical core is unchanged.

## v2 运镜分离与行程 / Camera-relative v2 and stroke range

上版只对整幅画面运动添加往复确认，仍可能被往复运镜干扰；图像位移百分比直接变成 L0 百分比，也使小幅实际往复只得到短行程。

现在先对画面分区采样，在边缘寻找覆盖多个方向、分布足够广的背景点，拟合背景平移／缩放／旋转；再寻找相对背景运动且局部一致的区域。主方向和无模型旋转分析使用去除背景影响后的运动。没有可靠的独立运动参考时，保持既有输出空闲策略，不退回整幅运镜信号。

有效的双向行程确认后，L0 按近期往复跨度逐步校准，目标参考行程约 75%，校准倍率最多 40。校准只作用于之后的运动增量，不因暂停、倍率变化或旧偏移而生成虚假运动；尚未确认往复时不放大小幅噪声。最终幅度仍受五档、用户行程倍率及既有输出限制影响。单／六轴使用相同的 L0，RTM 旋转辅助不改变它。

V2 now estimates camera motion from broadly supported edge features, then measures a coherent region moving relative to that background. Without an independent reference, it holds rather than treating whole-frame motion as a subject stroke. Once meaningful motion in both directions is established, recent stroke span gradually calibrates L0 toward roughly 75% travel, capped at a calibration gain of 40. Only future increments are scaled. Output presets, travel controls and existing limits still apply afterward.

## RTM Pose 2D 的 L0 五倍基础输出 / Dance L0 ×5

仅在 **RTM Pose 2D 分析模式**，L0 相对中位放大：`0.5 + (原 L0 - 0.5) × 5`，限定到 0～1。单轴与六轴都生效。例如原分析 L0 为 54%，基础输出变为 70%；后续 L0 总行程倍率为 0.5 时变为 60%，再进入反向、轴范围与限速等原有输出处理。

这个固定基础倍率应用于实时输出、录制及离线导出的共同换算入口，不修改骨架或画面观测；不对混合分析 v2 重复放大。舞蹈开启 v2 混合来源时，对混合后的舞蹈 L0 应用一次。模拟器收到的仍是输出端同一条最终 TCode，包含适用的全部倍率与限制。

Dance L0 is scaled fivefold about center and clamped to 0–1, for both single and six-axis output. A measured 54% becomes 70%; a subsequent 0.5 travel setting produces 60% before axis limits and other output constraints. The shared live/record/export conversion applies it once, without changing observations. Hybrid v2 does not receive this dance gain. The simulator still receives the final sink command.

## 验证与文件 / Verification and files

- 主程序 **129 项**自动测试、独立预览 **28 项**测试通过；模拟器消息／动画测试通过。
- 合成画面覆盖纯背景往复横移／上下／缩放／旋转、背景与局部不同方向、微小但明确的往复、左右／尺度主轴、参考不足、断帧／切镜头和重设参考。
- v1 原始 L0 数值回归、实际 ROI／采样点快照、v2 单／六轴与旋转辅助一致性、校准不改变辅轴观测和静止位置均通过。
- 五档输出脚本不同而分析样本相同；RTM L0 五倍、后续总行程换算、最终模拟器指令一致性通过。中英文启动与参考显示检查通过。
- 未连接真实设备，未向正式 Python 环境安装或升级依赖，未保存检查用个人配置。自动与合成检查不代表真实片段质量已验证。

129 main tests and 28 standalone tests passed, along with simulator message/animation checks. Coverage includes camera-only motion, small local strokes, alternate primary axes, lost references, calibration, unchanged v1 outputs, output-only presets and dance L0 gain routing. Startup and reference display were checked in both languages. No hardware was connected.

主要改动：

| 文件 | 作用 |
| --- | --- |
| `src/osr_screen_tcode/camera_motion.py` | 背景参考、局部运动和有效点选择 |
| `src/osr_screen_tcode/dominant_motion.py` | 保留主方向确认，新增往复跨度校准 |
| `src/osr_screen_tcode/motion_reference.py` | 实际测量快照、区域／点绘制、中英文说明 |
| `src/osr_screen_tcode/analyzer.py` | 只为 v1 提取实际参考并调整绘制，原 L0 核心不改 |
| `src/osr_screen_tcode/visual_pipeline.py`、`integrated_preview.py` | 共用同帧观测与界面显示 |
| `src/osr_screen_tcode/pose_output.py`、`app.py` | 舞蹈 L0 五倍基础输出与重设参考 |
| `tests/test_camera_motion.py`、`motion_scenes.py` 等 | 合成画面、回归、输出和界面检查 |

## 复测与限制 / Retesting and limitations

**先用 Log only，并让采集区域保留主体周围的背景。** 对比同一真实片段的 v1/v2：观察黄框是否落在期望区域、蓝点是否被人物或字幕占据、绿点是否跟随主体，以及跨度／校准是否在往复后建立。

边缘被主体占满、低纹理背景、遮挡、多运动区域、字幕和局部屏幕动画仍会干扰参考选择。当前只区分相对图像运动，不能保证选中用户期望的人物，也不能判断实际前后深度。短暂静止最多保留约 300 ms 的区域测量；参考丢失后需要重新确认往复，可能产生跟随延迟。

RTM 五倍与 v2 校准都会更容易触及用户设置的行程上限；模拟器表示最终指令，不是机械位置反馈。真实机械臂关节映射、逆运动学、碰撞检测和反馈仍未验证。默认处理最长边保持 640，舞蹈／混合设置保存与恢复默认规则不变，独立 Lab 源码和版本保持原样。

Use Log only and include background around the subject. Check the selected region and background points on real clips. Low texture, subject-filled edges, occlusion, captions and multiple moving regions can still cause rejection or a wrong region choice. This is relative image motion, not person identity or physical depth. Calibration/reacquisition adds delay, and larger base gains may reach configured endpoints sooner. Physical robot-arm mapping, IK, collision checking and feedback remain unverified. No package, commit, push, formal-directory or old-release changes were made.
