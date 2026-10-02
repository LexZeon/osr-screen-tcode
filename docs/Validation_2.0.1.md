# 2.0.1 — Resizable controls on high-DPI displays / 高 DPI 控制区布局修复

## English

The 2.0.0 control sidebar had a fixed pixel width while its text and widgets grew with display scaling. Enlarging the main window only enlarged the preview, leaving controls clipped. Version 2.0.1 measures the controls at their natural size and provides a draggable divider. This is a layout fix; analysis, capture coordinates, output calculations and the two-second continuation limit are unchanged.

### Changes

- `src/osr_screen_tcode/ui_layout.py`: initial window and pane sizing use content dimensions, display scale and the launching monitor's work area. The control surface retains its full requested width instead of clipping its children. Vertical scrolling and an automatic horizontal scrollbar keep overflow reachable when the window or pane is narrow.
- The control pane's width is saved in device-independent units. Restoring defaults clears that preference and fits the controls again. Tab navigation brings an off-screen focused control into view. Mouse-wheel scrolling over controls does not accidentally change combobox selections; Shift+wheel scrolls horizontally.
- `src/osr_screen_tcode/app.py`: integrates the panes and bilingual guidance, saves/restores the width, and scales the output-monitor canvas spacing and labels. Resizing also repaints the six-axis display while output is stopped.
- `tests/test_ui_layout.py` and `tests/test_app_layout.py`: cover overflow, focus, wheel routing, resize/reset/persistence, scaled startup bounds and real application layout. All application checks isolate personal settings.
- The old 2.0.0 release, tags, packages and archive remain intact. The independent Lab retains its existing version. No analysis or hardware-output feature is introduced.

### Final verification

- Isolated main suite: **435 tests passed in 814.436 seconds**. A test-only Tk geometry adjustment placed test windows on the ASUS display; personal settings were unchanged.
- Independent Lab: **38 tests passed in 0.394 seconds**. The simulator final-command stream check passed.
- PyInstaller **6.22.2** produced a fresh build, audited at **1,148 files / 277,467,311 bytes** before release-document assembly. Its actual frozen `--runtime-check` passed with version **2.0.1**, dependency imports, embedded-simulator resources and CPU inference; settings were unchanged.
- Actual source `Start.cmd` and the rebuilt EXE passed English/Chinese startup. Source `Pose-Preview-Lab/Start.cmd --smoke` and the EXE's `--preview-lab --smoke` both passed. Main and Lab personal-settings fingerprints were unchanged. These are pre-assembly startup checks.

Final ZIP extraction and actual `Start.cmd` checks occur after the release commit; their results are recorded in the [GitHub release body](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.1) and local archive records. The two archives identify their corresponding source commit in `RELEASE_INFO.json`. Earlier development checks below do not substitute for final artifact verification.

Native inspection on an ASUS PA279 portrait display (2160 × 3840, Windows scaling 150%) with the application rendered at 200% confirmed complete English measurement buttons and axis-limit controls; dragging the divider with the mouse worked. An earlier Chinese 200% inspection confirmed the sidebar controls fitted, before the subsequent output-chart spacing correction. These are local display checks, not a reproduction of the reporter's exact 4K configuration.

Development checks and corrections:

| Check | Result and follow-up |
| --- | --- |
| Initial 32 focused checks | Two failures: one test omitted the initial-fit call; the other exposed a real overflow-shrink bug when content was scrolled out of view. Both were corrected. |
| Follow-up 11 checks | Eight subtest errors came from a test parsing an empty `wraplength` value. The test was corrected. |
| 11 checks, 28.766 s | Passed before the output-chart spacing changes. |
| 11 checks, 41.342 s | Passed before the final legend spacing adjustment. |
| ASUS 11 checks, 47.749 s | One failure: Windows mixed-DPI non-client adjustment produced a physical width of 1762 instead of the test's exact 1768. The assertion was replaced with monitor-bounds checks and is covered by the final passing suite; this earlier run is not a pass. |

### Limits

The reporter's original display setup is unavailable. Very narrow windows may need horizontal scrolling even with the new automatic sizing. Local high-DPI and mixed-monitor checks do not establish every Windows scaling configuration. Real hardware, robot-arm mapping, inverse kinematics, collision handling and feedback remain unverified. Models, optional GPU downloads, personal settings, logs and caches must not be included in the release archives.

