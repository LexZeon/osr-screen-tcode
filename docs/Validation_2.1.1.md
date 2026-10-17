# 2.1.1 model setup and start-dialog checks / 模型设置与开始窗口验证

## English

### Scope and evidence

Baseline: official 2.1.0, `a1919a8d5f5c10dcc47c4ef6a6f89b6cfe89e3c6`. The user reported that checking ViTTrack/NeuFlow in start confirmation made the whole application unclickable, then requested model auto-detection and GPU setup access like RTM Pose. The user continued testing the old version and explicitly requested that this work not disturb it.

Before publication, the remote branch's October 11 contact-email commit `aebc03710eb507c0182d6f4ddc068c6389f1244c` was discovered and fast-forward integrated, preserving its UI/documentation updates and historical authorship. Local work was retained in a private file snapshot and a Git stash, then reapplied without conflict. The in-progress pre-integration full-run attempt was deliberately stopped and retained as partial evidence, not counted as a complete passing suite. Final verification uses the integrated source.

Local checkbox callbacks previously updated UI labels/grids but did not hash/load models. A private baseline Chinese 150% checkbox probe completed normally (25 timer callbacks and 12 Configure events after both toggles). Therefore the exact intermittent original freeze has **not** been reproduced or assigned a proven root cause. This version addresses verified synchronous file-validation work and modal/layout/lifecycle risks; original-operation retesting remains required.

### Changes and preservation

- Optional-model label refresh is coalesced outside native checkbutton variable traces. The start modal uses a coalesced, natural-width horizontal/vertical control surface, safe wheel/focus routing and a separate reachable footer. Parent Return/Escape and button actions defer to a nested native/GPU modal; shared GPU close restores the previous grab without taking it from another modal.
- Background detection validates a selected file or the known downloaded filename. **Detect models** and manual file selection use the same checked result path; no recursive scan or automatic download. Two worker slots, cancellation, monotonic tokens, original-value snapshots and owner checks prevent outdated results from replacing newer choices or applying after reset/close. Hash validation can cancel between chunks. No worker accesses Tk.
- **Enable CUDA** selects the existing shared CUDA preference and opens GPU setup. It does not download/install a runtime or enable either model switch. The existing explicit installer remains; RTM DirectML remains available and NeuFlow still requires CUDA. Shared backend changes are immediate; the start modal's enabled/model fields remain staged. CUDA self-check status is not an assertion of NeuFlow-model readiness.
- Model pins, setting keys/defaults, capture/analysis/output arithmetic and the two-second estimate limit remain unchanged. No old executable/package/runtime is replaced, no dependency is installed/upgraded and no hardware is connected. Lab stays 0.2.2-test.

### Development checks and corrections

The first focused run completed **86 tests / 229.300 seconds, all tests OK**, but its wrapper failed the final fingerprint assertion because the user was concurrently changing old-version settings. The user confirmed this activity. No configuration was restored. Subsequent isolated checks use a Python audit hook rejecting this process's writes/renames/deletes in the old settings directory, formal checkout and old 2.1.0 archive; external user changes are retained and recorded separately.

A subsequent 19-test run had one failure and nine errors. New widget-owned idle callbacks could be canceled through the root interpreter yet remain in a child's Tcl-command list, producing a real duplicate-command-cleanup error on close. Callbacks are now owned/canceled consistently by the root. The heartbeat test initially assumed three callbacks within a fixed 220 ms; it now requires actual timer progress with an overall timeout. A 20-test rerun cleared the cleanup errors but exposed one focus visibility assertion. Competing native focus was an initial hypothesis, not a confirmed cause. Component checks now deliver FocusIn events without forcing the user's keyboard focus; actual native interaction is checked separately. A modal-only run passed **3 tests / 33.851 seconds**.

The integrated serial suite completed **523 tests / 1,428.962 seconds with one failure and zero errors**: the English 150% synthetic-focus check found a model button 13 pixels below the scroll viewport. Protected-directory write attempts were zero. Its four language/scale combinations subsequently passed together, as did a controlled model-result release; those reruns do not erase the original failure or establish its cause. In that controlled check, changing the checking label to the missing-model label did not change the viewport, content size or scroll position.

A separate bounded probe established a related layout boundary: narrowing the start control surface and delivering FocusIn before that resize settled could leave a button below the viewport after the horizontal scrollbar appeared. This is a reproducible focus-versus-layout ordering defect, not an exact reproduction of the preceding full-run failure or the original complete freeze.

