# Pose Preview Lab 0.2.2-test

**Included with OSR test.26:** extract the complete **Windows.zip**, then run `Pose-Preview-Lab/Start.cmd`. It dispatches the same bundled EXE into the independent preview, with no separate Python installation. Source startup still needs Python 3.10+. Keep the complete archive together. Lab remains **0.2.2-test**. See the [portable guide](../tools/README-Portable.md) and [test.26 report](../docs/Test_2.0.0_test26.md).

**随 OSR test.26 提供：** 完整解压 **Windows.zip** 后运行 `Pose-Preview-Lab/Start.cmd`，由同一内置 exe 打开独立预览，无需另装 Python；源码启动仍需 Python 3.10+。请保留完整运行包，Lab 版本仍为 **0.2.2-test**。见 [便携包说明](../tools/README-Portable.md) 和 [test.26 记录](../docs/Test_2.0.0_test26.md)。

独立骨架预览测试器，不连接设备，不生成脚本，不读取或修改主软件设置。

## 一键运行

双击本目录的 **Start.cmd**，不是上一级的 Start.cmd。Start.md 是说明文件，不是可执行程序。
Windows 运行包使用同一内置 exe，无需外部 Python。仅源码启动需要 Python 3.10+：优先只读复用已有环境，否则首次启动在本目录创建环境并安装依赖，需要网络。模型不随源码或运行包提供、不自动下载。

1. 选择预览模式。RTM 模式需要 RTM Pose 2D 的 256x192 ONNX 模型，本机可自动发现上一级 models 里的匹配文件；不支持 3D 模型。两个画面运动模式不需要模型。
2. 点击“框选屏幕”，在任意显示器或跨显示器拖出人物所在区域，确认后点击“开始屏幕预览”。Enter 确认、R 重选、Esc 取消。请避免框入测试器自身。
3. 也可以“打开视频”做更方便的重复对比。
4. RTM 模式左侧橙色为原始识别，红点为被拒绝的观测；右侧青色为当前开关结果。同一帧配对显示，等比例完整显示。默认四项处理全关，以原始识别为准。
5. 四个开关可实时切换，每次切换重置历史与测量参考。“仅微抖平滑”只平滑 3 处理像素以内的变化，大位移直通。它仍可能带来少量滞后；不是识别纠错。
6. 切换预览模式会停止当前预览，请重新开始。画面运动模式不使用四个骨架处理开关，界面会将它们禁用。

## 模式与测量

- RTM 骨架：用两肩、两髋四点中心测量上下和左右位置，用两侧躯干平均长度测量画面尺度。参考由最初至少 0.3 秒、5 次有效观测的中位数建立；测量缺失超过 0.5 秒后重新建立参考。
- 画面运动：用图像特征的中位位移展示整体画面平移，不估计尺度。
- 画面运动 v2：用图像特征与鲁棒相似变换估计整体画面平移和缩放，不需要人体模型。不足 8 个可靠匹配时显示缺失并重置参考。
- 后两个模式是独立预览实验，并不是主软件的混合分析/混合分析 v2，也没有轴映射或设备输出。
- 图表显示最近 8 秒：X 正为向右、Y 正为向上，单位为画面宽/高百分比；尺度正为变大，单位为相对参考的百分比。重设参考按钮清空历史。
- 图表纵向刻度会自动变化，比较幅度请看百分比数字。缺失数据显示为空，不补零；基于 UI 收到的预览帧绘图，不是记录文件。
- 画面运动模式会追踪背景，受到运镜、变焦、特征丢失和积累漂移影响。RTM 尺度也会受到转身、遮挡影响。两者都不能测出真实深度。

## 分辨率对比

“处理最长边”提供 320、480、640、960、1280 像素，默认 640，实时生效、保持比例，小画面不放大。切换会重建参考。
建议用同一片段对比 320/640/960 的细节与处理耗时。状态栏显示实际处理尺寸、RTM 推理和总处理耗时。
这是采集后的缩小，不改变屏幕截图本身的原始尺寸。主要减少光流、复制、绘图的负担；RTM 输入仍为 192x256，不能保证推理耗时同比下降。低分辨率可能丢失细节。

## 多显示器与屏幕区域

0.2.2 与主软件共用屏幕坐标和框选组件，但仍独立采集、分析和保存本工具设置。坐标使用虚拟桌面的实际像素；位于主显示器左方/上方的显示器可以出现负 X/Y，不再改为 0。不同显示分辨率、缩放比例与跨显示器矩形使用同一坐标约定，预览完整等比例显示该矩形。

选择的新区域仅在确认后生效；取消保留旧区域。确认会清空旧预览和参考，防止将旧画面误认为新区域。预览正在运行时先停止，再重新框选。显示器断开、布局改变或区域超出可采集桌面时拒绝采集并显示错误，请重新框选；不会悄悄移动区域。显示器之间没有实际屏幕覆盖的桌面间隙在跨屏矩形中显示为黑色。极细长区域缩小后至少保留 1 像素短边，但这类区域通常不适合人体分析。

已用 1×640、640×1、16×16 和缩小后短边仅 1 像素的合成帧检查两个画面运动模式的完整分析调用：它们显示缺失，不生成运动数值。保留可显示画面不等于具有足够特征可分析；遇到这类选区应扩大实际画面范围，不会自动裁剪、拉伸或补出运动。

源码使用时，本目录需要与上级测试源码的 `src/osr_screen_tcode` 一起保留，不能单独复制本目录后删除上级共享屏幕组件；Windows 运行包应保留上级 exe、`_internal` 及整个目录。它不导入主界面、设备控制或主程序个人设置。

