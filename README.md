# SR6/OSR6 Realtime Screen TCode

## English

Windows and source prerelease: **2.0.0-test.26**, named **SR6/OSR6 Realtime Screen TCode**, for visual-analysis and robot-arm simulation experiments. Existing SR6/OSR6 TCode serial/BLE transport remains. **Robot-arm joint mapping, inverse kinematics, collision checking and physical feedback have not been implemented or verified.**

Other commercial-device adapters, discovery and custom bindings have been removed; legacy settings migrate to Log only. V2 includes persistent subject tracking and bounded brief-loss continuity, shared with confirmed quarter/half/full travel. RTM 2D base L0 output is multiplied by ten about center, before user travel and output constraints; this applies to live/record/export, not pose observations or v2.

Download the **Windows.zip** asset from the [test.26 release](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0-test.26), extract the entire folder and double-click its **Start.cmd** or exe. Keep `_internal` beside the exe; no separate Python installation is required. Its `Pose-Preview-Lab/Start.cmd` also uses the bundled runtime. For source development, the repository's **[Start.cmd](Start.cmd)** still requires Python 3.10+; [Start.md](Start.md) explains source startup. Begin with **Log only**. A legacy center command is not a validated safe robot-arm pose.

**Output Monitor** is the initial tab. **Show Preview** opens the bundled reference simulator, which receives final output after all host travel gains, coupling, inversion, limits and speed caps. **Analysis Preview** retains the paired sampled frames. Neither display is hardware feedback.

Full/Half Travel is listed first, followed by RTM 2D; Hybrid v2 remains selected by default. Dance defaults to 45 FPS, curve fitting on, GPU off, all four pose options on, L0 blending off at 30%, and compression latency 0. Dance and hybrid settings are saved separately. The L0 source label is shown only when dance blending is enabled and uses v2 only. The v2 rotation-assistance switch is hidden in dance and disabled in Hybrid 1.

Hybrid 1 retains its original L0 core. V2 tracks the same subject with multiple samples and independently checks background motion. Confirmed reciprocal strokes calibrate L0 travel. With the default fused reference, brief loss can use weak tracking or an already confirmed rhythm for **at most 2 seconds**, then hold; an unconfirmed velocity bridge is limited to 0.3 seconds and 15% travel before gains. Pauses and cuts stop old estimates. Actual samples and estimated **A?** markers are shown separately. Five presets affect final script/live travel only. Max edge stays 640.

Direct RTM Pose 2D L1/L2 output coupling passes through four points: **0.5× at bottom L0, 1× at 1/3 travel, 3.5× at 2/3, and 0.5× at top**, with linear interpolation between them. V2 retains **1 / 2.5 / 1**, peaking at center. Pose rotation base gains are **R0 ×3, R1/R2 ×1.5**, including Pose rotation assistance; direct Pose R1/R2 also follow L0 with 1× coupling through 2/3 travel, falling to 0.5× at the top. Original footage and physical hardware remain unverified; standalone Lab **0.2.2-test** shares screen selection and physical capture coordinates without device output.

Test.26 provides matching Windows/source archives with a commit manifest and SHA-256 checksums. GitHub's automatic source archives require Python; use the Windows asset for a bundled runtime. Previous releases retain their original assets. Models and optional GPU runtimes are not bundled. See the [test.26 guide](docs/Test_2.0.0_test26.md), [preview guide](Pose-Preview-Lab/Start.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [license](LICENSE).

Thanks to **DK**, **机械纪元**, and **“电话机”** for guidance, volunteer testing and suggestions. Contact: **aivnailedeng@gmail.com**.

## 中文

不带 RTM 的 v2 对 L1/L2/R0/R1/R2 只跟随确认后的明显变化与方向反转，过滤小幅高频噪声并平滑输出；L0 不受此过滤影响。

Without RTM, v2 secondary axes follow confirmed significant motion/reversals and produce smooth output; this filter never changes L0.

默认分析方式为混合分析 v2（推荐-非舞蹈），RTM 2D 旋转辅助默认关闭；恢复默认同步，已有保存的分析选择继续保留。

Default analysis is Hybrid v2 (Recommended Non-Dance), with RTM 2D rotation assistance off. Reset restores these defaults; existing saved mode selections are preserved.

## Windows 与源码预发布版

当前版本：**2.0.0-test.26**。本测试分支用于视觉分析与机械臂模拟实验，保留现有 SR6/OSR6 TCode 串口/BLE 接口。**尚未实现或验证机械臂关节映射、逆运动学、碰撞检测和真实位置反馈，不能当作已兼容机械臂的控制器。**