The private start-control surface now defers focus reveal and reapplies it after layout, using root-owned cancelable callbacks. Wheel/scrollbar interaction and focus outside the control body clear the remembered target, so manual scrolling is respected. The main sidebar implementation is unchanged. A deterministic regression sends only one FocusIn before the pending resize, retains strict pixel visibility assertions and checks manual scrolling, outside focus and destruction cleanup.

Read-only review also identified a debounce race where A→B path changes could drop B's automatic check; rescheduling and a regression cover the current selection. Unknown Tcl modal grab paths are compared as raw paths rather than assuming every native modal has a Python widget object. No failed development run is counted as final verification.

A late automatic lookup could also replace an empty default-model setting with its absolute path after live/export analysis had started, inadvertently triggering the existing stop-on-option-change behavior. Automatic completion now retains that active default choice and displays the verified path from its cache; explicit Detect/file selection still applies the chosen path. Three no-Tk regressions passed in 0.021 seconds, covering live, export and explicit detection, with zero protected-write attempts.

The private startup helper initially rejected Windows' exact null-input device before launching the frozen program. Its write audit now allows only the canonical `os.devnull` target while retaining rejection of other devices/files; 19 helper regressions passed in 2.632 seconds. The original pre-launch failure is retained. A fresh run then passed the rebuilt EXE's dependency/resources/CPU checks, actual RTM Pose CPU inference, ViTTrack CPU tracking and NeuFlow CUDA bidirectional flow using existing external files. No GPU runtime or model was installed or bundled. These synthetic model checks are not a video-quality benchmark.

### Final verification

- **524 main tests passed**, zero failures/errors/skips. These were three independent serial partitions of the same final source snapshot: GUI **227 / 528.219 s**, non-GUI A **146 / 277.250 s**, non-GUI B **151 / 467.891 s** (wrapper times). Their 524 unique completed IDs exactly equal discovery, with no duplicates/missing tests. Only the GUI process could construct windows; all three reported zero protected-directory write attempts. This is complete partitioned coverage, not a claim that the earlier failing serial invocation passed.
- **38 Lab tests / 2.175 s passed**; the simulator final-command stream check passed. The final four modal tests had also passed in **26.714 s** before the partitioned run. Private publication/startup-helper regressions are separate from these product counts.
- Actual source **Start.cmd**, English/Chinese **3 s Log only: 106/111 updates**, and final rebuilt EXE **108/110 updates**, passed with normal stop/worker exit. Source Lab was an isolated wrapper smoke of unchanged preview.py, not its actual Start.cmd; the bundled EXE's actual `--preview-lab --smoke` passed. The bundled Lab smoke has no origin flag, so its display placement is not verified.
- Native Chinese start confirmation was clicked on ASUS: both switches completed actual file verification, CUDA settings opened/closed, and Cancel returned both main switches to off with empty main paths. **1,229 heartbeats / 72.734 s**, maximum observed gap **0.719 s**, no callback/close errors or timeout. This isolated navigation check mocked GPU-status scheduling and configuration save; it started no inference/hardware and is not a GPU-installer or frame-rate benchmark.
- Actual source and final EXE checks passed dependency/resource/CPU inference, external **RTM Pose CPU**, **ViTTrack CPU** and **NeuFlow CUDA bidirectional flow** using existing model/runtime files. Model/GPU installation was not performed. The final EXE audit checked **89 own modules / 1,278 nested code objects**, found no absolute code filenames/private home constants, and found no raw UTF-8/UTF-16LE home path in **1,148 pre-assembly files**. This does not claim to audit every third-party compressed code object.
- Personal settings were isolated, observed and never restored; earlier external changes remain recorded. The formal checkout, shared runtime and old executable/archive were preserved. New settings/contact references use lexzeonstudio@gmail.com; the remote October 11 contact commit remains an ancestor.

Final ZIP extraction, actual portable Start.cmd, file-manifest checks, final commit/digests, public downloads and paired archive evidence are appended to the GitHub Release and durable local archive after assembling this committed source. They are not retroactively claimed as pre-commit source checks.

### Limits

