# 2.0.0-test.25：弱主体跟踪与短暂缺测接续

本版基于 test.24。用户明确确认：估算依然最多 2 秒，不要求无限生成动作。主程序 `2.0.0-test.25`、项目元数据 `2.0.0.dev25`；独立预览保持 `0.2.2-test`。双击根目录 [Start.cmd](../Start.cmd)，[Start.md](../Start.md) 为启动说明。

## 行为与范围

- 可靠测量继续沿用原主体／背景验证。弱跟踪独立保留同一主体的像素身份、框和原点；只有同帧背景也成立时，才给融合输出提供降低置信度的相对位移接续。背景未知时仅更新屏幕位置，不宣称运镜已扣除。
- 缺少像素支持时，位置估计用最多 0.35 秒的衰减速度；脚本优先沿用已确认节奏。未确认周期但近期运动稳定时，只做最多 **0.3 秒／15% 归一行程** 的单向减速接续，不制造新的往复。后续用户行程倍率仍会影响实际输出幅度。
- 所有接续受缺测期限约束。弱证据、预测与单帧识别闪回不能无限刷新 2 秒；稳定重捕获后才能建立新的接续窗口。明确暂停、切镜头、改变输入／处理尺寸或重设参考清除旧规律。
- 分析预览的淡色虚框、虚线三轴及 A? 表示弱跟踪／估算，状态区分脚本来源与持续时间。原 Observation、真实采样、置信度与观测历史不写入估算；目标 T?／到达百分比仍须独立实测成立。
- 单帧恢复不覆盖估计使用的已确认轴方向；估计到期后隐藏旧主体几何，不会借原跟踪器的短暂保持状态重新画成实测黄框。V? 暂存参考仍明确解释为假定客体，估计期间不更新到达比例、不连旧主体原点。
- 默认融合参考与全／半／1/4 行程共用接续；周期模式不因尚未确认的单向速度自行启动行程。其他手选 L0 参考保持原输出语义，仍可显示主体估计。直接 Pose 与混合 v1 不采用新的缺测输出路径。
- 稳定的粗略画面结构仍能匹配时，不再只因大量角点丢失就判为切镜头；它只允许有限接续，不将模糊帧提升为有效运动观测。明显黑场／无关画面仍重置。

没有新增设置项；中英文说明与显示同步，设置保存和恢复默认行为保留。最长边仍默认 640，最终行程倍率、限位、减速、TCode、录制与模拟器继续使用现有共同输出链路。

## 文件位置

- `subject_continuity.py`：真实像素弱跟踪、显示位置估计及期限。
- `motion_rhythm.py`／`fused_l0.py`：慢节奏确认、短速度桥接、弱位移接续、不可闪回续期的上限及平滑重入。
- `point_l0.py`／`visual_pipeline.py`：将估算单独传给融合输出，保留独立显示三轴；观测数据不变。
- `camera_motion.py`：大量丢点时额外核对粗略场景结构，区分模糊与明显切镜头。
- `motion_reference.py`／`integrated_preview.py`：虚线主体、来源标签和中英文状态。
- `tests/test_subject_continuity.py`、接续相关测试：缺测、恢复、暂停、切镜、期限与输出隔离。

以上源码文件均在 `src/osr_screen_tcode/` 内（tests 除外）。原有未提交修改和有意删除保留。

## 验证

最终源代码验证（串行执行）：

- 隔离入口 `tests/run_tests.py -v`：主程序完整 **392 项通过，452.396 秒**。个人设置指纹与本轮开始前一致，测试设置和预览均隔离。
- 独立预览完整 **38 项通过，0.388 秒**，本轮没有修改 Lab 源码。
- 根目录 `Start.cmd --smoke --language zh`／`en`，以及 Lab 的 `Start.cmd --smoke` 均正常退出；最终中文弱跟踪、英文短速度接续的原生窗口也已实际检查。
- 生产代码 Log only 实际读屏：**313 次统计更新**，从窗口事件循环开始至结束约 9.51 秒，正常停止、工作线程退出，无采集／界面回调错误。末次采集／分析约 64.02／64.62 FPS、输入年龄约 8.88 ms；仅是该次桌面运行的瞬时统计，不代表复杂视频或设备的延迟保证。
- `tests/test_simulator_stream.cjs` 通过：保留最终指令，预览动画不能覆盖它。未连接硬件。
- 最终个人设置指纹保持不变；正式仓库只读核对仍无修改。差异空白检查只剩原有 `CONTRIBUTING.md`、`OPEN_SOURCE_NOTICE.md` 的空白尾行，不属于本次改动。