此前已移除其他商业设备适配、外部设备服务扫描和自定义功能绑定；旧外部设备配置迁移到 `Log only`。test.12 针对主体占大部分画面的 v2 背景缺失改进运动分层；保留全/半行程、最终时序减速和 RTM Pose 2D 的 L0 基础输出 ×10。原有输出限位与限速继续生效。

本版本提供配套的 **Windows 免安装包和源码包**，项目名称为 **SR6/OSR6 Realtime Screen TCode**。在 [test.26 发布页](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0-test.26) 下载名称以 **Windows.zip** 结尾的附件，完整解压后双击包内 `Start.cmd` 或 `SR6-OSR6-Realtime-Screen-TCode.exe`；不需要另装 Python。不要单独移走 exe 或 `_internal` 文件夹。源码包与运行包对应同一提交，附版本清单与 SHA-256 校验；旧发布包保留原版本。

## 一键运行

**普通用户使用 Windows 包：** 解压完整目录后双击包内 **Start.cmd** 或 exe。`Pose-Preview-Lab/Start.cmd` 打开独立预览，也无需外部 Python。

**开发者使用源码：** Windows 下双击仓库根目录 **Start.cmd**。需要可用 Python 3.10+；启动器会复用已安装环境，或在本目录建立环境并安装依赖。不会向相邻正式仓库环境安装依赖。

[Start.md](Start.md) 是操作说明，不是可执行启动文件；如果链接只显示源码，请在文件资源管理器中双击同目录的 [Start.cmd](Start.cmd)。

先使用 `Log only`，不连接硬件。实际机械结构的关节定义、限位与独立急停需要另外验证；现有回中动作不能视为机械臂的安全姿态。

## 软件内分析预览

**test.26：Windows 运行包与配套源码留样。** 补齐独立 Lab 的打包入口与单独设置目录，以及音频回环所需资源；每个发布版本分别保留源码、运行包、构建清单和校验值。主程序分析与最终输出算法沿用 test.25，估算仍最多 2 秒。验证与打包边界见 [test.26 说明](docs/Test_2.0.0_test26.md)。

**test.25：短暂缺测的主体与脚本接续。** 默认融合参考先尝试基于真实像素的弱主体跟踪，再使用已确认的节奏估算；节奏尚未确认时，只允许近期稳定速度短暂减速接续，不凭空生成往复。估算仍最多 **2 秒**，单帧识别闪回不会续期，明确暂停／切镜头会停止旧规律。淡色虚框、虚线轴和 **A?** 表示弱跟踪或位置估计；实际测量与估算分别标注。全／半／1/4 行程共用，只续接已经确认的行程。没有新增开关或更改个人设置；详见 [test.25 说明](docs/Test_2.0.0_test25.md)。

Test.25 improves brief-loss continuity for the default fused reference: pixel-supported weak subject tracking, learned-rhythm prediction, or a short decelerating velocity bridge when no cycle has been confirmed. Prediction still expires within **2 seconds**; isolated reacquisition flashes cannot renew it. Pauses and cuts stop the old pattern. Dashed **A?** markers distinguish estimates from measured subjects. Cycle mode only continues an already established travel pattern. No new settings are required; see the [test.25 guide](docs/Test_2.0.0_test25.md).

**test.24：框选、采集和预览统一使用屏幕物理像素。** 修正把虚拟桌面尺寸当成单屏缩放倍率，以及把左侧／上方显示器负坐标改成 0 的问题。不同分辨率、横竖屏和混合 DPI 使用同一坐标基准；支持跨屏框选，显示器之间没有画面的空隙固定为黑色，越界或纯空隙选区会提示重选。

新的青绿选框使用深色卡片、屏幕编号和分辨率、尺寸／坐标及“使用此区域／重新选择／取消”按钮。选框内明亮、框外变暗，窄屏自动调整按钮排列。框选界面是打开时保存在内存中的一次**屏幕快照**；确认区域后，启动分析时重新实时采集，不把快照用作后续分析，不保存或上传这张快照。先停止分析再修改区域；运行时显示器布局或分辨率改变会停止采集并提示重新框选。

“采集”坐标与尺寸表示真正读取的屏幕像素；“分析尺寸”表示处理用图像大小；预览只是把同一画面等比例缩放到窗口，缩放和留黑不改变采集边界。处理最长边默认仍为 640。独立预览同步至 **0.2.2-test**。详细验证及局限见 [test.24 说明](docs/Test_2.0.0_test24.md)。

