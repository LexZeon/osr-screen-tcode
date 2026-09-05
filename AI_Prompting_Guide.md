# AI Prompting Guide

## Active 2.0 Test Work

- Current test: `2.0.0-test.3`; formal release remains `1.1.2`.
- Read `docs/Device_Compatibility_2.0.md` before changing device support.
- `device_backends.py` implements capability-based Intiface output; `device_controls.py` owns the new device-selection UI.
- Preserve the original analysis files and TCode mapper. Keep device I/O asynchronous and test stopping, stale output and reconnect identity.
- Test settings are isolated in `.osr_screen_tcode_2_0_test`. Do not package tests or include models.
- Display the device name as `SR6/OSR6`. Cooperation/copyright contact: `aivnailedeng@gmail.com`.
- 新增适配尚未经真机验证，Autoblow 当前未开放输出，不应写成已支持全部品牌型号。
- Custom mode is second in the device list. Bind only actual Intiface functions on one device; default unbound. Retain duplicate rejection, identity validation and timing-gap tests.
- Measurement/axis limits default open on first use and reset; preserve a later saved collapse choice.
- `gpu_runtime.py` / `gpu_downloads.py` / `gpu_controls.py` own optional CUDA/DirectML installation for source and portable builds. Frozen builds run bundled pip and GPU probes in hidden child processes via `__main__.py`. Publish only a separately verified runtime overlay in the test user directory, never numpy/OpenCV. Report real downloaded bytes and installation stages. Restart after installation/backend switching; never modify the formal runtime. `directml_pose.py` only adapts the inference session, preserving rtmlib's pose algorithms. Never package downloadable models or optional GPU runtimes.
- Use `ui_widgets.WideCombobox` for new dropdowns so complete option text remains accessible independently of sidebar width. GPU backend choice is a shared, saved preference in both model settings and the start dialog.
- Display the full name including `High Hardware Compatibility`. Keep Python/CLI and repository identifiers compatible. Future package filenames replace `/` with `-`; never use literal asterisks.

Use this guide when asking an AI coding assistant to continue work on **SR6/OSR6 Realtime Screen TCode High Hardware Compatibility**. It gives the assistant enough project context to make small, careful changes without damaging stable behavior.

## Project Context

- Project name: SR6/OSR6 Realtime Screen TCode High Hardware Compatibility.
- Platform: Windows desktop app.
- Current formal version: v1.1.2.
- Main purpose: read a selected screen region in realtime, analyze visible motion with low latency, and output TCode to OSR/SR6/OSR6-compatible devices through USB serial or BLE.
- Important stable feature: L0 output is the most important stable path. Do not rewrite the formal L0 core unless explicitly requested.
- Experimental area: RTM Pose 2D/3D dance analysis, optical-flow assist, Kalman fusion, and six-axis motion quality.

## Good Starting Prompt

```text
You are the feature-development AI for this SR6/OSR6 Realtime Screen TCode High Hardware Compatibility project.
Do not rewrite the whole project. First read the existing source, then make the smallest safe change.
Keep L0 stable unless I explicitly ask to change it.
If UI text changes, update both English and Chinese.
If settings change, update save/load/default behavior.
For test versions, update source and Start.cmd behavior only; do not package unless I ask.
For formal releases, update changelog, README/manuals when needed, build the Windows portable folder and zip, and confirm the zip does not include .git, caches, local models, or private paths.
After finishing, tell me what changed, which files changed, how it was verified, risks, and what to do next.
```

## Files To Read First

- `README.md`: user-facing overview, download notes, and current feature summary.
- `CHANGELOG_CN.txt` and `docs/版本日志.txt`: version history.
- `src/osr_screen_tcode/app.py`: main UI, preview, user controls, realtime start flow.
- `src/osr_screen_tcode/analyzer.py`: screen analysis, pose/RTM position calculation, smoothing, axis output.
- `src/osr_screen_tcode/config.py`: settings defaults and persistence.
- `src/osr_screen_tcode/tcode.py`: TCode formatting and output path.
- `src/osr_screen_tcode/sinks.py`: USB serial and BLE connection handling.
- `src/osr_screen_tcode/pose_backends.py`: local RTM Pose model loading and inference helpers.

