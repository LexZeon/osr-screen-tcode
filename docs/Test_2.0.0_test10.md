# 2.0.0-test.10 / Local source test

只更新测试目录源码。双击根目录 [Start.cmd](../Start.cmd)，[Start.md](../Start.md) 是说明。没有打包、提交或推送；独立 Lab 保持 0.2.1-test。

## 混合分析 v1 名称

改为 **混合分析（推荐-平面大幅动作）** / **Hybrid Analysis (Recommended - Large Planar Motion)**。原 v1 的分析和 L0 数值算法未改；旧中英文“内测”名称会迁移到新名称，已有输出设置保留。列表顺序仍为全/半行程、RTM Pose 2D、v2、v1；默认选中仍是 v2。

## v2 背景参考反复缺失

用户确认 test.9 主要闪烁的是“背景参考分布不足”。本轮处理实际筛选及状态连续性，而不是单独隐藏提示：

- 除原有分布广的背景外，允许足够长、有横向与纵向跨度、运动一致的边缘背景带，不再强求它覆盖三个象限。
- 背景部分遮挡时，允许用至少四个此前已确认、且本帧仍成功跟踪的背景点继续估计；仍校验点间跨度和运镜变化一致性。不把旧运镜直接外推成新观测。
- 短暂丢点最多保留参考 0.45 秒，显示“短暂丢点；保持参考”。该帧没有有效测量，输出保持，图表留缺口；不重复清空主轴、往复跨度与全/半行程的周期阶段。
- 区域仍被成功跟踪、只是停顿或换向变化很小时，保留区域；不再因为超过 0.3 秒没有明显速度就删掉参考。
- 持续缺失会清除参考；空白替换帧、过大突变、长断帧仍重置。恢复时不补算丢失期间的运动。

借鉴 v1 的区域连续性和三帧中位数抗噪思路，**只对扣除运镜后的 v2 局部运动应用**。真实跟踪端点仍供旋转估计和参考点显示；没有把 v1 的原始全画面信号接回 v2。全/半行程复用同一 v2 管线，因此同步获得这些修复。

## 更灵敏的 1/4 行程

全/半行程模式新增 **底→1/4→底**，现在按已确认的画面往复幅度自动选择四种状态：不动、1/4、半、全。1/4 档生成的是实际 L0 曲线，进入实时输出与录制／导出；不是只增加一个显示标签。

- 最小启动跨度从 1.5 降到 0.85 个图像百分点，但仍需达到原往复检测的方向反转幅度和持续时间，微小高频抖动不会直接启动。
- 达到 3 进入半行程，低于 2.4 回到 1/4；达到 8 进入全行程，低于 6 回到半行程。阈值间保留档位，避免频繁跳档。
- 保留余弦曲线和逐步节奏适应；短暂丢点暂停输出和周期阶段，不凭空继续往复。长时间无有效证据则停止并保持。
- 六轴可选 RTM 2D 旋转辅助，L1/L2 仍居中。五档、总行程／轴倍率、反向、原有限制及输出曲线拟合继续作用，可能改变最终幅度与跟随效果。
- 接近上下限减速仍默认开启、距离 10%，只改到达时间，不改目标坐标；导出时长可能增加。

## Pose 六轴输出联动

RTM Pose 2D 下，根据 L0 低／中／高计算的 L1/L2 倍率改为 **0.5／3.5／0.5**，中间连续线性变化。只在最终 TCode 映射处作用，以本条指令已经受限／限速后的 L0 为准。L1/L2 识别位置不变时，L0 从中段移向任一端仍会让实际输出向中心收拢；居中位置仍居中。

该固定输出规则无需新增设置，保存和恢复默认均使用同一规则。v2 图像平移仍为 1／2.5／1，勾选 RTM 旋转辅助也不套用 Pose 平移倍率。骨架、观测和脚本分析数据不应用此联动；模拟器仍接收实际输出端最终指令。中段放大后可能更早触及已有输出限制。

## 文件与验证

- `src/osr_screen_tcode/camera_motion.py`：背景带、已确认背景点跟踪、短缺保持、局部三帧中位数。
- `dominant_motion.py`、`visual_pipeline.py`：短缺时保存识别历史，不新增测量。
- `stroke_cycle.py`：1/4 档与暂停周期。
- `config.py`、`app.py`：v1 标签和旧名称迁移。
- `pose_output.py`、`tcode.py`、`app.py`：Pose 0.5／3.5／0.5 联动，保持 v2 原倍率。
- `motion_reference.py`、`integrated_preview.py`：中英文状态、1/4 显示及较矮窗口的说明字号。
- `tests/test_camera_motion.py`、`test_stroke_cycle.py`、`test_output_presets.py`、`test_device_ui.py`：新增场景、实际导出和配置迁移检查。

主程序 **154 项测试通过**；覆盖原 v1 精确数值、背景带往复／纯运镜、间歇与持续丢点、停顿不清除区域、背景部分遮挡、微抖拒绝、1/4 实际导出及 Pose 联动。独立 Lab **28 项通过**；模拟器最终指令测试、主程序中英文与独立 Lab 的 Start.cmd 启动检查通过。界面检查使用 Log only 和生成画面，不保存个人设置。

**残余限制：** 尚未用用户原始问题片段验证。缺少独立背景、严重遮挡或错误背景归属时仍可能保持或误判；短缺保持不能恢复未观测到的运动。1/4 灵敏度、档位阈值及节奏匹配仍需真实片段测试。没有连接真实设备，也不代表已兼容机械臂；关节映射、逆运动学、碰撞及反馈仍未验证。

## English

Hybrid v1 is now **Recommended - Large Planar Motion**, with its original numerical algorithm unchanged and old names migrated. V2 can use a coherent peripheral background band or freshly tracked, previously established background points when some are occluded. Brief losses hold output/reference for up to 0.45 s without inventing measurements or repeatedly resetting stroke evidence. A genuinely tracked stationary region stays valid; sustained loss, abrupt invalid motion and long gaps still reset.

V2 borrows v1's region continuity and three-frame median filtering after camera compensation. Full/Half Travel shares these changes and adds a more sensitive quarter-travel cosine cycle. Confirmed excursion thresholds are 0.85 minimum, 3/2.4 for quarter/half hysteresis, and 8/6 for half/full; high-frequency micro motion still needs valid reciprocal evidence. Existing output gains and timing-only approach braking remain in effect.

Direct RTM Pose 2D six-axis TCode coupling is now **0.5/3.5/0.5**, using each command's limited L0. Fixed L1/L2 observations move closer to output center as L0 approaches either end. V2 retains 1/2.5/1 with or without pose rotation assistance. Observations and script analysis data are unchanged; existing limits still apply and may be reached sooner around middle L0. This fixed rule needs no new saved setting.

Validation: 154 main tests, 28 standalone tests, simulator command checks and main Chinese/English plus standalone startup checks passed. The quarter cycle was checked through actual funscript export. Original user footage and hardware were not tested; camera separation, motion thresholds and cadence matching remain experimental.
