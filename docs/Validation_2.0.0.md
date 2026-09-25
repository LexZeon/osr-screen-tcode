# 2.0.0 — Windows packages and per-version archives / Windows 运行包与逐版留样

## English

Official release 2.0.0 uses test.25 as its analysis/output baseline and incorporates the verified portable Windows support. The application version and package metadata are both `2.0.0`. Analysis/output algorithms, settings defaults and the two-second continuation limit are unchanged. The old test.25 tag is not rewritten, and new binaries do not replace older release assets. Test.26 was a provisional release-preparation name, not a separately published version.

### Usage

- For normal use, download the release's **Windows.zip**, extract the complete folder, and double-click its `Start.cmd` or `SR6-OSR6-Realtime-Screen-TCode.exe`. No separate Python installation is required. Keep `_internal` and all supporting files together.
- `Pose-Preview-Lab/Start.cmd` uses the same EXE to open the independent visual preview, without hardware output.
- The separately attached `Start.cmd` is a spare launcher, not a replacement for the Windows ZIP.
- Developers can use the matching **Source.zip**; running from source still requires Python 3.10+. In both archives, `RELEASE_INFO.json` records the corresponding commit and `FILES_SHA256SUMS.txt` records internal file checksums. The release directory includes `SHA256SUMS.txt`.

### Changed files

- `SR6-OSR6-Realtime-Screen-TCode.spec`: collects the Lab's four public modules, soundcard loopback-audio headers and other required resources. It does not collect models or downloadable GPU libraries.
- `src/osr_screen_tcode/__main__.py` and `preview_lab_launcher.py`: dispatch the independent preview from the packaged application. They do not restore the removed main-window button or pass device/main-application settings to the Lab.
- `Pose-Preview-Lab/preview.py`: uses a separate user-settings directory and correct model-discovery locations when packaged. Existing local-settings behavior remains for source startup.
- `runtime_check.py`: provides an optional packaged-runtime check with isolated settings and Log only; it does not connect hardware or download dependencies.
- `tools/build_release.py`: builds source archives only from committed files in a clean Git checkout, includes Lab/Start.md, creates separate version outputs and refuses to overwrite old packages. It excludes models, downloadable GPU libraries, caches, logs, settings and personal paths while preserving licenses.
- `tools/Start-Portable.cmd` and `tools/README-Portable.md`: provide bilingual extraction/startup instructions so that the source launcher is not mistaken for a Python-free application.

### Final 2.0.0 validation

- Final isolated source suite: **424 tests passed in 461.808 seconds**, including license collection and official-version manifest checks. Lab: **38 passed in 0.341 seconds**. The simulator final-command check passed.
- Source Start.cmd and the rebuilt **2.0.0 EXE** passed English/Chinese startup and independent Lab startup. The EXE passed dependency/resource checks, CPU inference and an external RTM Pose 2D model. Main and Lab settings were unchanged; no device was connected or dependency installed.
- Before documentation/legal assembly: **1,148 files / 277,459,368 bytes** audited. Lab and simulator matched source. EXE SHA-256: `88f67638a21b04f4d55e701642ddb5ec9aa5c75d5014e1b93edffd55e17d4e7f`. Compared with test.25, the other 57 original source files are unchanged; production changes are version and portable-startup support.
- These results cover source and the frozen executable. Final ZIP extraction/startup and public asset hashes are recorded on the [2.0.0 release page](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0) after clean-commit assembly. Both archives identify that commit in RELEASE_INFO.json; earlier preparation packages must not substitute for final artifacts.

### Earlier release-preparation validation

