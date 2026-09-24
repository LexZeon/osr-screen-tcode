# 2.0.0-test.13 / Local source test

双击根目录 [Start.cmd](../Start.cmd)。[Start.md](../Start.md) 是可点击启动入口的说明文件。仅更新当前测试源码，独立 Pose Preview Lab 仍为 0.2.1-test。

## 快速丢点回退混合 v1

新增 **快速丢点时用混合 v1**，直接 Pose 默认开启，保存／恢复默认同步。近期 0.75 秒内有有效 Pose，随后观测丢失，同时原 v1 区域光流测得明显快速运动时，只让 v1 接续 L0；初始快速阈值为图像宽／高归一化运动约 12% 每秒。已经接管时，可在 v1 参考与快速运动仍有效期间持续使用；反转处允许约 0.35 秒的短暂减速。只有缺失而无快速运动证据、从未检测到 Pose、切镜头或长断帧，不启动回退。无法直接证明丢点原因一定是速度，因此这是有运动证据的回退启发式。

复用原 `RealtimeAnalyzer` 的混合 v1，数值核心没有修改。正常 Pose 帧只保留相邻画面，丢点时才运行额外 v1 光流，不额外采集或加载模型。进入／退出用约 0.2 秒过渡；v1 L0 不乘 Pose ×10，也不作为 Pose pattern 样本。其他轴保留最近 Pose 观测和现有输出规则；L1/L2 的设备联动仍可能随 L0 变化。v1 也失效时，交回自动补 L0／原保持策略。回退画面显示 v1 实际参考和独立 L0 来源，Pose 置信度不被伪造为有效。回退切换使用采集／视频时间。

## Pose 自动补 L0

新增 **L0 静止／小幅时自动生成**，仅直接 RTM Pose 2D 显示，默认开启，单轴／六轴共用：

- 原始 L0 约 0.65 秒没有有效变化后，优先使用有变化的 R1，再使用 R2。每个旋转轴自己的中点对应 L0 的 1/3，两端对应 L0 的 2/3。
- 当 L0 仍在运动但幅度小、R1 明显更大时也可触发，R1 不足时再检查 R2。当前按约 0.85 秒内的稳健跨度比较：L0 基础输出跨度不超过 10%，旋转跨度至少 16% 且至少为其两倍；退出阈值稍放宽以避免频繁切换，用户行程倍率不参与比较。
- R1、R2 都无有效变化，但其他识别轴仍在运动时，才生成 **1/4～1/2、峰到峰固定 1 秒**的余弦波。这里的 1 秒指源时间中的周期，不是位置按恒定速度上升／下降。
- 余弦波从切换前输出位置续接：在 1/4～1/2 内选择对应相位，并沿最近运动方向继续；范围外先从原位置用约 0.35 秒平滑进入最近边界，再开始固定周期，不瞬移到波峰／波谷。
- 旋转映射采用固定 Pose 旋转基础倍率后的数值，不带入用户行程倍率或反向。源切换用约 0.2 秒过渡；实际 L0 恢复足够幅度后交回识别。
- **所有识别轴都无有效运动时，不触发兜底余弦波**；已有波形保持当前位置。判断采用真实观测，缺失立即失效，静止判定保留约 0.65 秒的短窗口以跨过正常反转停顿；不会用生成的 L0 维持自身活动。关闭此开关可停用自动补 L0；停止分析后不会有独立计时器继续生成。
- 自动目标放在 L0 的 ×10 基础倍率之后，不重复乘 ×10，也不重复经过输出曲线拟合；用户行程倍率、反向、输出限制及末端减速继续生效。1/4～1/2 和 1 秒是这些后续处理之前的曲线参数。
- 分析观测、置信度与图表仍保留真实识别结果；分析预览单独标明 L0 来源。单轴模式也能在同次 Pose 推理中分析 R1/R2，但只输出 L0。

## 小幅往复渐放大

新增 **小幅往复渐放大**，仅直接 Pose 显示，**默认关闭**。仅 **L0、R0、R1 分别判断**，L1/L2/R2 不参与；单轴输出只采用 L0：

- pattern 指有实际幅度、持续重复且节奏比较稳定的小幅往复。确认约三个完整周期后，围绕该动作自身中点渐放大，约四秒由 1 倍升至最多 **2 倍**。
- 当前“小幅”检测范围为固定基础倍率后、用户倍率前的峰峰跨度约 **1.6%～20%**；半周期 0.16～2 秒。使用短中值过滤和有显著幅度的反转，比较最近周期的跨度与时长，拒绝微小噪声、快速抖动、单向移动和大幅动作。
- 实际幅度超过已确认跨度约 1.5 倍、节奏明显变化、停止往复或丢失有效观测后退出，增益最多约 0.25 秒回到 1 倍。停止往复需先等到预计反转未出现，因而不会在每次波峰／波谷停顿时立刻退出。
- 自动补出的 L0 与端点复位过渡不参与 pattern 检测或放大。开关不重置 Pose 的分析参考，五档预设不改变检测过程。
- 实时与离线导出共用放大规则；离线使用视频时间，不受分析速度影响。分析预览显示正在生效的各轴增益；图表继续显示观测数据。

