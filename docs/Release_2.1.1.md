# SR6/OSR6 Realtime Screen TCode v2.1.1

## English

**Responsive optional-model setup and a more robust start confirmation.** ViTTrack/NeuFlow controls coalesce status redraws outside checkbox traces. Model discovery and manual-file verification run in cancellable background workers; closing/resetting/changing a choice discards obsolete results. Start settings remain scrollable in both directions, with action buttons in a protected footer and input ownership respected for child dialogs.

- **Detect models:** checks a selected supported file or the known download location without enabling a model or downloading anything.
- **Enable CUDA:** selects shared CUDA acceleration and opens existing GPU setup; explicitly use the one-click installer if missing, then restart when prompted. This does not install automatically or enable either model switch. NeuFlow requires NVIDIA CUDA; RTM DirectML remains available. A runtime self-check is distinct from actual NeuFlow-model validation.
- Existing analysis/output calculations, default-off models, model pins, 640 processing default and two-second estimate limit are retained. Independent Lab remains 0.2.2-test. Feature and architecture guides are included in both ZIPs and provided as separate attachments.

The reported intermittent complete freeze after checking the models was **not precisely reproduced**. Known synchronous file-check and modal/layout/lifecycle risks were addressed; retest the original operation. See [validation and development-check details](https://github.com/LexZeon/osr-screen-tcode/blob/v2.1.1/docs/Validation_2.1.1.md).

Download the complete **Windows.zip**, extract it and double-click **Start.cmd** or the exe. Keep `_internal` beside it; Python is bundled. The matching **Source.zip** uses Python 3.10+. The separate launcher is a spare for the extracted full folder. Begin with Log only; real hardware, depth/contact and robot mapping remain unverified. Models and optional GPU libraries are excluded from the application ZIPs; existing model downloads remain pinned to v2.0.2.

Verification: **524 main tests passed** across three isolated processes (227 GUI, 146/151 non-GUI), with exact ID coverage; **38 Lab tests** and the simulator final-command stream passed. Actual source Start.cmd and rebuilt EXE passed English/Chinese realtime Log-only starts and Lab smoke checks; external RTM Pose CPU, ViTTrack CPU and NeuFlow CUDA checks passed. Native ASUS double-toggle / CUDA child-dialog / Cancel checks passed; no dependencies were installed and no hardware was connected. Detailed failed development attempts and test boundaries remain in the validation record. Final ZIP/download checks are appended after assembly. Contact: **lexzeonstudio@gmail.com**.

## 中文

**改善可选模型配置响应，加固开始确认窗口。** ViTTrack／NeuFlow 状态绘制移出复选框变量回调并合并刷新；自动检测、手选校验在可取消后台进行，关闭／重置／更改选择后丢弃旧结果。确认窗口支持双向滚动，按钮保留在页脚，子窗口持有输入时不穿透父窗口操作。

- **自动检测模型**：检查受支持的所选文件或固定下载位置，不自动启用或下载。
- **启用 CUDA**：选择共享 CUDA 并打开现有 GPU 设置；缺库时明确点击一键安装，按提示重启。不自动安装或勾选模型；NeuFlow 要求 NVIDIA CUDA，RTM DirectML 保留。运行库自检不等于 NeuFlow 模型实际通过。
- 原分析／输出计算、模型默认关闭及校验值、最长边 640 和两秒估算上限保留；独立 Lab 仍为 0.2.2-test。两份 ZIP 包含功能／结构指南，发布页另附独立文档。

原“勾选后整个软件卡住”的间歇性现场**尚未精确复现**。本版处理明确的同步文件检查和模态／布局／生命周期风险，仍需复测原操作；[验证记录](https://github.com/LexZeon/osr-screen-tcode/blob/v2.1.1/docs/Validation_2.1.1.md)保留开发过程和限制。

下载完整 **Windows.zip**，全部解压后双击 **Start.cmd** 或 exe，保留 `_internal`；运行包自带 Python。配套 **Source.zip** 需要 Python 3.10+；单独启动器只能配合完整运行目录。先用 Log only；真实硬件、深度／接触、机械臂映射仍未验证。应用 ZIP 不包含模型／可选 GPU 库，模型下载继续引用 v2.0.2。

验证：**主程序 524 项通过**，三个隔离进程覆盖全部唯一 ID（界面 227，非界面 146／151）；**Lab 38 项**和模拟器最终命令流通过。实际源码 Start.cmd／新 exe 中英文实时 Log only、Lab 烟测，以及外部 RTM Pose CPU、ViTTrack CPU、NeuFlow CUDA 均通过。华硕副屏原生双勾选／CUDA 子窗口／取消检查通过；未安装依赖、未连接硬件。验证记录保留开发失败及检查边界，最终 ZIP／下载检查在组装后追加。联系：**lexzeonstudio@gmail.com**。
