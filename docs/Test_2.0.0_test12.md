# 2.0.0-test.12 / Local source test

双击根目录 [Start.cmd](../Start.cmd)，操作说明见 [Start.md](../Start.md)。仅更新当前测试源码，独立 Pose Preview Lab 仍为 0.2.1-test。

## 快速拖动窗口与背景缺失

用户在 test.11 读屏拖动电脑窗口时发现：移动快了会丢失，预览显示“背景参考分布不足”。在不读取个人桌面内容的合成窗口中复现了以下问题：

- 大窗口进入原采样格时，文字／边界的强角点会挤掉同格的小背景角点。
- 金字塔光流在小背景上可能受大前景影响；快速移动的重复文字也可能匹配到相邻行，出现看似有效但方向／距离错误的跟踪。
- 原先单帧相对位移超过画面 6% 就重置，即使局部区域和背景都拟合良好。
- 小背景筛选要求其余大部分点共同符合一个变换，不适合多个部位独立运动。

test.12 在原 v2 管线内修正：

1. 保留原网格，并在上下外围窄带独立采样，减少小背景被挤掉的问题。默认处理最长边仍是 640。
2. 增加细尺度光流；用当前帧图块误差选择有证据支持的跟踪。对失败／较差的点，最多搜索 48 个分布开的图块，搜索范围受画面比例和 96 像素上限约束；要求高相关和明确的唯一匹配峰值。
3. 附近至少三个一致的可靠图块匹配可为重复文字提供初值，随后仍需通过当前帧的光流往返及图块检查。初值本身不会作为观测或设备目标。
4. 6% 以上的平移需额外满足点数、覆盖、拟合误差和一致性验证；超过 20% 仍重置，尺度突变与切镜头检查保留。不能仅凭移动快就生成有效观测。
5. 最多分离六个一致运动群，允许前景由多个独立运动群组成。外围归属、背景外推误差和连续确认继续检查；没有独立背景时不回退到全画面运镜输出。
6. 参考不足时显示候选点数、运动群数量和具体拒绝原因；实际采用的背景点仍单独计数，候选点不会伪装成已接受的蓝色背景点。图块补匹配显示实际通过检查的点数。中英文同步。

全/半行程、1/4 行程和 v2 共用上述分析；v1 的数值分析未修改。没有引入新模型、依赖或素材包。

