# 2.0.0-test.23：以主体框中心跟踪混合 v2

双击根目录 [Start.cmd](../Start.cmd)，确认标题 **2.0.0-test.23**。点击入口和复测说明见 [Start.md](../Start.md)。这是源码测试更新，没有发布新的安装包。

## 本轮针对的问题

用户反馈当前混合 v2 仍不如公开 1.1.2，希望借鉴旧版区域光流：先框住主体，再根据中心点分解主轴、副轴。本轮修改 v2 的运动采样、主体框和恢复验证；没有替换整个项目，也没有修改设备输出算法。

主要文件：

| 文件 | 本轮改动 |
| --- | --- |
| [regional_flow.py](../src/osr_screen_tcode/regional_flow.py) | 新增区域多点验证、按组平均与按需 DIS 补点 |
| [camera_motion.py](../src/osr_screen_tcode/camera_motion.py) | 整合主体框、固定中心、背景接续与连续角点 |
| [subject_tracking.py](../src/osr_screen_tcode/subject_tracking.py) | 验证完整缺失区间、拒绝矛盾恢复、保存框角点 |
| [motion_layers.py](../src/osr_screen_tcode/motion_layers.py) | 少量背景的候选与纹理验证 |
| [motion_reference.py](../src/osr_screen_tcode/motion_reference.py)、[point_l0.py](../src/osr_screen_tcode/point_l0.py) | 主体框/中英文标注、统一中心参考 |
| [test_regional_flow.py](../tests/test_regional_flow.py)、[compare_released_hybrid.py](../tests/compare_released_hybrid.py) | 回归用例与只读 v1 数值对照 |

## v1 是否改过

公开 [v1.1.2 发布页](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v1.1.2) 对应的远程标签，与本机标签均指向 `8ff39faf17b2709ec6cf9499213f66f8351110d1`。本轮只读核对，没有修改远程。

逐函数比较显示，v1 的区域提取、区域光流、L0 增量与原平滑/限制核心保留了旧算法；当前 `analyzer.py` 的混合路径增加了预览参考快照和绘制，另有 Pose 后端改动。相同参数、相同输入下的数值对照与应用默认参数应分开看。

| 应用默认参数 | 1.1.2 | 当前测试版 |
| --- | ---: | ---: |
| 平滑 | 0.08 | 0.28 |
| 死区 | 0.006 | 0.008 |
| 分析运动倍率 | 1.8 | 1.35 |
| 视觉行程 | 0.72 | 0.66 |
| 到达时间设置 | 20 ms | 24 ms |

这些设置及后续最终输出处理的差异，会使恢复默认后的实际体验不同。因此不能把“同参数下 v1 核心数值一致”解释成两个软件版本的默认最终脚本完全相同。本轮没有擅自改回旧默认参数。

可复现的只读核对入口：`python tests/compare_released_hybrid.py`。需要本地已有 `v1.1.2` 标签；不会联网获取、切换工作区、调用模型、连接设备或写设置。使用四种变形程度、共 380 帧相同输入，比较发布版与当前 v1 的分析 L0，并单独列出应用默认值。两份源码都在当前同一 OpenCV 5.0.0 环境运行，没有复现旧发布包的独立运行环境；它不是硬件效果或实时速度测试。

## 主体框、中心和采样

- **区域光流借鉴。** 保留原有精确刚性跟踪；对于不能用一个刚体变换解释的主体，先在整个运动区域验证相邻点的局部变化，再用分布在不同格子的运动估计主体框中心。采样数量多的纹理区域不会仅凭点多就压过其他区域。
- **按需 DIS 补采样。** 稀疏点不足以描述变形时，调用与 v1 同类的 DIS 光流。补点经过正反向一致性、纹理和图像误差检查；只接受当前画面测到的对应，不以预测坐标冒充测量。最多约 1200 个格点，按需计算并在当前帧内复用。
- **同一主体身份。** 主体框建立后，部分格子丢点不应使三轴原点跳到另一个小块。框和中心随已验证的主体运动搬运；不足时保持原身份，重新取得完整图像证据再接续。真正更换区域、切镜头仍重设参考。
- **保留框的角点。** 变形框连续搬运同一组角点，显示时才计算外接范围；短暂恢复也保存这些角点。避免正反小旋转反复取外接矩形，导致黄框和恢复采样范围越来越大。
- **中心驱动主副轴。** 运动增量在持续跟踪的 A 点计算，避免每帧换一批角点后，其平均位置变化把缩放/旋转泄漏为平移。既有连续主轴和附属轴继续从左右、上下、画面尺度的轨迹分解；这是画面代理坐标，不是真实深度。
- **区分尺度与变形噪声。** 对变形框按采样组估计尺度不确定性，避免把相关的局部形变当作很多独立点的高精度缩放。确有足够证据的尺度运动仍保留。

