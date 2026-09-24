# 2.0.0-test.7 / Local source test

本轮在 test.6 的同帧采集、分析和预览基础上修正 v2 主方向判断，整理舞蹈默认设置，并恢复最终输出的 3D 模拟预览。仅更新本地测试源码。双击根目录 **Start.cmd**；[Start.md](../Start.md) 是启动说明。基础移植与输出规则见 [test.6 记录](Test_2.0.0_test6.md)。

This update strengthens v2 direction selection, separates dance preferences, and restores the 3D preview of final output. Double-click the root **Start.cmd**. The [test.6 record](Test_2.0.0_test6.md) documents the underlying integration and output rules.

## v2 主方向 / Primary direction

- 初始以上下为主。持续单向横移／缩放不会仅凭速度或累计偏移接管 L0。
- 左右／尺度需要明显、持续的往复运动证据，并持续胜过当前方向，才平滑接管。短暂抖镜和小幅高频噪声不计为有效往复；其他可靠方向仍保留少量贡献。
- 主方向切换只分配之后的运动增量，不重新混合过去积累的画面偏移；暂停时不因权重变化生成虚假行程。积分在输出范围内截断，反向后可立即离开边界。
- 单轴与六轴使用相同的 L0 判断；RTM 2D 辅助只替换 v2 六轴旋转分析。舞蹈可选的 L0 混合也使用这个 v2 来源。原混合分析 1 的核心未改。

工程参数：方向证据使用 60 ms 低通、至少 0.75 个画面百分比点的转向幅度、至少 160 ms 的单程和最近 3 秒的双向行程。竞争方向须超过当前证据的 1.4 倍并持续 450 ms，权重按 350 ms 时间常数过渡。这些是测试中的识别阈值，不是机械位置或真实深度。使用源时间戳，非固定帧数。

Vertical is the initial fallback. One-way pan/zoom cannot win from speed alone. Alternatives require substantial reciprocal motion, a sustained advantage, and a smooth handover. Only subsequent motion increments are remapped, so old offsets cannot create a false stroke during a switch. Single-axis and six-axis v2 share L0; optional pose assistance changes rotations only. Hybrid 1 is unchanged.

## 默认设置与界面 / Defaults and UI

分析列表首项是 **RTM Pose 2D（推荐-舞蹈）**；首次启动与恢复默认仍选中 **混合分析 v2（推荐-非舞蹈）**，默认不带 RTM 旋转辅助。主界面默认打开 **输出监视**。

| 设置 / Setting | 舞蹈 RTM 2D / Dance | 混合分析 / Hybrid |
| --- | --- | --- |
| 采集 FPS / Capture FPS | 45 | 45 |
| 输出曲线拟合 / Output curve fitting | 开 / On | 开 / On |
| GPU | 关 / Off | 关 / Off |
| 光流、卡尔曼、异常过滤、微抖平滑 / Four pose options | 全开 / All on | 全关 / All off |
| 混合 L0 / Blend into L0 | 默认关，权重 30% / Off, 30% | 不适用 / N/A |
| 压缩延迟 / Compression latency | 0 | 0 |

舞蹈与混合分析分别保存上述设置。首次进入舞蹈使用舞蹈默认值；已有明确保存的旧设置只迁移到原本使用的模式，不覆盖另一组默认值。恢复默认会重置两组。主界面和开始弹窗、中英文同步。

舞蹈未启用混合时隐藏“L0 混合来源”，启用后只显示 **混合分析 v2**，不再选择 v1。旧 v1 混合来源设置会迁移到 v2。“v2：启用 RTM 2D 旋转辅助”只在混合分析 1/v2 出现，在 v1 中禁用以保留其原 L0 核心，在 v2 中可用；舞蹈模式隐藏此项。

RTM 2D is listed first; Hybrid v2 remains the default selected mode. Output Monitor is the initial tab. Dance and hybrid preferences are saved separately, including capture rate and the four pose options. Reset restores both profiles. The L0 source label appears only when dance blending is enabled and always uses v2. The v2 rotation-assistance control is hidden in dance and disabled in Hybrid 1.

## 显示预览与最终输出 / Simulator and final output

