# 2.0.0-test.16：小幅三维往复与帧率一致性

双击根目录 [Start.cmd](../Start.cmd)，确认标题 `2.0.0-test.16`。[Start.md](../Start.md) 提供可点击入口及保留设置说明。三维主轴与分析画面说明见 [test.15](Test_2.0.0_test15.md)。

## 本轮修正

- 修正小幅斜向漏判：先确认各分量是否有持续往返，再沿合成的三维候选方向检查实际幅度。较小的左右、上下或尺度分量不再因没有单独超过固定幅度门槛而被截掉；保留分量正负关系和整组轴的平滑转动。
- 修正小幅往复的启动位置依赖：首帧恰好位于中间时，识别从随后实际观测到的端点建立行程，不要求必须先从首帧位置走出完整门槛。
- 全／半行程的运动活跃判断改为沿当前主轴的每秒运动量，按画面时间戳计算。原来按每帧最大单一分量判断，会在高帧率或斜向小幅运动时误停。仅有横向附属位移时，不会单凭旧主轴往复记录继续生成 L0 周期。
- 保留每段至少约 0.16 秒、合成方向往复幅度、双向证据和方向确认要求；增加行进一致性检查。零碎高频抖动不能靠累计时间伪装成持续往返，单向加速平移／缩放仍不提供往复方向证据。
- v2、可选 RTM 2D 旋转辅助及全／半行程继续共用同一方向分析；分析预览显示的仍是实际采用的轴组。全／半行程的 1/4、半、全行程档位、平滑续接和节奏适应保留。

没有新增设置；中英文说明、版本和启动入口同步，原有保存／恢复默认逻辑继续使用。原混合 v1 数值核心与直接 Pose 输出保持；Pose 可选 v2 混合来源随共享算法更新。五档、最终行程倍率、联动、限制及到达时间减速仍在后续输出阶段应用，模拟器仍接收最终指令。

## 复现与文件

修正前，输入总峰峰幅度均为 2 个画面百分比单位、相同节奏的合成往复：30/60 FPS 的纯上下可以进入 1/4 行程，同幅度均分到三个方向后保持停止；纯上下到 120 FPS 也误停。另有总峰峰幅度 1.16 的往复从中间开始时无法建立证据。新增测试覆盖这些边界以及带较弱反向分量的倾斜方向。

- `src/osr_screen_tcode/dominant_motion.py`：端点启动、相对分量往复确认、三维幅度门槛和路径一致性过滤。
- `src/osr_screen_tcode/stroke_cycle.py`：按时间归一化的主轴运动活跃判断。
- `tests/test_camera_motion.py`：按实际单位方向夹角检查运镜场景；`tests/ui_smoke.py`：检查图片使用当前版本命名，避免覆盖旧版图片。
- `tests/test_motion_basis.py`：5 项新增回归，包含多个方向、起始相位、30/45/60/120 FPS、附属方向单向移动、微小噪声与单向加速。
- `src/osr_screen_tcode/__init__.py`、`pyproject.toml`、README、Start.md、AI 指南、当前手册入口及两份日志：测试版本与说明同步。

## 验证

- 主程序相关 **87 项完成通过**，包括 5 项新增回归。测试组首轮 86 项通过；一项旧断言使用按绝对值和归一化的分量权重判断方向，本轮改为检查与真实上下方向夹角小于 5°后，单独复验通过。该画面实测约 3.4°，不是运镜取代主轴。较弱但相关的尺度估计残差现在会保留，因此旧诊断权重不再等同于方向精度。
- 覆盖方向拟合、旋转共用、三维全／半行程、真实画面跟踪合成场景、少背景／运镜／暂停、实时 Log only 指令、脚本导出、五档与最终限制、设置保存与默认。首次探索还发现短晃后的细碎噪声被相对门槛误收，已加入路径一致性过滤，原有严格噪声回归通过。
- 本轮为相关模块复验，没有重跑主程序全部测试；test.15 完整 218 项的历史结果单独保留，不作为本轮完整测试结果。
- 独立预览 **28 项通过**（0.388 秒），Lab 未修改且版本仍为 `0.2.1-test`。模拟器检查通过：最终指令保留，动画不能覆盖它们。
- 主程序中文、英文 `Start.cmd --smoke` 均正常退出，标题 `2.0.0-test.16`；Lab 启动检查通过。中英文可见预览使用合成斜向场景验证，实际轴线、方向小图、状态说明均完整可见。未连接硬件或保存个人设置，图片只放临时目录。
- 方向算法单独处理 1200 个样本耗时 0.817 秒，平均约 0.681 ms／样本；不包含采集、模型和运动跟踪，不代表整机实际帧率。
- 语法及当前文档链接检查通过；差异格式检查仍只有原有 `CONTRIBUTING.md`、`OPEN_SOURCE_NOTICE.md` 的末尾空行提示，保留原改动。

## 复测与残余风险

使用 Log only 打开分析预览，比较相同总幅度的上下／斜向往复，以及 30、45、60 FPS 设置；观察主轴方向、1/4 行程是否连续，随后停止主体动作。也测试短促晃动和单向拖窗，确认未持续生成往复。实际分析帧率受采集与模型开销影响，设置值不代表实际帧率。

这次修正发生在已经获得有效运动观测之后，不能代替背景跟踪；小背景、遮挡或模糊仍可能丢失参考。三维坐标中的尺度是画面代理，不是真实深度。小幅信号更容易被识别后，可能触发现有行程放大／档位，需要用实际素材复测。新增方向确认计算也有处理开销。没有连接真实设备，未验证机械臂映射、逆运动学、碰撞检测或反馈。

仅更新当前测试源码，未打包、提交、推送或安装依赖；正式目录、旧发布包、有意删除与已有未提交改动保留。

## English

Test.16 fixes small oblique strokes losing weak signed components, and startup depending on the first sample's phase. Components establish sustained reversals relative to their own range; the combined candidate still needs absolute reciprocal evidence. Path consistency rejects high-frequency jitter that could otherwise accumulate into a seemingly long leg. One-way acceleration cannot establish a reciprocal direction.

Cycle activity now uses source-time speed along the actual main axis, rather than a per-frame cardinal displacement. Equal-amplitude oblique strokes and higher frame rates no longer fail that gate; transverse drift alone cannot keep an old main-axis cycle running. V2, its optional pose rotation assistance and cycle mode continue to share analysis. Existing defaults, saved settings, final output mapping and simulator command routing remain in place.

Validation: 87 relevant main tests passed across the module run and the corrected angular-accuracy assertion rerun; 28 Lab tests, bilingual startup/visible preview, and simulator command checks passed. This was targeted validation, not a full main-suite rerun. Footage, background ambiguity and physical hardware still need validation; image scale is not real depth or robot kinematics. Double-click [Start.cmd](../Start.cmd); no package, dependency installation, commit or push was made.