**黄框显示持续跟踪的主体运动框；A 为中心/参考点；绿色小圆是参与测量的采样组。** 采用变形框时，中英文均显示“主体框中心 / subject-box center”。这是一种视觉运动区域跟踪，不是通用人物语义分割或人体检测保证。

## 运镜和恢复

背景仍独立验证。小块背景还须有足够局部纹理，不能把模糊墙面上的弱梯度当成高精度运镜参考。新增薄边缘候选，避免形变主体占据所有候选机会；小块背景保留有限分布式种子，使下一帧不必恰好重新检测出同一批角点。额外种子只用于已确认的小块背景，宽背景仍按原采样处理：开发对照发现向宽背景重复补种子会扰动径向参考，因此已限制范围。

主体失配不再直接丢弃同一帧已验证的背景。确认中的背景点也可以在下一帧重新验证，但同一帧不重复计作连续确认。背景不足时不把整个画面的运动直接当作主体 L0。

变形框也保存最近可靠画面的主体区域、背景点、中心与累计值。短暂缺失后，在最多 0.25 秒内从那一帧对当前画面重新做背景和 DIS 主体验证，计算整个缺失区间的位移，而不是只加最后一帧的差值。至少六个能独立验证的小块背景点、分布式主体支持和误差检查仍必须成立；新观测只累计一次，不重复平滑或重复积分同一段。

另修复一条恢复矛盾：背景特征可以在旧区域内仍然匹配成功，但主体的固定图像参考已经移动到别处。现在固定参考与拟合位置明显不一致时拒绝恢复，不能一边把 A 移到新位置，一边记录“主体没有动”。这项回归单独测试。

原有独立目标 T?、假定目标 V?、连续交接及最多 2 秒已确认规律延续继续保留。没有可靠目标时按可见主体往复；不声称确认了语义接触。短暂失效不是新的有效测量。

## 影响范围和设置

普通混合 v2、全/半/1/4 行程和 v2 可选 RTM 2D 旋转辅助共用同一份主体运动测量；原有连续主副轴和旋转处理继续使用。单轴与六轴均覆盖。直接 Pose 与 v1 的分析核心、五档预设、总行程、各轴倍率、反向、联动、限位、末端减速、导出及模拟器最终指令链路没有改动。

没有新增用户设置键；保存/恢复默认与中英文设置继续共用原逻辑。最长边仍为 640，默认混合 v2 + 融合参考。测试时仍只用 Log only，不连接真实设备。test.22 的历史个人配置事故保留在对应版本文档，不作为本轮发生的新事故。

## 来源与交付

`regional_flow.py` 为本项目独立实现，没有复制外部追踪器源码，也没有增加模型或运行时依赖。参考与现有依赖：

