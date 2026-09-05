# SR6/OSR6 Realtime Screen TCode High Hardware Compatibility v2.0.0-test.3

> **BETA / PRE-RELEASE: experimental features, NOT stable 2.0.0.**
> **测试预发布：新增硬件兼容及 GPU 功能仍在测试，不是 2.0.0 稳定版。**

## English

**Adults only. Minors are prohibited.** Start with `Log only`, narrow travel limits and low intensity. Keep emergency stop accessible. Six-axis mode requires a clear subject and good lighting; preview is not actual device feedback.

- Original OSR / SR6/OSR6 TCode serial/BLE output is retained. SR6 and OSR6 refer to the same hardware family here.
- Experimental Intiface routing: The Handy, Lovense, Kiiroo / FeelTechnology, Vorze, We-Vibe, Satisfyer, MysteryVibe and Motorbunny, limited to detected functions. OSSM requires TCode-compatible firmware. **Autoblow is not enabled.**
- Custom mode binds L0/L1/L2/R0/R1/R2 to selected device functions, initially unbound. New hardware has not been physically validated; compatibility and motion quality are not guaranteed. Other devices show a labelled SR6/OSR6 reference preview, not their actual shape.
- RTM Pose 2D/3D can select CUDA or ONNX + DirectML. GPU is off by default. CUDA requires NVIDIA and a larger runtime; DirectML has a smaller runtime and supports compatible DirectX 12 AMD/NVIDIA/Intel GPUs. Size does not imply guaranteed accuracy differences.
- In-app runtime installation works in portable and source builds, with actual byte/percentage progress, component names, verification and CPU fallback. Restart after installation/backend switching when prompted. AMD hardware and all model/backend combinations still need testing.
- Full-width dropdowns, scrollable start dialog, clearer GPU detection/status, separate test settings and custom mappings.

### Downloads

Choose **Windows.zip** for normal use. Extract the complete folder, then double-click **Start.cmd** or the exe; Python is not required. Keep `_internal` beside the exe. Windows security software may warn about this unsigned test build.

Choose **Source.zip** for source code with `Start.cmd` / `Start-Source.cmd` (Python 3.10+ required if no runtime is available). Both archives contain README, bilingual tutorials/manuals, changelog, licenses and acknowledgements.

**No local models or optional CUDA/cuDNN/NVIDIA/DirectML runtimes are bundled.** Download them inside the app. CPU inference dependencies and installer tooling are included in Windows.zip. Intiface Central and GPU drivers are separate installations. Checksums: `SHA256SUMS.txt`.

Branch: `2.0.0-High-Hardware-Compatibility-BETA`. Tag: `v2.0.0-test.3`. This prerelease does not replace the stable release or merge into `main`.

Thanks to **“电话机”** for volunteer testing and suggestions. The name is intentionally unchanged in English.

## 中文

**仅限成年人使用，未成年人禁止使用。** 请先用 `Log only` 预览，再使用窄行程、低强度测试，并确保可以随时急停。六轴只适合光线好、主体清晰的画面；预览不代表设备真实位置。

- 保留 OSR / SR6/OSR6 原有 TCode 串口/BLE 输出。本项目中 SR6 与 OSR6 并列表示同一设备在不同平台的名称。
- 通过 Intiface 尝试适配 The Handy、Lovense、Kiiroo / FeelTechnology、Vorze、We-Vibe、Satisfyer、MysteryVibe、Motorbunny，仅限扫描出的型号和功能。OSSM 需要 TCode 兼容固件；**Autoblow 尚未开放输出**。
- 自定义设备可绑定 L0/L1/L2/R0/R1/R2 与设备交互，默认全部不绑定。新增设备尚未经实体硬件验证，**兼容不保证效果好或全系列支持**。没有对应外形的硬件会提示使用 SR6/OSR6 参考预览。
- RTM Pose 2D/3D 可选 CUDA 与 ONNX + DirectML，GPU 默认关闭。CUDA 用于 NVIDIA，运行库较大；DirectML 运行库较小，用于支持 DirectX 12 的 AMD/NVIDIA/Intel 显卡。不把体积差异当作准确率保证。
- 免安装 exe 和源码版都支持软件内安装运行库，显示真实百分比、大小、组件和当前阶段；校验失败可重试，推理失败回退 CPU。安装或切换后按提示重启；AMD 真机及不同模型组合仍待测试。
- 优化下拉列表完整显示、开始输出弹窗滚动、GPU 检测与状态；保留独立测试设置，不覆盖正式版设置。

### 下载与启动

普通用户下载 **Windows.zip**，**完整解压后双击 Start.cmd** 或 exe，无需另装 Python。不要单独移走 exe，也不要在 ZIP 内运行。此测试版未做代码签名，Windows 安全软件可能提示未知发布者。

源码用户下载 **Source.zip**，使用 `Start.cmd` / `Start-Source.cmd`；没有可用环境时需要 Python 3.10+。两个包均包含 README、中英文教程/手册、版本日志、许可证与第三方鸣谢。

**两个包均不含本地模型、CUDA/cuDNN、NVIDIA 可选运行库或 DirectML 二进制文件。** 有需要时在软件内下载；Windows 包包含 CPU 推理必需依赖和安装工具。Intiface Central 与显卡驱动需要另装。`SHA256SUMS.txt` 提供文件校验值。

发布分支为 `2.0.0-High-Hardware-Compatibility-BETA`，标签为 `v2.0.0-test.3`。不合并到 `main`，不替换已有正式版。

感谢 **“电话机”** 参与志愿测试并提供建议；英文也保留带引号的中文名字。

合作、侵权、许可证修正与建议 / Contact: **aivnailedeng@gmail.com**
