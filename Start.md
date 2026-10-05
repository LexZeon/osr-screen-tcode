# Start 2.1.0 / 启动 2.1.0

## English

### Windows portable package

1. Download the complete **Windows.zip** asset from the [2.1.0 release](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.1.0).
2. Extract the entire folder. Double-click **Start.cmd** or **SR6-OSR6-Realtime-Screen-TCode.exe**; keep `_internal` next to it.
3. For the independent visual Lab, run **Pose-Preview-Lab/Start.cmd** in that same extracted package.

Python is included. The separate Start.cmd release attachment is a spare launcher for the extracted folder and cannot replace the Windows ZIP. See [portable instructions](tools/README-Portable.md).

### Source edition

Double-click the repository's **Start.cmd** with Python 3.10+ available. It calls Start-Source.cmd and uses the local `.venv` when present. Local development may reuse an already complete sibling source environment read-only. Otherwise, the existing launcher creates a `.venv` in this source folder and installs this folder's requirements; it never installs into the reused sibling environment. Keep the complete source tree, including `src` and `Pose-Preview-Lab`.

The source Lab uses **Pose-Preview-Lab/Start.cmd**. No launch script behavior changed in 2.1.0.

### First use and modification

Begin with **Log only**. Output Monitor is the initial page. Choose the analysis mode and screen region as before; select the region again after changing display topology. Hybrid v2 is the default, processing longest edge remains 640, and brief-loss estimation remains at most two seconds. Optional models remain disabled by default: in Hybrid v2/Full-Half Travel, open Analysis Preview **+ Models**, download/select a supported model, then enable it. ViTTrack can use CPU; NeuFlow requires NVIDIA CUDA. No model or optional GPU runtime is bundled.

[FEATURES](docs/FEATURES.md) explains every feature and its effect. [ARCHITECTURE](docs/ARCHITECTURE.md) identifies the module to edit; [AI_Prompting_Guide](AI_Prompting_Guide.md) is the short handoff. Find a method without loading the program with `python tools/code_index.py _save_config` or `python tools/code_index.py realtime`. Use `python tests/run_tests.py -v` for isolated main tests. Historical startup details remain in [the unchanged 2.0.2 snapshot](docs/history/Start_2.0.2.md).

Real hardware and robot-arm mapping remain unverified. The simulator is a final-command display, not hardware feedback.

## 中文

### Windows 便携运行包

1. 在 [2.1.0 发布页](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.1.0) 下载完整 **Windows.zip**。
2. 全部解压后双击 **Start.cmd** 或 **SR6-OSR6-Realtime-Screen-TCode.exe**，保留旁边的 `_internal`。
3. 独立视觉 Lab：运行同一解压包内 **Pose-Preview-Lab/Start.cmd**。

运行包自带 Python。发布页单独的 Start.cmd 是完整解压目录的备用启动器，不能代替 Windows ZIP；另见[便携版说明](tools/README-Portable.md)。

### 源码版

准备 Python 3.10+，双击仓库根目录 **Start.cmd**，它调用 Start-Source.cmd。优先使用本目录已有 `.venv`；本地开发可只读复用已满足依赖的同级正式源码环境。否则，原启动器在当前源码目录新建 `.venv` 并安装当前目录要求，不向只读复用的同级环境安装依赖。保留 `src`、`Pose-Preview-Lab` 等完整源码。

源码独立 Lab 入口为 **Pose-Preview-Lab/Start.cmd**；2.1.0 未改变任何启动脚本行为。

### 初次使用与修改

先用 **Log only**，默认打开输出监视。照常选择分析方式与屏幕区域；改变显示器布局后重新框选。默认混合 v2、处理最长边 640、缺测估算最多两秒。可选模型仍默认关闭：选择混合 v2／全半行程，打开分析预览 **+ 模型**，下载／选择受支持文件后再勾选。ViTTrack 可用 CPU，NeuFlow 要求 NVIDIA CUDA，模型和可选 GPU 库不随包分发。

[FEATURES](docs/FEATURES.md)解释每项功能及影响；[ARCHITECTURE](docs/ARCHITECTURE.md)说明修改入口，[AI_Prompting_Guide](AI_Prompting_Guide.md)提供精简接手说明。用 `python tools/code_index.py _save_config` 或 `python tools/code_index.py realtime` 查询方法，无需启动软件。主程序隔离测试入口为 `python tests/run_tests.py -v`；历史详细启动说明保留在[原样保存的 2.0.2 快照](docs/history/Start_2.0.2.md)。

真实硬件与机械臂映射仍未验证；模拟器显示最终指令，不是硬件反馈。