These checks are finite and the original user freeze remains unconfirmed. Slow/network file I/O can still take time; canceled daemon work cannot apply an obsolete result. No actual GPU installation is necessary for this change; tests simulate installation decisions while real inference is checked separately when possible. Hardware, real depth/contact and robot mapping/feedback remain unverified.

## 中文

### 范围与证据

基线为正式 2.1.0，`a1919a8d5f5c10dcc47c4ef6a6f89b6cfe89e3c6`。用户反馈在开始确认窗口勾选 ViTTrack／NeuFlow 后整个软件无法点击，随后要求类似 RTM Pose 的模型自动检测与 GPU 配置入口；用户同时继续测试旧版，明确要求不受本轮影响。

发布前发现远程分支已有 10 月 11 日邮箱提交 `aebc03710eb507c0182d6f4ddc068c6389f1244c`，已快进整合并保留界面／文档修改及历史作者信息。本轮工作先留私有文件快照及 Git stash，再无冲突应用。整合前正在运行的完整套件被主动结束，日志保留为部分证据，不计作完整通过；最终验证使用整合后的源码。

原复选框只刷新文案／布局，不哈希或加载模型。私有基线中文 150% 双勾选探针正常结束（25 次定时回调、12 次 Configure）；因此**没有精确复现原间歇性卡死，也没有认定同一现场根因**。本版处理明确的同步文件校验及模态／布局／生命周期风险，仍需复测用户原操作。

### 改动与保留

- 模型状态绘制移到原生复选框变量回调之外，合并为空闲刷新。开始确认使用自然宽度的横向／纵向滚动、正确的滚轮／焦点路由及独立可见页脚；原生／GPU 子模态持有输入时，父窗口回车／Esc／按钮不穿透。GPU 窗关闭恢复原抓取，不抢其他模态输入。
- 后台检测所选文件或固定下载文件名，“自动检测模型”与手选校验共用结果检查，不递归扫描、不自动下载。两个执行槽、取消事件、递增 token、原值快照及窗口存活检查阻止过期结果覆盖新选择或在重置／关闭后回写；哈希可在分块间取消，线程不接触 Tk。
- “启用 CUDA”选择现有共享 CUDA 偏好并打开配置，不自动下载／安装运行库，也不勾选模型；沿用明确点击的一键安装。RTM DirectML 保留，NeuFlow 仍要求 CUDA。共享后端立即改变，开始窗口启用状态／模型字段仍暂存；CUDA 自检不冒充 NeuFlow 模型实际就绪。
- 模型校验值、设置键／默认、采集／分析／输出计算和两秒估算上限不变。旧 exe／包／运行库不替换，不安装／升级依赖，不连接硬件；Lab 仍为 0.2.2-test。

### 开发检查与修正

首轮定向 **86 项／229.300 秒全部 OK**，但包装器最后指纹断言因用户并行修改旧版设置而失败。用户已确认正在操作；未恢复配置。后续隔离检查通过 Python 审计钩子拒绝本进程写／重命名／删除旧设置、正式源码及旧 2.1.0 归档，保留并单独记录外部用户修改。

随后 19 项中有一项失败、九项错误：新增控件持有的空闲回调经根窗口取消后，子控件仍保留 Tcl 命令记录，关闭时出现真实重复清理错误，现统一由根窗口持有／取消。心跳测试原假定固定 220 ms 内执行三次，现改为实际等到定时进展并保留总超时。再跑 20 项清除清理错误，但出现一项焦点可见性断言失败；原生焦点竞争是初步假设，并非已证实原因。组件测试现生成 FocusIn 而不强占用户键盘，原生交互另测。一次模态定向 **3 项／33.851 秒通过**。

整合后串行套件完成 **523 项／1,428.962 秒，一项失败、零错误**：英文 150% 合成焦点检查发现模型按钮下沿超出滚动视口 13 像素，受保护目录写入尝试为零。随后四种语言／缩放组合一起通过，受控释放模型检测结果也通过；复跑不能抹去原失败，也不能据此认定原因。受控检查中，“检测中”文字变为“模型缺失”并未改变视口、内容尺寸或滚动位置。

另一个有限探针确认了相关布局边界：请求变窄后、尺寸尚未处理完时发送 FocusIn，横向滚动条出现后按钮仍可能落到视口下方。这证明焦点与布局顺序存在可复现缺陷，但不等于精确复现前述完整套件失败或用户原始整窗卡死。

