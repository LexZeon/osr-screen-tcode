# 2.0.0-test.18：往复区域优先与点参考脚本

双击根目录 [Start.cmd](../Start.cmd)，确认标题 `2.0.0-test.18`。可点击入口和操作说明见 [Start.md](../Start.md)。当前只更新测试源码，没有新 exe/ZIP。

## 跟随哪个区域

混合 v2 和全／半行程共用以下区域优先顺序：

1. 当前持续往复的区域。
2. 之前往复过、现在仍可连续跟踪的区域。
3. 当前具有最大持续位移的区域。

历史随实际跟踪区域移动，不绑定在固定屏幕坐标。新区域需连续胜出约 0.3 秒才切换；同级当前往复或幅度竞争还需明显胜过现区域。曾往复的区域不因短暂停顿就被单向大幅运动抢走，但失去跟踪超过约 0.45 秒后不再保留这项优先权。切镜头、重设参考清空历史。幅度比较使用短时间内一致的净位移，过滤零碎抖动。黄框和三轴显示实际采用区域；说明区显示采用哪一级优先权。

快速小区域以前可能已经跟踪成功，却因未达到全画面 4% 的面积要求被当作突变。本版允许具有充分点数、二维跨度、覆盖和独立背景支持的紧凑区域通过。较快但支持不足时短暂保持并说明原因，不立即清空全部参考。超过原有硬突变界限仍重置；没有把任意大位移当成有效动作。

## 根据往复中心生成 L0

在“分析预览”或开始分析的确认窗口选择 **v2 L0 参考 → 往复中心点**。这个设置只在混合 v2 和全／半行程显示，支持保存、重新加载、取消确认窗口和恢复默认。默认仍是 **三维运动轴**，已有分析模式选择保留。

- **三维运动轴（默认）**：保留原来的连续三维代理坐标输出。
- **往复中心点**：从已确认往复的端点估计中心 C，将当前沿主方向的位置映射到 L0 行程，更直接跟随视频往返相位。确认前使用原运动轴；暂停保持。C 是画面中的轨迹参考，不要求它是真实接触点。
- **交互点候选（实验）**：用扣除运镜后的区域扩张／收缩估计会聚候选 P?，经过多帧确认和实际往复后，按区域靠近／远离这个点生成 L0。平行移动、旋转或不一致光流无法确定唯一点时，不猜测接触点。短暂缺失保持；持续不可辨则平滑交回原运动轴。

来源发生变化时，首个新目标从上次目标继续，再逐步对齐新参考，不直接跳到新参考的绝对位置。点来源只替换 L0；六轴其余方向仍按原三维坐标和可选 RTM 2D 旋转辅助处理。纯 Pose 与 v1 不使用这个选项。

全／半行程保持底→1/4→底、底→中→底、底→高→底的离散幅度和余弦周期生成。中心选项使用同一主轴往复幅度／节奏；交互候选建立后改用靠近／远离的往复证据，不能把普通 v2 的连续相位映射误当作全／半行程的新幅度。

五档、总行程／逐轴倍率、反向、限位和最终时序减速仍在后续输出阶段应用。录制、视频导出、实时输出和模拟器继续使用原最终输出链路，点估计不会接收最终指令反向作为分析输入。

## 图上的 C 和 P?

C 是轨迹中心估计；P? 是有条件建立的运动会聚候选，**未确认真实接触**。点和选区均来自同一采样帧。没有足够证据时显示“确认中／不可辨”，不会用一个固定画面中心冒充接触点。

小窗口内自动使用简短说明，保留区域优先级、当前来源和拒绝原因；点击“参考详情”可看完整数值。不使用 Pose 时隐藏其四项处理开关，启用旋转辅助后重新显示。交互候选短暂缺失会明确显示“保持”；全／半行程显示当前实际采用证据的跨度。