## 怎么验证

0.2.1 保留你在 0.2.0 保存的四项开关。连续画面的稳定处理不变；检测到明显切镜头、整体关键点大幅跳变或超过 0.2 秒的帧间隔时，清空旧历史并重建参考。异常拉长的预测连线会隐藏。
状态栏“帧间隔”为相邻处理帧的采样时间差，不是端到端延迟；“视频跳过”是文件播放追赶时主动跳过的累计帧数，不包含源视频原有掉帧，也不是屏幕源丢帧统计。
突变检测只用小缩略图和关键点差异，不额外运行模型。相似镜头可能漏检；闪光或极快动作可能触发重置。不能保证消除所有拉线或原模型识别错误。

- 人物静止：比较手、膝、髋点来回晃动程度。
- 快速动作：观察右侧是否明显落后、是否错误拒绝真实动作。
- 遮挡/离开画面：预测最多保留 0.25 秒，之后隐藏，不长期猜测。
- 再次入画：检查是否能重新捕获。比较同一视频、同一片段，不要只看曲线好不好看。
- 耗时是本次推理和处理耗时，不是完整屏幕到显示延迟；本工具没有准确率真值，不能用平滑程度代替准确率。

CPU 推理，屏幕目标 60 FPS，实际速度受模型和硬件限制。视频跟随播放时间，处理不及会跳过旧帧。
这是单人区域的预览实验；强透视、快速转身、多人、卡通人物可能误识别。骨长门限也可能错拒真实变化。
模型可能对没有人物的画面仍给出关键点，本工具不能可靠判定人物存在。

源码启动的设置保存在本目录 settings.local.json，已忽略上传；删除这个文件即可恢复默认。Windows 运行包使用本工具独立的用户设置目录，不写主软件设置或依赖解压目录可写。0.1.0 的处理开关会在升级后首次重置为关闭，此后正常记住选择。源码和运行包不包含模型或可下载的 CUDA／DirectML 运行环境。

## English

Double-click **Start.cmd in this folder**. In the complete test.26 Windows package it uses the bundled EXE without external Python. Source startup requires Python 3.10+; a local environment and dependencies are installed if no usable existing environment is found. No model is bundled or downloaded.
Choose RTM Pose 2D (requires a 256x192 ONNX model), Image Motion (translation), or Image Motion v2 (translation plus scale). The image modes require no model and are not the main application's hybrid algorithms.
Select a region on any monitor or across monitors, confirm it, and start Screen, or open a video. Enter confirms, R reselects, and Esc cancels. Changing mode stops playback; restart to apply.
RTM left: raw orange joints, rejected observations in red. Right: selected processing on the same frame. All four switches default OFF and apply live. Micro smoothing only filters displacements within 3 processing pixels; larger movements pass through.
Charts show relative X/right, Y/up in percent of image width/height, and image scale percent, over 8 seconds. Scale is not depth. Camera motion, background motion, rotation and drift can affect these values. Missing observations are not plotted as zero.
Max edge: 320/480/640/960/1280, default 640. Changes apply live, reset the reference, preserve aspect ratio and do not upscale. Resizing occurs after capture; the screenshot size is unchanged and RTM input remains 192x256. Lower resolution mainly reduces image-processing overhead, not necessarily inference time.
Compare stillness, fast motion, occlusion and re-entry. Predictions expire after 0.25 seconds. Timing is processing time, not end-to-end latency. Smoothness is not proof of accuracy.
Version 0.2.1 preserves saved 0.2.0 switches and continuous-shot filtering. Obvious image cuts, broad pose jumps, image resizing or gaps over 0.2 seconds reset stale history. Implausibly stretched stale endpoints are hidden. Gap is source-sample spacing; Skipped counts deliberate file-playback skips, not screen frame loss. Similar cuts may be missed and flashes/fast motion may trigger resets.
Version 0.2.2 shares physical desktop coordinates and the region selector with the source application. Negative origins for monitors above/left of the primary display are retained. Mixed resolutions/scales and cross-monitor rectangles use the same coordinates for selection and capture. New selections clear stale preview/history; cancellation keeps the previous selection. Stop before selecting again. Invalid or disconnected regions are rejected instead of silently moved; reselect after changing the display layout. Uncovered gaps between monitors remain black. Very thin regions retain at least one processing pixel on the short edge; such regions are rarely useful for pose analysis. For source startup, keep this folder alongside the parent `src/osr_screen_tcode` shared screen helpers; for portable startup, retain the entire Windows folder, including the parent EXE and `_internal`. The main GUI, device control and personal settings are not imported.
The complete image-motion analysis was checked with synthetic 1×640, 640×1, 16×16 and downscaled one-pixel strips. Both image modes report missing measurements without inventing motion. A displayable image may still lack usable features; enlarge the selected content rather than relying on automatic cropping, stretching or extrapolation.
No device connection, axis mapping, script output or main application configuration is used. Source settings remain local in this folder's git-ignored `settings.local.json`; the Windows package uses the Lab's separate user-settings directory without changing main-application settings or requiring a writable extraction folder.

## 来源 / Attribution

- RTM Pose: OpenMMLab MMPose / rtmlib, https://github.com/Tau-J/rtmlib
- Optical flow: OpenCV pyramidal Lucas-Kanade with forward/backward consistency check.
- Optional fusion: OpenCV constant-velocity Kalman filter; bounded-displacement exponential micro smoothing.
- Image motion: OpenCV feature tracking and RANSAC partial affine estimation.
- This standalone experiment follows the parent repository license. Dependencies retain their respective licenses; see the parent THIRD_PARTY_NOTICES.md.