## L0 端点复位

Pose 的 ×10 基础输出可能把多个不同的识别位置截在同一个端点。仅靠原始 L0 是否仍有变化，无法判断这种输出停滞。

本版为直接 Pose 增加独立的 L0 输出参考复位：基础输出在同一端点区域持续至少约 0.3 秒，且有效的**左右胯点连线中点明显向上移动**，才允许触发。当前向上阈值为画高 2%，采用三样本中值，要求双胯点置信度有效且未被异常过滤；只停留、向下、微抖、单点异常或缺失后重新检测，不触发这项识别复位。

触发后用约 0.35 秒平滑回中，并以触发时的 L0 识别位置作为新的输出参考，避免马上又回到原来被截住的端点。其他轴的观测参考不变，后续正常运动仍可走到全范围。切镜头／重设参考会清除此临时状态，界面显示端点复位次数。这与默认自动补 L0、既有输出保护及手动回中是不同规则；本次没有删除原有保护。

## 基础倍率与设备联动

- Pose 提供的 **R0 基础幅度由 1 倍改为 3 倍**，围绕中位放大；直接 Pose 以及启用 Pose 的混合／全半模式旋转辅助都采用此基础倍率。非 Pose 的画面旋转分析不受影响。
- 直接 Pose L0 保持 ×10，Pose R1/R2 保持 ×1.5。
- Pose 设备 L0→L1/L2 联动改成四点线性曲线：

| 最终受限 L0 的行程位置 | L1/L2 联动倍率 | R1/R2 联动倍率 |
| --- | --- | --- |
| 底部 0 | 0.5 | 1.0 |
| 1/3，偏低 | 1.0 | 1.0 |
| 2/3，偏高 | 3.5 | 1.0 |
| 顶部 1 | 0.5 | 0.5 |

L1/L2 点间线性变化，中位为 2.25 倍。**R1/R2 从 L0 底部到 2/3 处保持 1 倍，此后线性收拢，顶部为 0.5 倍**；这是 Pose ×1.5 旋转基础倍率之后的设备联动，不改变基础倍率或用于自动补 L0 的识别信号。R0 不参与该收拢。联动只作用于设备目标层，采用本条指令经过倍率、反向、限速及限位后的实际 L0 指令位置；L1/L2/R1/R2 识别位置不变时也随之收拢／展开。不将设备联动值写回识别数据。v2 的联动仍是 1／2.5／1，中位峰值。模拟器仍接收输出端接受的同一最终 TCode 指令。

## 文件位置

- `src/osr_screen_tcode/pose_l0_fallback.py`：自动来源选择、余弦波、平滑交接、胯线触发的 L0 参考复位。
- `src/osr_screen_tcode/pose_fast_fallback.py`：快速运动证据、原 v1 按需接管及来源交接。
- `src/osr_screen_tcode/pose_pattern.py`：逐轴小幅往复确认、增益渐进及退出。
- `visual_pipeline.py`：同帧 Pose 观测与输出状态分开；`pose_output.py`、`tcode.py`：基础倍率与四点设备联动。
- `app.py`、`analysis_preferences.py`、`integrated_preview.py`、`output_curve.py`：主界面／启动确认／分析预览的双语开关、保存及恢复默认、实时／导出接线、自动曲线保真。
- `tests/test_pose_l0_fallback.py`、`test_pose_pattern.py` 及已有输出／设置／导出／联动测试：行为回归；`tests/ui_smoke.py`：可见双语检查。

## 验证记录

- 主程序完整回归 **202 项通过**（265.577 秒）。此后按最终要求补充“所有识别轴无运动时不生成兜底波”、旋转映射 1/3～2/3 与预览紧凑排版，相关 **72 项复验通过**（35.145 秒，包含 2 项新增的无活动／冻结续接回归）。此前完整 193／196 项也通过，不以历史次数替代最后复验。
- 最后增加 R1/R2 的 1／1／0.5 设备联动后，相关 **107 项再次通过**（25.531 秒，含实际受限／反向 L0、零行程和固定旋转收拢的新回归）。
- 独立 Lab **28 项通过**，版本仍为 0.2.1-test；模拟器最终指令检查通过。
- 最终源码的主程序中英文 Start.cmd 启动检查通过，标题／提示为 2.0.0-test.13；独立 Lab Start.cmd 启动检查通过。
- 中英文可见界面检查通过，三个 Pose 开关、自动 L0 来源、逐轴 pattern 增益与 v1 实际回退参考可见；启动确认窗口可滚动。截图只保存在系统临时目录。
- 回归覆盖：三档来源优先级、小 L0／大旋转接管、1/3～2/3 映射、固定 1 秒周期、范围内相位与范围外平滑续接、全轴静止／缺失禁止兜底波、停止后原位续接；R0/R1/L0 独立 pattern 与 L1/L2/R2 排除、幅度增大退出；有效胯线向上才复位；按需原 v1 回退与 Pose 恢复；五档不改分析、保存／恢复默认、脚本导出及最终指令路由。
- 没有连接真实设备、安装依赖、打包、提交或推送。工作区原有删除和未提交改动保留；差异检查仅有预先存在的 CONTRIBUTING.md、OPEN_SOURCE_NOTICE.md 末尾空行提示。