Test.24 uses physical desktop pixels throughout selection, capture and preview, retaining negative display origins and supporting mixed DPI, portrait displays and cross-monitor regions. Desktop gaps are black; out-of-bounds or gap-only regions are rejected. The opaque dark picker shows a bright selected area, teal borders, display labels, exact coordinates and three clear action buttons. It uses one in-memory screen snapshot; starting analysis after confirmation captures fresh live frames. Stop analysis before changing the region; a display-layout or resolution change stops capture and requires reselection. Capture dimensions, analysis dimensions and preview scaling have separate meanings; the default processing edge remains 640. The standalone lab is now **0.2.2-test**. See the [test.24 guide](docs/Test_2.0.0_test24.md) for validation and remaining limits.

**test.23：借鉴 1.1.2 的区域光流，跟踪主体框中心。** v2 对变形主体使用多组采样共同估计中心运动，必要时以经过正反向验证的 DIS 光流补点；主轴与副轴来自同一中心轨迹，避免改选小块区域时跳点。背景仍独立验证，可靠的画面尺度变化与变形噪声区分处理，保持所有最终输出设置。v1 与发布版在相同参数下的核心数值对照、默认参数差异和验证边界见 [test.23 说明](docs/Test_2.0.0_test23.md)。

Test.23 borrows the released v1 ROI-flow approach for a persistent subject-box center, spatially balanced samples and verified DIS support when the subject deforms. Main and secondary axes share that center trajectory. Camera ownership and final output processing remain separate. See the [test.23 guide](docs/Test_2.0.0_test23.md) for the v1 numerical audit, default differences and validation limits.

**test.22：主体 → 客体 → 假定客体。** 三轴原点 **A** 跟随主体上的同一图像位置；短暂丢点后从可靠旧画面重测完整位移，减少跳点与漏算。独立客体候选 **T?** 使用自己的图像跟踪；没有可靠客体时，以已确认的主体往复推定 **V? 假定客体**，不会显示为实测接触。修复目标反复有效／失效导致 L0 锁在一点的问题，恢复目标须持续稳定，期间继续跟随主体。详见 [test.22 说明](docs/Test_2.0.0_test22.md)。

Test.22 anchors **A** to the same tracked subject location, independently tracks object candidate **T?**, and labels **V?** as an assumed object inferred from observed reciprocation. A verified earlier frame can recover missed subject displacement. Intermittent target recovery no longer repeatedly restarts the output transition and pins L0. See the [test.22 guide](docs/Test_2.0.0_test22.md).

**test.21：** 融合参考的橙色 **T?** 改为独立物体边界候选，用它自己的多点跟踪，不要求与运动物体外观相同。目标可靠时按三轴原点到目标的距离比例接续 L0，估计到达 100% 对应分析底部。目标画外、遮挡或切镜头后接触双方均不在画面时，继续分析可见物体的往复；不显示虚假的到达比例。灰色 E?/S?/P? 仅是轨迹／会聚参考。详见 [test.21 说明](docs/Test_2.0.0_test21.md)。

Test.21 gives orange T? its own object-boundary candidates and multi-point tracking. Confirmed axis-origin-to-target distance controls L0; estimated 100% reach means bottom before final gains. Unseen targets and cuts with neither contact participant visible use measured reciprocal motion of visible objects instead. Offscreen arrows indicate direction, never an arrival position. E?/S?/P? remain gray geometric references. See the [test.21 guide](docs/Test_2.0.0_test21.md).

**test.20：** 修正目标总贴着三维轴的误导：**E?** 表示轨迹端点，**S?** 表示区域内缩放中心，**T?** 才表示区域外的会聚目标候选，仍未确认真实接触。单帧证据不足时，通过已有短时历史图像重新跟踪前景与背景，提高远处目标的定位支持；不把几帧位移重复计入 L0。设置与最终输出链路保留。详见 [test.20 说明](docs/Test_2.0.0_test20.md)。

Test.20 separates trajectory endpoints (E?), local expansion centers (S?) and external convergence candidates (T?, contact unconfirmed). A checked longer frame pair can locate distant candidates when single-pair evidence is weak. It never reintegrates multi-frame displacement into L0. See the [test.20 guide](docs/Test_2.0.0_test20.md).