**显示预览**打开项目已内置、基于 [nb-3d-simulator](https://github.com/nbnb9527/nb-3d-simulator) 的 SR6 参考模拟器；原署名与许可保留。**分析预览**页继续用于原始／处理后画面和图像观测图表。

模拟器接收 `_emit_command` 实际交给当前输出端的最终 TCode：包括曲线处理、五档／行程倍率、逐轴倍率、反向、L0 对 L1/L2 的 1／2.5／1 联动，以及已启用的启动缓升、限位、限速与边界处理。它不再根据原始识别值自行计算倍率，也不使用离线脚本去覆盖正在输出的指令。打开较晚时先接收最后一条指令，然后继续跟随实时输出；停止后保持最后收到的值。连接失效或写入失败的指令不广播。

可以在 **Log only** 下测试整条输出链路，无需硬件。点击显示预览只打开显示服务，不会自动开始分析或连接设备。模拟器的本地连接只接收输出并处理心跳，不向设备下发控制。原有 OFS 脚本播放代码保留，但收到主程序最终 TCode 后，其动画不会用默认值覆盖指令。

**Show Preview** opens the bundled simulator. It receives exactly the final TCode passed to the current output sink, after all enabled host gains, coupling, inversion and output constraints. Late clients receive the last command first. The simulator does not apply host travel gains again, and its OFS/default animation cannot override the direct stream. **Analysis Preview** remains the separate image-analysis view. Log only exercises the output route without hardware.

## 验证 / Verification

- 主程序 **116 项**自动测试、独立预览 **28 项**测试通过。
- 模拟器页面的 JavaScript 消息与动画代码在无浏览器、无 WebGL 的测试中通过：最终指令原样传入，100 次动画回调及断开连接不覆盖最后指令。
- 实际本地 WebSocket 测试通过：最后指令缓存、后续消息、心跳及关闭。组合行程倍率、逐轴反向、联动和限速后，模拟器指令与输出端一致。
- 主方向覆盖单向横移／缩放干扰、上下往复、真正的左右／尺度往复、短暂抖镜、高频噪声、静止保持、切换连续性及 30/45/60/120 FPS 源时间一致性。实际合成图像经过光流处理的横移干扰用例通过。
- 主界面／弹窗设置、保存／恢复默认、旧设置迁移、中英文启动检查通过；不连接设备、不保存测试配置。

116 main tests and 28 standalone tests passed. Separate simulator message/animation checks and a real loopback WebSocket test passed. Synthetic image flow, camera-drift interference, reciprocal motion, source clocks, configuration migration and both language startup paths were checked. No hardware was connected.

浏览器自动检查被本地文件 URL 安全策略拒绝，因此 **3D 窗口的实际渲染未完成自动验证**；上述消息代码与连接检查不等于视觉验证。

Browser automation rejected the local file URL. Actual 3D rendering has not been visually verified in this run; message-code and connection tests do not establish rendering correctness.

## 文件与限制 / Files and limits

- 主方向与回归用例：`src/osr_screen_tcode/dominant_motion.py`、`tests/test_dominant_motion.py`。
- 默认设置、保存／迁移与界面：`analysis_preferences.py`、`config.py`、`app.py`、`integrated_preview.py`；同帧分析：`visual_pipeline.py`。
- 最终输出预览：`preview.py`、`assets/osr_emu_standalone.html`；相关用例：`tests/test_device_ui.py`、`tests/test_analysis_preferences.py`、`tests/test_simulator_stream.cjs`。
- 版本、启动说明与记录：`README.md`、`Start.md`、`AI_Prompting_Guide.md`、两份版本日志及本说明。

**仍需真实片段复测。** 全画面光流不能可靠地区分摄影机和人物：往复运镜、主体较小、背景占多数、遮挡及切镜头仍可能误判；持续单向的真实左右／前后动作也可能暂时不接管 L0。尺度变化不是实际深度。默认最长边保持 640；独立 Lab 源码和版本保持原样。

模拟器是指令可视化，不是实际关节或位置反馈。机械臂关节映射、逆运动学、碰撞检测及真实反馈尚未验证。未打包、提交或推送；正式目录、正式环境依赖、旧发布包和远程历史未改。

Real clips still need review. Global flow cannot reliably separate camera and subject motion: reciprocal camera moves, dominant backgrounds, occlusion and cuts can still mislead it, while a genuine one-way lateral/scale motion may take longer to become primary. Image scale is not depth. Robot-arm mapping, IK, collision checks and feedback remain unverified. No package, commit, push or formal-environment change was made.
