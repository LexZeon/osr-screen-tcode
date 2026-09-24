# SR6/OSR6 Realtime Screen TCode 2.0.0-test.25

**源码预发布 / Source prerelease**

## 中文

本次公开 test.25 累积源码，包含 test.4～25 的预览整合、视觉分析、最终输出模拟器与采集修正。项目名称简化为 **SR6/OSR6 Realtime Screen TCode**，移除原名称中的兼容性宣传；保留现有 SR6/OSR6 TCode 串口／BLE 接口，其他商业设备适配已移除。

### 主要变化

- **主程序内分析预览**：同一采样帧的画面、原始／处理后骨架、运动证据与图表。默认打开输出监视；内置模拟器使用经过最终行程倍率、反向、联动、限位、限速与时序处理的指令。两者都不是设备位置反馈。
- **混合分析 v2＋融合参考为默认分析**：使用多组局部光流跟踪主体框中心，独立验证背景运镜，以连续的画面三维代理轴表达主副方向。保留原混合 v1 的 L0 核心，推荐用于平面大幅动作。v2 可选 RTM 2D 旋转辅助。
- **主体与目标分开**：A 为主体原点；T? 是独立跟踪的客体候选；没有可靠客体时，V? 表示由已确认往复推定的假定端点。可靠时按原点接近目标的比例生成 L0，远离大、靠近小；不能据此确认真实接触。
- **短暂缺测接续**：弱像素跟踪与 A? 虚线标注；已确认节奏最多延续 **2 秒**，最后 0.5 秒减速。没有已确认周期时，只允许最多 **0.3 秒／倍率前 15% 行程**的短速度接续，不生成假往复。单帧恢复不能续期，明确暂停／切镜／重设参考会清除旧规律；恢复后从当前输出衔接。
- **全／半／1/4 行程**：共用 v2 的往复证据，按幅度选择余弦行程并逐步匹配节奏；可选 Pose 旋转辅助。只接续已确认的行程。
- **RTM Pose 2D**：移植骨架稳定处理，增加可配置的 L0 自动来源、快速丢点时 v1 接管和逐轴小幅往复放大等行为。RTM Pose 3D 已移除。
- **多屏框选与采集一致**：采用物理像素坐标，支持不同分辨率、混合 DPI、负坐标与跨屏选区；空隙填黑，显示器布局改变会停止旧采集。深色快照选区提供清晰边框、屏幕编号和确认／重选按钮。默认处理最长边仍为 640。
- **最终输出设置保留**：五档只影响最终脚本／实时输出；接近上下限减速默认开启、距离 10%，只改变到达时间，不限制目标位置。中英文、保存与恢复默认同步。

### 运行

需要 **Windows + Python 3.10 或更新版本**。下载下方 GitHub 自动生成的 **Source code (zip)**，完整解压后双击根目录 `Start.cmd`；首次运行会在本目录建立 `.venv` 并安装依赖，需要联网。已存在的兼容环境可复用，共享环境只读，不向其中安装依赖。先选择 **Log only** 检查效果。

**本次没有新 exe 或独立 Windows 便携包**；自动源码 ZIP 不是免 Python 的程序包，旧版附件也不代表本次源码。模型和可选 GPU 组件由软件内另行下载，不随源码分发。独立预览为 **0.2.2-test**，仍不输出设备指令。

详见 [README](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/README.md)、[启动说明](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/Start.md) 和 [test.25 验证记录](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/docs/Test_2.0.0_test25.md)。

### 验证与限制

发布前复验：隔离主程序 **392 项（434.184 秒）**、独立预览 **38 项（0.346 秒）**通过；中英文启动、Lab 启动及模拟器最终指令检查通过，个人设置未改写。test.25 开发阶段另完成 Log only 实际读屏检查。完整记录保留开发过程中的失败与修正，不把自动测试等同于实片或硬件验证。

