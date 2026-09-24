# 2.0.0-test.21：独立目标跟踪、到达比例与画外目标接续

双击根目录 [Start.cmd](../Start.cmd)，确认标题 **2.0.0-test.21**。操作说明见 [Start.md](../Start.md)。仅更新测试源码。

## 用户要求与采用方式

橙点应该定位动作朝向的另一个物体，不能一直跟着三维轴；两者外观可以不同。用户明确确认：**三维轴原点到达橙点**才算完全到达，不是运动物体前缘碰到橙点。

目标可能在画面外，切镜头后实际接触双方甚至都不在画面里。这时应分析画面中可见物体的往复，不等待接触双方出现，也不沿用上一镜头的目标坐标或规律。

在 **v2 L0 参考 → 融合参考（默认）** 中启用本轮逻辑。已有保存的其他参考选择继续保留；选择其他参考仍使用原算法。没有新增设置键，主界面、分析预览、中英文、保存和恢复默认共用原设置。

## 独立目标

`target_regions.py` 沿已经测得的往复轨迹寻找可能到达的物体边界，使用颜色通道边缘、区域轮廓、轨迹范围、实际特征支持及候选竞争判断。候选必须在运动区域之外、位于轨迹端部朝向；不会为了让橙点远离三轴而人为挪动坐标，也不会把屏幕边缘当作接触点。

`reach_target.py` 使用候选物体自己的分布式特征和稳健变换跟踪。它比较的是目标与自己先前的外观，**不比较目标与运动主体的外观**。至少六个分布充分的点及连续确认才能提供到达比例；部分点丢失时可继续使用其余可靠点。运动主体覆盖目标时，其采样点不能接管目标。目标外观明显变为背景、候选被穿过或轨迹明显从旁边经过时，撤销或暂时搁置候选。

主运动与目标分别验证。主运动区域短暂失败、但目标及运镜仍能确认时，可以继续更新目标坐标；缺失的三轴原点不会被当作新的到达观测。目标失败而主体仍在运动时，从当前 L0 接回可见运动参考。复用已有采样和运镜结果，不增加模型、第二路采集或改变原有采样顺序。

橙色 **T?** 现在表示独立跟踪的物体边界候选。其采样点和区域轮廓也以橙色显示。test.20 的外部会聚参考改标灰色 **P?**；灰色 **E?** 是轨迹端点，**S?** 是局部缩放中心。上述几何候选均不能确认语义接触。

## 到达比例与输出

当原点和目标都有效时，用二者的画面距离除以已经观察到的退离距离，得到剩余比例。剩余比例越大，L0 越高；越靠近，L0 越低。三轴原点与橙点重合（允许小于约两像素的定位容差）时，估计到达 100%，分析 L0 为底部。只有横坐标相同、纵坐标还相差较大时不算完全到达。

新目标、目标恢复及回退到可见运动，均从当前输出接续，约 0.3 秒过渡并受连续速度约束；不会跳到新参考的绝对起点。已确认到达后即使画面暂停，也能完成平滑收尾。普通 v2 使用距离比例；全／半行程共用证据并保留 1/4、半、全行程的离散峰值及余弦曲线。可选 RTM 2D 旋转辅助走同一套目标参考。

预览中的比例明确标为图像估计、输出倍率前。五档、总行程、轴倍率、联动、反向、限位、减速、导出及模拟器继续走原有最终输出链路；实际指令可能与分析百分比不同。未改 v1 和直接 Pose 的分析、基础倍率或兜底规则。

## 画外、遮挡与切镜头

- 已跟踪目标移出画面：有可靠运镜时短暂搬运其坐标，最多保留两秒。位置保持在画外，边缘箭头只表示方向，**箭头端点不是到达位置**。仅搬运坐标不会产生到达比例或刷新目标确认时间。
- 运镜本身不明：隐藏无法配准的旧坐标，恢复后重新选点，不在新画面上画旧橙点。
- 目标未出现或暂时不可见：可见物体运动仍有效时，继续按原有优先级“当前持续往复 → 曾往复且仍能跟踪 → 当前持续运动幅度”产生 L0。不会将这个代理运动相位标成实际到达比例；远近没有证据时保留稳定方向并注明待确认。
- 切镜头：清除旧目标、旧相位和旧预测规律；只从新镜头的可见运动建立参考。即使接触双方都不在画面里也可以分析。
- 可见主运动也不清：只延续此前已确认的往复，最多两秒，最后半秒渐慢。明确暂停不继续振荡，预测不冒充观测。

## 文件

- `src/osr_screen_tcode/target_regions.py`、`reach_target.py`：新候选与独立目标跟踪。
- `camera_motion.py`：提供已验证的当前帧对应，让目标跟踪不受主区域短暂失败牵连。
- `point_l0.py`、`fused_l0.py`、`visual_pipeline.py`：到达比例、连续切换、共享全／半行程及暂停收尾。
- `motion_reference.py`：橙点、采样、画外箭头和中英文状态。
- `tests/test_reach_target.py`、`tests/motion_scenes.py`、`tests/ui_smoke.py`：不同外观双物体、只有可见代理、到达几何和显示回归；`tests/check_live_pipeline.py` 改善读屏检查计时及失败诊断。
- 版本、README、Start.md、AI 交接与两份日志同步更新。

## 研究参考

