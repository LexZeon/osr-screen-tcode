# 2.0.0-test.9 / Local source test

本轮只更新测试目录源码，不打包、不提交、不推送。双击根目录 [Start.cmd](../Start.cmd)；[Start.md](../Start.md) 是启动说明。独立 Lab 保持 0.2.1-test。

## v2 观测缺失

test.8 要求画面边缘至少 18 个背景点，主体也被限制在中间区域，稀疏／模糊背景和靠边主体容易持续被判缺失。现在使用至少 6 个分布足够广、运动一致的背景点，必要时从已跟踪主体区域外补充参考；主体可接近画面边缘。仍排除最外侧易裁切像素并保留背景分布、跟踪一致性和切镜头检查，不用整幅运镜冒充往复。

分析画面显示纹理不足、跟踪失败、背景分布不足、等待局部运动等原因，以及检测／跟踪／背景／局部点数。蓝点仍为实际采用的背景，绿点／箭头为扣除运镜后的实际局部采样。纯背景运动显示等待局部运动。

## 全/半行程模式

新增 **全/半行程模式（基于混合分析）**，列表第一，RTM Pose 2D 第二；首次启动与恢复默认仍选 v2，保存的选择保留。该模式继承同一个 v2 管线：v2 的观测、主轴与往复识别修改会同步影响新模式，混合分析 v1 不参与。

- 未确认有效往复或观测丢失：保持当前位置。
- 较小往复：底→中→底；较大往复：底→高→底。
- 每半程使用余弦插值，起止速度自然减小；进入或恢复时从保持位置平滑移到底部，不跳到固定起点。
- 近期反转时间用于估计周期，并缓慢调整节奏。参考周期限制 0.5–6 秒，默认初值 1.5 秒；停止运动后在短暂观察窗口内停止循环。
- 当前判别使用主方向的画面往复跨度：不足 1.5 个图像百分点不启动；达到 8 进入全行程，低于 6 回到半行程，中间保留前一档，避免来回跳档。尺度只是图像代理，不是真实深度。真实视频可能需要进一步校准这些实验阈值。
- 六轴可勾选 RTM 2D 旋转辅助，R0/R1/R2 沿用现有骨架旋转分析；L1/L2 居中。不带 RTM 时只生成 L0，其余轴居中。单／六轴采用相同 L0 节奏。
- 曲线目标仍经过五档、行程倍率、方向与既有限制。RTM 舞蹈 L0 的额外 ×5 不套用于此模式。

## 接近上下限时减速

主界面与启动弹窗的分析方式下面有复选框，默认开启；减速距离默认 10%，滑块 1–50%，保存／加载／恢复默认同步。

**只改时间，不改目标坐标。** 距离按每个轴的完整输出范围计算。向某端接近时，在该端减速区内把速度从区域入口的原速逐渐降低；当前曲线在限位处对应原速的 25%。离开该端正常响应。急停／手动回中直接使用原有指令。

实时 TCode 在倍率、反向、L0 联动和既有安全限制之后，延长指令 I 时间，模拟器转发同一最终指令。相同目标的后续帧保留尚未完成的减速时间。录制／视频导出只延长脚本点时间，不改坐标，六轴使用所需最长时间以保持轴间同步。**导出文件可能变长并与原视频逐渐错开；关闭该项恢复原时序。** 原有速度上限、端点留白和行程倍率是独立设置，仍会按原逻辑作用。

## 文件与验证

- `src/osr_screen_tcode/camera_motion.py`、`motion_reference.py`、`integrated_preview.py`：观测筛选和诊断。
- `stroke_cycle.py`、`visual_pipeline.py`：同源 v2 的全／半行程和节奏适应。
- `endpoint_slowdown.py`、`tcode.py`、`recorder.py`：最终时序减速。
- `app.py`、`config.py`：模式、主界面／弹窗、设置保存和默认值。
- `tests/test_camera_motion.py`、`test_stroke_cycle.py`、`test_endpoint_slowdown.py`、`test_output_presets.py`、`test_device_ui.py`：合成场景、完整导出、最终模拟器指令和设置验证。

主程序 **146 项测试通过**（最终完整复测 51.833 秒），独立 Lab **28 项通过**。模拟器指令脚本测试通过；主程序 `Start.cmd --smoke --language zh/en` 两种语言启动通过，独立 Lab `Start.cmd --smoke` 通过。查看了中文分析预览和英文启动弹窗，确认新模式、默认减速开关／10% 滑块、旋转辅助和画面说明可见。测试使用合成画面与 Log only，没有连接硬件，也未保存个人设置。

本轮改动文件的差异空白检查通过。全工作区检查仍报告此前 `CONTRIBUTING.md`、`OPEN_SOURCE_NOTICE.md` 的末尾空行；本轮未整理这些既有修改。

Validation: 146 main tests, 28 Lab tests, simulator command checks, Chinese/English main startup and standalone Lab startup passed. Chinese Analysis Preview and the English startup dialog were visually checked. Tests used generated frames and Log only without hardware or saved personal settings.

尚未使用用户真实问题片段复测。低纹理、无独立背景、遮挡、切镜头仍可能保持或误选区域。节奏匹配是实验估计，不能保证与视频严格同步。没有实机输出验证，也不代表机械臂兼容；关节映射、逆运动学、碰撞与反馈均未验证。

## English

Test.9 loosens v2's overly strict perimeter feature requirements while retaining independent spatial camera support. Sparse/blurred backgrounds and edge subjects have regression coverage; missing-reference reasons and point counts appear directly in Analysis Preview. Flat or inseparable scenes can still hold.

Full/Half Travel is first in the menu and directly subclasses the actual v2 pipeline. Small/large confirmed reciprocal excursions generate bottom→middle→bottom or bottom→top→bottom cosine cycles. No recent reciprocal evidence means hold. Period adapts gradually from recent reversals; optional RTM 2D supplies rotations while L1/L2 remain centered. Default selected analysis is still v2. The experimental thresholds and cadence limits above need real-clip validation.

Slow near upper/lower limits defaults on with a 10% distance, adjustable from 1–50%, in both main and startup controls. It modifies final timing only: TCode I durations or recorded/exported timestamps. Target positions are identical with this option on/off; existing gains and constraints retain their own behavior. Motion away from the approached endpoint is unchanged. Recorded/exported duration can increase and drift relative to the source video. Simulator messages include the same final target and interval sent to the sink. No hardware compatibility or real-clip success is claimed.
