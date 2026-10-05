# 2.1.0 Architecture and Reading Guide

## English

### Scope and public entry points

**2.1.0 moves existing methods into modules grouped by responsibility.** It does not add analysis algorithms, alter output mathematics, extend the two-second estimate limit, change saved defaults or implement robot-arm mapping. Read the user-facing [Feature Guide](FEATURES.md) for controls, effects and limitations; release validation records describe the checks actually completed.

Paths in the module tables are relative to `src/osr_screen_tcode/`. Root paths are explicitly marked. `app.py` remains the public `OsrScreenApp`/`main()` entry. It owns initialization, startup scheduling, frame/control queues, worker-result dispatch, preview refresh, close/shutdown and explicit factory hooks. Its imports still configure Windows DPI awareness and activate the private GPU runtime before importing the GUI/model-dependent stack.

`analyzer.py` remains the public `RealtimeAnalyzer` entry and exports `AxisAnalysis` and `SIX_AXES`. It retains initialization/state, reset, the main `process()` dispatch and shared position filtering. Existing callers still construct these public classes; splitting implementation into files does not create independent application/analyzer instances.

### Application responsibilities

The application composes **19 responsibility mixins**, alongside the existing `DeviceControls`, `GpuControls` and `tk.Tk` bases. These 19 mixins define no initializer and share the same `self`: Tk variables, configuration, queues, worker state and output objects are still owned by the public app. Dependencies between methods remain ordinary explicit method calls. Inheritance is organization of the existing object, not an independently injected service system.

| Module | Responsibility |
| --- | --- |
| `application/language.py` | Startup language selection, display/internal labels and widget localization. |
| `application/state.py` | Tk variable creation, variable registration and state-change wiring. |
| `application/settings.py` | Autosave scheduling, saved configuration and reset defaults. |
| `application/analysis_options.py` | Mode-dependent visibility, analysis option changes and profile synchronization. |
| `application/layout.py` | Main layout, generic controls, sections and folding. |
| `application/analysis_controls.py` | Analysis/filter/FPS/curve controls and their explanations. |
| `application/sources.py` | Screen/video/audio input controls, physical region checks and region selection. |
| `application/models.py` | Existing RTM model discovery, validation, selection and download. |
| `application/model_options.py` | Independent optional-v2 model controls, download events and cancellation. |
| `application/travel_controls.py` | Shared/individual travel sliders and displayed multiplier synchronization. |
| `application/device_panel.py` | Device connection panel, measurement and axis-limit UI. |
| `application/connection.py` | Device discovery, asynchronous connection/disconnection and error completion. |
| `application/manual_output.py` | Actual command emission, center, measurement and synthetic tests. |
| `application/presets.py` | Named presets, five play levels and hybrid sensitivity actions. |
| `application/realtime.py` | Live start/stop, worker loop, screen/video/audio capture and per-frame processing. |
| `application/start_dialog.py` | Start-confirmation view and application of reviewed settings. |
| `application/output.py` | Analysis-to-position interpretation, final travel/inversion/limits and output construction. |
| `application/video_export.py` | Offline video export, recording and script saving. |
| `application/monitor.py` | Final command parsing/history, axis indicators and output curves. |
| `application/translations.py` | Existing mode labels and English/reverse translation tables. |
| `application/tooltips.py` | Existing bilingual tooltip text and `Tooltip` presentation class. |
| `application/model_sources.py` | Supported RTM model URL/name constants. |

The last three modules contain shared constants/presentation support; they are not additional application mixins. Publicly imported labels/constants remain available through the facade where established callers expect them. `config.py` and `analysis_preferences.py` continue to own persisted configuration and independent dance/hybrid profiles.

### Analyzer responsibilities

`RealtimeAnalyzer` explicitly composes five mixins. They also have no initializer and use the facade's existing state and method signatures.

| Module | Responsibility |
| --- | --- |
| `analysis/flow.py` | Existing image-flow measurement, v1/Beta route logic and related L0 helpers. |
| `analysis/pose_motion.py` | Existing pose-biased image geometry and associated skeleton helpers. |
| `analysis/rtm_runtime.py` | Existing RTM backend invocation, runtime/loss state and inference helpers. |
| `analysis/rtm_geometry.py` | Existing 2D-derived pose/core/rotation geometry and axis interpretation. |
| `analysis/preview.py` | Existing analyzer overlay, skeleton and information-panel drawing. |

Some helper names still contain `3d` because they are established shared geometry/data names. They do not re-enable removed RTM Pose 3D inference or establish physical 3D/IK support.

### Explicit compatibility hooks