## Development Rules

- Keep changes scoped to the requested feature.
- Preserve existing UI style and ordinary-user workflow.
- Keep dangerous device motion protected by limits, speed caps, presets, and output clamping.
- Treat `Log only` as the safest preview/debug mode.
- Do not include local ONNX models in source releases or Git commits.
- Do not push to GitHub or rewrite Git history unless the user explicitly asks.
- Prefer readable, conservative changes over large refactors.

## UI And Settings Rules

- New controls should be visible, clearly named, and have short help text when useful.
- English and Chinese UI strings should stay synchronized.
- New settings need default values, save/load support, and restore-default behavior.
- Fold advanced or mode-specific settings when possible so the main UI stays approachable.
- RTM Pose model controls should appear only when an RTM Pose mode is selected.

## Test Version Rules

- Test versions are for quick iteration.
- Usually no portable zip is needed for test versions.
- Keep a one-click source launcher such as `Start.cmd`.
- Use test version names such as `1.1.1-test.29` until the user approves promotion.

## Formal Release Rules

For a formal release, prepare:

- Windows portable release folder with exe, `Start.cmd`, required dependencies, README, quick start, manuals, changelog, license, and acknowledgements.
- Windows zip named with the approved version, for example `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility-v2.0.0-Windows.zip` (future formal build).
- Source zip named with the approved version, for example `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility-v2.0.0-Source.zip` (future formal build).
- No `.git`, cache folders, local privacy paths, model files, `.onnx` files, or development build leftovers in the zips.
- Extract-and-run startup check for the Windows zip when packaging has changed.

## RTM Pose Notes

- RTM Pose 2D is recommended for lower-latency dance analysis.
- RTM Pose 3D can provide richer depth hints but is usually higher latency.
- GPU acceleration is optional and should default off unless explicitly changed.
- If GPU/CUDA is unavailable, the app should explain the fallback and continue on CPU when possible.
- Optical-flow assist and Kalman fusion are lightweight helpers for smoother keypoints, not replacements for model detection.

## Verification Checklist

- For code changes: run syntax/import checks that the project supports.
- For realtime/start-flow changes: start the app and confirm it does not exit immediately.
- For packaging changes: rebuild the affected zip, scan contents, extract to a temporary folder, and launch the exe.
- For README-only changes: text search is usually enough unless the user asks for packaging.

---

# AI 提示词指南

当你想让 AI 编程助手继续开发 **SR6/OSR6 Realtime Screen TCode High Hardware Compatibility** 时，可以把这份指南作为固定上下文。它能帮助 AI 在现有源码基础上做小而稳的修改，避免破坏已经稳定的功能。

## 项目背景

- 项目名称：SR6/OSR6 Realtime Screen TCode High Hardware Compatibility。
- 平台：Windows 桌面软件。
- 当前正式版本：v1.1.2。
- 核心用途：实时读取用户框选的屏幕区域，低延迟分析画面运动，并通过 USB 串口或 BLE 向 OSR/SR6/OSR6 兼容设备输出 TCode。
- 重要稳定功能：L0 输出是当前最重要、最稳定的路径。除非明确要求，不要重写正式版 L0 核心逻辑。
- 实验方向：RTM Pose 2D/3D 舞蹈分析、光流辅助、卡尔曼融合、六轴运动质量优化。

## 推荐起始提示词

