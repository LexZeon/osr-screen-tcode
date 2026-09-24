# 2.0.0-test.14：连续 v1 接管与更快的小幅放大

启动测试版请双击根目录 [Start.cmd](../Start.cmd)，确认标题 `2.0.0-test.14`。[Start.md](../Start.md) 提供可点击入口及完整操作说明。本轮仅更新测试源码；没有打包、提交、推送或安装依赖。此前的功能与参数见 [test.13](Test_2.0.0_test13.md)。

## 本轮变化

- Pose 的“快速丢点时用混合 v1”仍默认开启。开启时，原有 v1 持续处理与 Pose 相同的采样帧，保留运动历史，不再等丢点后才启动。两种分析在同一工作线程处理同批画面，不另开采集或模型；关闭开关后不运行该 v1。
- 保留“近期有效 Pose 丢失且 v1 有快速运动证据”的接管门槛。仅接管 L0，其他轴保留原有丢失处理。切镜头、尺寸改变和跟踪重置会清除旧历史；缺失本身不构成运动证据。
- 接管第一帧从当前输出续接，之后只跟随 v1 的位置变化。例如当前 L0 为 40%，v1 内部已经在 80%，接管保持 40%；随后 v1 从 80% 到 82%，L0 才相应增加 2 个百分点（再应用输出倍率与限制）。不会为了对齐旧坐标先走到 80%。到达限位后持续更新增量参考，反向无需先抵消隐藏偏移。
- 实时起点采用已经生成的 L0 指令位置，反算行程倍率、反向、限位映射、端点保护与启动缓入，避免重复乘算。即使拟合目标还在前方、输出因速度限制落后，也从当前指令接手。它是指令位置，不是硬件传感器反馈。原有输出限制仍可影响后续运动。
- 视频导出从输出拟合后的脚本位置接续，保持源视频采样时间。Pose 恢复后保留约 0.2 秒的平滑交回。回退 L0 不重复乘 Pose 的 10 倍，不参与 pattern 检测。
- “小幅往复渐放大”确认后的增长速度提高为原来的 **4 倍**：约 **1 秒从 1 倍升到最多 2 倍**。仍默认关闭，仅 L0、R0、R1 分别确认约三个稳定的小幅往复；L1/L2/R2 不参与。实际幅度变大、节奏中断或观测缺失时仍退出，退出耗时最多约 0.25 秒。确认所需周期数与最大倍率没有改变。
- 主界面、启动确认和分析预览复用中英文控件说明；保存、恢复默认、舞蹈与混合配置分别记忆的行为保持。

## 文件

- `src/osr_screen_tcode/pose_fast_fallback.py`：持续运行 v1、相对接续与平滑交回。
- `src/osr_screen_tcode/tcode.py`：从当前 L0 指令反算接管起点。
- `src/osr_screen_tcode/app.py`：实时与视频导出衔接、中英文说明。
- `src/osr_screen_tcode/pose_pattern.py`：更快的放大增长。
- `tests/test_pose_fast_fallback.py`、`tests/test_pose_pattern.py`、`tests/test_device_ui.py`、`tests/test_output_presets.py`：持续分析、接续、限位反转、输出乘算和导出验证。

## 验证

- 主程序完整测试：**211 项通过，158.067 秒**。覆盖原混合 v1 数值基线、持续运行／关闭、相对接续、恢复交回、时间异常、限位反转、实际指令落后目标时的接管、反向与行程乘算、脚本导出及更快放大。
- 独立预览：**28 项通过**。Lab 仍为 `0.2.1-test`。
- 模拟器指令检查通过：保留最终输出指令，动画不能覆盖。
- 主程序 `Start.cmd --smoke --language zh`、英文启动及 Lab `Start.cmd --smoke` 均正常退出；主程序标题为 `2.0.0-test.14`。
- 中英文可见界面检查通过：中文显示 v1 接续来源与参考；英文显示独立放大增益，开关排版正常。检查使用合成画面与模拟 Pose，没有连接真实设备。
- 差异格式检查仅保留既有的 `CONTRIBUTING.md` 与 `OPEN_SOURCE_NOTICE.md` 末尾空行提示，没有清理原有改动。

## 建议复测

先使用 Log only 观察输出监视和模拟器。选择 Pose，开启 v1 接管，先建立有效骨架，然后观察快速动作丢点期间：L0 应从此前位置继续，画面仍标出真实 v1 来源，恢复 Pose 时平滑交回。分别检查反向、较小行程倍率和速度限制下的表现。

开启“小幅往复渐放大”，对 L0/R0/R1 中任一轴做持续小幅往复：确认后应在约一秒内达到最高放大，其他未确认轴保持原倍率；把实际动作做大后应退出放大。

持续 v1 会增加每帧处理开销；模型推理与实际片段性能仍需在目标电脑复测。v1 仍可能受运镜影响，未改变其识别核心。真实设备微抖、机械臂关节映射、逆运动学、碰撞检测和反馈未验证，不能宣称机械臂兼容。

## English

Start the source test with [Start.cmd](../Start.cmd) and confirm `2.0.0-test.14`. When Pose fast-loss fallback is enabled, the original v1 analyzer continuously processes the same sampled frames. On handoff, L0 starts at the current applied command, or the fitted script position for video export, and follows subsequent relative v1 changes. It does not relocate to v1's accumulated absolute origin. Travel, inversion, limits, slowdown and final simulator command routing remain in place. Command positions are not physical feedback.

Confirmed small-cycle expansion now grows from 1× to at most 2× in about one second, four times faster. It remains default-off and independent for L0/R0/R1 only, with the existing confirmation and release conditions. All 211 main tests and 28 Lab tests passed, along with simulator, bilingual startup and visible UI checks. Continuous v1 increases processing cost; camera-motion sensitivity and physical hardware behavior require real-footage/device validation. No package, commit, push or dependency installation was performed.
