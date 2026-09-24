# 2.0.0-test.4

## 中文

本次仅为本地源码测试。双击项目根目录 **Start.cmd**；不要打开 release 中的旧 test.3 exe。没有生成新的发布文件夹或 ZIP，也没有改动 GitHub 上已发布的 test.3。

### 采集与预览

- 分析方式下方的“采集帧率 FPS”范围为 1-120，默认 45。主界面滑块在实时输出中也生效；开始弹窗的值在确认时应用，取消不更改设置。
- 保留 MSS 和原有区域/DPI 坐标逻辑，独立线程高频截图，仅保留最新帧。分析来不及时丢弃旧帧，不等待旧队列。有限内存占用，不录下整个屏幕历史。
- “采集 FPS”是截图速率，可能包含视频重复帧；“分析 FPS”是处理循环速率，不是模型检测速率。输入帧龄表示从开始截图到进入分析的时间，不包含后续推理、绘制、传输和设备动作。
- 预览发送上限从约 12.5 提高到最多 60 FPS，实际取决于处理耗时。相同一批只绘制最新预览，避免回放积压帧。
- 此滑块主要控制屏幕模式。60 FPS 视频不会凭空产生 120 个不同画面；RTM 模型慢时仍受推理性能限制。GPU/CPU、分辨率和运镜都会影响实际效果。

### 幅度与曲线

- 仅 RTM Pose 2D/3D 的六轴模式：L1/L2 相对中位的偏移乘以 `1 + 4 * L0`。这里的 L0 是分析阶段的 0-1 高度，位于后续行程倍率和反转之前；0/0.5/1 对应 1/3/5 倍。R1/R2 相对中位的偏移乘以 2。中位不移动，结果限制在 0-1。
- 幅度映射不改变 L0/R0、L0 Only 或基础分析；仍沿用之后的行程倍率、反转与设备上下限/限速/端点保护。放大后更容易触及上限，建议从较窄行程开始测试。
- “输出曲线拟合”默认开启，覆盖所有实时分析模式及视频脚本导出。基于 One Euro 自适应低通：慢动作减少抖动，快动作降低滤波滞后，不缓存未来帧。它不会修改模型骨架或基础分析算法。
- 这不是无延迟的完美曲线重建。滤波有少量滞后，无法修复持续误识别；可取消勾选对比。实时预览、设备输出与录制共用滤波后的分析值，设备仍经过安全映射。手动回中、测试动作和急停不经过新拟合层。
- FPS 与拟合开关本地保存；恢复默认时 FPS 为 45、拟合开启。不更改原有平滑、L0 防抖或压缩延迟设置。

建议先用 **Log only**，分别比较 45、60、120 FPS 和拟合开关，再接硬件低强度测试。不要把截图 FPS 当作视频或模型本身的帧率。

## English

Local source test only: double-click **Start.cmd** in the repository root, not the older test.3 exe under release. No new portable archive or GitHub publication is created.

Capture FPS below the analysis selector ranges from 1 to 120 (default 45), updates live from the main panel, and is saved locally. Start-dialog changes apply only after confirmation. A dedicated MSS thread owns capture resources and one replaceable latest frame; slow analysis does not build a queue. Existing region/DPI logic is retained. Preview delivery now allows up to 60 FPS rather than about 12.5, with actual performance depending on processing time.

Capture FPS counts screenshots, including possible duplicate video frames. Analysis FPS is the processing loop, not RTM inference frequency. Input age includes screenshot time and waiting before analysis, but not downstream analysis, rendering, transport or hardware latency. This is not a video frame interpolation feature.

In RTM Pose 2D/3D Six Axis only, centered L1/L2 displacement is multiplied by `1 + 4 * L0` (1x/3x/5x at analysis L0 0/0.5/1, before travel controls/inversion). R1/R2 centered displacement doubles. Values stay within 0-1; L0/R0, L0 Only and base analysis are unchanged by this amplitude mapping. Subsequent travel scales, inversion, limits, speed and endpoint protection remain active. Larger gains can saturate earlier.

**Output Curve Smoothing** is on by default for every realtime analysis mode and video script export. A causal One Euro adaptive filter reduces slow-motion jitter while reducing lag at higher speeds. It has no future-frame buffer, adds some lag, and cannot fix incorrect tracking or guarantee jitter-free hardware motion. Disable it for comparison. Manual centering, device tests and emergency stop bypass this layer. Settings persist; Restore Defaults enables it and restores 45 FPS.

Algorithm reference: [Casiez, Roussel and Vogel, CHI 2012](https://gery.casiez.net/publications/CHI2012-casiez.pdf).
