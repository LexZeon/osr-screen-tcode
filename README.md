# OSR6 Realtime Screen TCode

**OSR6 Realtime Screen TCode** is a Windows app that reads a selected screen region in realtime, converts visible motion into TCode, and outputs it to OSR/SR6/OSR6-compatible devices through USB serial or BLE. It can also preview output without hardware and record/export `.funscript`.

> **Adults only. This project is intended for adults. Minors are prohibited.**
>
> **Important six-axis warning:** Six Axis mode is only recommended when lighting is good, the main subject is clear, and the selected screen region is clean. If the image is unclear, crowded, dark, or unstable, start with `L0 Only` or `Log only` preview.

Current version: `1.0.2`



## Download

- Windows ready-to-run package: `OSR6-Realtime-Screen-v1.0.2-Windows.zip`
- Source package: `osr-screen-tcode-source-v1.0.2.zip`
- English quick start: `Quick_Start.md`
- Chinese quick start: `简易教程.md`
- Full English manual: `User_Manual_EN.md`
- Full Chinese manual: `用户使用手册.md`

Extract the whole Windows zip before running. Do not run the exe directly from inside the zip preview window.

## Run From Source

After cloning the repository on Windows, double-click `Start.cmd` or `Start-Source.cmd`. It creates a local `.venv`, installs the required Python packages, and starts the app from `src`.

## Main Features

- Realtime screen-region capture and motion analysis.
- USB serial and BLE UART output for TCode-compatible devices.
- `L0 Only` and `Six Axis` output modes.
- Hybrid analysis mode recommended for low-latency screen reading.
- Optional pose-assisted analysis for full-body/dance-style footage.
- Audio-only mode for rhythm-driven use.
- Per-axis limits, total travel scaling, presets, smoothing, speed limit, dead zone, gating, and other comfort controls.
- Measurement mode for saving safe upper/lower limits locally.
- Live output curve and 3D OSR6 preview based on the final limited output.
- Local settings persistence across launches.

## Works With USB Screen Stream

This tool can be used together with [usb-screen-stream](https://github.com/LexZeon/usb-screen-stream). For example, use usb-screen-stream to mirror a USB-connected phone or other device screen to the PC, then select that streamed window or region in OSR6 Realtime Screen TCode for realtime TCode output.

## First Use

For hardware use, read `Quick_Start.md` first. Before your first real session, use Measurement Mode to save comfortable safe upper and lower limits. These limits are stored locally. If the app works normally next time, you do not need to restore defaults again.

For preview without hardware, set output to `Log only`, click `Show Preview`, then start realtime output and select the screen region. The app will show the curve and preview without driving a device.

## Privacy

This is a local desktop tool. Screen capture and analysis run locally on your computer. The app does not upload your screen frames.

## AI/Vibe Coding Note

This project was built with AI-assisted vibe coding. It is shared directly as a practical OSR6 realtime screen-to-TCode tool, with rough edges expected and improvements welcome.

## Acknowledgements

This project learned from public open-source work around OSR/TCode tooling, realtime visual analysis, funscript generation, and simulator-style preview ideas, including projects such as FunGen, PoseFunscripter, and nb-3d-simulator. Please contact the maintainer if an acknowledgement or license notice should be corrected.

## Contact

For infringement concerns, license corrections, suggestions, or collaboration: aivnailedeng@gmail.com

---

# OSR6 实时读屏脚本输出工具

**OSR6 Realtime Screen TCode** 是一个 Windows 软件，可以实时读取你框选的屏幕区域，把画面运动转换成 TCode，并通过 USB 串口或 BLE 输出给 OSR/SR6/OSR6 兼容设备。也可以不连接设备先预览输出，或者录制/导出 `.funscript`。

> **成年人使用提示：本项目面向成年人使用，未成年禁止入内。**
>
> **六轴模式重要警告：六轴只建议在光线好、主体清晰、框选区域干净的画面里使用。** 画面太暗、主体不清楚、无关运动太多或画面不稳定时，请先使用 `L0 Only` 或 `Log only` 预览。

当前版本：`1.0.2`

## 下载

- Windows 免安装包：`OSR6-Realtime-Screen-v1.0.2-Windows.zip`
- 源码包：`osr-screen-tcode-source-v1.0.2.zip`
- 英文简易教程：`Quick_Start.md`
- 中文简易教程：`简易教程.md`
- 英文完整手册：`User_Manual_EN.md`
- 中文完整手册：`用户使用手册.md`

请先完整解压 Windows 压缩包，再运行软件。不要直接在压缩包预览窗口里双击 exe。

## 从源码运行

在 Windows 上 clone 仓库后，双击 `Start.cmd` 或 `Start-Source.cmd`。它会自动创建本地 `.venv`、安装 Python 依赖，并从 `src` 启动软件。

## 主要功能

- 实时框选屏幕区域并分析画面运动。
- 通过 USB 串口或 BLE UART 输出 TCode。
- 支持 `L0 Only` 和 `Six Axis`。
- 推荐使用低延迟的混合分析模式。
- 可选 Pose 辅助分析，适合完整人物/舞蹈画面。
- 支持只监听声音的节奏模式。
- 支持每轴上下限、总行程倍率、预设、平滑、限速、死区、活动门控等调试项。
- 测量模式可以手动遥控并保存本地安全上限/下限。
- 可查看实时脚本曲线和基于最终限制后输出的 3D 预览。
- 所有主要设置会保存到本地，下次打开继续使用。

## 可联动 USB Screen Stream

本工具也可以和 [usb-screen-stream](https://github.com/LexZeon/usb-screen-stream) 搭配使用。比如先用 usb-screen-stream 把 USB 连接的手机或其他设备画面投到电脑上，再在本工具里框选该窗口或区域进行实时 TCode 输出。

## 第一次使用

有设备请先看 `简易教程.md`。第一次正式使用前，建议先用测量模式保存适合自己的安全上限/下限。上下限会保存在本地。下次如果能正常输出脚本，就不用再恢复默认设置。

没有设备想先预览，可以把输出设为 `Log only`，点击 `Show Preview`，再开始实时输出并框选屏幕区域。这样只显示曲线和预览，不会驱动机器。

## 隐私

这是本地桌面工具。屏幕捕获和分析都在你的电脑本地运行，软件不会上传画面。

## AI / Vibe Coding 声明

本项目是 AI 辅助 vibe coding 做出来的实用工具。欢迎改进，也欢迎反馈问题。

## 鸣谢

本项目参考和学习了公开开源社区里 OSR/TCode、实时视觉分析、funscript 生成和模拟预览相关思路，包括 FunGen、PoseFunscripter、nb-3d-simulator 等项目。如有鸣谢或许可证信息需要修正，请联系维护者。

## 联系

侵权、许可证修正、建议或合作请联系：aivnailedeng@gmail.com