强模糊、遮挡、相似切镜与缓慢长周期仍可能造成缺测。画面尺度不是真实深度，T?／V? 不等于真实接触；估算不会无限延续。**机械臂关节映射、逆运动学、碰撞检测与真实位置反馈尚未实现或验证，不能宣称已兼容机械臂。** 原有回中位置也不是已验证的机械臂安全姿态。

## English

This source prerelease publishes the cumulative test.4–25 work under the shorter name **SR6/OSR6 Realtime Screen TCode**. Existing SR6/OSR6 serial/BLE TCode transport remains; other commercial-device integrations have been removed.

### Highlights

- Integrated paired-frame analysis/skeleton preview and an output monitor. The included simulator follows final transformed and timed commands, not physical feedback.
- Default **Hybrid v2 + Fused reference** tracks a persistent subject-box center with distributed optical-flow support and independently validated camera motion. Main and secondary directions use continuous image-proxy axes. Hybrid v1 retains its original L0 core; v2 offers optional RTM 2D rotation assistance.
- Separate measured subject **A**, independently tracked object candidate **T?**, and inferred endpoint **V?**. Reliable origin-to-target distance can guide near/far L0, without claiming actual contact.
- Bounded brief-loss continuity with dashed **A?** markers. A confirmed rhythm can continue for **at most 2 seconds**, braking over the last 0.5 seconds. Without a confirmed cycle, stable recent velocity permits only a **0.3-second / 15% normalized-travel** bridge before final gains. Detection flashes do not renew the deadline; pauses, cuts and resets clear the old pattern.
- Quarter/half/full cosine travel shares v2 evidence, adapts gradually to the observed cadence and only continues a confirmed stroke. Pose rotations are optional.
- RTM Pose 2D stabilization, configurable automatic L0, warm v1 handoff during fast Pose loss and per-axis small-cycle expansion. RTM Pose 3D has been removed.
- Consistent physical-pixel screen selection/capture across mixed DPI and multiple displays, including negative origins and desktop gaps. The snapshot picker has clear selection controls; display-layout changes stop capture. Default processing remains 640 pixels on the longest edge.
- Five presets affect final output only. Default near-limit slowdown uses a 10% zone and changes arrival time rather than target positions. Bilingual controls and saved/default settings remain supported.

### Run and validate

Use **Windows with Python 3.10+**. Download GitHub's automatic **Source code (zip)**, extract the complete folder and double-click root `Start.cmd`. Fresh startup creates a local `.venv` and installs dependencies; internet access is required. A compatible existing environment can be reused without installing into a shared environment. Begin with **Log only**.

**No new executable or portable Windows package is attached.** Source archives require Python, and older binary downloads do not contain this version. Models and optional GPU components are downloaded separately in the app. Standalone Preview Lab remains **0.2.2-test** and sends no device commands.

Publication checks passed **392 main tests (434.184 s)**, **38 Lab tests (0.346 s)**, bilingual startup, Lab startup and the final-command simulator check; personal settings were preserved. The preceding test.25 development also passed Log-only live capture. See the [quick tutorial](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/docs/Quick_Tutorial_EN.md) and [validation report](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/docs/Test_2.0.0_test25.md) for details, failed development attempts and limitations.

Blur, occlusion, similar-looking cuts and long slow cycles remain limitations. Image scale is not true depth, geometric candidates do not establish contact, and estimates never continue indefinitely. **Robot-arm joint mapping, inverse kinematics, collision handling and physical feedback are not implemented or verified.** No hardware compatibility or safe physical pose is established by these software checks.

## License and acknowledgements / 许可与署名

See [LICENSE](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/LICENSE) and [THIRD_PARTY_NOTICES.md](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.25/THIRD_PARTY_NOTICES.md). Required upstream notices and the credit for [nb-3d-simulator](https://github.com/nbnb9527/nb-3d-simulator) are retained. Models, downloadable GPU runtimes, personal settings, logs and private media are excluded from this source release.