## 中文

2.0.0 的控制栏使用固定像素宽度，但文字和控件会随显示缩放变大；放大主窗口只会扩大预览，导致控制项仍被裁切。2.0.1 改为按控件实际需要的宽度布局，并加入可拖动分隔栏。本次只修复布局，分析、采集坐标、输出计算与两秒接续上限不变。

### 改动

- `src/osr_screen_tcode/ui_layout.py`：初始窗口及栏宽结合内容尺寸、显示缩放和启动所在屏幕的工作区计算。控制内容保留完整宽度，不再强制裁切子控件；窗口或控制栏较窄时，纵向滚动和自动出现的横向滚动条确保内容可访问。
- 手动栏宽按设备无关单位保存；恢复默认会清除手动栏宽并重新适配。Tab 切换焦点会自动滚动到对应控件。控件上滚轮滚动不会误改下拉选项，Shift＋滚轮可横向滚动。
- `src/osr_screen_tcode/app.py`：接入分栏和中英文提示，保存／恢复栏宽，同步输出监视画布的间距与文字缩放；停止输出时调整窗口也会重画六轴显示。
- `tests/test_ui_layout.py`、`tests/test_app_layout.py`：覆盖溢出、焦点、滚轮路由、调整／重置／保存、缩放后的启动边界和实际程序布局。程序检查均隔离个人设置。
- 保留旧 2.0.0 发布、标签、运行包和归档，独立 Lab 沿用现有版本；没有新增分析或硬件输出功能。

### 最终验证

- 隔离主程序完整 **435 项通过，814.436 秒**。仅测试使用的 Tk 几何调整将测试窗口放在 ASUS 显示器，个人设置未变。
- 独立 Lab **38 项通过，0.394 秒**；模拟器最终指令流检查通过。
- 使用 PyInstaller **6.22.2** 在新目录构建，发布文档装配前审查 **1,148 个文件／277,467,311 字节**。实际打包程序的 `--runtime-check` 通过，确认版本 **2.0.1**、依赖导入、内嵌模拟器资源及 CPU 推理，设置未变。
- 实际源码 `Start.cmd` 与重新构建的 exe 中英文启动通过；源码 `Pose-Preview-Lab/Start.cmd --smoke` 和 exe 的 `--preview-lab --smoke` 均通过。主程序与 Lab 个人设置指纹未变。这些结果对应压缩包装配前的启动检查。

最终 ZIP 的重新解压及实际 `Start.cmd` 检查在发布提交后进行，结果记录在 [GitHub 发布正文](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.1)及本地归档记录中。两个压缩包通过 `RELEASE_INFO.json` 标识对应的源码提交。下述开发期检查不能替代最终产物验证。

在 ASUS PA279 竖屏（2160 × 3840、Windows 缩放 150%）以程序 200% 渲染进行原生窗口检查，英文测量按钮和轴上下限完整可见，鼠标拖动分隔栏通过。较早的中文 200% 检查确认控制栏内容适配，但发生在后续输出图表间距修正之前。这些是本机显示检查，并非原报告者完全相同的 4K 环境复现。

开发检查及修正：

| 检查 | 结果与处理 |
| --- | --- |
| 初轮 32 项针对性检查 | 两项失败：一项测试漏调初始适配；另一项发现内容滚出可视区后缩小无法更新的真实问题，均已修正。 |
| 后续 11 项 | 八个子测试错误来自测试解析空 `wraplength`，已修正测试。 |
| 11 项，28.766 秒 | 通过，早于输出图表间距修改。 |
| 11 项，41.342 秒 | 通过，早于最终图例间距调整。 |
| ASUS 11 项，47.749 秒 | 一项失败：Windows 混合 DPI 非客户区调整使实际宽度为 1762，而断言要求精确 1768；已改为屏幕工作区边界检查，并纳入最终通过的完整测试，此早期轮次不计为通过。 |

### 边界

尚无原报告者的显示环境；很窄的窗口仍可能需要横向滚动。本机高 DPI／混合显示器检查不能代表全部 Windows 缩放组合。真实设备、机械臂映射、逆运动学、碰撞检测和反馈仍未验证。发布包不得包含模型、可选 GPU 下载、个人设置、日志或缓存。
