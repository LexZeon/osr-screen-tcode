# 2.0.0-test.3 设备兼容说明

这是独立 BETA 预发布。Windows 免安装包完整解压后双击 `Start.cmd`；源码包也提供 `Start.cmd`，但需要可用的 Python 环境。不修改 1.1.2 正式目录或正式版设置。测试设置保存在用户目录的 `.osr_screen_tcode_2_0_test` 中。模型与可选 GPU 运行库不随包分发，需要时在软件内下载。

## 设备选择

| 主界面设备类型 | 连接方式 | 本测试的范围 |
| --- | --- | --- |
| OSR / SR6/OSR6 | 原有 Serial COM / BLE UART | 保留原有 TCode 六轴输出 |
| 自定义（Intiface） | 本机 Intiface Central | 设备类型第二项，把 L0～R2 分别绑定到选定设备的不同功能 |
| OSSM | TCode 串口 / BLE UART | 仅适用于兼容 TCode 的固件，不保证原厂固件可用 |
| Intiface / Buttplug | 本机 Intiface Central 服务 | 使用扫描返回的设备及其可用功能 |
| The Handy | Intiface Central | 尝试对扫描到的位置功能输出 L0；具体型号/固件需真机验证 |
| Lovense | Intiface Central | 尝试控制设备报告的振动、旋转、往复、收缩等功能 |
| Kiiroo / FeelTechnology | Intiface Central | 尝试控制扫描到的受支持型号；不代表全部产品或厂商 SDK 已接入 |
| Vorze、We-Vibe、Satisfyer、MysteryVibe、Motorbunny | Intiface Central | 同上，以扫描结果及功能列表为准 |
| Autoblow | 待适配 | 已核对官方云端 API；本测试未启用设备输出，选择后会明确提示 |

以上新增商业设备适配完成了模拟协议检查，尚未通过实体设备验证；兼容不保证效果好或同品牌所有型号可用。普通品牌模式控制一个功能，自定义模式可为六个轴分别绑定一个功能，始终只连接一个手动选定的设备。

## 自定义交互

选择设备类型第二项“自定义（Intiface）”，启动 Intiface 服务并扫描、手动选择设备。L0、L1、L2、R0、R1、R2 每行可选“不绑定”或设备真实返回的功能。例如将 L0 绑定位置功能、R0 绑定旋转功能、L2 绑定振动功能；实际可选项取决于硬件。

默认全部不绑定，至少绑定一个轴才可连接。同一功能不能重复绑定两个轴。使用非 L0 轴时需选择 Six Axis。绑定变化后需重新连接。保存的绑定只在服务地址、手动选择的设备身份和完整功能列表匹配时恢复；不会自动选中或连接设备。恢复默认会清除绑定。

自定义仅适用于 Intiface 支持的功能，不会自动兼容私有串口/HTTP 协议，也不执行自定义系统命令。同类功能合并发送，不同指令类型轮流读取最新目标，因此单项刷新频率可能降低。未绑定功能不主动驱动；停止请求作用于整个选定设备。

## 使用 Intiface

