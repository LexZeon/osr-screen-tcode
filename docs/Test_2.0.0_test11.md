# 2.0.0-test.11 / Local source test

只更新当前测试仓库源码。双击 [Start.cmd](../Start.cmd)，操作说明见 [Start.md](../Start.md)。不打包、提交或推送；独立 Pose Preview Lab 保持 0.2.1-test。

## 问题与底层修改

用户确认问题画面为“主体占大部分，背景很少”。旧 v2 先找空间分布充分的背景，再找局部动作；这会造成背景参考一直缺失，也可能把占据大部分特征点的主体误认为运镜并扣掉，导致 L0 行程极短。新增近景合成画面复现了后一种情况。

本轮在现有 v2 管线中增加运动分层，不修改 v1 数值算法，也不新增模型或依赖：

1. 用更细的网格抽取角点，避免小背景与高纹理主体挤在同一采样格时被挤掉；处理最长边仍默认 640。
2. 在背景指派前，分离最多三个一致的运动群。大主体与小背景运动不同时，允许位于画面外围、点分布能约束相似变换的小块背景参与估计。检查拟合误差、前景一致性以及向主体位置外推的不确定性，不再要求小背景覆盖大部分画面。
3. 新的小背景需要连续两个帧对确认。小动作不足以从单帧差异区分时，使用最多四帧、最长 0.2 秒的历史辨别区域；辨别后仍重新拟合当前帧对，输出不重复累计历史位移。
4. 已确认的小背景优先持续跟踪，只在同一背景附近补充角点。被遮挡时保持，避免让大主体接管运镜模型；宽背景与背景带仍使用原有筛选路径。
5. 已建立主体区域后，以区域整体的一致运动测量小变化，并用区域变换更新边界。避免每帧重新取内部角点的包围框，导致区域越缩越小、主体边缘混入背景。
6. 新局部区域要得到框内全部跟踪点的支持，不能仅凭被挑出的少量光流误差成立。纯运镜、断帧、切镜头及持续参考缺失继续保持或重置，明显切镜头会解除小背景锁定。

全/半行程模式继续共用同一个 v2 分析器，1/4、半、全行程及可选 RTM 2D 旋转辅助同步受益。五档预设、输出减速时序、模拟器最终指令路径保持现有行为。

## 联网参考与采用范围

