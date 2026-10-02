# SR6/OSR6 Realtime Screen TCode v2.0.1

## English

**High-DPI control-panel fix.** Controls now use their natural size, and the divider between controls and preview can be dragged. The control pane's width is saved across launches; restoring defaults returns to automatic sizing. On smaller windows, use the bottom horizontal scrollbar or Shift+wheel to reach wide controls. Tab navigation reveals focused controls, and scrolling over a combobox no longer changes its selection accidentally.

Startup sizing respects the monitor's work area. The output monitor also uses scaled spacing and repaints its axis display when resized. Analysis and final-output algorithms remain unchanged from 2.0.0; brief-loss estimates still continue for at most two seconds. Old release assets remain intact.

### Download and run

Download **Windows.zip**, extract the complete folder, then double-click its **Start.cmd** or **SR6-OSR6-Realtime-Screen-TCode.exe**. No separate Python installation is required. Keep `_internal` and all supporting files together. The separately attached `Start.cmd` is a spare launcher for that extracted folder, not a standalone application.

**Source.zip** contains the matching source and requires Python 3.10+ to run. `RELEASE_INFO.json` identifies the source commit, and `SHA256SUMS.txt` verifies the release files. The independent preview still starts through `Pose-Preview-Lab/Start.cmd`.

**Validation:** 435 isolated main tests and 38 Lab tests passed, along with the simulator final-command stream and frozen CPU/resource self-check. Actual source and rebuilt EXE startup passed in English and Chinese, including independent Lab startup; personal settings were unchanged. Native ASUS high-DPI checks confirmed complete controls and divider dragging; the reporter's original 4K setup has not been tested. Final ZIP extraction and actual `Start.cmd` results are recorded after the release commit in the [GitHub release body](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.1) and local archive records. See [validation details](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.1/docs/Validation_2.0.1.md).

Models and optional GPU runtimes are separate downloads. Physical hardware and robot-arm mapping remain unverified. Personal settings, logs and caches are excluded from release packages.

## 中文

**修复高 DPI 控制栏显示不全。** 控制项现在按实际尺寸布局，可以拖动控制栏与预览之间的分隔栏调整宽度。栏宽自动保存，恢复默认会重新自动适配。窗口较小时可用底部横向滚动条或 Shift＋滚轮访问较宽内容。Tab 切换会自动显示对应控件，在下拉框上滚动不会再误改选项。

启动窗口按所在显示器的工作区适配，输出监视的间距随缩放调整，改变尺寸时也会重画六轴显示。分析与最终输出算法沿用 2.0.0，短暂缺测估算仍最多两秒，旧版附件保留。

### 下载和运行

下载 **Windows.zip**，完整解压后双击包内 **Start.cmd** 或 **SR6-OSR6-Realtime-Screen-TCode.exe**，不需另装 Python。保留 `_internal` 和所有配套文件。单独附的 `Start.cmd` 只是解压目录内的备用启动器，不能单独运行整个软件。

**Source.zip** 为配套源码，源码启动需要 Python 3.10+。`RELEASE_INFO.json` 标识源码提交，`SHA256SUMS.txt` 用于校验下载文件。独立预览仍通过 `Pose-Preview-Lab/Start.cmd` 启动。

**验证：** 隔离主程序 435 项、Lab 38 项通过，模拟器最终指令流及打包程序 CPU／资源自检通过。实际源码与重新构建的 exe 中英文启动、独立 Lab 启动均通过，个人设置未变。本机 ASUS 高 DPI 检查确认控制项完整可见、分隔栏可拖动，尚未在原报告者的 4K 环境测试。发布提交之后的最终 ZIP 解压及实际 `Start.cmd` 结果记录在 [GitHub 发布正文](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.1)及本地归档记录中。详见[验证说明](https://github.com/LexZeon/osr-screen-tcode/blob/v2.0.1/docs/Validation_2.0.1.md)。

模型和可选 GPU 运行库另行下载。真实硬件与机械臂映射仍未验证；个人设置、日志与缓存不随发布包分发。