[OpenCV 光流教程](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html) 用于已有稀疏对应的跟踪思路。[Joint Hand Motion and Interaction Hotspots Prediction，CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/html/Liu_Joint_Hand_Motion_and_Interaction_Hotspots_Prediction_From_Egocentric_Videos_CVPR_2022_paper.html) 将运动轨迹与动作目标位置作为不同任务，支持此处把三轴区域与目标独立表示；[StillFast，CVPR 2023 Workshops](https://openaccess.thecvf.com/content/CVPR2023W/Precognition/html/Ragusa_StillFast_An_End-to-End_Approach_for_Short-Term_Object_Interaction_Anticipation_CVPRW_2023_paper.html) 是联合静态外观与时间信息的目标交互预测参考。本轮只采用适合现有程序的几何实现，没有实现论文网络、安装模型或新增依赖。

## 验证记录

- 主程序完整 **279 项通过**（513 秒），包括新增 11 项；覆盖原 v1 数值、Pose、v2 运镜、往复、设置、最终输出和全／半行程。
- 完整测试启动后又补了“未知运镜隐藏旧坐标”的细节和紧凑显示：最终目标回归 **11 项再次通过**（42.7 秒），显示／历史候选相关 **6 项通过**（14.8 秒）。没有把较早导入模块的完整测试冒充这些最后细节的验证。
- 独立预览 **28 项通过**；JavaScript 模拟器检查通过，最终指令不会被演示动画覆盖。
- 主程序 `Start.cmd --smoke --language zh/en`、独立预览 `Start.cmd --smoke` 通过；主程序标题为 **2.0.0-test.21**。
- 已检查中文独立目标、英文画外箭头、中文全／半行程＋骨架旋转辅助、中文只有可见运动代理四种窗口画面。橙点与三轴分离，未知到达比例不伪装为测量值。短预览中优先显示关键状态，完整信息在“参考详情”。图像仅存系统临时目录。
- 实际读屏 Log only 复测 **171 次统计更新**，正常停止，工作线程已退出，无采集错误或界面回调错误。末次统计约 67 FPS 采集／29 FPS 分析、输入帧龄 14.1 毫秒；仅代表此次桌面内容，不是所有视频或 45 FPS 的保证。默认处理最长边仍为 640。
- 相关文件语法、空白、冲突标记及个人路径检查通过；没有新增媒体素材、模型、运行库、缓存、用户设置或运行日志进入交付源码。

新增像素回归逐帧对比了开启／不提供独立目标参考时的主运动测量，结果完全一致；不同外观的双物体片段可跟踪独立边界，目标横坐标误差在测试约束的 4 像素内。另有原点重合到底、纵向错位不误报到达、越过候选不倍频、画外不钳制坐标、只剩可见代理仍输出、主区域短暂失败目标仍跟踪及切换无跳变的检查。这些均为可控合成场景，不能代表所有真实目标。

验证过程中也记录了失败：初版新增回归暴露主区域失败连带中断目标跟踪，修正两者独立跟踪后通过；最初两次截图未充分完成首次绘制，调整检查工具的布局及绘制时序后复验，并修正了短预览文字截断。第一次旧读屏检查在短固定时间内未获得足够统计更新（次数断言失败，其前的错误／回调／线程退出检查已通过）；工具改为窗口初始化后启动、从实际启动开始运行 8 秒并留出 1 秒收尾，复测 171 次通过。没有将第一次短时失败记为通过。

## 残余限制

这是物体边界和往复轨迹的几何候选，并非通用物体分割或语义接触检测。相邻多个物体、近似背景边界、纹理不足、严重模糊、变形、遮挡和以景深变化为主的镜头仍可能拒绝或选错目标。没有任何目标证据时，无法凭空恢复从未出现过的画外接触坐标；此时使用可见运动代理。

距离来自二维画面，既不是真实物理距离，也不是完整相机标定。退离距离由已观察到的运动估计，素材尚未展示完整行程时会继续调整。画面尺度仍不是真实深度。合成片段和桌面检查不能替代用户原视频复测。候选扫描最多每秒五次，跟踪也有开销，实际速度取决于画面和机器。

未连接真实设备，机械臂映射、逆运动学、碰撞检测和反馈未验证。无依赖安装／升级、打包、提交或推送；正式源码、旧发布包和远程历史未修改。测试图像仅在系统临时目录，不交付本地素材、模型、设置或日志。

## English

In the default fused v2 reference, orange **T?** is now an independently tracked object-boundary candidate. Its own features, geometry and appearance establish continuity; the target need not resemble the mover. Reliable source-axis-origin-to-target distance drives L0, with estimated 100% reach at the bottom before final gains. Source changes enter continuously. Quarter/half/full mode and optional RTM rotation assistance share this logic while retaining discrete travel classes and cosine easing.

Targets and source regions can lose tracking independently. An offscreen known target is briefly transported only by verified camera motion; its edge arrow is a direction, never a substitute contact coordinate. Unknown camera registration hides stale coordinates. With no target or with neither contact participant visible after a cut, measured reciprocal motion of visible objects drives L0 without waiting for a target. It is labeled as a motion proxy, not confirmed reach. Cuts discard old evidence; only loss of measured motion invokes the existing confirmed-rhythm continuation of at most two seconds, braking during the last half second.

Gray E?/S?/P? distinguish stroke endpoints and convergence references. All targets remain geometric candidates, not semantic contact or physical depth. Saved settings, defaults, final output processing and simulator command delivery are preserved. No new dependencies, hardware tests, packages, commits or pushes.

Validation: **279 main tests and 28 standalone tests passed**. The final coordinate-hiding and compact-display refinements were covered by 11 target tests and 6 reference tests respectively. Both startup languages, the standalone launcher, simulator command checks and four window scenarios passed. A first short Log-only check failed its update-count assertion; the revised startup-timed 8-second check produced 171 updates, stopped cleanly and reported no capture/UI errors. The measured desktop throughput is not a performance guarantee for arbitrary videos.