- Isolated full main suite: **423 passed in 537.951 seconds**. The later license-file collection correction has **12 packaging tests passed in 2.128 seconds**, including preservation of ONNX Runtime third-party notices and NumPy's nested license. The full run preceded that packaging-only correction; these are separate results.
- Independent Lab: **38 passed in 0.330 seconds**. The simulator final-command stream check passed.
- Actual source `Start.cmd` checks passed in English and Chinese; the source Lab launcher also passed. Actual PyInstaller EXE startup passed in both languages, and `--preview-lab --smoke` passed. Personal main and Lab settings were unchanged.
- Frozen dependency/resource checks passed, including audio headers, Windows BLE imports, embedded simulator and actual CPU inference. An existing external RTM Pose 2D model ran on CPU; the model was not bundled. English Pose Log-only capture produced **241 statistics updates in 8 seconds**, and Chinese default Hybrid v2 Log-only capture produced **1,157 updates in 30 seconds**; both stopped normally with worker shutdown and unchanged settings. The Chinese packaged window was visually inspected. These desktop checks do not establish tracking accuracy on arbitrary footage.
- The PyInstaller output audit checked **1,148 files / 277,459,377 bytes** before assembly of documentation and legal notices. Lab modules and embedded simulator matched the source. Publication must use the final fresh-extraction checks and matching asset hashes recorded with the release; a source test is not proof that an arbitrary ZIP works.

The first 23 targeted checks had 22 passes and one failure: a test hard-coded LF line endings for Windows, causing the assertion for a fully copied document to fail. The follow-up compares the actual source-file bytes. All 11 packaging-only checks then passed (2.001 seconds), without weakening the content-completeness requirement.

### Archive rules

Retain matching source and Windows archives, checksum lists and release notes separately for each version. Historical versions are copied for preservation without deleting originals or rewriting tags. Label missing content in incomplete early development snapshots; do not present them as complete releases or fabricate a version's EXE. Machine-specific archive paths belong only in the local handoff, never in public source.

### Limits

Models and optional GPU runtimes require separate downloads. Bundling the basic CPU environment does not establish validation of every GPU configuration. The application is unsigned. Physical hardware, robot-arm mapping, inverse kinematics, collision handling and feedback remain unverified. Image analysis retains test.25's limitations: strong blur, occlusion, similar-looking cuts and longer cycles can still lose references; estimates continue for at most two seconds.

## 中文

正式版 2.0.0 以 test.25 为分析与输出基线，纳入经过验证的 Windows 便携运行支持。版本和元数据均为 `2.0.0`。分析／输出算法、默认设置和两秒接续上限不变。不改写旧 test.25 标签，不以新的程序覆盖旧版附件。test.26 只是前期发布准备中的临时名称，没有单独发布。

### 使用

- 普通用户下载 Release 中的 **Windows.zip**，完整解压后双击包内 `Start.cmd` 或 `SR6-OSR6-Realtime-Screen-TCode.exe`，不需要安装 Python。必须保留 `_internal` 与其他配套文件。
- `Pose-Preview-Lab/Start.cmd` 使用同一 exe 打开独立视觉预览，无硬件输出。
- Release 单独附的 `Start.cmd` 是备用启动器，不能单独替代 Windows ZIP。
- 开发者使用同版本 **Source.zip**，源码启动仍需 Python 3.10+。两个包中的 `RELEASE_INFO.json` 记录对应提交，`FILES_SHA256SUMS.txt` 记录内部文件校验；发布目录有 `SHA256SUMS.txt`。

### 改动位置

- `SR6-OSR6-Realtime-Screen-TCode.spec`：收集 Lab 四个公开模块、soundcard 音频回环头文件和现有必需资源，不收模型或下载 GPU 库。
- `src/osr_screen_tcode/__main__.py`、`preview_lab_launcher.py`：打包程序独立预览分派，不恢复已经移除的主界面旧按钮；不向 Lab 传设备或主程序设置。
- `Pose-Preview-Lab/preview.py`：打包时使用独立用户设置目录和正确的模型发现位置；源码原有本地设置行为保留。
- `runtime_check.py`：可选打包运行自检，隔离设置、只用 Log only，不连接硬件，不下载依赖。
- `tools/build_release.py`：仅已提交、干净 Git 文件可组成源码包；补全 Lab/Start.md，独立版本输出，拒绝覆盖旧包。排除模型、可下载 GPU 库、缓存、日志、设置及个人路径，保留许可证。
- `tools/Start-Portable.cmd`、`tools/README-Portable.md`：双语解压和启动说明，避免把源码启动器当成免 Python 程序。