- [Norfair camera_motion.py](https://github.com/tryolabs/norfair/blob/master/norfair/camera_motion.py)：参考其带掩码的光流、平移／单应性运镜模型，以及保留较长参考帧以辨别微小运动的思路。本项目采用短历史进行区域辨别，然后回到当前帧对测量。
- [Real-Time Hysteresis Foreground Detection in Video Captured by Moving Cameras 项目](https://github.com/hadign20/Unsupervised-Video-Object-Detection)：参考前景／背景分别建模、估计运镜时排除前景的思路。该项目的背景占多数假设不适合本次近景，因此没有照搬其背景选取规则。
- [OpenCV 几何估计文档](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)：现有 OpenCV 提供的稳健相似变换拟合用于运动群和当前帧运镜估计。

以上是方法参考；本轮实现为项目内独立代码，没有引入上述项目的模型、运行库或源码包。运动分层和背景归属仍是图像几何推断，不是人体语义分割或真实深度估计。

## Pose 联动峰值改到偏高位置

仅 RTM Pose 2D 的六轴 TCode 输出采用以下连续分段线性曲线：

| 最终受限 L0 的位置 | L1/L2 倍率 |
| --- | --- |
| 最低处 | 0.5 |
| 1/3 | 2.0 |
| 中位 | 2.75 |
| **2/3** | **3.5，最高** |
| 最高处 | 0.5 |

按当前指令已经受限／限速的 L0、相对于所设 L0 下限至上限的比例计算。固定 L1/L2 识别位置也会随 L0 收拢或展开。原有限位、倍率、反向及速度控制继续生效，放大后可能更早触及行程限制。

该固定输出规则无需新设置，保存与恢复默认使用同一规则。v2 平移仍是低／中／高 1／2.5／1、峰值在中位；启用 RTM 旋转辅助也不改变这个范围。骨架、图表及脚本分析数据不应用 Pose 联动，模拟器仍收到输出端最终接受的指令。

## 验证与文件

**主程序 160 项、独立 Lab 28 项测试通过**；模拟器最终指令测试、主程序中英文和独立 Lab 的 Start.cmd 启动检查通过。新增近景测试覆盖小背景／背景条带、不同纹理、平移／缩放／转镜、背景遮挡恢复、切镜头、纯运镜不生成行程，以及 1/4／半／全实际分析输出。中英文近景预览确认了分层背景标记、蓝色背景点及 1/4 状态。

另用 640×480 合成近景连续检查 181 帧：168 帧有效运动、9 帧跟踪停顿、2 帧建立参考、1 帧确认背景、1 帧短缺保持；最后三秒 L0 分析跨度为 81%。本机分析器调用耗时中位数 13.40 ms、95 分位 15.51 ms（去除前 11 帧，不含采集、Tk 绘制、设备 I/O 或 RTM 推理）。这是指定合成画面的测量，不能代表实际视频的准确率或完整应用帧率。

- `src/osr_screen_tcode/motion_layers.py`：运动群分离、小背景选择与连续确认。
- `src/osr_screen_tcode/camera_motion.py`：细网格采样、历史辨别、当前帧补偿、背景跟踪及主体区域维护。
- `src/osr_screen_tcode/motion_reference.py`：中英文“分层背景”来源和确认状态。
- `src/osr_screen_tcode/pose_output.py`、`tcode.py`、`app.py`：Pose 峰值在 2/3 的输出曲线。
- `tests/test_closeup_motion.py`、`tests/motion_scenes.py`：无需外部片段的近景回归场景；原有主轴、旋转、输出、保存／恢复默认及 v1 基线测试继续保留。
- `tests/test_output_presets.py`：导出预设检查计入原有录制压缩的整数误差（99→100 可能因不足 2 点而省略，极值差最多 1 点）；仍检查五档识别结果完全一致、最终曲线不同。录制器本身未修改。
- `tests/ui_smoke.py`：近景预览与中英文界面检查；临时图片位于系统临时目录，不进入源码。

## 复测方式与残余风险

先关闭旧主程序，再双击根目录 Start.cmd，确认窗口顶部 test.11。选择 v2，在原问题片段上查看分析预览：小背景被采用时会显示“分层背景 Δ”，蓝点应落在背景，黄框与绿点应跟随主体；认反时点“重设参考”。可用同一片段切换全/半行程观察输出曲线。

尚未用用户原始问题片段验证，合成场景通过不代表所有近景都可靠。完全没有可跟踪的独立背景、背景也在独立运动、严重模糊／遮挡、景深差异造成视差或两种运动无法区分时，仍可能保持或误判。多帧确认会增加少量建立参考的时间；没有把尺度变化解释为真实深度。未连接真实设备，机械臂关节映射、逆运动学、碰撞及反馈仍未验证。

## English

V2 now separates competing image motions before assigning a background in close-ups with a large foreground. A coherent small peripheral background is confirmed across frame pairs. A short historical baseline helps discover subtle motion groups, while only current-frame displacement enters output. Confirmed background points are replenished near the same patch; occlusion does not promote the foreground to camera. The tracked region is transformed rather than repeatedly shrunk to an inner corner box. New regions must be supported by the other tracks inside them, rejecting isolated flow-error clusters. Full/Half Travel shares the same v2 implementation, including quarter travel and optional pose rotations.

Direct Pose TCode coupling is 0.5 at low L0, **3.5 at 2/3 travel**, and 0.5 at high L0, interpolated linearly using the limited command. V2's 1/2.5/1 central peak is unchanged. No new saved setting, dependency or model is needed; default max edge remains 640. All 160 main tests, 28 Lab tests, simulator command checks and main Chinese/English plus Lab startup checks passed. A 640×480 synthetic close-up measured 13.40 ms median / 15.51 ms p95 for the analyzer only; it is not an application FPS or real-footage accuracy claim. Original footage and physical hardware remain unverified.
