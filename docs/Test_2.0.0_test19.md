# 2.0.0-test.19：融合参考、多点支持与短时规律延续

双击根目录 [Start.cmd](../Start.cmd)，确认标题 **2.0.0-test.19**。操作入口见 [Start.md](../Start.md)。这是源码测试更新，没有新 exe/ZIP。

## 本轮使用方式

在“分析预览”或开始分析的确认窗口，把 **v2 L0 参考** 选择为 **融合参考（默认）**。新设置和恢复默认使用融合参考；之前保存的三种参考仍保留，所以已有配置可能需要手动切换一次。主界面与确认窗口、中英文、保存与恢复默认共用同一设置。

融合参考先统一方向，再利用三种证据各自的作用：主轴负责连续位移，中心 C 负责往复范围和相位，可靠交互候选 P? 负责远近方向并提供相位修正。P? 时有时无不会反复重启整段输出。候选与主轴运动不一致时不强行相加。C 是相位中心，不能对它取绝对距离，否则会把一次往复变成两次。

**方向确认后：远离往复目标 L0 大，靠近目标 L0 小。** 独立的“交互点候选”也修正为这个方向。未确认交互方向时保留稳定主轴方向，并明确显示“远近待确认”；单目运动无法保证判断哪一端是真实交互端。用户的最终“反向”设置仍会翻转实际输出。

## 画面标注

- **T?**：橙色圆圈与箭头标注往复目标估计。可能是可靠交互候选、经过方向确认的轨迹近端，或尚未确认远近的轨迹端点；说明文字区分这些情况。它不等于已确认接触。
- **C**：往复中心。**P?**：光流会聚候选。尺度方向在二维画面中无法定位时，不画一个虚假的目标端点。
- 绿色小圆显示实际区域内多组有效采样的平均位置。多组都经过当前帧跟踪与区域验证；失去支持的点不靠预测补成“已跟踪”。
- 识别不清而延续输出时，显示“沿用已确认规律（预测）”“预测延续减速中”或“延续已满 2 秒；保持”。原始观测仍显示缺失，不能把预测当作重新识别成功。缺失时隐藏旧屏幕坐标上的 T?。

## 延续规律的边界

只在最近有效观测中已经确认稳定往复并能拟合节奏时，短暂延续之前的幅度、方向和周期。启动无参考、随机噪声、单向移动不会凭空启动周期。

按用户确认：从最后有效运动开始，最多延续 **2 秒**。最后 **0.5 秒**逐渐减慢相位推进，到时保持当时位置。不会靠不断收到缺失帧刷新这 2 秒。重新识别后从当前输出接续，不跳回旧参考的绝对位置。

明确静止／暂停的有效重复帧保持当前位置；持续暂停清除节奏记忆。切镜头、明显突变、超过 0.5 秒的采样断档、画面尺寸变化和重设参考停止旧规律。无法区分遮挡与新场景的片段仍可能延续到 2 秒上限，需要实片复测。

普通 v2 只对 L0 延续。其他轴保留原本的丢失处理；可选 RTM 2D 旋转辅助保持。全／半行程共用融合证据，仍保留 1/4、半、全行程和余弦缓动，识别时跟随往复相位，短暂不清时延续已经建立的周期。纯 Pose 和 v1 不使用此融合选项。

## 多点采样改进

原有 v2 已采用多点光流。本轮把选中区域划分为最多九组空间支持，各组平衡参与局部变换估计，降低某一块高纹理区域对平均结果的支配，并降低异常组的权重。保留最多 54 个分散的有效前景端点，下一帧重新验证，同时补充正常网格的新特征；部分点丢失后仍可由剩余点支持。

背景归属、相邻运动一致性、快速运动上限和区域切换优先级继续生效。平均只发生在同一个已验证区域；不会把背景和独立运动主体混在一起。重复画面不清掉有效种子，不重复累计位移。没有添加模型或依赖，最长边仍默认 640。