## 复测与限制

关闭旧程序、双击 Start.cmd，确认 test.13。先选 Log only，直接 Pose 模式：静止 L0，分别让 R1、R2 有变化，再让 R0 或 L1/L2 保持运动以验证余弦波，最后完全静止，确认波形保持当前位置。开／关“小幅往复渐放大”，用数个小幅重复动作后接大幅动作，检查对应轴增益上升后退出。L0 卡在端点时，上移胯线，再确认复位计数和回中；只等待或向下不应增加识别复位计数。

当前验证使用合成骨架／画面与模拟输出，没有本次真实素材或实机复测。v1 接管时会增加光流开销，运镜也可能被 v1 当成动作；回退不能保证补回所有快速运动丢点。小幅阈值、周期确认和胯线阈值需要真实片段继续检验；遮挡、运镜或异常关键点仍可能造成误判。更大的 R0 幅度可能更早触及限制，也可能放大输入噪声。后续用户倍率、限位与减速可能改变实际幅度和时序，不能把理论波形直接当成机械位移。尺度不是真实深度，输出值不是反馈，机械臂映射／逆运动学／碰撞与反馈尚未验证。

## English

A default-on fast-loss option uses the original Hybrid v1 L0 when recent valid Pose disappears and ROI flow shows fast image motion. Startup/static loss, cuts and long gaps do not alone activate it. V1 is evaluated on demand from adjacent frames, with a 0.2 s handoff, no Pose ×10 gain and no feedback into pattern detection. Pose confidence remains truthful; v1 references/source labels are shown. This is a heuristic, not proof of why Pose failed; camera motion and tracking failures remain limitations.

Test.13 adds default-on Pose L0 generation after about 0.65 s without meaningful L0 motion, or small L0 with clearly larger rotation: moving R1 first, then R2, mapping each axis midpoint to one-third L0 and either end to two-thirds. Only if another observed axis is moving does it generate a quarter-to-half cosine with a fixed one-second peak-to-peak period. Entry resumes from the current position and phase; outside the quarter-to-half range, it first eases to the nearest boundary over about 0.35 s without a position jump. All-axis stillness/missing observations prevent a new fallback wave and freeze an existing one; generated output cannot sustain its own activity. Generated targets bypass the ×10 L0 base gain and repeated curve filtering, while subsequent travel controls and constraints still apply.

Default-off small-stroke expansion independently confirms about three steady small cycles per eligible Pose axis (L0/R0/R1 only; L1/L2/R2 excluded), then ramps toward at most 2× over four seconds around that motion's midpoint. It releases when actual motion grows, rhythm breaks or observations disappear. Generated L0 never feeds this detector. Pose output stays separate from observations, presets and confidence.

Stuck L0 output reference recovery requires a valid hip-line midpoint moving clearly upward (2% frame height, three-sample median), after at least 0.3 s at the same base-output end. Waiting, downward movement or missing hips alone do not trigger this recovery. A 0.35 s return to center rebases only L0 output. Existing output protection and manual centering remain separate.

Pose-derived R0 base gain is now ×3, including Pose rotation assistance; R1/R2 remain ×1.5 and direct Pose L0 remains ×10. Pose hardware L1/L2 coupling linearly connects (L0, gain) = (0, 0.5), (1/3, 1), (2/3, 3.5), (1, 0.5), using the current limited L0 command. Pose hardware R1/R2 separately retain 1× from bottom through 2/3 L0, then contract linearly to 0.5× at the top, after their ×1.5 base gain; R0 and automatic-L0 source observations are unaffected. V2 coupling is unchanged. Settings, reset defaults, live/export routing and preview labels are bilingual. Only test source is updated; no package, commit, push or dependency installation. Real footage and hardware remain unverified.

Validation: 202 full-suite tests passed, followed by 72 focused tests after final no-activity gating, 1/3–2/3 rotation mapping and compact preview layout (including two new cases). All 28 Lab tests, simulator stream checks, bilingual main startup and visible UI checks passed; Lab startup also passed. After adding final R1/R2 hardware coupling, 107 relevant tests passed again, including limited/inverted L0 and zero-travel checks. No real hardware or original-footage validation.
