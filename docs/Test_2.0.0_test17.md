# 2.0.0-test.17：设备失败弹窗与视频参考保持

双击根目录 [Start.cmd](../Start.cmd)，确认标题 `2.0.0-test.17`。[Start.md](../Start.md) 提供可点击入口。此前三维主轴与小幅往复改动见 [test.15](Test_2.0.0_test15.md)、[test.16](Test_2.0.0_test16.md)。

## 设备输出失败

- 设备写入失败时停止实时输出，由主界面弹出“设备输出失败”。说明设备可能未接入、连接中断或写入超时，并保留异常类型和原始错误文字；提示检查后重新连接，无设备时选择 Log only。不能单凭写入失败认定设备一定被拔掉。
- 串口未连接、串口只写入部分指令以及 BLE 未连接都会报错，不再静默当作写入成功。连接失败、连接超时也明确提示未能接入设备。
- 失败连接标为不可用，需要用户重新连接；不自动重发失败指令，不自动改用 Log only 开始输出。用户选择的输出方式仍保留。
- 失败指令不会转发到模拟器。带原连接标识的错误由 Tk 主线程处理一次，过期连接的错误不会关闭已经更换的新连接。模拟器显示的是主机指令，不代表设备已执行或传感器反馈。
- 采集／模型错误继续单独报告，不误称为设备未接入；实时任务初始化也纳入异常处理。

用户已确认 Log only 不会自动停止。排查期间，使用保存的分析设置临时改为 Log only，真实屏幕采集＋本地 CPU Pose 模型运行约 10 秒保持正常；v2 真实采集检查也正常。没有连接或驱动真实硬件，因此没有判定本次串口失败是线缆、驱动、设备状态还是超时，也没有擅改发送频率或到达时间。

## v2 的“局部运动群不稳定”

原来小背景确认要求主体的大多数特征属于少数几组整体移动。人体各部位分别移动或发生连续变形时，真实背景候选也可能因此被拒绝。

- 保留原有整体运动组判断，额外检查相邻特征在扣除候选运镜后的位移方向与大小是否一致，允许主体各部分分别运动。
- 背景仍需通过点数、空间分布、外围位置、前景背景归属和外推误差检查。相邻运动一致性只用于确认独立主体，不能代替背景运动模型。
- 若相连的主体区域无法用一个整体变换稳定表示，在有限候选范围内寻找有足够特征、空间跨度和邻近观测支持的局部区域。局部拟合允许剪切与长宽比例变化；独立背景仍使用原有模型。
- 优先继续跟踪原来的局部区域，避免每帧追逐不同部位。采用局部时，分析预览显示“稳定局部”，黄框和箭头就是实际使用的区域。此时输出取自这个区域的变化，不能当作整个人体的位置或完整骨架分析。
- v2、可选 RTM 2D 旋转辅助及全／半行程共享改动。直接 Pose 和原混合 v1 的识别核心、基础倍率与联动设置保持。

## 视频重复帧

读屏频率高于视频帧率时，可能连续读到完全相同的画面。旧处理会拿零运动帧重新判断背景归属、反复确认，甚至把之前已确认的背景丢掉。

现在完全相同的画面保留参考、运动层与有效历史，显示“画面尚未更新；保持参考”，采用位移为零，不重复积分上一帧。新的不同画面继续正常跟踪。全／半行程按不同画面之间的实际时间计算运动速度；长时间暂停后会停止周期，切镜头仍会清除旧参考。没有跳过“只是变化很小”的不同画面。

已拒绝的画面不会因为被重复读取而恢复有效观测，也不会延长原有短暂丢失宽限；启动时的空白画面仍报告缺少特征。

## 文件与验证

- `src/osr_screen_tcode/app.py`、`sinks.py`：连接及写入错误、主线程弹窗、失败指令与模拟器隔离。
- `camera_motion.py`、`motion_layers.py`：重复帧处理、相邻光流一致性、稳定局部区域选择。
- `motion_reference.py`、`stroke_cycle.py`：实际区域标记、中英文诊断及测量时间。
- `tests/test_output_failures.py`：7 项新增，模拟未连接、超时、短写、弹窗、停止、旧连接隔离及初始化错误。
- `tests/test_video_reference.py`：5 项新增，覆盖变形主体、随机跟踪错误、重复帧、暂停、切镜头和重复无效画面的丢失处理；`tests/motion_scenes.py` 和 `tests/ui_smoke.py` 增加相应合成场景。
- `tests/test_camera_motion.py`：模拟光流的透视保留测试改用不同输入帧，与模拟的运动对应；原透视补偿断言保持。
- `tests/test_device_ui.py`：失败指令测试检查新的设备输出异常，并验证原始异常及错误文字保留；不转发模拟器的断言保持。
- 版本、README、Start.md、AI 指南、当前手册入口及两份日志同步；没有新增设置或改变保存／恢复默认行为。

