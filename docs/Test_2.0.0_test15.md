# 2.0.0-test.15：v2 连续三维运动轴

双击根目录 [Start.cmd](../Start.cmd)，确认标题 `2.0.0-test.15`。[Start.md](../Start.md) 有可点击启动入口。仅更新测试源码，未打包、提交、推送或安装依赖；已有未提交修改与有意删除保留。Pose 的持续 v1 接管与更快放大见 [test.14](Test_2.0.0_test14.md)。

## 实际分析与输出

- v2 不再从上下、尺度、左右三个独立方向中选一个并交换轴位。它在三维画面运动坐标中拟合连续主轴，可以同时包含左右、上下和尺度变化，并保留各分量的正负关系。真正只有上下运动时，三维主轴可以自然对齐上下方向。
- 主轴由扣除运镜后的有效往复运动确定。单向位移不能凭速度夺走主轴；近三秒的运动相关性参与方向判断，候选需持续约 0.3 秒，转向逐步进行。多个方向强度相近而没有明确主方向时保持参考，不任意切换。
- L0 沿主轴；L1/L2 沿两个彼此垂直、且垂直于主轴的附属方向。这两个方向随主轴一同转动，保持同一组坐标关系与正向，不独立翻转。世界坐标的上下或左右不再固定属于某个输出轴。
- 只将新的运动增量投影到当前轴组，不把已积累的旧位置按新轴组重新计算。因此方向变化本身不会产生一次旧偏移造成的跳位。限位后反向也无需先抵消隐藏偏移。
- R0/R1/R2 的**旋转近似变化**同样相对这组轴表达。默认参考方向分别对应上下、画面尺度、左右；之后沿主轴和两个附属轴表达增量。可以使用画面旋转近似或可选 RTM 2D 旋转辅助。没有把这些经验信号当成真实三维欧拉角。
- 不带 RTM 时，原有 L1/L2/R0/R1/R2 的显著变化确认、高频噪声过滤和输出平滑继续生效。L0 单轴与六轴共用同一主轴；五档预设仍只改变最终输出。最终行程倍率、反向、联动、限位和减速继续应用，模拟器仍使用最终指令。
- 全／半行程模式直接共用 v2 **沿三维主轴的往复跨度和节奏**，不再取某个单独分量的跨度。例如斜向动作的三维总幅度可能比任一个屏幕分量更大，模式可据此选择 1/4、半或全行程。该模式 L1/L2 仍居中，可选骨架旋转辅助保留。
- 原混合 v1 的数值核心、直接 Pose 输出及其默认设置不变。Pose 内可选的 v2 L0 混合来源随 v2 一起更新。没有新增需要迁移的设置；默认与恢复默认仍使用 v2，已有模式选择继续保存。

## 分析画面

在实际识别区域的中心绘制彩色轴，并在下方图表右侧提供固定视角的小图，不遮挡主体区域：

| 颜色 | 轴 | 含义 |
|---|---|---|
| 青色 | L0 / R0 | 主运动方向及相对它的旋转信号 |
| 紫色 | L1 / R1 | 第一个垂直附属方向 |
| 金色 | L2 / R2 | 第二个垂直附属方向 |

箭头为正向；背向线、小图虚线与减号表示反向。原黄框和背景／局部特征参考保留。说明区显示带正负号的 X/Y/S 主轴方向以及确认、跟随或保持状态。叠加图取自**当前分析实际采用的轴组**，不使用设备输出乘算后的数据。仅单轴输出、全／半行程时，未启用的附属轴仍可作为方向参考显示。

三维轴在计算中保持正交；投影到屏幕后，三条线看起来不一定是直角。

这里的 X、Y 是按画面宽高归一化的位移，S 是画面尺度变化代理；三者组成实验运动坐标。轴组显示位置附着于跟踪区域中心，不是已重建的人体／机械臂空间位置。单目画面尺度不是真实深度；没有新增 3D 模型、逆运动学、碰撞检测或硬件反馈。

## 文件与技术依据

