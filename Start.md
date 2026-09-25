# Start 2.0.0 / 启动 2.0.0

## English

**Double-click [Start.cmd](Start.cmd)** and confirm the official version **2.0.0**. Start.md is the guide; if your editor opens the script as text, double-click Start.cmd in File Explorer. For a bundled runtime, download the Windows.zip asset from the [2.0.0 release](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0), extract the entire folder and double-click its Start.cmd or exe. Keep `_internal` beside the exe. Source startup needs Python 3.10+. The Windows package also includes `Pose-Preview-Lab/Start.cmd`. This release retains test.25's analysis/output behavior and incorporates the verified packaging work; see the [2.0.0 validation record](docs/Validation_2.0.0.md).

The default Hybrid v2 / Fused reference now distinguishes weak subject tracking, learned-rhythm prediction and a short velocity bridge. Dashed A? markers are estimates. Continuation remains limited to two seconds and cannot be extended by isolated detection flashes; explicit pauses, cuts and resets stop the old pattern. Cycle mode only continues confirmed travel. Existing saved settings and the other manual L0 reference modes are preserved.

**Test.24 screen selection:** stop analysis, open the region picker and drag across the desired display area. Teal borders, display numbers, resolution, coordinates and dimensions identify the selection. The selected area stays bright while the surroundings dim. Choose **Use this region / Enter**, **Select again / R**, or **Cancel / Esc**; cancellation preserves the prior region. Narrow displays use a compact button layout.

The picker shows a single in-memory **screen snapshot**, never saved or uploaded. After confirming and closing it, starting analysis captures fresh live frames; the snapshot does not freeze subsequent analysis. X/Y and width/height are physical pixels, including negative coordinates on displays above or left of the primary display. Cross-display gaps are black. Out-of-desktop and gap-only regions are rejected instead of being silently moved.

Stop before editing the region. After unplugging, rearranging or changing a display's resolution, select the region again; a detected change stops the old capture. **Capture** reports the actual screen coordinates and dimensions; **Analysis size** reports the processing image dimensions, with the default longest edge still 640. Preview scaling and letterboxing only change presentation. Standalone **Lab 0.2.2-test** shares these fixes and remains free of device output. Validation and limitations are in the [test.24 guide](docs/Test_2.0.0_test24.md).

Test.23 follows a persistent subject-box center using distributed measurements, with round-trip-verified DIS support for deformation. Yellow marks the tracked motion box, A its center/reference, and green circles the actual support groups. Main and secondary axes share this motion. Camera evidence, saved/default choices and final output processing remain separate. See the [test.23 guide](docs/Test_2.0.0_test23.md).

**Historical test.22 preferences incident:** a development check accidentally overwrote this machine's test preferences. No original backup was recovered. They were reset to factory defaults with Log only; personal connection and travel preferences need re-entry. This was not recovery of the original settings. See the incident record in the [test.22 guide](docs/Test_2.0.0_test22.md).

Select **v2 L0 reference → Fused reference (default)**. Orange T? is an independently tracked object-boundary candidate. It uses its own features and appearance, not a visual match to the mover. Confirmed axis-origin-to-target distance drives L0: farther is higher, estimated 100% reach is bottom before final gains. Source changes continue from the current output.

An offscreen arrow indicates direction only. If the target is unseen, obscured or absent after a cut, L0 follows reciprocal motion of visible objects; it does not wait for either contact participant to appear. Unknown target reach is never displayed as confirmed contact. Only loss of the visible motion itself invokes the existing learned-rhythm continuation, up to 2 seconds with braking in the last 0.5 seconds. Cuts clear old evidence. Quarter/half/full mode shares this reference and retains its travel classes and cosine shape. Saved choices and final output limits remain. See the [test.22 guide](docs/Test_2.0.0_test22.md).

Test.22 first maintains subject anchor **A**, then an independently tracked object candidate **T?**. With no reliable object, **V?** explicitly denotes an assumed endpoint inferred from confirmed subject reciprocation. It is not an observed object or contact percentage. Recovery measures actual subject/background pixels against the last verified frame; intermittent target readiness must settle before taking over L0. No new setting is required; select **Fused reference** if an older reference choice was saved. Strong deformation, sustained blur, occlusion and semantic contact remain limitations.

## 中文

**点击 [Start.cmd](Start.cmd) 运行 2.0.0 正式版主程序。** 如果编辑器只打开文件，请在文件资源管理器中双击同目录的 Start.cmd；Start.md 本身是说明文件。

这是源码目录的说明。想免装 Python，请下载 [2.0.0 发布页](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0) 的 **Windows.zip**，完整解压后双击其中的 `Start.cmd` 或 exe，保留同目录 `_internal`。运行包的独立预览也可通过 `Pose-Preview-Lab/Start.cmd` 打开。每版源码与运行包分别留样，不能混用其他版本的 exe／内部文件。

