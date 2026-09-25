# SR6/OSR6 Realtime Screen TCode v2.0.0

## English

**Official 2.0.0 release:** test.25 is the analysis/output baseline, with Windows portable packaging included. Earlier tags and releases remain intact.

### Download and run

**For normal use, download the asset whose name ends in Windows.zip. Extract the complete folder, then double-click its Start.cmd or SR6-OSR6-Realtime-Screen-TCode.exe. No separate Python installation is required.**

- Keep the entire folder, especially `_internal`. Do not run inside the ZIP or move the EXE away from its supporting files.
- The separately attached `Start.cmd` is a spare launcher. Place it inside the extracted application folder; it is not a self-contained application.
- For the independent visual preview, double-click `Pose-Preview-Lab/Start.cmd`. It uses the same bundled runtime.
- `Source.zip` contains the matching source. Running from source requires Python 3.10+.
- `RELEASE_INFO.json` in both archives identifies the same source commit. Use `SHA256SUMS.txt` to verify the downloaded files.

This release completes Windows packaging and the standalone-preview entry point, includes required loopback-audio resources, and adds complete source snapshots and per-version checksums. Analysis and final-output algorithms remain those of test.25; brief-loss estimates still continue for **at most 2 seconds**. Matching source and Windows archives are retained for each release without replacing older versions.

Models, downloadable GPU runtimes, personal settings, logs and caches are excluded. Start with **Log only**. The application is unsigned; physical robot-arm mapping, inverse kinematics, collision handling and feedback remain unverified.

Validation: **424 isolated main tests and 38 Lab tests passed**, including matching source/Windows manifests and license collection. Simulator final-command checks, actual source and rebuilt 2.0.0 EXE startup in both languages, standalone Lab, CPU inference and an external pose model passed. Personal settings were unchanged. Earlier preparation checks and limitations remain in the validation report.

[Startup guide](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0/tools/README-Portable.md) · [Changes and validation](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0/docs/Validation_2.0.0.md) · [Third-party notices](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0/THIRD_PARTY_NOTICES.md)

## 中文

**正式版 2.0.0：** 分析／输出以 test.25 为基线，提供 Windows 便携运行包。原有标签与发布保持不变。

### 下载和运行

**普通用户请下载名称以 Windows.zip 结尾的附件。完整解压后，双击里面的 Start.cmd 或 SR6-OSR6-Realtime-Screen-TCode.exe。不需要另外安装 Python。**

- 保留整个目录，尤其是 `_internal`；不要在压缩包内运行或单独搬走 exe。
- 单独附的 `Start.cmd` 是备用启动器，必须放在已解压的程序目录里，不能单独作为应用运行。
- 独立视觉预览：双击 `Pose-Preview-Lab/Start.cmd`，使用相同的内置运行时。
- `Source.zip` 是配套源码，源码启动需要 Python 3.10+。
- 两个包的 `RELEASE_INFO.json` 指向同一源码提交；`SHA256SUMS.txt` 用于核对下载文件。

本版补齐 Windows 打包与独立预览入口、音频回环依赖资源、完整源码留样和逐版校验。分析与最终输出算法沿用 test.25，短暂缺测估算仍最多 **2 秒**。每次发布保留配套源码和 Windows 包，不覆盖旧版。

模型、可下载 GPU 运行库、个人设置、日志及缓存不随包分发。首次建议用 **Log only** 检查。程序未数字签名；真实机械臂映射、逆运动学、碰撞检测和反馈仍未验证。

验证：隔离主程序 **424 项、Lab 38 项通过**，包含源码／Windows 清单一致性和许可证收集。模拟器最终指令、实际源码与重新构建的 2.0.0 exe 中英文启动、独立 Lab、CPU 推理及外部模型检查通过，个人设置未变。前期准备验证及限制保留在验证报告中。

[启动说明](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0/tools/README-Portable.md) · [改动与验证](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0/docs/Validation_2.0.0.md) · [第三方许可](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0/THIRD_PARTY_NOTICES.md)
