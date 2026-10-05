# Windows portable edition / Windows 便携版

## English

1. Download the complete **Windows.zip** asset from the GitHub release.
2. Choose **Extract all**. Do not run inside the ZIP or move the EXE away from `_internal`.
3. Double-click **Start.cmd** or **SR6-OSR6-Realtime-Screen-TCode.exe** in the extracted folder.

Python and the basic dependencies are bundled. The separately downloadable Start.cmd is only a
spare launcher: it does not work without the extracted Windows package.

Version **2.1.0** reorganizes source responsibilities while retaining 2.0.2 behavior. The complete
[feature explanations](docs/FEATURES.md) and [code architecture](docs/ARCHITECTURE.md) are included
in this folder and provided as separate release attachments. No setting migration is required.

For the independent visual preview, open **Pose-Preview-Lab/Start.cmd**. It uses the same bundled
runtime and does not feed device output or script generation. Models and downloadable GPU
runtimes are excluded; download them through the application when needed. CPU hybrid analysis
can run first. Use **Log only** for initial checks. Real hardware, robot joint mapping and feedback
have not been validated for this release. The executable is not digitally signed; verify the
repository and published SHA256 before running an unfamiliar download.

In **Hybrid v2** or **Full/Half Travel**, open **+ Models** in Analysis Preview. **v2 optional models** provides independent
ViTTrack and NeuFlow v2 switches, both off by default. Use the adjacent **Download** button
before enabling a model. ViTTrack works on CPU; NeuFlow requires enabled NVIDIA CUDA through
**GPU settings**. This NeuFlow graph does not support DirectML. Missing or failed models use
the original analysis. Models assist image evidence; improvement is not guaranteed for every video.

The matching **Source.zip** contains the application, independent preview, launchers, tests and
build tools. Source startup needs Python 3.10+. The bundled `docs/Source_Start.md` describes that
separate developer workflow. `RELEASE_INFO.json` identifies the committed source version;
`FILES_SHA256SUMS.txt` lists extracted-file hashes; release-level `SHA256SUMS.txt` lists asset hashes.
Legal notices are in **LICENSE**, **THIRD_PARTY_NOTICES.md**, **OPEN_SOURCE_NOTICE.md** and **licenses**.

## 中文

1. 在 GitHub Release 下载名称以 **Windows.zip** 结尾的完整运行包。
2. 右键 ZIP，选择“全部解压”。不要在压缩包内直接运行，也不要只复制 EXE。
3. 打开解压后的文件夹，双击 **Start.cmd** 或 **SR6-OSR6-Realtime-Screen-TCode.exe**。

本运行包自带 Python 运行时与基础依赖，不要求安装 Python。`_internal` 是程序必须的
运行文件，请与 EXE 保持在一起。Release 单独提供的 Start.cmd 只是同一启动器的备用下载，
单独下载它不能代替 Windows ZIP。

**2.1.0** 只整理源码职责，保留 2.0.2 行为，不要求迁移设置。本目录包含
[逐项功能说明](docs/FEATURES.md)和[源码结构说明](docs/ARCHITECTURE.md)，发布页也单独提供这两个附件。

独立视觉预览：打开 **Pose-Preview-Lab** 文件夹，双击其中的 **Start.cmd**。
它使用同一套内置运行时，不参与设备输出或脚本生成。

模型和可下载的 GPU 运行库没有打包，按软件提示另外下载；普通混合分析可先用
CPU 运行。首次测试请选择 **Log only**。真实硬件、机械臂映射与反馈未在本发布中验证。
Windows 如提示未知发布者，请先核对下载仓库和 SHA256；此包尚未数字签名。

选择**混合分析 v2**或**全／半行程**，点分析预览中的“**+ 模型**”，在“**v2 可选模型**”中分别开启 ViTTrack、NeuFlow v2；
两项默认关闭，先点旁边的“下载”。ViTTrack 可用 CPU；NeuFlow 需在“GPU 设置”中启用 NVIDIA
CUDA，当前模型不支持 DirectML。模型缺失或失败时使用原分析；它们辅助画面观测，不保证每段视频都更好。

源码留样为同版本 **Source.zip**，包含主程序、独立预览、启动器、测试与构建工具。
源码启动需要 Python 3.10+；源码包的 Start.md 说明与本免 Python 运行包不同。
本包 `docs/Source_Start.md` 仅供源码开发参考。`RELEASE_INFO.json` 记录源码提交与版本，
`FILES_SHA256SUMS.txt` 可核对解压文件；发布目录 `SHA256SUMS.txt` 可核对下载的 ZIP。
许可证与借鉴说明见 **LICENSE**、**THIRD_PARTY_NOTICES.md**、**OPEN_SOURCE_NOTICE.md**
以及 **licenses** 目录。