- 本项目 [v1.1.2](https://github.com/LexZeon/osr-screen-tcode/tree/v1.1.2)：区域光流与短时稳健统计的思路。
- [OpenCV DIS 文档](https://docs.opencv.org/4.x/de/d4f/classcv_1_1DISOpticalFlow.html)：使用现有 OpenCV DIS API。
- [OpenCV LK 示例](https://github.com/opencv/opencv/blob/4.x/samples/python/lk_track.py)：正反向检查、重采样的参考思路，未复制示例源码。
- [Median Flow 论文](https://dspace.cvut.cz/bitstream/handle/10467/9553/2010-forward-backward-error-automatic-detection-of-tracking-failures.pdf)：多点跟踪与跟踪失败验证的参考。

OpenCV 自 4.5.0 起使用 Apache-2.0；本项目已有依赖要求为 4.9 及以上。见 [OpenCV LICENSE](https://github.com/opencv/opencv/blob/4.x/LICENSE) 和 [第三方说明](../THIRD_PARTY_NOTICES.md)。本轮没有把模型、GPU 库、第三方视频、缓存、日志、个人设置或本机私有路径加入源码。

## 验证记录

- 主程序最终完整隔离检查：**292 项通过，420.998 秒**，正常 OpenCV 线程配置；真实个人设置指纹不变。覆盖相机运镜误触发、目标、主体恢复、切镜头、暂停、快速运动、单轴/六轴、全半行程、可选旋转、最终输出、设备错误及线程停止。
- 独立预览：**28 项通过，0.345 秒**。
- 模拟器 JavaScript 检查通过：最终指令保留，动画不能覆盖指令位置。
- 与公开 v1.1.2 的相同参数数值核对：四种场景共 **380 帧，v1 分析 L0 最大差值均为 0**。应用默认值及最终脚本不属于该等价范围。
- 中英文主 Start.cmd、独立 Start.cmd 均正常启动并退出。修正框膨胀后，中文 v2、英文全半行程 + 模拟 RTM 旋转的可见窗口检查通过：黄框、A、三轴、采样组和双语诊断可见。该检查使用合成画面与模拟骨架，不是真实模型/硬件验证。
- 最终源码单独实际读屏、Log only 连续运行 8 秒：**307 次统计更新**，约 9.5 秒含启动/收尾，停止后工作线程退出，无采集错误或界面回调错误。该次末尾采集约 64.2 FPS、分析约 64.0 FPS、输入帧龄约 7.8 ms；这是当时桌面场景的单次数据，不是复杂视频速度保证。
- 最终中英文 Start.cmd 再次启动通过；真实个人设置内容与启动检查前指纹相同。源文件核对无本轮意外删除，已有未提交修改和三项有意删除保留。新增未忽略文件中无模型、运行库、媒体、日志或个人设置。

- 连续 20 秒、601 帧变形近景最终检查：571 帧 ready、25 帧 holding、3 帧 missing、2 帧 calibrating。原始累计上下位移与已知往复的相关系数约 **0.789**；按正余弦与线性趋势分解，20 秒中心漂移约 **X -14.0 px、Y +11.6 px**。主体框可持续跟踪，但长期绝对位置仍会漂移，不能算长期精确锁定。修正框膨胀前同一诊断曾达到 0.936，但使用了逐渐扩大的取样范围，不能将那个较好数字当作最终版本结果。此检查固定单线程，不是实时吞吐承诺。
- 新增整段恢复检查：相隔 0.12 秒的真实图像中主体移动 12 px，恢复完整约 5 个画面百分点；同一时间戳不能再次恢复，超过 0.25 秒拒绝旧缓存。

同一近景合成画面、151 帧、30 FPS、上下往复叠加小幅运镜；test.22 使用改动前源码副本，test.23 使用最终源码。行程为最后 90 帧分析 L0 的最大值减最小值，不代表实际设备行程，也不单凭行程大就认定识别正确：

| 画面 | test.22 可靠帧 | test.23 可靠帧 | test.22 分析行程 | test.23 分析行程 |
| --- | ---: | ---: | ---: | ---: |
| 轻度形变（12） | 123/151 | 141/151 | 91.5% | 100.0% |
| 较明显形变（24） | 5/151 | 126/151 | 2.0% | 69.9% |
| 更强形变（36） | 0/151 | 90/151 | 0% | 59.1% |
| 每三帧局部模糊 | 104/151 | 104/151 | 100.0% | 100.0% |

最终四种检查均无主体重置。较明显形变回归另外要求上下轨迹相关系数大于 0.9、相邻分析 L0 变化小于 0.25、主体框不膨胀超出已知场景，以及普通 v2/全半/模拟 RTM 旋转使用相同运动观测；这些断言均通过。

开发过程记录：第一轮完整隔离检查为 291 项、386.660 秒，1 项失败（模糊/稀疏画面纯运镜）。已增加小块背景的纹理可定位性检查，第二轮完整隔离检查为 291 项、406.537 秒，纯运镜已通过，但新增变形轨迹测试未过：与已知往复相关系数约 0.803，低于要求 0.9。定位为非刚体暂缺测后遗漏中间位移，增加上述完整区间恢复后，单项及第三轮全部 292 项通过。较早原型还出现了小主体模糊后恢复幅度不足、宽背景补种子扰动径向参考；逐项数值对照后分别修正了恢复矛盾、非刚体路径误用和补种子范围。旧测试中“必须采用小块 patch”的断言改为“主体框、多组真实采样”，保留原有效帧数和行程要求；没有降低这些数值门槛。

第三轮完整检查耗时 403.828 秒。随后实际窗口检查发现连续小旋转反复取外接矩形，使黄框膨胀到画面外。改为持续保存角点，并扩展真实帧回归约束框的大小；相关 7 项通过后，第四轮全部 292 项再次通过，结果列在上方。初次中文窗口暴露的问题已修复，不能把那次窗口检查算作通过。

公开实景补充检查：OpenCV [vtest.avi](https://github.com/opencv/opencv/blob/4.x/samples/data/vtest.avi) 前 300 帧（10 FPS，处理最长边 640），输出均有限且处于 0–1。最终仅 **31 帧**为 ready/tracking，最大相邻分析 L0 变化约 0.0054；该多人远景的跟踪仍不理想，不能算识别效果通过。单线程诊断的处理耗时中位数约 75.1 ms、95 分位 91.7 ms，不是应用实时速度保证。素材只在临时目录用于检查，不随源码分发。

真人低帧率补充：TensorFlow.js [pose_squats.mp4](https://github.com/tensorflow/tfjs-models/blob/master/pose-detection/test_data/pose_squats.mp4)，其[原始测试说明](https://github.com/tensorflow/tfjs-models/blob/master/pose-detection/src/blazepose_tfjs/blazepose_test.ts)注明来自 Pexels 深蹲视频，压缩到 5 FPS。以实际 5 FPS 时间戳处理全部 65 帧，28 帧 ready、15 帧 holding、12 帧 missing；分析 L0 行程约 20.4%。输出有限且在 0–1，但仍有频繁缺测，不能作为低帧率真人准确跟踪已解决的证据。只使用视频数据做本地检查，没有引入 MediaPipe/TensorFlow 代码、模型或运行库，没有将素材纳入交付。

## 剩余限制

强形变、纹理不足、持续模糊、遮挡、多主体交叉和前景/背景难以区分仍可能导致保持或重新识别；长时间积分仍可能漂移。DIS 补点有额外开销，实际速度取决于输入和电脑；640 是默认处理上限，没有为了速度盲目降低它。自动化合成测试不能代替用户原片或真实设备验证，不能承诺所有场景“完美”。

真实机械臂关节映射、逆运动学、碰撞和反馈未验证。没有修改正式目录、旧发布包或远程历史；没有安装依赖、打包、提交或推送。

## English

Test.23 keeps v1's core analysis and the final output pipeline while improving v2 subject motion. A persistent motion box uses locally verified, spatially balanced samples; on-demand DIS supplies additional current-frame correspondences with forward/backward and appearance checks. Main and secondary axes use the same transported center, rather than a changing feature centroid. Correlated deformation is included in scale uncertainty.

Camera ownership remains separate. Thin-perimeter proposals and bounded retained seeds support small backgrounds; broad backgrounds keep their original sampling. Recovery rejects a fitted cohort that contradicts the fixed subject appearance. The yellow box, A center and support groups are shown with English/Chinese diagnostics.

Persistent corner coordinates prevent the deforming box from inflating under repeated small rotations. Axis-aligned bounds are derived for display and selection rather than fed back as new corner identities.

Deforming boxes recover the entire missing interval from the last verified image, for at most 0.25 seconds, using independently re-matched camera and subject pixels. The recovered interval is integrated once. This fixes missed displacement during brief losses without treating predicted positions as observations.

Same-parameter numerical comparisons against the v1.1.2 tag are separate from application defaults and final output. Defaults changed historically, including smoothing, gain and visual stroke. Use `python tests/compare_released_hybrid.py` for the read-only audit; see the validation record above for final results and limitations.

V2, quarter/half/full cycles and optional RTM rotations share these measurements. Saved/default settings, direct Pose, v1 and final output multipliers remain unchanged in this update. Source only; no hardware or physical robot-arm compatibility claim. Use [Start.cmd](../Start.cmd).
