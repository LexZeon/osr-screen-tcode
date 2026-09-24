# 2.0.0-test.6

默认分析方式为混合分析 v2（推荐-非舞蹈），RTM 2D 旋转辅助默认关闭；恢复默认同步，已有保存的分析选择继续保留。

Default analysis is Hybrid v2 (Recommended Non-Dance), with RTM 2D rotation assistance off. Reset restores these defaults; existing saved mode selections are preserved.

## 变化 / Changes

- 独立预览 0.2.1 的原始／处理后画面、四项骨架处理和观测图表已移植到主程序。“分析预览”与实际分析、输出共用同一采样帧；原指令监视移到“输出监视”页。独立工具保留用于对照。
- 屏幕继续使用只保留最新帧的 MSS 采集。RTM 2D 在分析线程内对当前帧推理一次。RTM / v2 视频播放跟随源时间、跳过积压帧；离线导出使用视频时间戳。实时与离线分析互斥；停止会取消未完成导出。
- 菜单改为 **混合分析（内测）**、**混合分析 v2（推荐-非舞蹈）**。混合分析 1 保留原有 L0 核心。
- v2 使用画面运动 v2 的上下、左右、尺度观测，以近期运动强度选择主要方向。L0 以主方向为主并保留其他方向贡献，权重平滑变化；单轴与六轴使用同一 L0。下表是各方向占主导时的主要分配，过渡期间按权重混合。

| 主方向 | L0 | L1 | L2 |
| --- | --- | --- | --- |
| 上下 | 上下 | 尺度 | 左右 |
| 前后近似（尺度） | 尺度 | 上下 | 左右 |
| 左右 | 左右 | 尺度 | 上下 |

- v2 的 **“启用 RTM 2D 旋转辅助”** 默认关闭。关闭时，R0/R1/R2 从画面特征的透视形变、平面转角估计；开启时，六轴模式改用同一帧的 RTM 2D 骨架旋转分析，原始平移观测与方向分配不变。单轴模式不加载此辅助模型。两种旋转来源都是二维启发式，不是真实三维关节角。
- 不带 RTM 的 v2 六轴额外过滤 L1/L2/R0/R1/R2：忽略小幅摆动，明显运动及反转需持续确认，再平滑跟随；不影响 L0。当前观察范围内，持续位移约需 2.5% 行程、反转约 3.5%，新方向确认约 120 ms，之后以 160 ms 平滑并限制变化率。录制、导出和实时链路共用此结果，五档倍率在其后应用。
- RTM Pose 2D 模式保留上下→L0、尺度→L1、左右→L2 的固定平移分配和原有骨架旋转启发式。它的可选混合来源 1/v2 **仍只混入 L0**。
- RTM / v2 六轴最终 TCode 的 L1/L2 联动倍率按 L0 低／中／高 **1／2.5／1**：`1 + 1.5 × (1 − |2 × L0 − 1|)`。使用本条指令已经过限位、启动渐入和限速的 L0 值。每次从未放大的 L1/L2 重新计算；L0 从中段下降时，即使识别位置不变，L1/L2 输出也会向中心收拢。原有限位、反向、限速和手动回中继续有效。
- 上述 L0 联动仅用于实时 TCode（包括 Log only）和输出监视，不回写骨架、观测或脚本数据。L0 Only、混合分析 1 和声音分析不使用此联动。骨架旋转的原有 R1/R2 基础倍率保留。
- 将旧三档的首次启动基础参数移到默认配置（包括每条指令最大变化 1300、间隔 24 ms）；已有保存值保留，五档按钮不再重写这些参数。
- **五档预设只设置最终输出行程倍率：0.55 / 0.75 / 1 / 1.15 / 1.30。** 同时作用于录制、导出脚本和实时输出，不改分析方法、识别增益、平滑、死区、帧率、四项骨架处理或已有输出保护。倍率显示在原有 L0／六轴总行程控件中；其他轴的独立行程设置继续有效。
- 移除 RTM Pose 3D 选项、模型加载和下载目标。历史 3D 设置迁移到 RTM Pose 2D + Log only，丢弃旧 3D 路径，不把 3D 文件当作 2D 模型。少量内部共用几何辅助函数保留历史名称。
- RTM / v2 最长边默认 640，可选 320/480/640/960/1280，只缩小不放大。四项骨架处理首次默认关闭，已保存选择继续保留；v2 旋转辅助开关及新设置支持保存、读取和恢复默认。界面中英文同步。