Three factory methods remain on `OsrScreenApp` in `app.py`: `_create_analyzer()` calls the facade's `make_analyzer`, `_create_screen_capture()` calls `LatestScreenCapture` with the facade's `ScreenCapture` factory, and `_create_region_selector()` calls the facade's `ScreenRegionSelector`. Call sites in the extracted modules use these methods. This preserves established factory patch locations and public-entry behavior while making dependencies visible. Replacing a factory does not mean every internal implementation import becomes interchangeable.

Six extracted analyzer methods use **local imports of the public `RealtimeAnalyzer`** before making their existing static helper calls: three sites in `analysis/pose_motion.py`, one in `analysis/rtm_geometry.py` and two in `analysis/preview.py`. Keeping these calls on the facade preserves public-class static-helper patch/lookup semantics; importing inside the method avoids the facade/mixin import cycle. These are explicit compatibility decisions, not new model execution paths.

Keep normal imports, declared classes and method calls. Do not replace this structure with reflective method installation, dynamically generated mixins, `exec()` or an implicit dependency-rewriting mechanism. Follow references and the method-resolution order when changing shared `self` dependencies.

### Two flows and their boundaries

**Live:** UI settings → validated settings/region snapshot → source capture → sampled image observations → interpreted analysis axes → output curve and user travel → live TCode mapping → selected sink and final-command simulator/monitor.

- `sources.py` validates the physical region before workers use it; `capture.py`, `screen_geometry.py` and `region_selector.py` retain physical-pixel and mixed-DPI behavior.
- `visual_pipeline.py` gives the integrated preview and Pose/v2/cycle analysis the same sampled frame. `visual_lab/` retains image observations and bounded pose stabilization. V1/Beta routes still enter `RealtimeAnalyzer` through the existing factory.
- V2 subject, camera, targets, phase and continuity remain in the existing motion/reference modules. `v2_models.py`, `v2_model_assets.py` and `v2_model_assist.py` retain default-off model assistance and artifact validation; a model box is not a direct L0 observation.
- `application/output.py` interprets positions; `output_curve.py` smooths them. `tcode.py` retains actual live limits, coupling, speed/activity/startup handling; `command_cadence.py` and `endpoint_slowdown.py` retain timing. `manual_output.py` emits commands to `sinks.py` and the simulator bridge. `monitor.py` shows commands, not physical feedback.

**Recording/offline export:** sampled analysis positions → applicable Pose interpretation/output curve → script travel/inversion → normalized recorder actions and endpoint-adjusted timestamps → axis `.funscript` files. Live recording and offline export use `recorder.py`; offline export is orchestrated by `application/video_export.py` rather than a hardware sink.

The script branch is not a copy of final live TCode. It does not bake every device-axis limit, per-update speed cap, live idle/endpoint action or TCode-only axis coupling into normalized actions. The simulator receives final live commands; the analysis preview receives observations/reference details. Manual center and emergency-center commands have their existing separate path. Audio generates L0 without image observations. Independent Lab remains an isolated preview without device output or main settings.

### Preservation requirements

- Keep `_rtm_pose_model_dir()` on `app.py`: its `__file__` is the established anchor for resolving the source model root. Moving that path expression into `application/models.py` would change its parent depth.
- Preserve DPI/private-GPU activation import order. Do not casually import the model/GUI stack earlier from a newly extracted module.
- Preserve signatures, event names, queue routing, thread/Tk boundaries and start/stop/close ordering. Moving code between files is not authorization to change callback cadence or error behavior.
- Preserve configuration keys/migrations, per-mode defaults, source timing, observation-versus-estimate distinctions, output stages and their limits. Optional models remain off by default; prediction remains at most two seconds. Do not infer real depth/contact or hardware mapping from a structural change.
- Keep source, portable packaging and independent Lab entry points together. This document is a responsibility map, not proof that every scene, device or runtime combination has been tested.

### Read only what a change needs

Root `tools/code_index.py` builds an **AST index from source text**, without importing the application, creating Tk windows, loading models or opening capture/devices. With no arguments it lists module summaries/counts; its optional query matches module paths or declared function/method names, and `--json` returns structured results with signatures and line numbers.

```text
python tools/code_index.py application/realtime
python tools/code_index.py _save_config --json
```

Start with the relevant row above or a method-name query. Read the indexed method and its callers, then only the specific configuration/output helper it uses. For an output-only change, inspect the final mapping/recorder distinction before reading model code; for a region change, inspect physical geometry and capture before pose math. Use targeted text searches and small surrounding slices instead of rereading whole facades or long historical logs. Select checks from the affected boundary and existing regression coverage; do not treat the index as an execution trace or a validation result.

