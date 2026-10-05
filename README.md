# SR6/OSR6 Realtime Screen TCode

## English

**2.1.0 organizes the existing application into readable modules.** It changes source structure and documentation, with the same UI, defaults, capture, analysis, model choices, output arithmetic and two-second estimation policy as 2.0.2. `app.py` and `analyzer.py` remain the public entry points. This version does not claim an analysis-quality improvement.

Download the complete **Windows.zip** from the [2.1.0 release](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.1.0), extract it and double-click **Start.cmd** or the exe. Keep `_internal` beside the executable; Python is bundled. The matching **Source.zip** needs Python 3.10+ and the root [Start.cmd](Start.cmd). [Start.md](Start.md) explains both editions.

- [Every user feature explained](docs/FEATURES.md): inputs, analysis modes, options, output, devices, recording and previews.
- [Code architecture and modification map](docs/ARCHITECTURE.md): find the responsibility before opening a large file.
- [Short AI/developer handoff](AI_Prompting_Guide.md): constraints, focused reading and validation.
- [2.1.0 validation](docs/Validation_2.1.0.md) and [release notes](docs/Release_2.1.0.md).
- [Contributing](CONTRIBUTING.md), [license](LICENSE), [third-party notices](THIRD_PARTY_NOTICES.md) and [open-source notice](OPEN_SOURCE_NOTICE.md).

Hybrid v2 remains the default analysis; Full/Half Travel is listed first, followed by RTM Pose 2D. ViTTrack and NeuFlow v2 remain optional and **off by default**, with software downloads. ViTTrack can use CPU; NeuFlow requires NVIDIA CUDA and does not support DirectML. RTM's existing DirectML option remains. Models and optional GPU runtimes are not in either application ZIP.

**Output Monitor** remains the first tab. **Show Preview** opens the simulator, which receives final TCode commands. **Analysis Preview** shows image evidence and overlays; the independent **Pose-Preview-Lab** remains 0.2.2-test without device output. Use **Log only** for initial checks. Real depth, semantic contact, robot joint mapping, inverse kinematics, collision detection and feedback remain unverified.

Historical release documentation, acknowledgements and validation are retained. The previous [README](docs/history/README_2.0.2.md), [startup guide](docs/history/Start_2.0.2.md) and [AI guide](docs/history/AI_Prompting_Guide_2.0.2.md) are unchanged historical snapshots; their original relative links refer to the repository root. Earlier tags and release assets remain available.

Thanks to **DK**, **机械纪元**, and **“电话机”** for guidance, volunteer testing and suggestions. Contact: **aivnailedeng@gmail.com**.

## 中文

**2.1.0 将现有程序整理为便于阅读的模块。** 本版只调整源码结构与文档，界面、默认值、采集、分析、模型选项、输出计算和最多两秒估算规则沿用 2.0.2。`app.py`、`analyzer.py` 继续作为公开入口；本版不宣称提高识别效果。

在 [2.1.0 发布页](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.1.0) 下载完整 **Windows.zip**，全部解压后双击 **Start.cmd** 或 exe。保留旁边的 `_internal`，运行包自带 Python。配套 **Source.zip** 使用 Python 3.10+ 和根目录 [Start.cmd](Start.cmd)，两种启动方式见 [Start.md](Start.md)。

- [逐项功能说明](docs/FEATURES.md)：输入、分析模式、选项、输出、设备、录制与预览。
- [程序结构与修改入口](docs/ARCHITECTURE.md)：先按职责找模块，再阅读需要修改的代码。
- [精简 AI／开发者接手说明](AI_Prompting_Guide.md)：约束、定向阅读及验证方法。
- [2.1.0 验证记录](docs/Validation_2.1.0.md)和[发布说明](docs/Release_2.1.0.md)。
- [贡献说明](CONTRIBUTING.md)、[许可证](LICENSE)、[第三方声明](THIRD_PARTY_NOTICES.md)及[开源说明](OPEN_SOURCE_NOTICE.md)。

默认分析仍为混合 v2；全／半行程排列第一，RTM Pose 2D 随后。ViTTrack、NeuFlow v2 仍为软件内下载的可选模型，**默认关闭**；ViTTrack 可用 CPU，NeuFlow 要求 NVIDIA CUDA、不支持 DirectML，RTM 原有 DirectML 保留。模型和可下载 GPU 运行库均不放入源码／Windows ZIP。

启动默认显示**输出监视**；**显示预览**打开接收最终 TCode 的模拟器；**分析预览**显示图像观测与标注。独立 **Pose-Preview-Lab** 仍为 0.2.2-test，不参与设备输出。首次检查用 **Log only**；真实深度、语义接触、机械臂关节映射、逆运动学、碰撞检测及反馈仍未验证。

历史说明、署名与验证记录保留。前版 [README](docs/history/README_2.0.2.md)、[启动指南](docs/history/Start_2.0.2.md)、[AI 指南](docs/history/AI_Prompting_Guide_2.0.2.md)逐字保留为历史快照，原相对链接仍以仓库根目录为基准；旧标签和发布附件不覆盖。

感谢 **DK**、**机械纪元**和**“电话机”**提供建议、志愿测试与协助。联系：**aivnailedeng@gmail.com**。
