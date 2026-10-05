# SR6/OSR6 Realtime Screen TCode v2.0.2

## English

**Optional models for Hybrid v2, off by default.** ViTTrack subject tracking and NeuFlow v2 optical-flow assistance can be enabled separately or together in Hybrid v2 and Full/Half Travel. The analysis preview, advanced sidebar and start-confirmation dialog share saved settings; restoring defaults turns both off. Existing Hybrid 1 and direct Pose paths retain their behavior.

- **ViTTrack:** CPU-capable subject-region tracking, initialized from a subject accepted by ordinary analysis. Its box only helps nominate real pixel tracks; the box center is never directly turned into L0.
- **NeuFlow v2:** ordinary sparse/DIS motion is tried first, with neural flow requested adaptively when evidence is insufficient. Forward/backward and image checks still validate correspondences, and camera motion is checked independently. **Requires enabled NVIDIA CUDA.** This exported model failed actual DirectML loading, so DirectML is explicitly unsupported for NeuFlow; RTM Pose can still use DirectML. Unsupported/missing/failed models retain the original analysis route.
- **Model controls:** explicit Download / Select model / Cancel download, with pinned size and SHA-256 validation. Model toggles never install a runtime automatically. GPU settings are accessible without enabling RTM rotation assistance. Changing active model options stops the current analysis and applies the new settings on restart.
- **Preview layout:** model setup starts collapsed behind **+ Models**. The expanded area has bounded height and both scroll directions, keeping its controls reachable in narrow/high-DPI previews without shrinking fonts.

These are experimental options, not a promise of better results on every video. Max processing edge remains 640. Final travel gains, axis limits, speed handling and simulator output still use the final command chain. Brief-loss estimation remains limited to **two seconds**. Models do not verify physical depth, contact or robot-arm compatibility.

### Download and run

Download **Windows.zip**, extract the complete folder and double-click **Start.cmd** or the exe. No separate Python is required; keep `_internal` beside the exe. The separately attached Start.cmd is a spare launcher for that extracted folder. **Source.zip** contains matching source and needs Python 3.10+.

Model files and optional GPU libraries are **not included in either ZIP**. Use the application's Download button; the separately supplied NeuFlow ONNX artifact is an optional model download. Existing locally downloaded supported files can be reused. Start with **Log only** and compare the same clip with each option before combining them. Standalone Lab remains **0.2.2-test** and has no device output.

**Validation:** 502 isolated main tests and 38 Lab tests passed, along with the simulator final-command check. Actual source Start.cmd and rebuilt exe passed English/Chinese Log only and Lab startup. The rebuilt exe executed real ViTTrack CPU tracking and NeuFlow CUDA bidirectional flow successfully. High-DPI model controls were checked at 200%/300%. Development failures, fixes and limits are retained in [the validation record](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.2/docs/Validation_2.0.2.md). Final extracted-package and hosted-download evidence accompanies this release and the local archive.

Models derive from [OpenCV ViTTrack](https://huggingface.co/opencv/object_tracking_vittrack) and [NeuFlow v2](https://huggingface.co/Study-is-happy/neuflow-v2), under Apache-2.0. Exact provenance and export instructions are retained in the repository's third-party notices, model registry and export helper. Old releases/assets remain intact; personal settings, logs and caches are excluded from packages. Physical hardware and robot-arm mapping remain unverified.

## 中文

**为混合 v2 增加默认关闭的可选模型。** ViTTrack 主体跟踪与 NeuFlow v2 光流辅助可分别开启，也可同时使用，适用于混合 v2 和全／半行程。分析预览、侧栏高级设置与启动确认框同步保存选项，恢复默认会关闭两项。混合 v1 与直接 Pose 保留原有路径。

- **ViTTrack：** 可用 CPU，在原分析确认主体后辅助保持主体区域。框只用于选择真实匹配点，框中心不会直接成为 L0 位移。
- **NeuFlow v2：** 先使用原稀疏／DIS 光流，证据不足时再自适应调用神经光流；仍需正反向和图像验证，运镜另行验证。**需启用 NVIDIA CUDA。** 本次导出的模型在 DirectML 实际加载失败，因此明确不支持 NeuFlow 的 DirectML 路径；RTM Pose 原有 DirectML 保留。模型缺失、失败或运行条件不满足时使用原分析。
- **模型控件：** 提供下载、选择、取消下载，按固定大小和 SHA-256 校验文件。勾选模型不会自动安装运行库；不开启 RTM 旋转辅助也能打开 GPU 设置。更改正在使用的模型选项会停止分析，重新开始后生效。
- **预览布局：** 模型设置默认收起，点 **+ 模型** 展开。展开区域限制高度并支持上下／横向滚动，窄窗口和高 DPI 下不缩小字号，仍可操作控件。

这些是实验选项，不能保证每段视频都更好。处理最长边仍默认 640；最终行程倍率、上下限、速度处理与模拟器继续使用最终输出链路。短暂缺测估算仍最多 **两秒**；模型不能验证真实深度、接触或机械臂兼容性。

### 下载和运行

下载 **Windows.zip**，完整解压后双击 **Start.cmd** 或 exe，无需另装 Python，保留 exe 旁的 `_internal`。单独提供的 Start.cmd 是完整解压目录的备用启动器。**Source.zip** 为配套源码，需要 Python 3.10+。

两个 ZIP **均不包含模型和可选 GPU 库**。通过软件内“下载”准备模型，另行提供的 NeuFlow ONNX 附件仅为可选模型文件；已下载的受支持文件可以复用。先用 Log only，对同一片段分别比较效果，再决定是否一起开启。独立 Lab 仍为 **0.2.2-test**，不参与设备输出。

**验证：** 隔离主程序 502 项、Lab 38 项及模拟器最终指令检查通过。实际源码 Start.cmd 和新 exe 的中英文 Log only、独立预览启动通过；新 exe 已实际执行 ViTTrack CPU 跟踪和 NeuFlow CUDA 正反向光流。模型控件检查覆盖 200%／300% 缩放。开发失败、修正和限制保留在[验证记录](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.2/docs/Validation_2.0.2.md)；最终解压包和线上下载证据附于本发布及本地归档。

模型来源为 [OpenCV ViTTrack](https://huggingface.co/opencv/object_tracking_vittrack) 和 [NeuFlow v2](https://huggingface.co/Study-is-happy/neuflow-v2)，使用 Apache-2.0 许可，具体来源与导出方法保留在第三方声明、模型登记表和导出工具中。旧版附件保留，个人设置、日志、缓存不随包分发。真实硬件和机械臂映射仍未验证。