---

## 中文

### 范围与公开入口

**2.1.0 只把既有方法按职责搬进模块。** 不新增分析算法、不修改输出数学、不延长最多两秒估算、不改变保存默认，也不实现机械臂映射。控件用途与边界见[功能指南](FEATURES.md)，实际完成哪些验证以发布验证记录为准。

模块表路径相对 `src/osr_screen_tcode/`，根目录路径会注明。`app.py` 仍公开 `OsrScreenApp`／`main()`，保留初始化、启动调度、帧／控制队列、工作线程结果分派、预览刷新、关闭和显式工厂入口。其导入仍先设置 Windows DPI 感知、激活私有 GPU 运行库，再导入 GUI／模型相关层。

`analyzer.py` 仍公开 `RealtimeAnalyzer`、`AxisAnalysis`、`SIX_AXES`，保留初始化／状态、reset、主 `process()` 分派和共用位置过滤。调用者继续实例化公开类；拆文件不会创建独立的主程序／分析器实例。

### 主程序职责

主程序显式组合 **19 个职责 mixin**，另保留 `DeviceControls`、`GpuControls`、`tk.Tk`。这 19 个 mixin 没有初始化方法，共用同一 `self`：Tk 变量、配置、队列、线程状态、输出对象仍由公开主程序持有。跨方法依赖仍是普通显式调用；这是同一对象的代码整理，不是独立注入服务系统。

| 模块 | 职责 |
| --- | --- |
| `application/language.py` | 启动语言、显示／内部标签与控件本地化。 |
| `application/state.py` | Tk 变量创建、变量登记和状态变化接线。 |
| `application/settings.py` | 自动保存调度、配置保存、恢复默认。 |
| `application/analysis_options.py` | 模式可见性、分析选项变化和配置同步。 |
| `application/layout.py` | 主布局、通用控件、分区和折叠。 |
| `application/analysis_controls.py` | 分析／滤波／FPS／曲线控件及说明。 |
| `application/sources.py` | 屏幕／视频／声音控件、物理区域验证和框选。 |
| `application/models.py` | 既有 RTM 模型发现、验证、选择、下载。 |
| `application/model_options.py` | v2 可选模型独立控件、下载事件和取消。 |
| `application/travel_controls.py` | 总／逐轴行程滑块及倍率显示同步。 |
| `application/device_panel.py` | 连接面板、测量与轴限位 UI。 |
| `application/connection.py` | 发现、异步连接／断开和错误完成处理。 |
| `application/manual_output.py` | 实际发送、回中、测量、合成测试。 |
| `application/presets.py` | 具名预设、五档与混合敏感度操作。 |
| `application/realtime.py` | 实时启停、线程、屏幕／视频／声音采集及逐帧处理。 |
| `application/start_dialog.py` | 启动确认显示和应用检查后的设置。 |
| `application/output.py` | 分析位置解释、最终倍率／反向／限位和输出构造。 |
| `application/video_export.py` | 离线视频导出、录制和脚本保存。 |
| `application/monitor.py` | 最终指令解析／历史、轴状态和输出曲线。 |
| `application/translations.py` | 原模式标签、英文与反向翻译表。 |
| `application/tooltips.py` | 原双语提示文本及 `Tooltip` 显示类。 |
| `application/model_sources.py` | 受支持 RTM 模型 URL／文件名常量。 |

后三项是常量／显示辅助，不是额外主程序 mixin。原公开导入标签／常量仍在既有调用者期待的入口可用。`config.py` 与 `analysis_preferences.py` 继续负责保存配置及独立舞蹈／混合配置。

### 分析器职责

`RealtimeAnalyzer` 显式组合五个 mixin，同样没有初始化方法，使用公开类既有状态和方法签名。

| 模块 | 职责 |
| --- | --- |
| `analysis/flow.py` | 原光流测量、v1／内测路线和相关 L0 辅助。 |
| `analysis/pose_motion.py` | 原 Pose 倾向图像几何及骨架辅助。 |
| `analysis/rtm_runtime.py` | 原 RTM 后端调用、运行／缺测状态与推理辅助。 |
| `analysis/rtm_geometry.py` | 原二维派生核心／旋转几何和轴解释。 |
| `analysis/preview.py` | 原分析器叠加图、骨架与说明面板绘制。 |

某些辅助名仍有 `3d`，因为是既有共享几何／数据名，不代表重新启用已移除 RTM Pose 3D 推理，也不构成真实三维／IK 支持。

### 显式兼容入口