The main app integrates the lab's paired-frame preview and stabilization. Hybrid 1 is now labeled Internal Test and retains its L0 core. Hybrid v2 is Recommended for Non-Dance: recent vertical, image-scale and horizontal motion smoothly determine the primary L0 direction. L1/L2 use the remaining directions as shown above. Single-axis mode uses the same L0.

V2 offers optional RTM 2D rotation assistance. With it off, image feature perspective and planar rotation produce approximate R0/R1/R2 signals; with it on, six-axis mode uses pose rotation heuristics without changing the underlying translation measurements or direction assignment. Without RTM, secondary axes additionally suppress small/brief motion and confirm meaningful reversals before smoothing; L0 is unaffected. RTM mode's optional hybrid blend still changes L0 only. Image scale is not physical depth and neither rotation source is a 3D joint solver.

The five presets change final travel only (0.55 / 0.75 / 1 / 1.15 / 1.30), including recording and exported scripts. Analysis settings and state remain unchanged. RTM/v2 six-axis TCode additionally applies the 1 / 2.5 / 1 L0-to-L1/L2 coupling; this hardware-output adjustment never alters observations or script data. Output limits and speed caps remain active. RTM Pose 3D is removed.

## 本地验证 / Local verification

双击根目录 [Start.cmd](../Start.cmd)，先选 Log only。混合分析 1 与任意单轴模式只应输出 L0；v2／RTM 2D 六轴输出六个轴。v2 可直接运行不带 RTM 的版本；开启旋转辅助需要本地 RTM 2D 模型。切换分析方法、单／六轴或辅助来源会停止当前分析，请重新开始。

验证重点：原混合分析 1 数值回归、主方向切换、单／六轴 L0 一致、RTM 辅助只替换旋转、画面旋转近似、五档分析一致而脚本幅度不同、同帧配对、切镜头／断帧、固定观测的 L0 联动、限位／反向／限速、保存／恢复默认、停止与导出互斥。

启动检查：`Start.cmd --smoke --language zh` 或 `--language en`，使用临时 Log-only 设置，不保存个人配置。主程序 103 项测试、独立预览 28 项测试通过。自动检查不能替代真实视频复测。

Start with Log only. Test the two v2 variants and the dominant direction weights shown in the preview. The startup smoke switches use temporary settings and never connect hardware. Switching analysis mode, output axis count or rotation source stops the current analysis so the next run uses one consistent configuration.

## 验证记录与文件 / Verification and files

- 主程序 103 项自动测试、独立预览 28 项测试通过；中英文 Start.cmd 临时配置启动及界面检查通过。
- 使用已有 CPU 模型完成 12 帧配对推理；v2 的 L0 不随 RTM 旋转辅助开关变化。
- 实际解码临时合成 AVI：v2 带／不带 RTM 均导出六轴 funscript，检查值域及源视频时间戳。未连接设备，临时视频／脚本已随测试目录删除；未保存个人设置。
- 主入口与设置：`src/osr_screen_tcode/app.py`、`config.py`；同帧分析／预览：`visual_pipeline.py`、`integrated_preview.py`、`visual_lab/`。
- v2 主方向、旋转近似、辅轴过滤：`dominant_motion.py`、`frame_rotation.py`、`secondary_motion.py`；最终机械输出倍率：`pose_output.py`、`tcode.py`。
- 测试新增／更新位于 `tests/`；启动入口是根目录 `Start.cmd`，说明是 `Start.md`。

103 main tests and 28 standalone lab tests passed. Both language startup/UI checks passed. Existing CPU-model inference and real decoding of a temporary synthetic AVI were checked; both v2 variants exported six scripts. This validates the software paths, not real-clip quality or physical hardware.

## 限制 / Limits

运镜、背景、透视变化、遮挡和转身会影响识别；不带 RTM 的旋转信号尤其容易受到镜头运动影响。画面尺度不是真实深度。参考重建或观测不足时保持既有空闲策略；重建后的目标可能变化，继续受输出限速约束。

实际机械臂关节映射、逆运动学、碰撞检测、限位与反馈未验证。输出监视是指令值，不能声称已到达该物理位置；项目名称不表示已兼容任意机械臂。

Camera motion, background, perspective, occlusion and reference resets can change targets. Image-based rotations are experimental. Automated and synthetic checks do not establish real-clip quality or robot-arm compatibility; joint mapping, IK, collision checks and feedback remain unverified.

仅更新本地测试源码和启动说明；不修改正式环境依赖，不打包、提交、推送，不覆盖正式目录和旧发布包。
