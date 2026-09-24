# 2.0.0-test.20：区分轨迹端点与目标，改善远处候选定位

双击根目录 [Start.cmd](../Start.cmd)，确认标题 **2.0.0-test.20**。入口说明见 [Start.md](../Start.md)。只更新测试源码。

## 修正原因

用户确认：画面真正朝向的目标更远，橙色 T? 却像跟着三维轴移动。核对 test.19 后发现，无可靠会聚点时，T? 实际取自“当前区域附近的往复中心，加减半个轨迹跨度”。它属于轨迹端点，本来就容易靠近随区域移动的三维轴。局部缩放的会聚中心也常落在区域内部，不能因此确认语义交互目标。

另外，旧会聚拟合要求每帧缩放至少 0.4%，容易排除远处目标对应的弱缩放；单帧光流误差经过远距离外推还会被放大。仅放宽阈值不足以解决像素级定位，因此本轮加入更长帧间的实际跟踪作为候选定位证据。

## 画面标注

- **E?**：轨迹端点；无法确认交互目标。方向已确认时显示近端，否则注明远近待确认。
- **S?**：落在跟踪区域内的局部缩放中心；交互目标未定位。
- **T?**：落在区域外的会聚目标候选；仍未确认真实接触。
- **C**：往复相位中心。单独显示的 **P?** 是光流会聚候选；与 T?/S? 重合时不重复叠字。

这一区分只改变显示含义，不强行拉远坐标，不排除真实的近处运动，不用距离阈值改变 L0 极性。设置没有新增或迁移：中英文、“融合参考”的默认值、保存和恢复默认仍共用现有设置。已有保存选择不会被覆盖。

## 定位改进

`interaction_point.py` 在稳健筛选后重新拟合最终支持，检查二维分布、实际径向信号和外推不确定度。纯平移、旋转、近直线采样与噪声不能只靠小分母生成远处点。较不确定的有效候选以较低权重更新位置，减少转向附近抖动。

单帧不足时，`target_baseline.py` 使用 v2 已有短时历史图像（当前历史窗口满足不超过 0.2 秒），将当前已验证的前景点、背景点重新匹配到较早画面。最多 54 个前景点和 36 个背景点；采用真实往返光流与图像误差检查，另行验证这一帧对的运镜。背景不确定度会进入目标判断，不能靠增加前景数量把共同运镜误差平均掉。

附加匹配不做昂贵的快速图块搜索。主分析原有快速补匹配、采样顺序、区域选择及运镜分离保持。较长帧间位移**只用于定位候选点**，径向 L0 增量仍来自当前帧对的实际端点，不把几帧位移重复累计。缺失时只能用已经测得的运镜搬运候选坐标，不能刷新确认时间或生成测量值。

普通 v2 与全／半行程共用此改进。v1、直接 Pose 的算法与倍率、五档、行程、联动、最终限位／减速和模拟器链路保留。test.19 的“仅延续已确认规律、最多 2 秒、最后 0.5 秒减速”继续使用。

研究参考：[OpenCV 光流教程](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html) 的稀疏对应与往返验证；[Optical Expansion，CVPR 2020](https://openaccess.thecvf.com/content_CVPR_2020/html/Yang_Upgrading_Optical_Flow_to_3D_Scene_Flow_Through_Optical_Expansion_CVPR_2020_paper.html) 对光流、缩放与三维运动尺度歧义的区分。这里使用适配现有程序的几何实现，没有引入论文网络、模型或新依赖。

## 文件

- `interaction_point.py`、`target_baseline.py`、`camera_motion.py`：候选定位、较长帧间验证和缺失时的运镜修正。
- `fused_l0.py`、`motion_reference.py`：标注类别及中英文说明。
- `motion_tracking.py`：附加匹配可以跳过快速图块搜索，主分析默认行为不变。
- `tests/test_target_reference.py`、`tests/motion_scenes.py`：已知远处目标、像素跟踪、噪声／平移拒绝、运镜及超时验证。
- `tests/ui_smoke.py`：增加远处目标画面检查。版本、README、Start.md、交接指南和日志同步更新。

## 验证记录

- 主程序完整 **268 项通过**（约 309 秒），包含本轮新增 6 项回归；相关定位／融合 26 项先行验证通过。原 v1 数值、Pose、背景分离、重复帧、输出、全／半行程、设置保存／恢复默认一并通过。
- 独立预览 **28 项通过**，源码未改动。
- JavaScript 模拟器检查通过：最终指令保留，动画不能覆盖实际输出。
- 主程序 `Start.cmd --smoke --language zh/en` 与独立预览 `Start.cmd --smoke` 通过，主程序标题为 **2.0.0-test.20**。
- 三张窗口图像检查通过：中文远处 T? 与跟踪区域分离、英文 S? 明确目标未定位、中文全／半行程 E? 明确只是轨迹端点。仅合成画面，图像留在系统临时目录。
- 实际读屏 Log only **182 次统计更新**，正常停止，没有采集或界面回调错误。末次统计约 91 FPS 采集／90 FPS 分析、输入帧龄 6.3 毫秒，仅代表该次桌面画面，不是复杂视频的性能保证。用户设置未保存，未连接硬件。
- 改动文件的空白、冲突标记与隐私路径检查通过。没有模型、运行库、媒体素材或日志加入交付源码。

新增几何及像素回归已通过：弱缩放可定位远处点；候选不会因为跟踪区域移动而被拉回轴中心；缺失搬运不延长证据期限。实际像素场景逐帧核对“启用／禁用较长帧间定位”的主运动测量完全一致。

在 320×240、241 帧的已知径向目标合成片段中，初期较短基线方案仅有 3 帧有效确认，较长帧间方案得到 97 帧确认（其中 90 帧可标注外部 T?），95% 定位误差约 2 像素。更小的 2.5% 尺度振幅片段仍只有少量确认，未把它描述为已解决。这些数字只代表该合成素材；较长匹配仍可能失败。

## 残余限制

会聚点不是语义接触检测。纯平面平移、严重模糊、遮挡、很小幅度、画面外目标或复杂变形可能无法定位真正交互目标；此时 E?/S? 不会伪装成 T?。真正目标也可能落在选中区域内部，此时保守显示 S? 并继续使用几何运动证据。用户原视频仍需复测。增加的短时匹配有处理开销，实际帧率取决于画面和机器。

真实设备、机械臂关节映射、逆运动学、碰撞与反馈未验证。未连接设备、安装或升级依赖、打包、提交或推送；正式仓库和旧发布包未改动。

## English

Test.20 distinguishes **E?** (trajectory endpoint), **S?** (internal expansion center) and **T?** (external convergence candidate, contact unconfirmed). Previous endpoint fallbacks naturally stayed near the moving axis origin; they no longer claim to locate an interaction target. Marker coordinates are not artificially displaced.

Weak but supported radial motion is evaluated by uncertainty rather than a fixed per-frame scale floor. An optional older frame pair revalidates bounded foreground/background correspondences and its own camera fit to locate distant candidates. Only the candidate position uses that longer baseline; current-pair increments still drive L0. Camera-only transport of a missing point never renews evidence. Existing settings, default/save/reset behavior, output mappings and the 2-second continuation remain unchanged.

Semantic contact, very small planar movement, severe blur and the user's original footage remain unverified. No physical device, installation, package, commit or push was involved.

Validation: **268 main tests and 28 standalone tests passed**, plus simulator command checks, both startup languages, three window-image checks and a live Log-only run with 182 statistics updates and a clean stop. Current-pair camera/motion values remain identical with and without the additional target baseline in the pixel regression.