本版参考光学扩张可辅助判断运动方向、但尺度与真实深度仍有歧义的思路：[Yang & Ramanan, CVPR 2020](https://openaccess.thecvf.com/content_CVPR_2020/html/Yang_Upgrading_Optical_Flow_to_3D_Scene_Flow_Through_Optical_Expansion_CVPR_2020_paper.html)。实现是本地鲁棒几何估计，没有移植论文网络或新增模型／依赖。单目区域扩张也可能来自物体形变、相对缩放等，不能据此确认空间接触或机械结构。

## 修改位置

- `src/osr_screen_tcode/motion_focus.py`：区域历史、往复优先级与防抖切换。
- `camera_motion.py`：实际候选选择、紧凑快速运动验证、点估计接入。
- `interaction_point.py`、`point_l0.py`：会聚候选、往复中心与 L0 来源接续。
- `visual_pipeline.py`：共享分析结果、v2 L0 和全／半行程接入。
- `motion_reference.py`：实际区域优先级、C／P? 与当前来源显示。
- `app.py`、`config.py`、`integrated_preview.py`：中英文选项、保存／恢复默认与确认窗口。
- `tests/test_motion_focus.py`、`tests/test_point_l0.py`、`tests/motion_scenes.py`、`tests/ui_smoke.py`：多区域竞争、快速区域、点估计、来源连续性和导出验证。

## 验证

- 主程序完整 **252 项通过**，约 257 秒；含原 v1 基准、Pose、设备失败、最终乘算、区域竞争、快运动、点参考和导出。全套后仅修改诊断显示与小窗口布局，相关测试另行复验（结果见下方）。
- 独立预览 **28 项通过**；未修改独立预览代码。
- 模拟器最终指令检查通过：坐标／时间保留，动画不覆盖最终指令。
- 根目录 `Start.cmd --smoke --language zh/en` 与 Lab `Start.cmd --smoke` 均正常退出。
- 中英文可见窗口检查通过：多区域往复中心、径向交互候选、全／半行程与模拟 Pose 旋转辅助；截图仅保存在临时目录，使用合成画面。
- 真实屏幕采集使用 Log only 运行并正常停止，154 次界面采集统计更新，无硬件写入／线程错误，不保存用户设置。此项验证运行链路，不等于验证原视频识别质量。
- 新增可纳入源码的文件只有源码、测试与文档；未添加模型、运行库、日志、缓存、用户设置或测试媒体。差异格式检查仅保留接手时 `CONTRIBUTING.md`、`OPEN_SOURCE_NOTICE.md` 的已有末尾空行提示。

界面调整后的区域／点参考 17 项复验通过；最终点参考／全半行程 15 项复验通过，最终英文带旋转辅助界面重新检查通过。

固定种子合成片段中，50×50 的快速局部区域在 320×240 画面内往复：有效帧由旧版 18/73 提高到 67/73。往复中心模式与合成运动相位的相关性约 0.99；径向运动候选的靠近／远离输出约 0.89。这些是特定合成条件的结果，不是实片准确率。

## 残余风险与复测

仍需用用户原视频复测。严重模糊、过大帧间位移、遮挡、强烈变形、缺乏独立背景或多个重叠主体仍可能保持或选错区域；强快速变形测试仍存在较多拒绝。会聚点不一定是用户想要的语义交互点。中心与主方向会随新观测慢慢更新，不能保证所有片段的相位完全一致。

建议先选 Log only，打开分析预览，对比三种 L0 参考。观察黄框是否跟随预期部位，C/P? 是否合理；先暂停再继续播放，检查输出接续，再看输出监视或模拟器中的最终结果。原 v1、直接 Pose、设备发送频率及最终输出算法本轮未改。

未连接真实设备；机械臂关节映射、逆运动学、碰撞检测和反馈尚未验证。正式目录、旧发布包与远程历史未修改，未打包、提交、推送或安装依赖。

## English

Test.18 prioritizes current reciprocal regions, then previously reciprocal regions that remain tracked, then the greatest sustained displacement. History follows tracked endpoints; temporal competition and path consistency suppress switching on jitter. Compact fast regions can pass with strong local support and an independent camera reference.

The v2 L0 reference selector offers the original 3D motion axis (default), stroke center C, or an experimental interaction candidate P?. C maps confirmed stroke phase to L0. P? uses supported radial expansion/contraction and requires temporal and reciprocal evidence; it cannot confirm physical contact. Missing evidence holds briefly and then returns smoothly to the original axis. Paused frames do not generate new point displacement. Source transitions start from the previous target.

Cycle mode retains quarter/half/full cosine strokes and uses the shared primary-axis evidence, or qualified approach/recede evidence for P?. Other axes, direct Pose, v1 and downstream output processing retain their existing behavior. The selector is saved, restored, translated and shared with startup confirmation. Final gains, limits and slowdown still apply to scripts and simulator commands.

Real footage, severe blur/deformation, ambiguous camera motion, semantic contact and physical hardware remain unverified. Image scale is not depth. This is a source-only test update.
