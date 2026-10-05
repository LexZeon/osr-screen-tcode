# SR6/OSR6 Realtime Screen TCode v2.1.0

## English

**The same application, organized by responsibility.** Version 2.1.0 splits the large application and legacy analyzer into explicit modules so human maintainers and AI assistants can locate a feature and read a smaller file. It retains the existing UI, setting keys/defaults/save/reset, capture, analysis, model choices, output calculation and two-second estimate policy of 2.0.2. There are no new runtime features or accuracy claims.

- The public `app.py` entry shrinks from 5,643 to about 360 lines; `application/` separates language, state, settings, model setup, input, realtime capture, devices, presets, output and monitoring. Existing methods share the same application state.
- The public `analyzer.py` entry shrinks from 2,778 to about 300 lines; `analysis/` separates legacy flow, pose motion, RTM runtime/geometry and preview. Original method signatures and calculations are retained.
- **FEATURES.md** explains every current feature, its input/output effect, defaults, limits and modification entry. **ARCHITECTURE.md** maps responsibilities and workflows. Both are separate release attachments and included in both application ZIPs.
- The current AI/startup guides are shorter; their previous versions and README are preserved byte-for-byte as historical snapshots. `tools/code_index.py` reads source AST without loading Tk, models or personal settings, and finds modules/methods by name.

ViTTrack and NeuFlow v2 remain **off by default**. Existing download links and pinned files are retained. NeuFlow requires NVIDIA CUDA; RTM's existing DirectML option remains. Models and optional GPU libraries are excluded from the application ZIPs.

### Download and run

Download the complete **Windows.zip**, extract the folder and double-click **Start.cmd** or the exe; keep `_internal` beside it. The separate Start.cmd is a spare launcher for that folder, not a complete application. The matching **Source.zip** needs Python 3.10+. The independent Lab remains **0.2.2-test**, without device output.

Begin with **Log only**. Recorded scripts and final device TCode have different downstream processing, explained in FEATURES; the simulator continues to display final commands. Physical hardware, depth, semantic contact and robot joint mapping remain unverified.

**Validation:** 502 main tests and 38 Lab tests passed, along with final-command simulator checks, bilingual source/new EXE launches and independent Lab starts. All 200 original application methods and 98 analyzer methods were checked for structural equivalence; bilingual controls/settings snapshots and 224 analyzer frames matched the baseline. Actual RTM CPU, ViTTrack CPU and NeuFlow CUDA checks passed. Settings stayed unchanged. See [the validation record](https://github.com/LexZeon/osr-screen-tcode/blob/v2.1.0/docs/Validation_2.1.0.md) for methods, development-check corrections and finite-test limits. Final ZIP evidence is added to this release after assembly.

## 中文

**按功能职责整理同一个程序。** 2.1.0 拆分大型主界面与旧分析器，便于人工维护者和 AI 按功能定位、少读无关代码。沿用 2.0.2 界面、设置键／默认／保存／重置、采集、分析、模型选项、输出计算及最多两秒估算；不增加运行功能，不宣称提高识别效果。

- 公开 `app.py` 入口由 5,643 行缩为约 360 行；`application/` 分开语言、状态、设置、模型、输入、实时采集、设备、预设、输出及监视，原方法继续共用相同程序状态。
- 公开 `analyzer.py` 由 2,778 行缩为约 300 行；`analysis/` 分开旧光流、姿态运动、RTM 运行／几何与预览，保留原签名和计算。
- **FEATURES.md** 解释每项现有功能、影响范围、默认、限制和修改入口；**ARCHITECTURE.md** 给出职责地图及运行流程。两份说明作为独立附件，也包含在源码和 Windows ZIP 中。
- 精简当前 AI／启动指南，前版及 README 逐字保留为历史快照；`tools/code_index.py` 只解析源码 AST，按模块／方法名查询，不加载 Tk、模型或个人设置。

ViTTrack、NeuFlow v2 仍**默认关闭**，原下载地址和校验文件保留。NeuFlow 要求 NVIDIA CUDA，RTM 原有 DirectML 保留；模型和可选 GPU 库不放入应用 ZIP。

### 下载和运行

下载完整 **Windows.zip**，全部解压后双击 **Start.cmd** 或 exe，保留旁边 `_internal`。单独的 Start.cmd 是完整目录的备用启动器，不能代替运行包；配套 **Source.zip** 需要 Python 3.10+。独立 Lab 仍为 **0.2.2-test**，不参与设备输出。

先使用 **Log only**。脚本与最终设备 TCode 的后续处理不同，详见 FEATURES；模拟器仍显示最终指令。真实硬件、深度、语义接触和机械臂关节映射仍未验证。

**验证：** 主程序 502 项、Lab 38 项，以及模拟器最终指令、中英文源码／新 exe 和独立预览启动通过。200 个原界面方法、98 个原分析器方法核对结构等价，中英文控件／设置快照及 224 帧分析结果与基线一致。实际 RTM CPU、ViTTrack CPU、NeuFlow CUDA 检查通过，个人设置未变。方式、开发检查修正及有限测试边界见[验证记录](https://github.com/LexZeon/osr-screen-tcode/blob/v2.1.0/docs/Validation_2.1.0.md)；最终 ZIP 证据在组装后追加于本次 Release。