### 最终 2.0.0 验证

- 正式版本隔离完整 **424 项通过，461.808 秒**，含许可证收集及正式版本清单核对；Lab **38 项通过，0.341 秒**，模拟器最终指令检查通过。
- 实际源码 Start.cmd 与重新构建的 **2.0.0 exe** 中英文启动、独立 Lab 启动通过；exe 的依赖／资源、CPU 推理及外部 RTM Pose 2D 模型执行通过。主程序和 Lab 个人设置未变，未连接设备或安装依赖。
- 文档／法律声明装配前，运行载荷 **1,148 个文件／277,459,368 字节**通过审查；Lab、模拟器与源码一致。exe SHA-256：`88f67638a21b04f4d55e701642ddb5ec9aa5c75d5014e1b93edffd55e17d4e7f`。相比 test.25，其余原有 57 个源码文件完全未改，生产代码只涉及版本及便携启动支持。
- 上述验证覆盖源码与打包 exe。干净提交装配后的最终 ZIP 解压／启动及公开附件哈希记录在 [2.0.0 发布页](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0)。两个包通过 RELEASE_INFO.json 关联对应提交，不以早期准备包替代正式产物。

### 前期发布准备验证

- 隔离主程序完整 **423 项通过，537.951 秒**。随后许可证文件收集修正的 **12 项打包测试通过，2.128 秒**，覆盖 ONNX Runtime 第三方声明和 NumPy 深层许可证。完整检查早于这项纯打包修正，两组结果分开记录。
- 独立 Lab **38 项通过，0.330 秒**；模拟器最终指令流检查通过。
- 源码实际 `Start.cmd` 中英文启动、源码 Lab 启动通过；实际 PyInstaller exe 中英文启动及 `--preview-lab --smoke` 通过。主程序和 Lab 个人设置保持不变。
- 打包依赖／资源检查通过，包含音频头文件、Windows BLE 导入、内嵌模拟器及实际 CPU 推理。外部已有 RTM Pose 2D 模型实际 CPU 执行通过，模型未打包。英文 Pose Log only 读屏 **8 秒 241 次统计更新**；中文默认混合 v2 Log only **30 秒 1,157 次更新**，均正常停止及退出线程，设置未变。已查看中文打包窗口。这些桌面检查不能证明任意素材的识别准确率。
- 文档／法律声明装配前，PyInstaller 输出 **1,148 个文件／277,459,377 字节**通过内容审查；Lab 模块和模拟器与源码一致。发布以最终重新解压检查及附件哈希为准，结果随 Release 记录；源码测试不能代替实际 ZIP 验证。

初轮 23 项定向检查中 22 项通过，1 项测试把 Windows 换行硬编码为 LF，导致完整复制文档的断言失败；后续按实际源文件字节核对，11 项纯打包检查通过（2.001 秒），未放宽内容完整性要求。

### 归档规则

按版本独立保留配套源码和 Windows 包、校验清单、版本说明。旧版本只复制留样，不删除原件或重打标签。不完整的早期开发快照应单独标明缺失，不能冒充完整发布包或凭空构造某版 exe。本机归档路径只写入本地接手说明，不放进公开源码。

### 边界

模型与可选 GPU 运行库需要单独下载，不能把已打包基础 CPU 环境等同于完成所有 GPU 实机验证。应用没有数字签名。真实硬件、机械臂映射、逆运动学、碰撞检测及反馈仍未验证。画面识别沿用 test.25，强模糊、遮挡、相似切镜和较长周期仍可能失去参考；估算仍最多 2 秒。
