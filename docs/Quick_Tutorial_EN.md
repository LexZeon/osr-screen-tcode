# Quick Tutorial — 2.0.0-test.26

**SR6/OSR6 Realtime Screen TCode** is a Windows screen/video analysis and TCode scripting experiment. This prerelease provides matching **Windows and source archives**. Download the **Windows.zip** asset for a bundled runtime; GitHub's automatic “Source code” ZIP/tar archives require Python. Older releases retain their original files.

## Run the Windows package

1. Open the [test.26 release](https://github.com/LexZeon/osr-screen-tcode/releases/tag/v2.0.0-test.26) and download the asset whose name ends in **Windows.zip**.
2. Extract the **complete folder**, then double-click its `Start.cmd` or `SR6-OSR6-Realtime-Screen-TCode.exe`. No separate Python installation is required. Keep `_internal` and all supporting files beside the executable; do not run inside the ZIP or move the EXE alone.
3. Confirm the window shows **2.0.0-test.26** and select **Log only** before starting analysis. Existing settings are retained; **Restore defaults** is optional and replaces your saved preferences.
4. For the independent visual preview, double-click `Pose-Preview-Lab/Start.cmd` in the extracted folder. It uses the bundled runtime and does not send device commands.

The separately attached `Start.cmd` is a spare launcher for the extracted application folder, not a self-contained application. Matching Windows/source archives include commit manifests and file checksums; use the release's `SHA256SUMS.txt` to verify downloads. See the [portable startup guide](../tools/README-Portable.md).

## Start from source

1. Install Python **3.10 or newer** with Tkinter support. The standard Windows Python installer includes Tkinter.
2. Download this prerelease's source archive and extract the entire folder, or check out its tag. Keep `src`, `Pose-Preview-Lab`, the launchers and requirements together.
3. Double-click the root [Start.cmd](../Start.cmd). On a fresh checkout it creates this folder's `.venv` and installs dependencies, so the first start needs internet access. It may reuse an existing compatible environment; a shared neighboring environment is read-only and is never upgraded by the launcher.
4. Confirm the window shows **2.0.0-test.26**. [Start.md](../Start.md) is the operating guide, not an executable.
5. Select **Log only** before starting analysis. Existing settings are retained; **Restore defaults** is optional and replaces your saved preferences.

Models and optional GPU components are downloaded separately through the application's controls. Hybrid v2 without RTM rotation assistance does not require a pose model. RTM Pose 2D and RTM rotation assistance need a compatible local model; model download and optional GPU setup are described in the [README](../README.md). No trained models or downloadable GPU runtimes are included in either archive.

## Check analysis and output

1. Choose Screen or video input and select L0-only or six-axis output. The default analysis is **Hybrid v2 (Recommended Non-Dance)** with **Fused reference** and RTM rotation assistance off.
2. For screen input, stop analysis before choosing a region. Drag over the desired area, then choose **Use this region** or press Enter. The picker uses physical screen pixels across displays, including negative coordinates. Display gaps are black; reselect after changing the display layout or resolution.
3. Start realtime output in **Log only**. The default **Output Monitor** tab shows commands; **Analysis Preview** shows the sampled frame, subject tracking and analysis values. The default processing longest edge is 640.
4. **Show preview** opens the integrated simulator. It receives final commands after output transforms, limits and timing; it is not physical-device feedback.
5. Stop before changing the analysis method, input or capture region. Use recording or video export to save scripts as described in [Start.md](../Start.md).

The analysis choices serve different inputs:

- **Full/Half Travel** uses v2 evidence to choose quarter, half or full cosine-shaped strokes and adapt their rhythm. Optional RTM 2D rotation assistance is available; L1/L2 stay centered.
- **RTM Pose 2D** is recommended for dance and offers paired raw/processed skeletons, stabilization and configurable Pose L0 behavior. RTM Pose 3D is not available in this OSR version.
- **Hybrid 1** is recommended for large planar motion and retains its original L0 analysis core.
- **Hybrid v2** tracks a subject and separates supported camera motion. Its continuous three-axis frame uses horizontal/vertical/image-scale proxies, with optional RTM 2D rotations. Image scale is not physical depth.

## Read the markers

- **A** and the yellow subject box mark a measured subject reference. The colored axes and green samples show the motion evidence used by v2.
- **T?** is an independently tracked object candidate, not confirmed contact. A reliable origin-to-target distance can guide L0: farther is higher and estimated arrival is bottom before final output gains.
- **V?** is an assumed endpoint inferred from confirmed visible reciprocation when no reliable object is available. It is not an observed object or an actual arrival percentage.
- Dashed **A?** boxes and axes indicate weak tracking or position estimates. They are separate from measured observations.

The default fused reference can bridge brief tracking loss. A previously confirmed rhythm continues for **at most 2 seconds**, slowing over the last 0.5 seconds. Without a confirmed rhythm, stable recent velocity permits only a **0.3-second / 15% normalized-travel** decelerating bridge before output gains; it cannot invent a reversal. A single detection flash does not renew the loss deadline. Explicit pauses, cuts and reference resets end the old pattern; stable recovery resumes from the current output. Quarter/half/full mode only continues an already confirmed stroke.

The five intensity presets affect final realtime/recorded/exported output, not analysis. **Slow near limits** defaults on with a 10% zone and changes arrival time, not target position; exported scripts can therefore run longer than the original video.

## Limits and further reading

Start with Log only. Existing SR6/OSR6 serial/BLE TCode interfaces remain, but robot-arm joint mapping, inverse kinematics, collision handling and physical feedback are not implemented or verified. A simulator or centering command does not establish hardware safety or compatibility. Blur, occlusion, similar-looking cuts and long loss can still cause tracking to stop.

See the [test.26 packaging and validation report](Test_2.0.0_test26.md), [test.25 analysis limitations](Test_2.0.0_test25.md), [README](../README.md), [license](../LICENSE) and [third-party notices](../THIRD_PARTY_NOTICES.md). Test.26 retains test.25's analysis/output behavior. The application is unsigned; bundling the CPU runtime does not verify every GPU configuration or physical hardware. The standalone [Pose Preview Lab](../Pose-Preview-Lab/Start.md) remains available for comparison and never sends device commands.
