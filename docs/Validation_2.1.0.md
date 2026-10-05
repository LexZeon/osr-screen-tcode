# 2.1.0 structural release / 结构整理版本

## English

### Scope and method

The user requested **2.1.0**, modular organization without changing application content/behavior, a release, and explanations of every feature. Baseline is official 2.0.2 commit `b9c5a572051e6e6b87103933bd8d229b205b7088`. The work uses the same working repository and preserves old releases and the formal source environment.

`app.py` retains the public `OsrScreenApp`, its initializer, main queue dispatch, model-root path, close and CLI. Its 190 other methods move into 19 explicit `application/` mixins. Each has ordinary imports, no new initializer and the same `self` state. Three small facade factories preserve the original analyzer/capture/region-selector globals for existing callers and tests; four existing call sites invoke those factories.

`analyzer.py` retains the public `AxisAnalysis`/`RealtimeAnalyzer`, initial/reset state and processing entry. Its 94 other methods move into five `analysis/` mixins. Six methods add an explicit local import of the public class to preserve static-helper resolution. No executable source generation, reflection registry or runtime AST loading is used.

Translations, bilingual tooltips and model source constants move intact. The only new developer utility is an AST-only source index; it is not part of application startup. Runtime version metadata changes to 2.1.0. Historical README/Start/AI guide bytes remain intact under `docs/history/`, while current guides point readers to the relevant responsibility.

### Structural and behavior evidence

- **All 200 original app methods** have equal signatures, decorators and method AST after accounting only for relative-import depth and the four explicit factory call sites. Eight constant definitions and the Tooltip class AST are identical. Code is moved, not rewritten.
- **All 98 original analyzer methods** have equal signatures, decorators and method AST except the six explicit compatibility imports. Existing public backend and static-helper patch points were actually exercised successfully.
- Baseline and reorganized application snapshots in English and Chinese, with all **nine visible analysis choices per language**, have identical widget trees, labels, geometry, saved configuration per mode and reset-default state. This comparison ran before changing only the displayed version metadata, so the version label does not mask any other difference. Settings stayed unchanged.
- Analyzer comparison: **14 configurations / 224 frames**, positions, confidence, activity, reference and preview arrays matched exactly; constructor/reset state matched. **24 synthetic RTM samples** produced equal geometry, overlay and Kalman results. Two existing focused non-GUI tests passed.
- The AST-only code index successfully locates `_save_config` and the realtime responsibility without loading the application. Previous guide snapshots were verified byte-for-byte.

### Development checks and final verification

The first private multi-root UI snapshot helper left a Tk callback from the first diagnostic root pending and printed an invalid-command warning when creating the next root. The helper now cancels its pending diagnostic callbacks before opening a new root; the rerun and the baseline/refactor comparison passed cleanly. Product close behavior was not changed to conceal this helper issue.

An inspection caught a generated self-import in the new translation module before application execution, and three method-local relative imports needed one additional parent level. These were corrected before the import/UI checks above. The whitespace check also identified redundant final blank lines in the analyzer/new analysis files; these were removed without changing statements, and the final executable was rebuilt from the tidied source.

Final isolated main suite: **502 passed / 457.455 seconds**. Independent Lab: **38 passed / 0.326 seconds**. The final-command simulator stream check passed. Actual source Start.cmd launched English and Chinese Log only for three seconds (88 and 91 updates), with normal stop; the independent source Lab launched successfully.

A fresh PyInstaller build passed English/Chinese three-second live starts, dependency/resource/CPU self-check and bundled Lab launch. Actual external **ViTTrack CPU tracking** and **NeuFlow CUDA bidirectional flow** passed. An additional real RTM Pose CPU model/live check passed for **8 seconds / 254 updates**. Main and Lab personal-settings fingerprints stayed unchanged. These runs used the secondary display; no dependency was installed/upgraded and no hardware was connected.

The publication helper's final **22 offline checks / 0.810 seconds** passed. Its first 21-check run had one failure because CRLF archive-index text bypassed the English insertion; newline handling was fixed before the complete reruns. A monitor diagnostic initially used a nonexistent function name and stopped before launch; using the existing `screen_monitors()` succeeded. These are development-helper failures, not passing program tests.

Final ZIPs are assembled after committing this record. The exact final extraction, launcher/hash/download/publication results are retained in the release body and durable archive evidence; they are not attributed to these earlier source/executable checks.

### Practical limits

This is a finite equivalence check and regression suite, not proof for every real video or hardware configuration. Internal method ownership and traceback file locations now reflect the new modules; public application/analyzer class paths remain compatible. Mutating an imported module object's properties still reaches shared imports, while reassigning an old facade's imported global name is not generally a cross-module dependency override; the three documented factory boundaries preserve the tested injection points.

No model, optional GPU runtime, local setting, log, cache or private user path is eligible for Git/application ZIPs. No dependency installation or hardware connection is required by this structural work. Real hardware, depth/contact and robot-arm mapping remain unverified.