```text
你是这个 SR6/OSR6 Realtime Screen TCode High Hardware Compatibility 项目里的功能开发专用 AI。
不要重写整个项目。先读现有源码，再做最小、安全的修改。
除非我明确要求，否则保持 L0 稳定。
如果修改 UI 文字，记得同步中文和英文。
如果修改设置项，记得同步保存、读取和恢复默认逻辑。
测试版只需要源码和 Start.cmd 能运行，除非我要求，否则不要打包。
正式版需要更新版本日志、README/手册，重新生成 Windows 免安装文件夹和 zip，并确认 zip 里没有 .git、缓存、本地模型和隐私路径。
完成后告诉我：改了什么、哪些文件变了、怎么验证、有什么风险、下次可以继续做什么。
```

## 开始前优先阅读的文件

- `README.md`：项目简介、下载说明、当前功能摘要。
- `CHANGELOG_CN.txt` 和 `docs/版本日志.txt`：版本记录。
- `src/osr_screen_tcode/app.py`：主界面、预览、用户控件、实时输出启动流程。
- `src/osr_screen_tcode/analyzer.py`：屏幕分析、pose/RTM 位置计算、平滑、各轴输出。
- `src/osr_screen_tcode/config.py`：设置默认值和本地保存。
- `src/osr_screen_tcode/tcode.py`：TCode 格式和输出路径。
- `src/osr_screen_tcode/sinks.py`：USB 串口和 BLE 连接。
- `src/osr_screen_tcode/pose_backends.py`：本地 RTM Pose 模型加载和推理辅助。

## 开发原则

- 修改范围尽量贴近用户要求。
- 保持现有 UI 风格和普通用户操作流程。
- 危险设备运动必须继续受上下限、限速、预设和输出夹紧保护。
- `Log only` 是最安全的预览和调试模式。
- 不要把本地 ONNX 模型加入源码发布包或 Git 提交。
- 不要主动 push 到 GitHub，不要重写远程历史，除非用户明确要求。
- 优先做保守、可读、可验证的小改动，避免大重构。

## UI 和设置规则

- 新控件要清楚可见，名称直观，必要时加简短说明。
- 英文和中文 UI 文案要同步。
- 新设置需要默认值、保存/读取逻辑，以及恢复默认支持。
- 高级设置或模式专属设置尽量折叠，避免主界面太乱。
- RTM Pose 模型相关控件只应在选择 RTM Pose 模式时展开。

## 测试版规则

- 测试版用于快速迭代。
- 测试版通常不需要重新打 Windows 免安装 zip。
- 保留一键源码启动入口，例如 `Start.cmd`。
- 用户确认通过前，使用类似 `1.1.1-test.29` 的测试版号。

## 正式版打包规则

正式版需要准备：

- Windows 免安装发布文件夹，包含 exe、`Start.cmd`、必要依赖、README、简易教程、用户手册、版本日志、许可证和鸣谢。
- 带批准版本号的 Windows zip，例如 `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility-v2.0.0-Windows.zip`（后续正式版）。
- 带批准版本号的源码 zip，例如 `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility-v2.0.0-Source.zip`（后续正式版）。
- zip 里不能包含 `.git`、缓存目录、本地隐私路径、模型文件、`.onnx` 文件、开发构建中间产物。
- 如果重新打包了 Windows zip，要解压到临时目录并启动 exe，确认不会闪退。

## RTM Pose 注意事项

- RTM Pose 2D 更适合低延迟舞蹈分析。
- RTM Pose 3D 可以提供更多深度线索，但通常延迟更高。
- GPU 加速是可选项，默认应关闭，除非用户明确改变。
- 如果 GPU/CUDA 不可用，软件应显示原因，并尽量自动回退 CPU。
- 光流辅助和卡尔曼融合是让关键点更平滑的轻量辅助，不是完全替代模型检测。

## 验证清单

- 改代码后：运行项目支持的语法/导入检查。
- 改实时输出或启动流程后：启动软件，确认不会立刻退出。
- 改发布包后：重新生成对应 zip，检查内容，解压到临时目录并启动 exe。
- 只改 README 或普通文档时：通常做文字搜索确认即可，除非用户要求重新打包。
