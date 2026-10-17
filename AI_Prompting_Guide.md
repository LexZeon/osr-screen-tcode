# Developer / AI handoff — 2.1.1

## English

This is the current, short handoff. The full previous guide is retained in [docs/history/AI_Prompting_Guide_2.0.2.md](docs/history/AI_Prompting_Guide_2.0.2.md), including the October 11 contact-email refresh. Historical requirements are evidence, not unfinished tasks. Verify current Git/source/release state before claiming publication.

### Read only what the task needs

1. Check branch/status, `src/osr_screen_tcode/__init__.py`, and the user's latest scope.
2. Use [ARCHITECTURE](docs/ARCHITECTURE.md) to select a responsibility and [FEATURES](docs/FEATURES.md) for behavior/defaults.
3. `python tools/code_index.py <module-or-method>` reads AST only. Examples: `realtime`, `_save_config`, `_new_output`, `model_options`. `--json` supports focused tooling. Open the named module and its relevant tests, rather than all historical guides or every source file.
4. Read [Validation_2.1.1](docs/Validation_2.1.1.md) for the model-setup/modal fix; [Validation_2.1.0](docs/Validation_2.1.0.md) preserves the earlier structural equivalence checks.

### Structure and behavior boundaries

- `app.py` retains public `OsrScreenApp`, Tk initialization, queue dispatch, close and CLI. `application/` contains normal explicit mixins, one responsibility per file, all sharing the existing `self` state and no new initializer. Three small facade factories keep established analyzer/capture/region-selector injection points working.
- `analyzer.py` retains public `RealtimeAnalyzer` and lifecycle/process entry. `analysis/` owns the original flow, pose motion, RTM runtime/geometry and preview methods. Their six explicit local facade imports preserve existing static class-helper resolution.
- Capture geometry, visual pipeline, model validation, final TCode, sinks and recording keep their independent modules. Models are observational evidence; diagnostic boxes/prediction are not measured motion. Script files and final device commands have different downstream processing: see FEATURES.
- 2.1.0 is a structural release. UI text/layout, setting keys/defaults/save/reset, method arguments, event ordering, mathematics, model pins and the two-second estimate limit are retained. Keep DPI/GPU activation before importing Tk/cv2 and keep the RTM model-root calculation on the public app module's `__file__`.
- Hybrid v2 remains default with a 640 longest edge. ViTTrack/NeuFlow are separate default-off switches, only v2-based modes; NeuFlow requires explicitly enabled NVIDIA CUDA. RTM DirectML remains available. Neither model nor optional runtime belongs in Git or an application ZIP.
- 2.1.1 adds root-owned coalesced refresh, `application/model_checks.py` background checks and guarded modal navigation. Workers receive plain snapshots/cancel events; Tk alone applies a current token/path/owner result. Keep the original default-off switches, pins and output mathematics. CUDA shortcut opens shared setup without automatic installation; the shared backend choice is immediate while start-dialog enabled/model values are staged. The user's exact intermittent checkbox freeze remains unconfirmed; do not claim a precise reproduction.

### Working and verification rules

Preserve user settings and unrelated changes; do not reset or restore an old fingerprint. Use only Log only diagnostics, isolate config before importing GUI/runtime modules, and close windows inside the protection scope. Respect the user's chosen display for visual tests. Reuse the formal Python read-only; do not install/upgrade into it.

Run `python tests/run_tests.py -v` for the isolated main suite, the Lab tests for affected Lab changes, and `node tests/test_simulator_stream.cjs` for final-command behavior. Check source launch, rebuilt exe and a freshly extracted portable package when releasing. Validate real inference separately from provider listings. Report failed attempts and residual limits honestly; no claim of verified depth/contact/robot joint mapping/IK/collision/feedback.

The completed baseline is **2.1.0**; this fix is **2.1.1**. The user keeps testing the old app: do not stop it, replace its files, reset its settings or install into its runtime. Prefer ASUS for isolated new-version tests. Concurrent old-app settings changes must be preserved and distinguished from this process's writes. Ongoing authorization covers verified matching source/Windows releases; keep feature explanations, English-first notes and immutable paired archives. Exclude models, optional GPU libraries, config, logs, caches, secrets and local user paths from public artifacts.