方法核对参考 [OpenCV 光流文档](https://docs.opencv.org/4.5.4/dc/d6b/group__video__track.html)：细尺度跟踪与带初值的 LK 用于不同位移条件；图块匹配及验证是本项目独立实现。素材采用可重复生成的文字窗口和纹理场景，不包含用户桌面图像。

## Pose 基础倍率

| 项目 | test.11 | test.12 |
| --- | --- | --- |
| 直接 RTM Pose 2D 的 L0 | 5 倍 | **10 倍** |
| Pose 提供的 R1/R2 | 2 倍 | **1.5 倍，原幅度的 75%** |
| Pose L0→L1/L2 联动 | 0.5／3.5／0.5，峰值 2/3 | 保持 |

倍率应用于相对中位的偏移，后续用户倍率、限位、反向等照常作用。L0 只用于直接 Pose，单／六轴和实时／录制／导出共用；v2 的 Pose 辅助不重复放大 L0。R1/R2 同步作用于直接 Pose 及混合／全半模式的 Pose 旋转辅助，R0 和不带 Pose 的图像旋转估计保持现有行为。骨架观测不受这些倍率影响。达到限制后，最终行程不会再按比例增加。

## 到达时间与实机微抖

用户还报告疑似 L0 的细小抖动，并询问 20 ms 是否更好。**20 ms 对应 50 Hz，并不是降低频率**；原设置实际写入 TCode 的 I 到达时间，发送跟随分析更新。Pose 分析慢于 24 ms 时，设备可能提前到达目标后等待下一条，因而有停走感；这只是从代码得到的可能原因，未通过实机确认。

当前实时输出用最近最多五次更新间隔的中位数作为到达时间参考，取其与用户设定下限的较大值，然后应用上下限减速。不改变目标坐标、不补发历史目标，也不将分析线程改为定频发送。

- 界面由“间隔 ms”明确为“到达时间下限 ms”，中英文提示说明其意义。原保存字段 `output_interval_ms` 和默认 **24 ms** 保留，保存／恢复默认同步。
- 暂停超过 0.5 秒或回中后清除节奏历史；手动／急停回中的显式时间不受影响。
- 模拟器仍接收输出端实际接受的最终指令及时间；离线脚本继续以源视频时间为基础，不带入本机处理快慢。原有脚本末端减速规则保留。
- 本轮没有增加目标死区。若监视数值本身来回跳动，或驱动器／机械机构产生抖动，需要另行定位；不能保证节奏修正消除微抖。L0 基础倍率提高也可能放大输入细微变化。

## 验证记录

- **主程序 169 项测试通过**（204.691 秒）；随后合并诊断文字、补充保存／默认断言后，相关 **54 项再次通过**。
- **独立 Lab 28 项通过**；模拟器最终指令检查通过。
- 主程序中英文、独立 Lab 的 Start.cmd 启动检查通过。主程序启动提示现在直接读取源码版本，避免硬编码旧版本号。
- 中英文可见窗口检查通过；修正了英文缺失诊断挤掉底部 L0 数值的问题，参考画面与诊断均可见。截图只在系统临时目录。
- 640×480 合成文字窗口，以每 12 帧完成一次 ±75 像素往复，连续 97 帧得到 **92 帧有效运动、2 帧建立参考、3 帧缺失**；后段 L0 分析跨度 **53.6%**。纯整幅画面快速移动未生成行程，随机纹理切镜头仍重置。测试不使用用户桌面或真实硬件。
- 同一快速窗口场景分析器调用耗时中位数 **50.22 ms**、95 分位 **70.94 ms**（去除前 12 帧，不含画面生成、采集、Tk 绘制、设备 I/O 或 RTM 推理）。额外匹配增加开销；这是本机指定合成场景的测量，不代表完整应用帧率或实际素材准确率。

## 文件位置

- `src/osr_screen_tcode/motion_tracking.py`：细尺度跟踪、有限范围图块补匹配及初值验证。
- `src/osr_screen_tcode/camera_motion.py`、`motion_layers.py`：外围采样、快速位移验证、多前景运动群。
- `src/osr_screen_tcode/motion_reference.py`：候选拒绝原因和补匹配点数。
- `src/osr_screen_tcode/pose_output.py`：Pose 基础输出倍率。
- `src/osr_screen_tcode/command_cadence.py`、`tcode.py`、`app.py`：实时到达时间参考与中英文设置说明。
- `tests/test_fast_motion.py`、`motion_scenes.py`：快速文字窗口、纯画面移动、纹理切镜头及多前景运动群复现。
- `tests/test_command_cadence.py`、`test_device_ui.py`、`test_output_curve.py`：目标坐标保持、末端减速顺序、回中、保存／默认和 Pose 倍率。
- `tests/ui_smoke.py`、README、Start.md 和版本日志：可见诊断及启动说明。
- `Start-Source.cmd`：启动提示从源码读取版本号。

## 复测与限制

关闭旧程序，双击根目录 Start.cmd，确认标题 test.12；先用 Log only 读屏拖动窗口。采集框应保留窗口外有纹理的背景。看蓝点是否留在背景、黄框是否跟着窗口，再逐渐提高拖动速度；全/半行程会使用同一 v2 修正。新诊断行可以区分缺少可用角点、无法分离运动和背景外推不稳定。

没有用户原始录屏或实机验证。完全无纹理／不可见的背景、严重模糊、遮挡、重复图案或多运动归属不明确时仍可能保持或误判；额外匹配也会增加分析开销。尺度不是物理深度。现有 SR6/OSR6 接口保留，机械臂映射、逆运动学、碰撞和反馈尚未验证。

## English

Test.12 addresses fast window dragging in screen capture. Independent perimeter samples preserve small background corners; fine-scale flow and bounded, unique patch matching recover large displacements and seed nearby ambiguous text tracks. Every seed is rechecked against the current frame. Strongly supported translation above 6% no longer resets solely for speed; the 20% translation cap, scale/cut gates and camera-only rejection remain. Foreground consistency may come from multiple coherent motion groups. V2 and Full/Half Travel share the implementation; v1 analysis is unchanged. Candidate rejection and recovered-track diagnostics are bilingual.

Direct Pose L0 base gain is ×10; pose-derived R1/R2 are ×1.5, including optional hybrid/cycle assistance. Pose L1/L2 coupling remains 0.5/3.5/0.5 with its peak at 2/3 travel. Live TCode arrival time follows recent measured update cadence with the saved minimum (24 ms by default), before endpoint slowdown. This is not a send-rate scheduler and does not alter target coordinates. Offline scripts retain source-based timing.

All 169 main tests and 28 Lab tests passed; 54 relevant tests were rerun after diagnostic layout/save-reset assertions. Simulator command checks, Chinese/English main startup, Lab startup and visible bilingual diagnostics passed. The 640×480 synthetic window yielded 92 valid observations out of 97 frames, with a late L0 span of 53.6%; analyzer latency was 50.22 ms median / 70.94 ms p95, excluding capture/UI/RTM/device I/O. Additional matching costs processing time. These are synthetic measurements, not real-footage accuracy or application FPS. Physical-jitter improvement, original user footage and robot-arm hardware remain unverified.