**test.19：** 在 **v2 L0 参考 → 融合参考（默认）** 使用主轴连续运动、往复中心相位和可靠交互候选共同生成 L0。方向确认后远离目标 L0 大、靠近 L0 小。采样圆点显示同一区域的多组有效支持。识别不清时仅沿用已确认的规律，最多 **2 秒**，最后 **0.5 秒**减速停住；明确暂停、切镜头和重设参考停止延续。旧参考选择保留，已有保存的选择不会强制改动。详见 [test.19 说明](docs/Test_2.0.0_test19.md)。

Test.19 adds the default fused L0 reference, aligned near/far polarity, an estimated T? target and spatially balanced multi-point support. Unclear tracking continues only a confirmed rhythm for up to 2 seconds, braking over the last 0.5 seconds. Pauses, cuts and recalibration stop continuation. Existing saved references remain selected. See the [test.19 guide](docs/Test_2.0.0_test19.md).

**test.18：** v2 区域选择按“当前往复 → 曾往复且仍在跟踪 → 当前持续幅度最大”，并改善快速小区域被误重置。新增 **v2 L0 参考**：默认三维运动轴、往复中心点 C、交互点候选 P?（实验）。点来源从当前目标续接，最终行程倍率继续生效；P? 不确认真实接触。全／半行程共用区域与往复证据。详见 [test.18 说明](docs/Test_2.0.0_test18.md)。

Test.18 prioritizes reciprocal regions and adds optional stroke-center and interaction-candidate L0 references, with continuous source transitions and unchanged final output processing. P? is a geometric candidate, not confirmed contact. See the [test.18 guide](docs/Test_2.0.0_test18.md).

**test.17：** 设备未接入或写入失败时，停止实时输出并弹窗提示连接问题与具体错误，不自动重试发送。v2 对重复视频帧保持参考，补充相邻运动一致性和稳定局部区域跟踪，改善变形主体的“局部运动群不稳定”；全／半行程共用。详见 [test.17 说明](docs/Test_2.0.0_test17.md)。

Test.17 reports device connection/write failures in a dialog and stops output. V2 retains references across repeated video frames and validates locally coherent deforming subjects, tracking a supported local patch when necessary. Cycle mode shares the fixes. See the [test.17 guide](docs/Test_2.0.0_test17.md).

**test.16：** 修正小幅斜向往复漏判和起始位置依赖；全／半行程按主轴每秒运动判断活跃，避免高帧率误停。保留双向幅度门槛，并过滤零碎抖动累计出的假往复。详见 [test.16 说明](docs/Test_2.0.0_test16.md)。

Test.16 fixes small oblique strokes and phase-dependent startup. Cycle activity uses source-time speed along the main axis, with reciprocal and jitter rejection retained. See the [test.16 guide](docs/Test_2.0.0_test16.md).

**test.15：** 混合 v2 改为连续三维运动轴（左右、上下、画面尺度），不再在三个单独方向之间选择主轴。L0 沿主轴，L1/L2 沿两个相互垂直的附属方向；旋转变化也相对这组轴表达。全／半行程共用沿主轴的往复幅度与节奏。分析画面显示实际采用的彩色轴和立体方向小图，详见 [test.15 说明](docs/Test_2.0.0_test15.md)。

Test.15 fits a continuous local 3D motion frame in image-proxy coordinates. L0 follows the primary direction, L1/L2 the orthogonal transverse directions, and rotation-proxy changes use the same frame. Cycle mode shares its projected stroke evidence. The analysis preview draws the actual frame; image scale is not physical depth. See the [test.15 guide](docs/Test_2.0.0_test15.md).

**test.14：** Pose 开启 v1 接管后，v1 持续分析同批画面；接管从当前输出位置开始，只续接后续变化，避免追向 v1 自己的累计位置。小幅往复确认后的放大速度提高至原来的 4 倍，约 1 秒达到最多 2 倍；其余判定与默认值保留。实时指令与导出均已接入，详见 [test.14 说明](docs/Test_2.0.0_test14.md)。

Test.14 keeps v1 warm alongside Pose and anchors handoff at the current output before following relative changes. Confirmed small-cycle expansion now reaches 2× in about 1 s, four times faster. See the [test.14 guide](docs/Test_2.0.0_test14.md).