## 中文

本文件是当前精简接手说明。完整前版指南保留在 [docs/history/AI_Prompting_Guide_2.0.2.md](docs/history/AI_Prompting_Guide_2.0.2.md)，沿用 10 月 11 日的联系邮箱更新；历史要求是证据，不代表尚未完成的任务。声称发布前先核对 Git、源码及实际 Release 状态。

### 定向阅读

1. 核对分支、状态、`src/osr_screen_tcode/__init__.py` 和用户最新范围。
2. 用 [ARCHITECTURE](docs/ARCHITECTURE.md)选职责模块，用 [FEATURES](docs/FEATURES.md)查功能、默认及影响范围。
3. `python tools/code_index.py <模块或方法>` 只读 AST；可查 `realtime`、`_save_config`、`_new_output`、`model_options`，支持 `--json`。只打开命中的模块及相关测试，避免每次阅读全部历史或全项目。
4. 本轮模型配置／确认窗口修复读 [Validation_2.1.1](docs/Validation_2.1.1.md)；前轮模块化对照证据保留于 [Validation_2.1.0](docs/Validation_2.1.0.md)。

### 结构及行为边界

- `app.py` 保留公开 `OsrScreenApp`、Tk 初始化、队列调度、关闭与 CLI；`application/` 用普通显式 mixin 分职责，沿用原 `self` 状态，不增加初始化。三个小工厂保留原分析器、采集与框选依赖接入点。
- `analyzer.py` 保留公开 `RealtimeAnalyzer`、生命周期及 process；`analysis/` 搬迁原光流、姿态运动、RTM 运行／几何及预览方法，六处显式局部导入保留公开类静态 helper 的解析。
- 采集几何、视觉管线、模型校验、最终 TCode、设备 sink 与录制保持独立模块。模型提供观测证据，诊断框和估计不是实测运动；脚本与设备最终指令的后续处理不同，详见 FEATURES。
- 2.1.0 只整理结构，保留 UI 文案／布局、设置键／默认／保存／重置、参数、事件顺序、数学、模型校验值及最多两秒估算。DPI／GPU 激活仍先于 Tk／cv2 导入；RTM 模型根路径仍以公开 app 的 `__file__` 计算。
- 默认混合 v2、最长边 640；ViTTrack／NeuFlow 独立且默认关闭，仅用于 v2 管线；NeuFlow 明确要求 NVIDIA CUDA，RTM DirectML 保留。模型和可选运行库不进入 Git 或应用 ZIP。
- 2.1.1 增加根窗口统一持有的空闲合并刷新、`application/model_checks.py` 后台检查与模态输入保护；线程只接收普通快照／取消事件，由 Tk 按当前 token／路径／所属窗口应用结果。保留默认关闭、模型校验值及输出数学。CUDA 快捷入口打开共享配置，不自动安装；共享后端立即修改，而开始窗口启用状态／模型值仍暂存。原用户间歇性勾选卡死未精确复现，不可声称已定位同一现场原因。

### 工作与验证

保留用户设置和无关改动，不恢复旧指纹。使用 Log only，在导入界面／运行时前隔离配置，并在保护范围内关闭窗口；视觉测试尊重用户指定显示器。正式 Python 只读复用，不安装或升级依赖。

完整主程序用 `python tests/run_tests.py -v` 隔离入口；涉及 Lab 时运行其测试，最终指令用 `node tests/test_simulator_stream.cjs`。发布需源码启动、新 exe 及新解压运行包检查；真实推理与仅列出后端区别验证。如实记录失败和局限，不宣称真实深度、接触、关节映射、IK、碰撞或反馈已验证。

已完成基线 **2.1.0**，本次修复为 **2.1.1**。用户正在继续测试旧版：不停止它、不替换其文件、不重置其设置、不安装到它的运行库；新版隔离测试优先 ASUS。旧窗口并行保存的设置保留，并与测试进程自身写入区分。持续授权涵盖完成验证后的源码／Windows 配套发布；保留功能解释、英文先中文后的文案及不可覆盖的配对归档。公开物料排除模型、可选 GPU 库、配置、日志、缓存、秘密和本机用户路径。