开发过程与失败尝试：

- 第一轮完整 **389 项／455.788 秒**，一项失败：径向运动用例末帧进入弱跟踪时，文字遗漏 V? 解释。该用例的原始测量一致性、L0 相关性、方向及目标类别已通过；修复文字，不放宽原数值断言。
- 交叉审查新增两个显示回归：单帧闪回后到期重新出现旧黄框、单帧闪回覆盖原三轴缓存。两项先实际复现失败，再仅修复显示快照与缓存更新条件；不更改原始观测或主轴学习。随后融合失败用例、七项接续管线与九项显示检查共 **17 项／11.105 秒**通过。
- 原生窗口检查发现初稿虚线过淡；提高对比度、加黑描边并保留断口。两次断口／对比度断言失败后完成修正。英文短速度来源最初泛称两秒，改为实际最多 0.3 秒／倍率前 15% 行程，停止状态及计时同步。最终中文弱跟踪与英文短速度窗口均已实际查看。
- 最初部分测试导入时独立主体模块仍由并行开发写入，出现加载错误；待模块完成后复验，不将这类未完成的尝试计为通过。所有 GUI 与完整套件检查串行；界面检查使用合成画面和整个生命周期内的配置保存隔离。

## 边界

“持续输出”指减少短暂识别中断，不代表缺少任何画面证据时永久生成动作。超过 2 秒仍无法识别会停在当前位置；未建立主体／运动历史时不凭空启动。速度桥接更短，弱跟踪也可能跟丢或误跟，故通过独立字段和虚线标注，并限制寿命。

二维画面无法保证真实主体／客体语义、真实深度或接触。强遮挡、快速变形、模糊和新镜头仍可能停止；粗略场景相似不能绝对排除外观相近的切镜。没有验证真实机械臂、关节映射、逆运动学、碰撞检测或反馈。

慢周期的限制单独核对：`MotionRhythm` 的独立测试能拟合 6 秒周期，但主分析的中心参考仍只有约 3 秒历史，6 秒往复的相位可能反复失效。完整分析器注入实际正弦观测的 20 秒探针中，2.5 秒／4 秒周期已有预测模型，6 秒没有。不能把单类测试称为全链路 6 秒支持；本版未为此改动主轴识别算法。

以上开发与验证阶段仅修改测试源码，没有安装依赖、打包、提交、推送或自动连接设备；正式目录、旧发布包及 PoseBridge Lab 未改。

## 源码预发布整理

随后用户明确要求移除兼容性宣传并发布 GitHub。显示名称统一为 **SR6/OSR6 Realtime Screen TCode**，同步窗口、模拟器标题、元数据、文档以及未来打包名称；构建规格文件改名为 `SR6-OSR6-Realtime-Screen-TCode.spec`。发布使用 `2.0.0-beta` 分支与 `v2.0.0-test.25` 预发布标签，保留旧分支、旧版本和 main 的历史。

本次提供源码和 Start.cmd；GitHub 自动源码压缩包需要 Python，不提供新 exe 或 Windows 运行包。模型、可下载 GPU 运行库、日志、缓存、个人设置均不在发布文件中。发布整理不更改分析、默认设置或最终设备输出算法。

发布前针对最终名称重新验证：隔离主程序 **392 项通过（434.184 秒）**，独立预览 **38 项通过（0.346 秒）**；中英文主程序启动、Lab 启动和模拟器最终指令检查均通过，个人设置指纹不变。206 个 Git 源码候选文件未发现禁带运行组件、个人配置或私有路径；暂存差异空白检查通过。补全实际内嵌模拟器、Three.js r127 和 ONNX Runtime 诊断图的 MIT 许可文本，详见 `THIRD_PARTY_NOTICES.md`。只编译检查改名的构建规格／脚本语法，未运行打包或验证新的运行包。

## English

Test.25 adds a separate bounded subject-continuity layer. Real pixels can support a weak subject marker; independently supported camera correspondences are required before its displacement can assist fused L0. Missing pixels permit only explicitly labeled estimates. Established rhythm can continue for at most two seconds; a stable recent velocity can provide a shorter decelerating bridge without inventing a reversal. Isolated detection flashes cannot renew a loss episode indefinitely.

Measured observations, confidence, target/reach evidence and history remain separate. Dashed A? boxes and axes identify weak/estimated positions. Default fused v2 and confirmed cycle travel share output continuity; other manual references retain their original output meaning. Existing settings, 640 processing size and final output transforms are preserved. Validation and remaining limitations are recorded above.