**test.13：** Pose 快速丢点默认回退原混合 v1 的 L0，有快速画面运动证据才启用，恢复后平滑交回。Pose 新增默认开启的自动 L0：静止或 L0 幅度小、旋转明显更大时先用 R1，再用 R2；R1/R2 无变化但其他识别轴仍有有效运动时，才生成 1/4～1/2、固定 1 秒周期余弦波。新增默认关闭的L0/R0/R1 逐轴小幅往复渐放大，实际幅度变大时退出。L0 卡端点须胯线明显上移才触发识别复位。Pose R0 基础幅度 ×3；设备 L1/L2 联动为底部 0.5、1/3 处 1、2/3 处 3.5、顶部 0.5，点间线性变化。Pose R1/R2 从 L0 底部到 2/3 处为 1 倍，顶部收拢至 0.5 倍。设置保存／恢复默认、实时与导出同步，详见 [test.13 说明](docs/Test_2.0.0_test13.md)。

Test.13 adds default-on Pose L0 generation for still/small L0 with stronger rotation, and default-off independent expansion of small repeated L0/R0/R1 strokes (L1/L2/R2 excluded), releasing when real amplitude grows. No fallback wave starts when all observed axes are still/missing; an existing wave holds its current position. Endpoint reference recovery requires clearly upward hips. Pose R0 base gain is ×3; hardware translation coupling connects (0, 0.5), (1/3, 1), (2/3, 3.5), (1, 0.5). See the [test.13 guide](docs/Test_2.0.0_test13.md).

**test.12：** 针对读屏快速拖动窗口时丢失背景，v2 增加细尺度跟踪、外围独立采样和可靠图块补匹配；一致的大位移不再只因超过 6% 就重置。全/半行程共用修正，预览显示候选背景被拒绝的具体原因。Pose L0 基础输出 **5→10 倍**，R1/R2 **2→1.5 倍**；L1/L2 联动仍为 **0.5／3.5／0.5，峰值在 L0 的 2/3 处**。验证及限制见 [test.12 说明](docs/Test_2.0.0_test12.md)。

Test.12 improves fast window/foreground tracking with independent perimeter samples, fine-scale flow and verified patch recovery. V2 and Full/Half Travel share the change. Direct Pose L0 base gain is now ×10, with pose-derived R1/R2 ×1.5. The live TCode arrival time follows observed update cadence with the configured minimum (24 ms by default), before endpoint slowdown; it does not set the send rate or change target coordinates.

Test.10 renames v1 to Recommended - Large Planar Motion without changing its algorithm. V2 adds background-band support, tracked-background continuity and brief-loss reference retention, borrowing v1's three-frame median filtering after camera compensation. Full/Half Travel adds a more sensitive quarter-travel output cycle.

第一项 **全/半行程模式（基于混合分析）**：直接复用 v2，按往复幅度自动生成底→1/4→底、底→中→底或底→高→底的余弦曲线，周期逐步匹配画面节奏；可选 RTM 2D 旋转辅助，L1/L2 居中。v2 已改进稀疏／模糊背景和靠边主体的筛选，缺失时显示具体原因及特征点数。

分析方式下新增 **接近上下限时减速**（默认开启、距离 10%，可调 1–50%）：最终输出只延长到达时间，目标位置不变。录制／导出可能比原视频更长，关闭恢复原时序；模拟器收到同一最终 TCode 坐标和时间。

Test.9 adds Full/Half Travel on the shared v2 pipeline, with automatic half/full cosine strokes, gradual cadence adaptation and optional RTM 2D rotations. V2 handles sparse/blurred background references and edge subjects more reliably and displays missing-reference reasons. Final-output approach braking defaults on with a 10% zone; it changes arrival time only, preserving target positions. Exported scripts may run longer than their video.