- 主程序完整执行 235 项（包含 12 项新增），约 306.6 秒：234 项通过，1 项旧测试仍期待直接抛出 `OSError`，与新增分类异常不符。仅更新该测试的异常类型及原始原因断言后，单项复验通过（约 0.68 秒），期间未再改动程序代码。最终 235 项均完成通过验证；未在这次单项测试修正后重复整套运行。
- 覆盖少背景、非刚性变形、重复帧、重复无效帧、快速拖动、纯运镜、随机噪声、遮挡与切镜头；原 v1 数值、Pose 自动 L0／pattern／v1 接管、三维主轴、全／半行程、设置保存与恢复默认、最终倍率／减速／模拟器路径通过。
- 独立 Lab 28 项通过；Node 模拟器最终指令检查通过。
- 根目录 Start.cmd 中文／英文启动检查与 Lab Start.cmd 启动检查通过。中英文可见分析预览截图已检查：实际区域、“稳定局部”、重复帧零位移说明与轴组正常显示。设备错误弹窗的中英文内容及调用次数用模拟设备测试，未连接真实硬件。
- 最终 v2 真实读屏＋Log only 检查约 4.5 秒产生 157 次更新，无采集／回调错误，停止后工作线程退出；不保存测试设置、不发送硬件指令。这项检查不等同于已复现用户原视频。
- 修改文件语法及启动文档链接检查通过。Git 差异检查仍有此前已有的 CONTRIBUTING.md、OPEN_SOURCE_NOTICE.md 末尾空行提示；本轮没有清理这些既有改动。

## 残余风险与复测

合成变形场景证明可以恢复原来持续拒绝的观测，但不能保证用户原视频已经解决。更强烈的变形、快速遮挡、背景完全缺失或相邻光流本身错误，仍可能保持或重设参考。局部区域跟踪可能选择身体的某一部分，其运动不一定代表整个人的主要动作；请通过黄框判断实际采用位置。

两组带运镜的合成变形场景分别获得 168/181、156/181 帧有效观测，后半段分析 L0 幅度约 0.92、0.84（分析归一化范围 0～1，尚未乘最终输出设置）。这些数值不代表用户原片效果或硬件行程。

排查用的更强变形合成场景仍有较多保持与重新建立参考，输出往复幅度很短，这项限制尚未解决。没有通过取消背景验证或把整幅运镜直接输出的方式消除提示。

新增局部判断有处理开销。三维画面尺度不是真实深度，机械臂映射、逆运动学、碰撞检测与反馈仍未验证。先以 Log only 播放原先出错的视频，观察“稳定局部”、黄框及参考状态；如仍不足，请保留具体拒绝原因。

仅更新当前测试源码，未打包、提交、推送或安装依赖；正式目录、旧发布包、原有未提交改动及有意删除保留。未把本地模型、画面、日志或个人设置加入源码。

## English

Test.17 stops realtime output and shows a device failure dialog with the actual error. Missing transports, serial partial writes and connection timeouts are reported. Failed writes are not retried or forwarded to the simulator; stale connection errors cannot disconnect a replacement. Capture/model failures remain distinct. No physical device was driven, so the underlying serial failure has not been diagnosed.

V2 can validate independently moving deforming subjects using neighboring compensated-flow agreement, then track a supported local affine patch when the whole connected region is inconsistent. Existing independent-background and ownership checks remain. The actual region is labeled in the bilingual preview. Completely repeated video frames retain references and contribute zero movement; cycle activity uses the measured time between distinct frames. V2 and cycle mode share these changes.

Repeating a rejected frame cannot restore confidence or extend the existing loss grace period. Blank startup frames still report missing features. Two synthetic deforming scenes produced 168/181 and 156/181 ready observations; these are synthetic results, not validation of the user's footage or physical travel.

Validation: all 235 main tests were exercised (234 passed in the full run; one outdated exception-type assertion was updated and passed its targeted rerun, with no subsequent application-code change). The 28 Lab tests, simulator stream check, bilingual main startup, Lab startup and visible bilingual reference previews passed. A final live screen/Log-only run delivered 157 updates and stopped normally. Popup behavior was tested with simulated transports, not physical hardware. Syntax/startup links passed; two pre-existing EOF whitespace notices were preserved.

Strong deformation, occlusion and absent/ambiguous background remain limitations; the strongest synthetic deformation still frequently holds/recalibrates. Local-part motion is not whole-body tracking, and image scale is not physical depth. No package, commit, push or dependency installation was performed.