私有开始控制区现延后显示焦点，并在布局完成后重新校正，由根窗口持有可取消回调。滚轮／滚动条操作和控制区外焦点会清除记忆目标，尊重手动滚动；主侧栏实现不变。确定性回归只在待处理缩放前发送一次 FocusIn，保留严格像素可见性断言，并检查手动滚动、外部焦点及销毁清理。

只读审查还发现 A→B 快速改路径可丢失 B 自动检测的防抖竞争，已改为重排当前选择并加回归。未知 Tcl 原生模态抓取直接比较路径，不假定都有 Python 控件对象。开发失败不记为最终通过。

自动检测若在实时／离线分析开始后才完成，原本可能把空的默认模型设置写成绝对路径，误触已有的选项变更停止逻辑。现在自动完成保留活动中的默认选择，仅通过缓存显示已校验路径；显式检测／手选仍应用所选路径。三项无 Tk 回归在 0.021 秒通过，覆盖实时、离线及显式检测，受保护写入尝试为零。

私有启动工具首次在新 exe 启动前拦截了 Windows 的空输入设备；审计现只额外允许规范化后的 `os.devnull`，继续拒绝其他设备／文件，19 项工具回归在 2.632 秒通过，原启动前失败保留。全新重试随后通过新 exe 的依赖／资源／CPU 检查，以及现有外部 RTM Pose CPU、ViTTrack CPU、NeuFlow CUDA 双向光流实际运行；未安装或打包模型／GPU 库。这些合成模型检查不代表视频质量跑分。

### 最终验证

- **主程序 524 项全部通过**，零失败／错误／跳过。同一最终源码快照分三个独立进程串行执行：界面 **227 项／528.219 秒**，非界面 A **146／277.250 秒**，非界面 B **151／467.891 秒**（包装器计时）。524 个实际完成 ID 与发现集合完全一致，无重复／缺失；只有界面组允许建窗，三组受保护目录写入尝试均为零。这是完整分组覆盖，不冒称之前失败的串行完整运行已经通过。
- **Lab 38 项／2.175 秒通过**，模拟器最终命令流检查通过；最终四项模态测试此前亦在 **26.714 秒**通过。私有发布／启动工具回归另计，不混入产品测试数。
- 实际源码 **Start.cmd** 中／英文各 **3 秒 Log only：111／106 次更新**；最终新 exe **110／108 次更新**，均正常停止并退出线程。源码 Lab 为不改 preview.py 的隔离包装烟测，不冒称实际 Lab Start.cmd；包内 exe 的实际 `--preview-lab --smoke` 通过。包内 Lab 无原点参数，显示器位置未核验。
- 华硕副屏原生中文开始确认框：鼠标双勾选后实际校验两模型，打开／关闭 CUDA 设置，取消后主界面两开关关闭、路径仍为空。**72.734 秒内 1,229 次心跳**，最大观测间隔 **0.719 秒**，无回调／关闭错误及超时。此隔离导航检查模拟 GPU 状态调度及配置保存，未启动推理／硬件，不是安装器或帧率跑分。
- 实际源码和最终 exe 通过依赖／资源／CPU 推理、外部 **RTM Pose CPU、ViTTrack CPU、NeuFlow CUDA 双向光流**，复用既有模型／运行库，未执行安装。最终 exe 审查 **89 个自有模块／1,278 个嵌套代码对象**，未发现绝对编译文件名／私人主目录常量；**1,148 个组装前文件**未发现 UTF-8／UTF-16LE 主目录字节。不宣称穷尽第三方压缩代码对象。
- 个人设置隔离、仅观察、不恢复，先前外部变化保留记录；正式源码、共享环境和旧 exe／归档保留。新增联系信息使用 lexzeonstudio@gmail.com，远程 10 月 11 日邮箱提交保留为祖先。

最终 ZIP 解压、实际便携 Start.cmd、文件清单、最终提交／哈希、公开下载及配对归档证据，会在组装本次已提交源码后追加到 GitHub Release 与本地持久归档，不倒填冒充提交前源码检查。

### 局限

有限测试不证明原用户间歇性卡死已消除。慢速／网络文件仍可能耗时，但取消的后台任务不得应用过期结果；本轮不需要实际安装 GPU 库，安装决策用模拟测试，真实推理另行验证。真实硬件、深度／接触及机械臂映射／反馈未验证。