正式版沿用 test.25 的分析／输出行为，并纳入经过验证的打包支持；见 [2.0.0 验证记录](docs/Validation_2.0.0.md)。

**test.22 历史设置事故：** 当时开发检查曾意外覆盖测试版个人配置，未找到原配置备份。当时已设为项目默认值并使用 Log only；原连接信息、个人行程与偏好需要重新设置。这不是恢复原设置，事故及修正见 [test.22 说明](docs/Test_2.0.0_test22.md#本机验证中的配置事故)。

1. 关闭旧程序，双击 Start.cmd，确认标题 **SR6/OSR6 Realtime Screen TCode v2.0.0**。本源码启动器需要 Python 3.10+；Windows 运行包已自带必要运行环境。
2. 默认仍为混合分析 v2（推荐-非舞蹈），默认打开“输出监视”。先选 Log only，选屏幕区域或视频，再开始分析。
3. “显示预览”打开 3D 模拟器，使用经过倍率、反向、联动和输出限制后的最终指令；“分析预览”显示同帧骨架或实际运动参考。最长边默认 640。
4. 列表第一是全/半行程模式，第二是 RTM Pose 2D。选择 Pose 可看到下面三个开关，主界面、分析预览和启动确认共用保存设置；舞蹈与混合模式分别记忆。

## test.25 短暂缺测接续

使用默认的“混合分析 v2＋融合参考”。画面清楚时仍使用可靠主体与背景测量；短暂参考不足时尝试保留同一主体，**A?／淡色虚框／虚线三轴** 表示弱跟踪或位置估计，不代表新观测。状态会区分弱跟踪接续、已确认节奏预测和短速度接续。

估算最多 **2 秒**，不会因为偶尔识别到一帧而不断续期；没有确认节奏时，稳定速度只能短暂减速延续，不能自动变成往复。持续缺测后保持当前位置，识别稳定恢复后平滑接回。切镜头、明确暂停、重新设置参考或点击停止会结束旧规律。全／半／1/4 行程只续接已经确认的行程。

默认最长边 640、多显示器框选及最终输出倍率保留；独立预览仍为 0.2.2-test。本次无需修改设置，其他三种手选 L0 参考保留原输出语义。见 [test.25 验证与边界](docs/Test_2.0.0_test25.md)。

## test.24 多显示器框选与尺寸核对

先停止分析，再点“框选屏幕区域”。界面会显示各屏编号及分辨率；鼠标可以跨屏拖拽。青绿色框内保持原亮度，框外变暗，坐标和尺寸跟随选框更新。松手后点“使用此区域”，也可按 Enter；“重新选择”或 R 清除本次框选；“取消”或 Esc 保留原区域。按钮会根据屏幕大小调整排列。

框选使用打开时的一次**屏幕快照**，只保存在内存，不保存或上传；确认并关闭框选界面后，再启动分析时读取的是新的实时画面。快照期间视频看起来暂停，是为了清楚选区，并非把后续分析冻结在那一帧。

- X、Y、宽、高都是**屏幕物理像素**，与 Windows 的 100%／150% 等缩放比例分开；左侧或上方显示器的负坐标正常保留。
- 可以跨屏框选，显示器之间没有实际画面的空隙固定填黑。区域不能超出整个桌面的边界，也不能只包含空隙；无效时需重选，不会自动移到主屏。
- 运行中先停止，再改选区或手动坐标。拔插显示器、调整屏幕排列或分辨率后，重新框选再开始；程序检测到这类变化会停止原采集。
- “采集”行显示实际读取的 X/Y 和尺寸；“分析尺寸”是送入处理的图像大小，默认最长边仍为 640；窗口里的预览仅等比例缩放显示同一画面，留黑不代表多读或漏读了屏幕区域。

主程序与独立预览 **0.2.2-test** 共用屏幕坐标与框选逻辑。采集修正不改变 v1、v2、Pose 的输出倍率或设备算法。完整验证和适用边界见 [test.24 说明](docs/Test_2.0.0_test24.md)。

## 设备输出失败提示

设备未接入、断开或写入失败时，会停止实时输出并弹窗显示具体原因。请检查连接后重新连接；无设备时选择 Log only。程序不会自动重发失败指令，分析／采集错误也不会误报成设备未接入。

## test.23 主体框与中心运动

恢复默认后选择混合分析 v2，打开“分析预览”：黄框表示主体运动框，**A** 是持续跟踪的框中心／参考点，主轴、副轴从同一中心的运动分解。绿色采样组共同参与估计；明显变形时显示“主体框中心”。窗口拖动等刚性画面仍使用精确跟踪。

多点不足时才补充验证过的 DIS 光流；不会因为刚好换了一批角点，就把新的角点平均位置当成主体跳动。原有融合参考、独立目标、最多 2 秒的已确认规律延续，以及全／半／1/4 行程共用逻辑。最长边仍默认 640，所有最终输出倍率与模拟器链路保留。

请优先比较主体框是否持续跟随、A 的上下／左右方向是否贴合，以及输出监视的最终脚本。不是所有变形、遮挡或快速模糊都能恢复；没有独立运镜证据时仍可能保持。版本差异与本轮验证见 [test.23 说明](docs/Test_2.0.0_test23.md)。

## v2 三维运动轴

**test.22 先跟主体，再找客体：** 将 **v2 L0 参考** 选为 **融合参考（默认）**。**A** 是主体上的同一跟踪点，也是三轴原点；test.23 的黄框改为持续跟踪的主体运动框，绿色点显示实际采样。主体短暂模糊／丢点后，尝试从最近可靠画面重新匹配整个缺失区间，不只接上最后一帧的位移。只有真实图像重新匹配成功才恢复观测。

- **橙色 T?：独立客体候选。** 用客体自己的图像特征跟踪；主体短暂丢失时，若客体仍可验证就保持同一身份。二者均可靠时才更新到达比例，A 到达 T? 为估计 100%，对应输出倍率前 L0 底部。
- **浅黄色 V?：假定客体。** 没有可靠客体时，由主体已确认的往复方向、中心与幅度推定端点，继续按主体相位生成 L0。它不是实测客体，不显示实际到达百分比；远近方向无法确认时会提示。
- **暂缺测时：** 明确标为保持／预测。目标重新稳定后再从当前输出接入，避免有效／失效交替把脚本锁住。没有经过确认的往复，不会凭空启动规律；已确认规律仍最多延续 2 秒，最后半秒减速。

本轮没有新增开关，也没有修改产品的保存／默认规则。其他安装若保存了不同参考，需手动选择融合参考体验完整流程；本机配置例外见上方事故说明。全／半行程和可选 RTM 旋转辅助共用改动。真实语义客体、强变形、持续模糊和长遮挡仍需实片复测。

test.18 按“当前往复 → 曾经往复且仍能跟踪 → 当前持续幅度最大”选择实际区域，黄框和三轴随区域移动；新增快速小区域验证，减少可靠运动被误重置。此前重复帧保持和稳定局部跟踪继续使用。

**保留的独立目标与到达比例：** 打开“分析预览”，把 **v2 L0 参考** 选为 **融合参考（默认）**。橙色 **T?** 从运动轨迹朝向的独立物体边界选点，用该物体自己的多组特征跟踪，不要求它和运动物体外观相似。目标确认后，按“三维轴原点到橙点”的距离比例接续 L0：远离时大、靠近时小，估计到达 100% 对应分析 L0 底部。切换参考从当前位置接续。

**目标不在画面内也能分析：** 已知目标移出画面后，仅短暂保留由可靠运镜修正的位置，边缘箭头只指方向，不把边缘当作到达点。目标未确认、遮挡或切镜头后接触双方都没出现时，使用画面里可见物体的往复；优先当前持续往复，其次曾往复且仍能跟踪，再其次当前持续幅度。不会等到橙点出现才开始分析，也不会把代理运动百分比写成实际到达百分比。旧参考选择仍保留，需手动切换一次。

**E?／S?／P?** 以灰色区分轨迹端点、缩放中心和光流会聚参考；它们不是独立接触目标。T? 也只是几何候选，不能确认真实接触。

主轴保持连续运动，中心 C 校准往复相位，可靠径向证据确定远近方向：远离参考点 L0 大、靠近 L0 小。绿色小圆显示多组有效采样。未确认远近时会明确提示。

**识别不清时延续：** 只沿用之前已经确认的稳定往复，最多 **2 秒**，最后 **0.5 秒**渐慢并停在当前位置。画面明确标为预测，不会伪造观测；暂停、切镜头和重设参考停止旧规律。再次识别后从当前输出接续。全／半行程也共用这一融合与延续逻辑，并保留 1/4、半、全行程。最终行程倍率、反向和限制继续生效。

- 选择混合 v2 后打开“分析预览”。主轴是左右、上下、画面尺度共同形成的连续方向，可以倾斜，不再是三选一。
- 主体区域显示三条彩色轴，下方图表右侧有立体方向小图：青色 L0/R0 为主方向，紫色 L1/R1、金色 L2/R2 为两个垂直方向；箭头为正向，反向线对应负向。轴组以主体跟踪点 A 为原点，黄框随实际采样区域更新。
- L0 沿主轴，L1/L2 沿附属方向。R0/R1/R2 的变化也相对这组轴表达；开启 RTM 辅助时使用骨架旋转信号，否则使用画面旋转近似。方向不足或冲突时保持参考，切镜头与重设参考清除旧历史。
- 全／半行程共用三维主轴上的往复幅度和节奏，仍输出 1/4、半或全行程；该模式 L1/L2 仍居中。五档、行程倍率和最终输出限制继续在后续应用。
- 三维轴是画面运动坐标，S 表示尺度变化，不能理解成真实空间深度或机械臂关节轴。无需新增开关；保存的分析模式与恢复默认仍使用 v2。

## Pose 保留设置

- **快速丢点时用混合 v1：默认开启。** 开启后 v1 持续分析同一批画面。近期有效 Pose 丢失且 v1 测到快速画面运动时，从当前输出位置接续 L0，只采用接管后的变化，不跳到 v1 自己累计的位置；恢复 Pose 后平滑交回。其他轴不改成 v1 分析，回退 L0 不乘 Pose 的 10 倍。未建立 Pose、静止缺失或切镜头不会单凭缺失启用。

- **L0 静止／小幅时自动生成：默认开启。** L0 静止，或 L0 幅度小而旋转明显更大时，先采用 R1，再采用 R2；各自中点对应 L0 的 1/3，两端对应 L0 的 2/3。R1/R2 无变化但其他识别轴仍有有效运动时，才生成 **1/4～1/2、峰到峰固定 1 秒的余弦波**。实际 L0 恢复足够幅度后平滑交回识别。所有识别轴静止或缺失时，不启动兜底波；已启动则保持当前位置，不继续走波。只在分析运行中生效。
- **小幅往复渐放大：默认关闭。** 仅 L0、R0、R1 各自确认约三个稳定的小幅往复，L1/L2/R2 不参与；确认后，约一秒渐增至最多 2 倍（放大速度为原来的 4 倍）；实际幅度变大、节奏中断或丢失观测时平滑退出。自动生成的 L0 不参与 pattern 检测或放大。
- 余弦波从切换前的输出位置续接：范围内选择对应相位，范围外先平滑进入 1/4～1/2，随后继续固定 1 秒周期，不跳到预设波峰。
- **L0 端点复位：须胯线明显向上才触发。** 仅停留、向下或微抖不触发识别复位。当前要求双胯点有效、上移达到画高约 2%；回中用约 0.35 秒，并重设 L0 输出参考。原有输出保护与手动回中保留。
- **R0 基础幅度 ×3**；直接 Pose L0 保持 ×10，Pose R1/R2 保持 ×1.5。自动生成 L0 不重复乘 ×10，用户倍率与输出限制继续生效。
- Pose 设备 L0→L1/L2 联动按最终受限的 L0：**底部 0.5 倍 → 1/3 处 1 倍 → 2/3 处 3.5 倍 → 顶部 0.5 倍**，点间线性变化。固定 L1/L2 识别位置也随 L0 收拢／展开。

- **Pose 的 R1/R2 也跟随最终 L0 收拢：底部至 2/3 处保持 1 倍，顶部降至 0.5 倍，之间线性变化。** R1/R2 基础倍率仍为 1.5，R0 不参与这项收拢。

“分析预览”会分别显示 L0 自动来源、正在使用的逐轴放大倍率、端点复位次数。观测图表仍是识别数据。自动波形的理论幅度／周期是后续用户行程倍率、限制与末端减速之前的参数，最终输出可能不同。

## 保留的操作

- 舞蹈默认四项处理全开，混合 L0 默认关；开启后来源只用 v2。RTM 2D 旋转辅助只在混合／全半模式显示。
- 五档只改变最终脚本／实时输出的行程幅度，不改变分析。3 档为原幅度。
- 全/半行程直接复用 v2，根据往复幅度生成底→1/4→底、底→中→底或底→高→底的余弦曲线，并逐步匹配节奏。可选 Pose 旋转辅助，L1/L2 居中。
- v2 保留 test.12 的小背景和快速窗口跟踪改进。读屏拖动窗口时保留窗口外背景；黄框／绿点应跟随主体、蓝点应留在背景。参考认反时点“重设参考”。无有效独立背景时仍可能保持。
- **接近上下限时减速**默认开、距离 10%，只延长到达时间，不限制目标位置；导出脚本可能比视频更长。到达时间下限默认 24 ms，实时参考实际更新间隔，它不是发送频率开关。

多显示器功能、验证结果和复测方法见 [test.24 说明](docs/Test_2.0.0_test24.md)。独立实验预览仍可从 [Pose-Preview-Lab/Start.cmd](Pose-Preview-Lab/Start.cmd) 打开，当前版本 **0.2.2-test**，同步本轮多屏框选和采集修正，仍不输出设备指令。

2.0.0 运行包验证记录见 [2.0.0 说明](docs/Validation_2.0.0.md)。持续运行 v1 会增加处理开销，三维方向、目标估计与预测延续的实片效果和真实设备仍需复测。
