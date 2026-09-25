# SR6/OSR6 Realtime Screen TCode v2.0.0-test.26

## English

### Download and run

**For normal use, download the asset whose name ends in Windows.zip. Extract the complete folder, then double-click its Start.cmd or SR6-OSR6-Realtime-Screen-TCode.exe. No separate Python installation is required.**

- Keep the entire folder, especially `_internal`. Do not run inside the ZIP or move the EXE away from its supporting files.
- The separately attached `Start.cmd` is a spare launcher. Place it inside the extracted application folder; it is not a self-contained application.
- For the independent visual preview, double-click `Pose-Preview-Lab/Start.cmd`. It uses the same bundled runtime.
- `Source.zip` contains the matching source. Running from source requires Python 3.10+.
- `RELEASE_INFO.json` in both archives identifies the same source commit. Use `SHA256SUMS.txt` to verify the downloaded files.

This release completes Windows packaging and the standalone-preview entry point, includes required loopback-audio resources, and adds complete source snapshots and per-version checksums. Analysis and final-output algorithms remain those of test.25; brief-loss estimates still continue for **at most 2 seconds**. Matching source and Windows archives are retained for each release without replacing older versions.

Models, downloadable GPU runtimes, personal settings, logs and caches are excluded. Start with **Log only**. The application is unsigned; physical robot-arm mapping, inverse kinematics, collision handling and feedback remain unverified.

Validation: 423 isolated main tests, 38 Lab tests and the simulator stream check passed. A later packaging-only license fix passed all 12 targeted checks. Actual source and EXE startup passed in both languages, including the standalone Lab; the frozen EXE passed CPU/model inference and timed Log-only capture. Personal settings remained unchanged.

[Startup guide](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.26/tools/README-Portable.md) · [Changes and validation](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.26/docs/Test_2.0.0_test26.md) · [Third-party notices](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.26/THIRD_PARTY_NOTICES.md)

## 中文

### 下载和运行

**普通用户请下载名称以 Windows.zip 结尾的附件。完整解压后，双击里面的 Start.cmd 或 SR6-OSR6-Realtime-Screen-TCode.exe。不需要另外安装 Python。**

- 保留整个目录，尤其是 `_internal`；不要在压缩包内运行或单独搬走 exe。
- 单独附的 `Start.cmd` 是备用启动器，必须放在已解压的程序目录里，不能单独作为应用运行。
- 独立视觉预览：双击 `Pose-Preview-Lab/Start.cmd`，使用相同的内置运行时。
- `Source.zip` 是配套源码，源码启动需要 Python 3.10+。
- 两个包的 `RELEASE_INFO.json` 指向同一源码提交；`SHA256SUMS.txt` 用于核对下载文件。

本版补齐 Windows 打包与独立预览入口、音频回环依赖资源、完整源码留样和逐版校验。分析与最终输出算法沿用 test.25，短暂缺测估算仍最多 **2 秒**。每次发布保留配套源码和 Windows 包，不覆盖旧版。

模型、可下载 GPU 运行库、个人设置、日志及缓存不随包分发。首次建议用 **Log only** 检查。程序未数字签名；真实机械臂映射、逆运动学、碰撞检测和反馈仍未验证。

验证：隔离主程序 423 项、Lab 38 项、模拟器指令流检查通过；后续纯打包许可修正的 12 项定向测试通过。实际源码／exe 中英文启动、独立 Lab、打包 CPU／模型推理和定时 Log only 读屏通过，个人设置未改变。

[启动说明](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.26/tools/README-Portable.md) · [改动与验证](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.26/docs/Test_2.0.0_test26.md) · [第三方许可](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.0-test.26/THIRD_PARTY_NOTICES.md)