## 中文

### 范围与方式

用户要求 **2.1.0**，在不改变程序内容／行为的情况下模块化，发布 Release 并解释每项功能。基线为正式 2.0.2 提交 `b9c5a572051e6e6b87103933bd8d229b205b7088`，沿用当前工作仓库，保留旧发布及正式源码环境。

`app.py` 保留公开 `OsrScreenApp`、初始化、主队列调度、模型根路径、关闭和 CLI；其余 190 个方法搬入 19 个显式 `application/` mixin，使用普通导入，无新增初始化，共用原 `self` 状态。三个小工厂保留原分析器／采集／框选全局接入点，四个原调用位置经工厂调用。

`analyzer.py` 保留公开 `AxisAnalysis`／`RealtimeAnalyzer`、初始化／重置状态及处理入口，其余 94 个方法搬入五个 `analysis/` mixin。六个方法增加公开类的显式局部导入，保持原静态 helper 解析；不使用运行时代码生成、反射注册或 AST 装载。

翻译、双语提示及模型来源常量原样搬迁；新增源码索引只供开发者解析 AST，不进入程序启动。版本元数据改为 2.1.0，旧 README／Start／AI 指南原字节保存于 `docs/history/`，当前说明引导定向阅读。

### 结构与行为证据

- **200 个原 app 方法**的签名、装饰器及方法 AST 一致，只对齐相对导入深度和四个显式工厂调用；八个常量定义与 Tooltip 类 AST 完全一致，没有重写方法。
- **98 个原 analyzer 方法**的签名、装饰器及 AST 一致，仅六处兼容导入有变化；原公开 backend 和静态 helper patch 接入已实际验证。
- 中英文各 **九种可见分析选项**的前后快照中，控件树、文字、几何、各模式保存配置及恢复默认状态完全一致。对照在只改显示版本前执行，避免用版本文字差异遮蔽其他变化；个人设置未变。
- 分析器 **14 组配置／224 帧**的位置、置信度、活动、参考及预览数组逐项精确一致，构造／重置一致；**24 组合成 RTM 样本**的几何、骨架标注和 Kalman 一致，两个现有无界面定向测试通过。
- AST 源码索引成功定位 `_save_config` 和 realtime 模块，无需加载软件；前版说明快照逐字节核对。

### 开发检查与最终验证

首次私有多窗口快照脚本关闭第一个 Tk 根窗口时残留诊断回调，创建第二个根窗口后打印 invalid-command 提示。脚本现在先取消自己的待执行回调，再开下个诊断窗口；重跑及前后对照均通过。未修改产品关闭行为来掩盖该脚本问题。

静态检查在执行软件前发现生成的翻译模块自导入，另有三个方法内相对导入需要多一层父级，均在上述导入／界面检查前修正；空白检查还发现分析器及新分析模块末尾多余空行，已整理，不改变语句，并从整理后的源码重新构建最终 exe。

最终隔离主程序 **502 项通过／457.455 秒**；独立 Lab **38 项通过／0.326 秒**，模拟器最终指令流检查通过。实际源码 Start.cmd 中英文 Log only 各运行三秒（88／91 次更新），正常停止；源码独立 Lab 启动通过。

全新 PyInstaller 构建通过中英文三秒实时启动、依赖／资源／CPU 自检与内置 Lab 启动；实际外部 **ViTTrack CPU 跟踪**、**NeuFlow CUDA 双向光流**通过。额外真实 RTM Pose CPU 模型与实时检查 **8 秒／254 次更新**通过。主程序及 Lab 个人设置指纹未变；窗口使用副屏，未安装／升级依赖、未连接硬件。

发布辅助工具最终 **22 项离线检查／0.810 秒**通过。首次 21 项中一项因 CRLF 归档索引导致漏插英文说明而失败，修正换行处理后完整重跑通过。显示器诊断首次误用了不存在的函数名，在启动前停止；改用现有 `screen_monitors()` 后成功。这些是开发辅助检查失败，不记作程序测试通过。

最终 ZIP 在提交本记录后组装；对应最终解压包的实际启动／校验／下载／发布结果保存在 Release 正文及长期归档证据，不冒充上述较早源码／exe 检查结果。

### 实际限制

有限对照与回归不能证明所有实片和硬件配置。方法实际归属和异常栈文件位置会反映新模块，公开主程序／分析器类路径继续兼容。修改共同导入模块对象的属性仍共享生效；重赋旧入口中某个导入变量不是普遍的跨模块依赖覆盖，三个明确工厂保留已验证的接入点。

模型、可选 GPU 库、个人设置、日志、缓存和本机路径不进入 Git／应用 ZIP；本轮结构工作不要求安装依赖或连接硬件，真实硬件、深度／接触和机械臂映射仍未验证。