默认打开 **输出监视** 页。**显示预览**打开内置的 [nb-3d-simulator](https://github.com/nbnb9527/nb-3d-simulator) 参考模拟器，显示经过总行程／逐轴倍率、反向、联动、限位和限速等处理后的最终输出指令。“分析预览”页保留同一采样帧的原始／处理后画面。两种显示都不是硬件反馈。

- RTM Pose 2D 移植了 Lab 0.2.1 的四项可选稳定处理、切镜头／断帧重置和异常预测端点隐藏；需要本地 256x192 ONNX 模型。RTM Pose 3D 已移除。
- 混合分析 1 标为“推荐-平面大幅动作”，保留原有 L0 核心。**混合分析 v2 标为非舞蹈推荐**，持续跟踪同一主体并独立验证背景运镜。默认融合参考遇到短暂缺测时，可用弱跟踪或已确认节奏接续最多 **2 秒**，随后保持；未确认节奏的短速度接续仅限 0.3 秒／倍率前 15% 行程。暂停或切镜头会停止旧估算。确认有效双向往复后逐步校准 L0 行程，五档仍只改最终输出。持续双向运动确定三维主轴方向，六轴 L1/L2 分析相对主轴的横向分量，方向改变不会重映射旧位置。
- v1/v2 在分析画面中显示实际采用的黄框区域、绿色采样点／运动箭头；v2 另显示蓝色背景参考点、主方向、往复跨度和校准倍率。右侧参考画面不被说明遮挡。这里的 L0 是输出倍率前的分析值。
- **RTM Pose 2D 的 L0 基础输出幅度为原来的 10 倍**，相对中位放大，单／六轴、实时／录制／导出都生效；后续用户倍率与输出限制照常作用，骨架观测不变，混合分析 v2 不重复使用此舞蹈倍率。
- Pose 提供的旋转基础倍率为 **R0 ×3、R1/R2 ×1.5**（R1/R2 为此前 2 倍的 75%），直接 Pose 和混合／全半模式中的 Pose 旋转辅助同步生效。直接 Pose 的 R1/R2 另外跟随 L0 联动：底部至 2/3 行程保持 1 倍，之后线性降至顶部 0.5 倍。
- **到达时间下限 ms** 默认为 24，保存／恢复默认沿用原设置。实时 TCode 的到达时间还参考最近实际更新间隔，再应用上下限减速；20 ms 并不表示降低发送频率。模拟器继续接收最终指令。此节奏修正尚未经过实机微抖复测。
- **五档只调整最终录制、导出脚本和实时输出幅度**（0.55 / 0.75 / 1 / 1.15 / 1.30），不改变分析方法或识别处理。
- 全/半行程模式排在列表第一，RTM Pose 2D 第二，默认选中项仍为 v2。舞蹈默认 45 FPS、曲线拟合开、GPU 关、四项骨架处理全开、混合 L0 关且权重 30%、压缩延迟 0；混合分析的四项处理默认关。两组设置分别保存与恢复默认，已有明确保存的选择保留。最长边仍为 640。
- 舞蹈启用混合 L0 后才显示来源，来源只保留 v2。v2 旋转辅助项在混合分析 1/v2 和全/半行程模式显示，v1 中禁用，舞蹈隐藏。
- RTM Pose 2D 六轴 L1/L2 仅在 TCode 输出处应用联动：L0 最低处 **0.5 倍**，**1/3 处 1 倍**，**2/3 处最高 3.5 倍**，最高处回到 **0.5 倍**，相邻节点之间连续线性变化。采用当前指令已受限的 L0，固定识别位置也会随之收拢或展开。v2 的图像平移联动保持 **1／2.5／1**、峰值在中位。骨架、图表和脚本分析数据不受此倍率影响。
- 图表显示画面位移与尺度，尺度不是实际深度；运镜和缩放也会影响数值。
- 独立 `Pose-Preview-Lab/Start.cmd` 当前为 0.2.2-test，使用同一套多屏框选与采集坐标；其自身仍不输出设备指令。

详细操作见 [Start.md](Start.md) 和 [test.24 说明](docs/Test_2.0.0_test24.md)。

## 模型与运行环境

模型不随源码提供。主程序保留本地模型选择、下载/检测和可选 GPU 运行环境功能；独立预览目前使用 CPU。可下载组件与驱动的实际支持情况以检测结果为准，不保证启用 GPU 必然更快。

发布时不得包含本地模型、可下载 GPU 运行库、缓存、个人设置或日志。源图像在本地处理，模型及依赖下载需要网络。

## 文档

- [test.26 Windows 运行包与版本留样](docs/Test_2.0.0_test26.md)
- [test.25 短暂缺测接续、验证与边界](docs/Test_2.0.0_test25.md)
- [test.24 多屏框选、采集与预览](docs/Test_2.0.0_test24.md)
- [test.12 变更与范围](docs/Test_2.0.0_test12.md)
- [预览操作与限制](Pose-Preview-Lab/Start.md)
- [接口范围](docs/Device_Compatibility_2.0.md)
- [开发指南](AI_Prompting_Guide.md)
- [第三方声明](THIRD_PARTY_NOTICES.md)
- [许可证](LICENSE)

历史版本日志和旧发布包描述的是当时的功能，不代表本测试版仍提供那些适配。旧演示图不再用于当前 README。

## 鸣谢与联系

感谢 **DK**、**机械纪元** 的技术指导，以及 **“电话机”** 的志愿测试与建议。保留所用开源组件的原始署名，详见第三方声明。

合作、版权和反馈：**aivnailedeng@gmail.com**