1. 从 [Intiface 官网](https://intiface.com/)安装 Intiface Central，启动它的服务。应用内“下载 Intiface”会打开官网，不会自动安装。
2. 打开设备电源。释放手机应用及其他软件对该设备的连接占用。
3. 在本软件主界面选择品牌，保留默认地址 `ws://127.0.0.1:12345`，或填写 Intiface 实际显示的服务地址。
4. 点击“扫描/刷新设备”，随后手动选择设备和控制功能。扫描不发送运动指令。
5. 选择跟随轴。L0 是默认值；选择其他轴后使用六轴输出。速度/强度上限默认 20%。
6. 点击“连接设备”，然后“开始实时输出”。商业设备连接成功后不会自动回中。
7. 点击“停止”或“急停回中”会向所选 Intiface 设备发送停止请求。此类设备的急停不发送 SR6/OSR6 回中指令。

同型号设备如果名称重复，请先在 Intiface 中设置不同显示名称。每次打开软件均需重新扫描；程序不会保存并盲用跨会话的设备编号。

## 输出与延迟

- 原有 L0、RTM Pose、光流、卡尔曼和六轴分析算法未修改。新增兼容层接收原有安全输出层生成的指令。模型加载层支持 CUDA/DirectML 推理后端与 CPU 回退，设置和安装说明见主 README。
- 位置功能跟随所选轴受上下限、行程倍率、反转等约束后的数值，额外限制移动速度。20% 表示最多约 20% 全行程/秒，不是把位置行程缩为 20%。
- 振动、连续旋转、往复速度及收缩/充气强度由所选轴的运动速度生成，20% 表示强度上限为 20%。静止及第一次观测为零强度。
- 为保证运动时间可控，本测试的位置输出要求设备提供 `LinearCmd`；不支持只有 `ScalarCmd Position` 的位置控制。
- 单独选定某个功能后，其他功能不会被自动驱动；停止请求作用于选定设备。
- 后台只保留最新目标，默认最多约 20 次/秒，并遵守服务提供的更慢时间间隔。旧帧不排队追赶。
- 新输出中断超过 600 ms 时，停止设备并要求重新连接；连接断开、功能改变或指令被拒绝时也停止本次输出，不自动重连后重放。
- Intiface 的蓝牙、网络和实际硬件仍会带来延迟。预览数值不是传感器读回的物理位置。

## 预览与来源

继续使用项目原有的开源 [nb-3d-simulator](https://github.com/nbnb9527/nb-3d-simulator) / [osr-emu](https://github.com/Eroscripts/osr-emu) SR6 参考模型。暂未找到可直接集成且适配本输出流程的上述商业设备外形预览。

选择其他设备时，主界面和 3D 预览都显示“预览形状与实际设备不同”；该模型演示映射前的受限轴指令，不代表商业设备的几何结构、全部轴数或实际反馈。已打开的预览会随设备选择更新说明。

接口参考：[Buttplug v3 设备枚举](https://buttplug.io/docs/spec-v3/spec/enumeration/)、[通用输出指令](https://buttplug.io/docs/spec-v3/spec/generic/)、[Autoblow 官方 API](https://developers.autoblow.com/reference/http-api-v1-autoblow/)。Autoblow 存在云端频率限制，停止 `goto` 运动的行为还需确认，因此不以未经验证的命令冒充实时兼容。

SR6/OSR6 在本项目中并列显示，指用户在不同平台见到的同一设备称呼。合作与侵权联系：aivnailedeng@gmail.com。

---

# 2.0.0-test.3 Device Compatibility

This is an isolated source test build. Run `Start.cmd`. No exe or zip is produced, and the 1.1.2 release and its settings are unchanged. Test settings use `.osr_screen_tcode_2_0_test` in the user home directory.

The main window retains native TCode serial/BLE for OSR / SR6/OSR6. OSSM requires TCode-capable firmware; stock firmware is not guaranteed to work. The Handy, Lovense, Kiiroo / FeelTechnology, Vorze, We-Vibe, Satisfyer, MysteryVibe and Motorbunny use Intiface Central. Availability depends on the exact model, firmware and features returned by Intiface. These integrations are simulator-tested, not hardware-certified. Autoblow remains explicitly unavailable pending validation of cloud rate limits and stopping behavior.

Install and start [Intiface Central](https://intiface.com/), power on the device, close competing device controllers, select a brand in this app and click **Scan / Refresh Devices**. The default server URL is `ws://127.0.0.1:12345`. Select the actual device, its function and a source axis, then connect and start realtime output. Scanning sends no movement commands. Connecting does not automatically center commercial devices. The download button opens the Intiface website; it does not install software.

Brand modes drive one selected function. **Custom (Intiface)** is the second device option and can bind L0 through R2 to separate functions of one selected device. Every axis starts unbound; at least one binding is required and duplicate function bindings are rejected. Non-L0 bindings require Six Axis. The brand selector never auto-selects hardware. Duplicate devices must have unique display names in Intiface. Device indexes are not persisted; scan and manually select again after restarting. Saved bindings return only for the same server, device identity and full feature list. Restore Defaults clears them. Custom mode is not arbitrary HTTP/serial protocol support or a system-command runner.

Same-type functions share one command; different types rotate using the newest target at each device timing gap. Per-function updates may therefore be slower. Compatibility does not guarantee good motion quality or support for every product in a brand.

Position functions follow already limited axis positions, with an additional movement speed cap. A 20% cap means about 20% of full stroke per second, not 20% of position travel. Position output requires `LinearCmd` with duration; scalar-only position devices are not enabled. Speed/intensity functions follow axis motion speed, with zero output on the first sample or when stationary and a default 20% maximum. Other motors are not automatically mapped. Stopping affects the selected device.

The backend retains only the newest target, respects the device timing gap and sends at most about 20 updates per second. Stale output beyond 600 ms, disconnects and command rejection stop the session. Reconnect manually; buffered movements are not replayed. Bluetooth and hardware latency still apply.

The preview retains the existing open-source SR6 reference geometry. Other device selections display **Preview shape differs from the actual device**, both in the main window and in the preview. It shows limited axis commands before device-specific mapping, not measured hardware feedback. Existing preview windows receive updated device notices.

The original analysis algorithms and TCode mapper are unchanged. Protocol references and preview upstream links are listed above. SR6/OSR6 is the combined name used for the same device across platforms in this project. Cooperation and copyright contact: aivnailedeng@gmail.com.