实现研究参考了 [CoTracker 官方项目](https://github.com/facebookresearch/co-tracker) 的共同跟踪与网格支持思路，以及 [OpenCV 光流教程](https://docs.opencv.org/4.13.0/d4/dee/tutorial_optical_flow.html) 的特征跟踪与往返校验。这里采用适配现有项目的轻量几何实现，没有移植 CoTracker 网络，也不宣称达到其遮挡跟踪能力。

## 文件与输出链路

- `fused_l0.py`、`motion_rhythm.py`、`point_l0.py`：融合、方向、节奏确认、延续与接续。
- `region_support.py`、`camera_motion.py`：分组估计、采样点保留和实际区域验证。
- `visual_pipeline.py`、`stroke_cycle.py`：普通 v2 与全／半行程共用，以及显式预测输出标记。
- `app.py`、`config.py`、`integrated_preview.py`、`motion_reference.py`：选项、保存／默认、中英文、目标与预测标注。
- `tests/test_fused_l0.py`：融合、部分点丢失、暂停／切镜头、延续终止、真实输出路由与导出；原有单独参考的保持测试明确选择原参考继续验证。

五档、逐轴行程、反向、设备限位、设备联动与最终时序减速沿用原输出链路。现有“六轴总行程”针对 L1/L2/R0/R1/R2；L0 使用单独行程滑块，本轮不改变这个映射。模拟器继续接收成功发送的最终 TCode，预测也走相同路径。导出仍沿用现有脚本行程与时间处理，不能把脚本坐标当成真实设备反馈。

## 验证记录

- 主程序完整 **262 项通过**，最终一轮约 **262 秒**。包含新增的 10 项融合／多点／延续测试，以及原有 v1 数值基准、Pose、运镜分离、强变形、部分背景遮挡、重复帧、设置与输出检查。前一轮发现首个有效位移被额外保持一帧，修正后重新完整验证通过。
- 独立预览 **28 项通过**；独立预览源码未修改。
- 新增测试实际移除约三分之一前景跟踪点，检查剩余多组支持与往复相位；另检查高纹理局部不会独占平均、噪声与单向运动不生成规律。
- 观测缺失注入检查覆盖普通 v2 与全／半行程：只延续 L0，原始置信度保持 0，末段减速且 2 秒后不再改变目标；恢复没有位置跳变。另验证随机噪声、暂停、切镜头不启动／继续旧规律。
- 实时 Log only 与视频导出检查覆盖预测期间的行程倍率、原始观测与预测状态分离，以及模拟器与成功发送指令一致。JavaScript 模拟器检查通过，动画不会覆盖最终指令。
- 根目录 `Start.cmd --smoke --language zh/en` 和独立预览 `Start.cmd --smoke` 均正常退出，主程序显示 **2.0.0-test.19**。
- 中英文窗口图像检查通过：中文径向目标 T? 与九组采样、英文缺失时的预测提示、中文带模拟 RTM 旋转辅助的全／半行程。图像仅保存到系统临时目录；使用合成画面，没有加入源码。
- 真实读屏复测采用 Log only，**192 次采集统计更新**，正常停止，无采集错误或界面回调错误。末次统计约 96 FPS 采集／49 FPS 分析，仅代表这次桌面画面的测量。早先两次固定短时检查分别未满足线程收尾时限和更新次数要求；追加检查未复现线程异常，未修改生产停止逻辑。实际设备未连接。
- 未安装／升级依赖，正式 Python 环境只读复用；未打包、提交或推送。

## 仍需复测

用户原视频、强变形、严重模糊、重叠动作以及真实语义交互目标仍需验证。规律拟合并非所有动作都能成功；确认不足时保持。预测最多 2 秒并不意味着知道这段时间画面中的实际动作。真实设备、机械臂映射、逆运动学、碰撞与反馈未验证。

未安装依赖、未连接真实设备、未打包、提交或推送；正式目录与旧发布包不变。

## English

Select **v2 L0 reference → Fused reference (default)**. Valid saved individual references are preserved. Motion-axis increments maintain continuity, the stroke center anchors range/phase, and qualified interaction evidence establishes polarity and gently corrects phase. Away is larger L0; toward is smaller L0, before user inversion. The individual interaction option uses the same corrected polarity. T? distinguishes an interaction candidate from an inferred stroke endpoint; it never confirms contact.

Only recently observed, stable reciprocal motion can supply a continuation. Tracking uncertainty may continue L0 for at most 2 seconds from the last observation, with phase-speed braking over the final 0.5 seconds. Missing frames cannot renew that deadline. Confirmed pauses, cuts, long sampling gaps, resolution changes and recalibration stop old continuation. Observations remain missing and the preview explicitly labels prediction. Reacquisition continues from the previous target.

Up to nine spatial support groups balance the selected region's measured transform, and up to 54 distributed successful endpoints are revalidated on the next frame. Normal feature detection replenishes points. Background/region validation precedes measurement averaging; separate objects are not pooled. No new model or dependency is used. Full/half mode retains quarter/half/full peaks and cosine easing; direct Pose/v1 and final output mappings remain unchanged. Real-footage target semantics and physical hardware remain unverified.

Validation: all 262 main tests and 28 standalone-preview tests passed, along with simulator command checks, Chinese/English startup and window-image checks. A live-screen Log-only recheck stopped cleanly after 192 statistics updates, with no capture or UI callback errors. Earlier fixed-duration screen checks had timing/count failures; no production shutdown change was made. No physical device was connected.