- `src/osr_screen_tcode/dominant_motion.py`：带符号的三维相关性、连续正交轴组、主轴跨度与旋转增量投影。
- `src/osr_screen_tcode/stroke_cycle.py`：共用主轴往复证据。
- `src/osr_screen_tcode/visual_pipeline.py`：v2、旋转辅助、Pose 的 v2 混合来源及预览快照。
- `src/osr_screen_tcode/motion_reference.py`、`integrated_preview.py`：区域上的实际轴线、立体小图与中英文说明。
- `tests/test_motion_basis.py`、`test_dominant_motion.py`、`tests/ui_smoke.py`：斜向／反向运动、正交与符号稳定、运镜、输出连续、旋转投影、全半共用及显示检查。

实现参考了主成分分析由数据相关性确定方向的基本方法，见 [OpenCV PCA 说明](https://docs.opencv.org/4.x/d1/dee/tutorial_introduction_to_pca.html)；现有 NumPy 的 [eigh](https://numpy.org/doc/stable/reference/generated/numpy.linalg.eigh.html) 用于实对称协方差矩阵分解。这里的往复门槛、时间确认、附属轴整体转动和增量投影是本项目的实验处理，不是文档对本项目效果的保证。

## 验证

- 主程序完整复验：**218 项全部通过，820.227 秒**。复验进程限定 OpenCV 为一个线程以控制测试资源占用，没有修改程序实际运行配置。此前完整检查发现首个有效运动帧漏计，已修复；默认线程设置下该首帧回归单测也再次通过。
- 覆盖带正负分量的三维斜向、正交与正向稳定、附属平移／旋转投影、运镜和高频噪声、模糊方向保持、跨帧率、静止不重映射旧偏移、主轴跨度驱动全半、v2 与旋转辅助共用轴组、预览快照及原有输出链路。
- 独立预览 **28 项通过**，Lab 保持 `0.2.1-test`；模拟器检查通过，最终指令未被动画覆盖。
- 最终源码主程序中文、英文 `Start.cmd --smoke` 均正常退出，标题 `2.0.0-test.15`；Lab 启动检查通过。
- 中英文可见界面检查通过：合成斜向往复同时产生 X、Y、S 分量，实际区域轴线与图表右侧方向小图完整可见。没有连接真实设备；生成的检查图片保存在临时目录，没有加入源码。
- 单独方向算法检查：1200 个合成样本耗时 0.775 秒，平均约 0.646 ms／样本。此数值不含采集、模型和背景跟踪，也不是实际帧率保证。
- 语法与文档链接检查通过；差异格式检查仅保留原有 `CONTRIBUTING.md`、`OPEN_SOURCE_NOTICE.md` 的末尾空行提示，未清理既有改动。

## 复测重点与残余风险

先用 Log only 打开分析预览，测试斜向往复、上下同时缩放、主方向缓慢改变，以及明显运镜。应看到整组轴随主方向缓慢转动，换向时轴的正向不会来回翻转；静止时不会只因轴组变化而多输出一次行程。再查看最终输出监视与模拟器，比较行程倍率生效后的实际指令。

反复运镜仍可能与主体往复混淆；小背景跟踪不足时仍会保持。方向需要一段往复证据，突然变化存在确认延迟；画面尺度与透视旋转只能作近似。三维跨度可能让斜向动作选择比旧版更大的行程档位；附属轴正向随整组坐标关系决定，可能与旧版直接交换轴后的方向不同，应根据预览箭头和输出反向选项复测。实片手感、真实设备抖动与机械臂兼容性仍未验证。

## English

V2 now fits a continuous local frame in right/up/image-scale space. L0 follows the main reciprocal direction, while L1/L2 follow its transported orthogonal transverse directions. Rotation-proxy changes are expressed in the same frame. Only new increments are projected; changing the frame does not remap old offsets. Cycle mode shares the projected three-dimensional stroke amplitude and rhythm.

The analysis image shows the actual adopted frame at the tracked region, plus an oblique inset and signed X/Y/S direction. Cyan is L0/R0, purple L1/R1, gold L2/R2; arrows mark positive ends. The frame is an image-motion estimate, not physical depth, reconstructed body position or robot kinematics. Existing output controls, saved modes and defaults remain in place. Camera ambiguity, confirmation delay, physical-device behavior and robot compatibility require further validation.

Validation: all 218 main tests and 28 Lab tests passed. The full rerun bounded OpenCV to one test-process thread; production settings were unchanged. The first-valid-frame regression also passed separately with default threading. Final bilingual startup, visible UI and simulator command checks passed. No physical hardware was connected.