`app.py` 的 `OsrScreenApp` 保留三个工厂：`_create_analyzer()` 调用该入口的 `make_analyzer`；`_create_screen_capture()` 用该入口的 `ScreenCapture` 构造 `LatestScreenCapture`；`_create_region_selector()` 调用该入口的 `ScreenRegionSelector`。搬迁模块通过这些方法创建对象，保留原工厂替换／公开入口行为并让依赖可见；替换工厂不代表内部每个导入都可任意互换。

六个搬迁分析方法在使用原静态辅助前，**局部导入公开 `RealtimeAnalyzer`**：`analysis/pose_motion.py` 三处，`analysis/rtm_geometry.py` 一处，`analysis/preview.py` 两处。调用仍经公开类，保留静态方法查找／替换语义；方法内导入避开公开类／mixin 循环。这是兼容处理，不是新模型路线。

继续使用普通导入、声明类与显式调用；不建议改成反射安装方法、动态生成 mixin、`exec()` 或隐式改写依赖。修改共享 `self` 依赖时跟踪实际引用和方法解析顺序。

### 两条流程与边界

**实时：** UI 设置 → 已验证设置／区域快照 → 来源采集 → 采样画面观测 → 分析轴解释 → 输出曲线与用户行程 → 实时 TCode 映射 → 所选 sink 与最终指令模拟器／监视。

- `sources.py` 在交给线程前验证物理区域；`capture.py`、`screen_geometry.py`、`region_selector.py` 保留物理像素和混合 DPI 约定。
- `visual_pipeline.py` 为集成预览和 Pose／v2／周期分析提供同一次采样帧；`visual_lab/` 保留画面观测与短时骨架稳定。v1／内测仍经原工厂进入 `RealtimeAnalyzer`。
- v2 主体、运镜、目标、相位、接续仍在原运动／参考模块。`v2_models.py`、`v2_model_assets.py`、`v2_model_assist.py` 保留默认关闭辅助与文件校验；模型框不是直接 L0 观测。
- `application/output.py` 解释位置，`output_curve.py` 平滑；`tcode.py` 保留实时限位／联动／速度／活动／渐入，`command_cadence.py`／`endpoint_slowdown.py` 保留时序。`manual_output.py` 发至 `sinks.py` 和模拟器桥，`monitor.py` 显示命令，不是物理反馈。

**录制／离线导出：** 采样分析位置 → 适用 Pose 解释／输出曲线 → 脚本倍率／反向 → 归一化录制动作与端点调整时间戳 → 各轴 `.funscript`。实时录制和离线导出共用 `recorder.py`，离线由 `application/video_export.py` 调度，不走硬件 sink。

脚本分支不复制最终实时 TCode，不把全部设备限位、每次更新限速、实时空闲／端点动作和仅 TCode 联动写入归一化动作。模拟器收到最终实时指令；分析预览收到观测／参考详情。手动／急停回中保留独立路径。纯声音不经过画面观测；独立 Lab 不输出设备，也不使用主程序设置。

### 搬迁后必须保留

- `_rtm_pose_model_dir()` 留在 `app.py`，其 `__file__` 是原源码模型根路径锚点；把路径表达式搬入 `application/models.py` 会改变父目录深度。
- 保留 DPI／私有 GPU 激活导入先后，不随意从新模块提前导入模型／GUI 层。
- 保留签名、事件名、队列分派、线程／Tk 边界和启停／关闭顺序；搬文件不授权改回调节奏或错误行为。
- 保留配置键／迁移、模式默认、源时序、观测／估计区别与输出阶段限制；可选模型仍默认关，估算仍最多两秒。结构改动不能推出真实深度／接触／硬件映射。
- 保留源码、便携包和独立 Lab 配套入口；职责地图不证明所有场景、设备、运行库组合已测试。

### 定向阅读工作法

根目录 `tools/code_index.py` **只从源码文本建立 AST 索引**，不导入软件、不创建 Tk 窗口、不加载模型、不打开采集／设备。无参数显示模块摘要／方法数；查询匹配模块路径或函数／方法名，`--json` 提供含签名与行号的结构化结果。

```text
python tools/code_index.py application/realtime
python tools/code_index.py _save_config --json
```

先按职责表或方法名定位，读该方法及调用者，再读其具体配置／输出依赖。只改输出时先看最终映射与录制区别；改选区时先看物理几何／采集，再看 Pose 数学。用定向文本搜索和少量上下文，避免重复读整份入口或冗长历史日志。验证选择跟随受影响边界与已有回归覆盖；索引不是执行轨迹或验证结论。
