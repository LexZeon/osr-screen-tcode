# SR6/OSR6 Realtime Screen TCode — Feature Guide

## English

This guide describes the user functions retained in **2.1.0**. The release reorganizes existing program responsibilities; it does not introduce a new analysis model, a longer prediction window, or new hardware mapping. Defaults below describe a fresh configuration or **Reset all defaults**. Previously saved choices can differ.

### 1. Start and understand the three kinds of results

For the Windows portable package, extract the complete folder and run **Start.cmd** or the EXE. Keep `_internal` and the accompanying folders beside the EXE. Source startup uses the repository's **Start.cmd** and requires Python 3.10 or later. **Start.md** is a guide, not a launcher. Models and optional GPU runtimes are separate downloads.

1. **Analysis observations** are image measurements: skeleton points, motion direction, subject/background support and image scale. They are shown in Analysis Preview.
2. **Script positions** are normalized analysis output after the applicable Pose processing, output curve, travel multipliers and inversion. Recording/export can also extend script time near endpoints.
3. **Final live commands** apply device-axis limits, live speed/activity/startup handling and applicable axis coupling. Output Monitor and the simulator display these TCode commands.

Recorded funscripts are not a byte-for-byte copy of the live command stream. Device limits, live per-update speed caps, live idle/endpoint handling and TCode-only coupling are not all written into the normalized script. A smooth chart is not proof of accurate recognition or physical movement.

Begin with **Log only** to inspect results without sending commands to hardware. The supported transport is existing SR6/OSR6 TCode over serial or BLE UART. Image scale is not measured physical depth; target candidates do not confirm contact. Robot-arm joint mapping, inverse kinematics, collision checking and physical position feedback have not been implemented or verified.

### 2. Inputs, region and processing size

Open **More settings → Input source**. Choose one input; audio-only input does not run visual analysis.

| Function and entry | What it does | Settings and limits |
| --- | --- | --- |
| **Screen** | Captures fresh frames from the selected desktop rectangle for live analysis. | Default input. Stop before changing its region. Keep the application's own moving windows outside the selected content. |
| **Video File → Select** | Opens a local video for live, playback-timed analysis. | Reading a video does not mix its soundtrack into visual output. Processing that cannot keep up can skip old playback frames. Offline export is a separate action. |
| **Audio Only** | Listens to system output or a selected input device and generates L0. | Does not read screen images, detect a person or infer motion direction from the scene. |
| **Select screen region** | Opens a dimmed desktop snapshot with a bright selected area, teal border, monitor labels and exact coordinates. | Enter confirms, R reselects, Esc cancels. The snapshot stays in memory; live analysis captures new frames after confirmation. Cancellation keeps the old region. |
| **X / Y / Width / Height** | Defines the same capture rectangle numerically. | Physical desktop pixels, including negative origins for displays above/left of the primary display. Mixed DPI, portrait displays and cross-display rectangles use this same convention. Invalid/out-of-desktop or gap-only rectangles are rejected. Gaps between displays are black. |
| **Capture FPS** | Sets the target rate of screen capture/analysis. | Default 45; 1–120. Increasing it uses more resources and does not create extra source-video frames. Actual rates depend on capture, model and processing cost. |
| **Analysis Preview → Processing max edge** | Resizes the sampled frame before Pose/v2 processing. | 320 / 480 / 640 / 960 / 1280; default 640. Preserves the full aspect ratio and does not enlarge small frames. Changing it rebuilds the reference. The RTM model still has a fixed input size. This control is disabled for the older analysis routes. |
| **Advanced → Compression / Latency** | Positive values shrink frames in the older main analysis route; this setting also adjusts some short prediction terms in the existing Pose-derived motion geometry. | Default 0; range −5…5. Nonpositive values preserve frame detail in the older route. Pose/v2 frame size is controlled by Processing max edge; the fast-v1 Pose helper receives that same sampled frame without a separate compression resize. This is not a global Pose prediction-duration control, an end-to-end latency measurement or a guarantee that −5 is more accurate than 0. |

**Capture** dimensions describe the pixels read from the desktop. **Analysis size** describes the processing image. Preview scaling/black margins only affect display. A very thin region remains displayable but may have too few useful features to analyze. If the monitor layout or resolution changes during capture, the program stops; reselect before restarting.

Audio's **Audio analysis** choices are **Audio Level** (smoothed volume to position), **Dynamic Accent** (volume response above center, with rising volume contributing to activity) and **Beat Pulse** (a decaying pulse triggered by rising volume). These are not note recognition or validated beat annotation. The audio device defaults to **System Output** (loopback); choose Default Input or a listed input device when appropriate, and **Refresh** to rescan. Audio gain defaults to **2.5**, UI range **0.2–8**; threshold **0.02**, range **0–0.35**; audio smoothing **0.25**, range **0–0.95**. More smoothing is steadier and slower. These controls change audio L0 analysis; subsequent travel/output handling still applies.

### 3. Choose an analysis mode and axes

Use **Analysis mode** in the sidebar, Analysis Preview or start-confirmation dialog. The list order is not the default selection: **Hybrid Analysis v2** is the fresh default. Mode selection changes analysis; **L0 Only / Six Axis** selects the output axes.

| Mode | Meaning and output | Model/default/limit |
| --- | --- | --- |
| **Hybrid Analysis v2 (Recommended - Non-Dance)** | Tracks one persistent moving subject using distributed image support, separately checks background/camera motion and fits a continuous motion frame from horizontal, vertical and image-scale changes. L0 follows the main direction; L1/L2 use transverse directions. Rotation is an image proxy unless RTM rotation assistance is enabled. | No model required. Default mode. Without RTM, secondary axes follow confirmed significant motion/reversals with smoothing; this does not filter L0. Background evidence can still be insufficient, causing hold or bounded continuity. |
| **Full/Half Travel (Hybrid Analysis)** | Shares v2 subject/camera/reference analysis, then forms a cosine L0 cycle from confirmed reciprocal amplitude and cadence: bottom→quarter→bottom, bottom→middle→bottom or bottom→top→bottom. Cadence adapts gradually. | No model required. The quarter/half/full class is automatic, not a manually chosen constant oscillator. L1/L2 stay centered. Optional RTM rotations and the same v2 model assistance remain available. Final travel settings can change the resulting amplitude. |
| **RTM Pose 2D (Recommended - Dance)** | Uses 2D body keypoints to derive L0 and, in Six Axis mode, body-based auxiliary signals. Displays paired raw/processed skeletons from the same sampled frame. | Requires a supported local 256×192 RTMPose ONNX model. GPU defaults off. This is image-space analysis, not 3D joint reconstruction. RTM Pose 3D has been removed. |
| **Hybrid Analysis (Recommended - Large Planar Motion), v1** | Retains the original regional optical-flow L0 route for large planar movement. | No model required; **L0 only**, even if Six Axis is selected. Does not inherit v2 models, fused-reference tracking or v2 rotation assistance. |
| **Stroke Phase (Beta)** | Uses confirmed image-flow direction to approach the corresponding L0 endpoint. | Older experimental route; not v2's subject/target/cadence pipeline. |
| **Motion Center (Beta)** | Uses the vertical center of changed image areas for L0. | Unrelated movement and camera changes can affect it. |
| **Optical Flow (Beta)** | Accumulates vertical image flow into L0. | Image flow can drift or include camera movement. |
| **Hybrid Motion (Beta)** | Combines changed-area center and accumulated image flow. | Separate older experiment; not Hybrid v1/v2. |
| **Activity Pulse (Beta)** | Makes a repeating triangular L0 pulse from image activity. | A synthetic response to activity, not a measured subject trajectory or confirmed reciprocal rhythm. |

The fresh output mode is **L0 Only**. **Six Axis** uses L0/L1/L2/R0/R1/R2 when the selected route supplies them. These names are TCode axes; the preview's apparent 3D motion frame does not establish physical robot-arm axes. Selecting Six Axis does not make Audio Only a six-axis motion detector or make v1 supply auxiliary movement.

### 4. V2 references, target markers and brief-loss continuity

In v2 or Full/Half Travel, use **Analysis Preview → v2 L0 reference** (also in the start dialog). This changes how image evidence produces analysis L0, before final user travel gains.

| Reference | Meaning |
| --- | --- |
| **Fused reference (default)** | Aligns the motion axis, confirmed stroke center/phase and reliable interaction evidence. Once near/far polarity is confirmed, away is higher L0 and toward is lower L0. A reliable independently tracked target can supply a distance/reach relationship; otherwise visible reciprocal motion remains usable. |
| **3D motion axis** | Uses displacement along the learned image-motion direction. The third component is image scale, not true Z distance. |
| **Stroke center** | Uses the confirmed reciprocal center/phase as a reference. |
| **Interaction candidate (experimental)** | Uses available geometric interaction evidence. It does not verify the identity of a contacted object or actual contact. |

Source changes continue from the current output instead of jumping to another source's accumulated position. **Reset reference** clears old calibration/history; use it after a wrong direction/reference or a material scene change.

Read the preview markers as follows:

- **Yellow subject region / A:** the tracked subject region and persistent image anchor. Green sample groups support its measured motion; blue points support the independently validated background.
- **T? (orange):** an independent object-boundary candidate tracked using its own image features. Any reach percentage is an image-based estimate. Estimated 100% corresponds to analysis L0 bottom before gains; it is not verified physical contact.
- **V?:** an assumed endpoint/object inferred from confirmed subject reciprocation when a reliable object is absent. It is not an observed object and supplies no actual-contact percentage.
- **E? / S? / P? (gray):** trajectory endpoint, local expansion center or geometric convergence/interaction reference. They are not confirmed contact targets.
- **A? / pale dashed box and axes:** weak tracking or position estimation, distinguished from actual observations. An offscreen target arrow indicates direction only, not an arrival point at the screen edge.

With the default fused reference, short loss first tries supported weak subject tracking, then an already confirmed rhythm. Missing-data estimation lasts **at most 2 seconds**, with the last **0.5 seconds** slowing to a hold. If no reciprocal rhythm was confirmed, a recent stable velocity can bridge for only **0.3 seconds**, within **15% travel before gains**, without inventing a reversal. Single-frame reacquisition flashes do not restart the deadline. Stable measured recovery reconnects from current output.

Pauses, cuts, stop, input/size changes and reference reset clear old continuity. Full/Half Travel continues only an already established travel class; it cannot start a new cycle from missing evidence. The individual references retain their own semantics and are not equivalent to the full fused continuity workflow. Strong blur, long occlusion, similar-looking cuts and unavailable independent background remain limitations.

### 5. Pose controls and generated movement

Use **RTM Pose model settings**, **Analysis Preview** or the start dialog. Dance and hybrid profiles save their FPS, curve smoothing, GPU, pose filtering and applicable L0 options separately. Fresh dance defaults are 45 FPS, output curve on, GPU off, four pose filters on, Hybrid L0 blend off with stored weight 30%, automatic L0 on, fast-v1 loss handoff on and pattern expansion off. Fresh hybrid profiles have the four pose filters off.

| Control | Effect | Default and scope |
| --- | --- | --- |
| **Reject outliers** | Rejects implausible keypoint jumps/limb changes; confident repeated observations can reacquire points. | On in dance. A heuristic can also reject genuine fast motion. |
| **Optical flow** | Tracks previous skeleton keypoints between detections using image support. | On in dance. Predicted points expire; this is not a new model detection. |
| **Kalman** | Fuses keypoint predictions and RTM observations to reduce jitter. | On in dance. Does not establish physical accuracy. |
| **Micro smoothing** | Smooths small keypoint movement (up to about 3 processing pixels), letting larger changes pass through. | On in dance. Can introduce a little lag. |
| **Hybrid L0 blend / weight** | Mixes v2 into direct Pose L0 only; the remaining weight is RTM's contribution. | Off, weight 30%; adjustable 1–100%. Source is v2 only. Other axes remain Pose-derived. This blend does not implicitly enable ViTTrack/NeuFlow. |
| **Generate L0 when still / small** | After about 0.65 s of still L0, or small L0 with clearly larger rotation, tries R1 then R2 to produce L0. Their midpoint maps to one-third and either end to two-thirds. If rotations are still but another observed axis moves, it can use a quarter-to-half cosine with a fixed 1 s period. | On, direct Pose only, while analysis runs. All observed axes still/missing means hold; it does not start a fallback wave. Enough real L0 movement takes over smoothly. Generated values describe motion before final gains/timing, and do not receive the direct Pose L0 ×10 gain again. |
| **Small-cycle expansion** | Independently confirms about three steady small cycles on L0, R0 or R1, then gradually expands around each movement's midpoint up to 2× in about 1 s. | Off. L1/L2/R2 and generated/recovering L0 are excluded. Larger real motion, broken rhythm or lost observations releases expansion. Final gains/limits still apply. |
| **Use Hybrid v1 on fast Pose loss** | Runs v1 continuously on the same sampled frames. After recent valid Pose loss plus fast supported v1 motion, hands L0 over from the current output and uses subsequent v1 changes. Pose recovery returns smoothly. | On, direct Pose only; costs extra processing. L0 only, without Pose's ×10 gain. Startup, a cut or missing Pose alone does not activate it. Other axes keep their normal loss behavior. |
| **v2: RTM 2D rotation assist** | Supplies Pose-based rotation signals in v2 / Full/Half Travel Six Axis output. | Off. Requires the RTM model. Disabled for v1 and hidden in direct Pose; does not replace v2 L0 or its image translation. |

Pose keypoint prediction is short (up to **0.25 s**) and is distinct from v2's maximum two-second output continuity. Obvious cuts, broad pose jumps, size changes and source gaps over about 0.2 s reset stale pose history. Similar cuts can escape detection; flash/very fast movement may trigger a reset.

Direct Pose's measured **L0 base amplitude is ×10 about center** before user travel gains. Pose rotations use **R0 ×3, R1/R2 ×1.5**, including rotation assistance. These are output interpretation gains, not changes to the skeleton measurement. Pose L0 endpoint-reference recovery requires valid hips moving clearly upward (about 2% of frame height); merely holding an endpoint, downward motion or tiny jitter does not trigger that recovery. Its roughly 0.35 s return and reference reset are separate from manual centering and live endpoint handling.

### 6. Model files, GPU and optional v2 assistance

| Entry | Behavior and limits |
| --- | --- |
| **RTM Pose model → Select model / Download** | Prepares the supported 2D ONNX model required by direct Pose or v2 rotation assistance. Keep the model external to the application package. A filename alone does not establish compatibility. |
| **GPU settings** | Detects/checks the selected backend, offers private optional-runtime installation/cancellation when needed and reports restart requirements. GPU defaults off. CUDA is for NVIDIA; RTM's DirectML backend can use compatible DirectX 12 AMD/NVIDIA/Intel devices. Stop output before switching backends. Install/switch may require restart. RTM can fall back to CPU; enabling GPU is not an accuracy or speed guarantee. |
| **Analysis Preview → + Models** | Expands the initially collapsed, bounded scrolling v2 model controls. The sidebar and start dialog show the same saved choices. Only v2 and Full/Half Travel use these options. |
| **ViTTrack subject tracking** | Optional CPU-capable assistance for retaining a subject region after ordinary analysis identifies it. |
| **NeuFlow v2 optical-flow assist** | Optional dense flow assistance requested adaptively when ordinary sparse/DIS evidence is insufficient. Requires enabled **NVIDIA CUDA**. This exported graph does **not** support DirectML; RTM DirectML support is separate. |
| **Select / Download / Cancel** for either v2 model | Selects a supported pinned artifact or downloads and verifies its size/hash. Each model has an independent switch and file. Checking a switch does not install dependencies. Changing a currently used model option stops analysis so the next run applies a consistent selection. |

**Both v2 models default off**, can be selected independently and are turned off by Reset all defaults. Downloaded files remain on disk after reset. Missing, incompatible or failed optional models retain ordinary v2 analysis. Direct Pose, its optional L0 blend and v1 do not silently inherit these models. A tracked bounding-box center is not a direct L0 measurement; neural correspondences still require image support and camera validation. Optional assistance can cost time and does not guarantee better output on every clip. Model weights and optional CUDA/DirectML libraries are excluded from source/Windows ZIPs.

### 7. Filters, travel settings and final live output

Open **More settings → Advanced**, **L0 travel**, **Six-axis individual travel**, or **Measurement mode and axis limits**. The stages have different roles:

| Setting | What changes | Default/range/scope |
| --- | --- | --- |
| **Output Curve Smoothing** | One Euro adaptive smoothing on interpreted positions, before recording and live mapping. Slow motion is smoothed more; fast motion responds more directly. | On. Adds some lag; does not repair bad observations. Generated Pose L0 keeps its existing curve/transition without another smoothing pass. Manual center/emergency center bypass it. |
| **Smoothing / Deadzone / L0 jitter guard** | Older analysis-route filtering; reduces small changes/rapid reversals before its output. | Enabled by default; smoothing 0.28 (0–0.95), deadzone 0.008 (0–0.12), guard 0.70 (0–1). These older sliders are not a second set of Pose keypoint filters or a substitute for v2 reference validation. They also configure the Pose fast-v1 helper. |
| **Gain / Visual stroke / Response curve** | Older analysis sensitivity and position shaping. | Fresh gain 1.35 (0.2–4), visual stroke 0.66 (0.35–1.2), Linear / Soft / Sharp / Ease In. Changing final travel is usually the relevant amplitude adjustment for the Pose/v2 main pipeline. |
| **L0 travel multiplier** | Scales L0 displacement about center after analysis. | 0–3×; fresh 1×. Zero removes travel; larger values can saturate. Applies to recording/export and live output. |
| **Total auxiliary travel / individual axis travel** | Scales L1/L2/R0/R1/R2 about center; an individual multiplier combines with the shared auxiliary multiplier, with the product capped at 3×. | 0–3×, fresh 1×. Does not magnify L0 again. Applies to recording/export and live output. |
| **L0 reverse / auxiliary global and per-axis reverse** | Reverses the relevant final position direction. | Off. Auxiliary global/per-axis reversals combine; two reversals cancel for that axis. Does not reverse the measured image trajectory. |
| **Play Preset 1–5** | Sets L0 and shared auxiliary travel to 0.55 / 0.75 / 1 / 1.15 / 1.30×. | Fresh/reset level 3. Changes final amplitude only, preserves the selected analyzer and running analysis state. Limits/caps still apply. |
| **Axis lower / upper limits** | Maps normalized live movement into each saved TCode range. | TCode 0–9999; fresh full range. L0 has compact sliders, all six axes have separate entries. These are commanded ranges, not measured mechanical limits; scripts remain normalized. |
| **Per-update speed limit** | Limits the maximum live TCode coordinate change in an update. | On; fresh maximum step 1300. It is not a calibrated physical velocity limit; its effect depends on actual update cadence. |
| **Minimum arrival time** | Lower bound for TCode `I` time. Actual update cadence can extend it. | Fresh 24 ms. It does not set send frequency. |
| **Approach-limit slowdown** | Extends live arrival time when approaching an axis endpoint, without changing that target position. Recording/export uses endpoint timing to extend timestamps. | On, 10% zone; 1–50%. Moving away from limits, manual center and emergency center are not slowed by this feature. Scripts may be longer than the source video. |
| **Activity gate / Idle** | When activity is too low, live output holds or moves toward center. | Gate on, threshold 0.0035 (0–0.04); idle Hold or Center, fresh Hold. This is live handling, not a new visual detector. |
| **Startup ramp** | Gradually introduces live movement at startup. | On, fresh 700 ms. Not a scene-motion measurement. |
| **Extreme-position reset / hold time** | Live endpoint handling can ease an axis away from prolonged endpoint occupancy. Some older analysis routes also use endpoint recovery. | On, fresh 850 ms. Distinct from direct Pose's upward-hips reference recovery; does not determine a mechanically safe pose. |
| **Endpoint guard / margin** | Reserves an endpoint buffer in live output and supported older L0 analysis. | On, fresh 10%, configurable up to 25%. Different from slowdown: guard affects positions; slowdown affects time. |

In **direct Pose Six Axis live commands**, L1/L2 coupling depends on the already limited L0: gain **0.5 at bottom → 1 at one-third → 3.5 at two-thirds → 0.5 at top**, with linear interpolation. R1/R2 keep coupling 1 through two-thirds, then decrease to 0.5 at top. **V2 live translation coupling** retains **1 → 2.5 → 1**, peaking at center. These couplings occur in TCode mapping; they do not change skeleton observations or normalized script data. R0 does not use the Pose R1/R2 coupling.

**Hybrid six-axis tuning** offers total strength, jitter reduction, sensitivity levels 1–10 and independent auxiliary gains/reversal, plus **Stable six axes**. It belongs to the older hybrid tuning route; it does not replace the dedicated v2 secondary-motion filter or tune direct Pose. Its presence does not cause v1 to output auxiliary axes. Use the shared/individual travel controls for final amplitude across modes.

The named **Safe / Standard / Full Travel / Sensitive Hybrid / Stable L0** actions are broader presets than the numbered Play Preset buttons. They can change limits, speed, filters, gain and travel; Sensitive Hybrid and Stable L0 select v1, and Full Travel selects L0 Only. “Safe” is the preset's name, not a hardware-safety certification. Check the resulting mode and settings before starting.

### 8. Connection, manual commands and tests

| Entry | What it does | Limits |
| --- | --- | --- |
| **Output → Log only** | Produces/logs commands for inspection and the reference simulator without hardware transport. | Useful for initial analysis and settings checks. Does not validate a connected device. |
| **Serial COM / USB Serial** | Sends TCode to the selected port with the configured baud rate (fresh 115200). Refresh/detect assists port selection. | The two choices use serial transport. A listed port alone does not prove a compatible device. |
| **BLE UART** | Uses the saved device name/address and UART service/write characteristic UUIDs to send commands. | This is BLE TCode UART, not generic support for any Bluetooth device. BLE axis feedback/query is not implemented. |
| **Connect and center / Disconnect** | Opens/closes the selected transport; Connect and center sends a center command after connection. | Center is the command midpoint, not verified physical neutral. Connection or write failure stops output and reports the error; failed commands are not automatically resent. |
| **Query device axes** | Sends a firmware `D2` query over serial while realtime output is stopped. | Depends on firmware reply; no reply does not establish lack of axes. This is not physical position feedback. |
| **Center** | Sends a center command to active output axes. | Bypasses output curve and approach slowdown. |
| **Emergency stop and center** | Stops the analysis/output task and requests a center command (600 ms arrival). | A software command, not an independent hardware power cut. It cannot guarantee movement when a device/transport has failed or prove that centering is safe for another mechanism. |
| **Medium test / Full L0 test / SR6/OSR6 six-axis test** | Sends synthetic test motion and then returns to center. | Does not use scene recognition. Full L0 test exercises a much wider command range. Use Log only first and review saved ranges before hardware use. |
| **Measurement mode → axis / slider / Send position** | Sends a manual selected-axis TCode coordinate, 0–9999, while realtime analysis is stopped. | **Send while dragging** defaults on. This mode is for finding a command range; it is not feedback and should not be assumed to obey the live normalized travel path. |
| **Save as lower / upper; current axis center** | Stores the manual coordinate as that axis limit, or sends 5000 to the selected axis. | Current axis center here means 5000; it is distinct from centering within a saved asymmetric range. Stored numbers need physical checking for the actual mechanism. |

Only currently supported TCode transport controls are present. Removed commercial-device adapters, external device-service discovery, custom bindings and Pose 3D are not hidden functions to enable; old configurations migrate away from these routes.

### 9. Recording, export, monitor, simulator and Lab

| Function and entry | Meaning |
| --- | --- |
| **Start recording → Save script** | Starts a fresh in-memory recording of normalized interpreted positions. Saving stops recording and writes `.funscript` files. Starting a new recording clears the previous unsaved recording. Small changes are coalesced into script actions. It records positions, not screen video or hardware feedback. |
| **Analyze video and save script** | Analyzes a selected local video offline and saves scripts; stop live analysis first. This is separate from playback-timed realtime video input. Export samples according to source timing and the configured target (capped at 60 FPS for this path), then applies script travel/inversion/curve and endpoint timing. Cancel stops the export rather than writing an incomplete result. |
| **Axis script files** | L0 uses the base name. L1 `.surge`, L2 `.sway`, R0 `.twist`, R1 `.roll`, R2 `.pitch` append to the base name before `.funscript`. Only axes with recorded actions produce files. Device limit/coupling effects should be checked in the playback/controller used later. |
| **Output Monitor** | Initial tab. Shows live final TCode coordinates/commands and the recent output curves, plus travel presets/limits and recording status. The curve is a command history, not a sensor trace. |
| **Show Preview** | Opens the bundled reference 3D simulator. It receives the same final live TCode coordinates and arrival times after travel, inversion, coupling, limits and live speed handling. It is a visualization, not a mechanical digital twin or hardware feedback. |
| **Analysis Preview** | Shows paired images from one sampled analysis frame, raw/processed Pose or original/current motion view, reference details and observation charts. Mode/filter/reference/model controls share settings with the sidebar/start dialog. Hiding this tab does not stop analysis. |
| **Analysis status/charts** | Shows inference/processing time, source-frame gap, resets and deliberate video skips. These are processing diagnostics, not complete screen-to-device latency. Charts show relative image X/Y/scale, not physical distance; missing observations are not plotted as measured zero. |
| **Independent Pose Preview Lab → `Pose-Preview-Lab/Start.cmd`** | Starts the separate **0.2.2-test** preview using the portable runtime or source Python. Supports screen/video, RTM skeleton, Image Motion translation and Image Motion v2 translation+scale. Its two image modes are separate experiments, not the main v1/v2 algorithms. It never connects hardware or creates device commands/scripts. |

The independent Lab shares region/physical capture geometry with the main application and has its own settings. Its four pose filters default **off**, unlike main dance defaults. It offers max-edge comparison, reference reset and paired raw/processed frames; predictions expire after 0.25 s. Lab CPU processing time and target rates are not a guarantee of realtime throughput. Keep the Lab alongside the complete application; its screen helpers/runtime are shared.

### 10. Saved settings, language and high-DPI layout

Choose English or Chinese at startup; the choice is saved. Changing documentation language does not change an existing application's chosen language. Routine edits autosave, with persistence on close; dance/hybrid analysis profiles are separate, while output travel/connection choices are application settings. Stop before changing a locked input/region or resetting the configuration. The start dialog is a review/apply step for the same settings, not a separate unsaved analysis profile.

**Reset all defaults** asks for confirmation because it overwrites local saved settings, including capture region, connection details, limits, multipliers, analysis/audio parameters and layout. It restores v2, Play Preset 3 and default-off optional models. It does not delete downloaded model files or restore someone else's historical personal configuration. Lab settings are independent.

Drag the divider between controls and preview to set sidebar width. The saved width uses device-independent units; the initial window fits the display work area. Narrow panels have vertical/horizontal scrolling, Shift+wheel scrolls horizontally, ordinary wheel scrolling does not silently change a combobox choice, and Tab-focused controls scroll into view. Optional model controls start collapsed and scroll within their bounded panel. Reset defaults also resets sidebar width. These are presentation changes; they do not rescale capture coordinates or analysis output.

### 11. Source entry points for maintainers

Unless marked as root paths, files below are under `src/osr_screen_tcode/`. They identify current responsibilities; modify a feature's implementation together with its UI/configuration and appropriate checks. The table is not an invitation to expose internal class names in the user interface. `app.py` and `analyzer.py` retain the public class entry points; the corresponding `application/` and `analysis/` modules now own their extracted responsibilities.

| Responsibility | Source entry points |
| --- | --- |
| Public application class and startup | `app.py`; `__main__.py` |
| Language, translated controls and hover help | `application/language.py`; `application/translations.py`; `application/tooltips.py` |
| Initial UI state, saved settings and analysis profiles | `application/state.py`; `application/settings.py`; `config.py`; `analysis_preferences.py` |
| Main panel layout, mode controls and start-confirmation dialog | `application/layout.py`; `application/analysis_controls.py`; `application/analysis_options.py`; `application/start_dialog.py` |
| Physical screen geometry, input selection and capture | `application/sources.py`; `screen_geometry.py`; `region_selector.py`; `capture.py` |
| Start/stop, screen/video/audio live processing and UI events | `application/realtime.py` |
| Shared sampled-frame Pose/v2/cycle pipeline and preview | `visual_pipeline.py`; `integrated_preview.py`; `visual_lab/observations.py`; `visual_lab/stabilizer.py` |
| Original v1 and Beta image routes | `analyzer.py`; `analysis/flow.py`; `regional_flow.py`; `motion_focus.py` |
| V2 subject and independent camera motion | `camera_motion.py`; `motion_tracking.py`; `subject_tracking.py`; `motion_layers.py`; `region_support.py` |
| V2 axes, rotations and secondary filtering | `dominant_motion.py`; `frame_rotation.py`; `secondary_motion.py`; `motion_reference.py` |
| V2 reference, targets and bounded continuity | `point_l0.py`; `fused_l0.py`; `reach_target.py`; `interaction_point.py`; `target_baseline.py`; `target_regions.py`; `motion_rhythm.py`; `subject_continuity.py` |
| Quarter/half/full cycle | `stroke_cycle.py`; `visual_pipeline.py` (`StrokeCycleAnalyzer`) |
| Pose backend, gains, generated L0 and handoff | `pose_backends.py`; `directml_pose.py`; `analysis/rtm_runtime.py`; `analysis/rtm_geometry.py`; `analysis/pose_motion.py`; `pose_output.py`; `pose_l0_fallback.py`; `pose_pattern.py`; `pose_fast_fallback.py` |
| Model selection/download UI and source constants | `application/models.py`; `application/model_options.py`; `application/model_sources.py` |
| V2 model registry/assets/assistance | `v2_models.py`; `v2_model_assets.py`; `v2_model_assist.py` |
| GPU detection/download/install UI | `gpu_controls.py`; `gpu_runtime.py`; `gpu_downloads.py` |
| Audio input and level/accent/pulse analysis | `audio.py` |
| Output interpretation, curve, travel/limits and live timing | `application/output.py`; `application/travel_controls.py`; `output_curve.py`; `tcode.py`; `command_cadence.py`; `endpoint_slowdown.py` |
| Named and numbered presets / sensitivity actions | `application/presets.py` |
| Device panel, transport, connection/manual commands/tests | `application/device_panel.py`; `application/connection.py`; `application/manual_output.py`; `sinks.py`; `device_controls.py`; `device_test.py` |
| Recording and offline analysis | `application/video_export.py`; `recorder.py`; `analyze_video.py` command-line path |
| Analysis overlay drawing | `analysis/preview.py`; `integrated_preview.py`; `motion_reference.py` |
| Final simulator and output monitor | `application/monitor.py`; `preview.py`; `assets/osr_emu_standalone.html` |
| Sidebar/scaling/combobox presentation | `ui_layout.py`; `ui_widgets.py` |
| Independent Lab launcher and implementation | `preview_lab_launcher.py`; root `Pose-Preview-Lab/` |
| Portable packaging/startup and runtime check | Root `Start.cmd`; root `tools/`; `runtime_check.py`; root `SR6-OSR6-Realtime-Screen-TCode.spec` |

Existing release validation records in `docs/` document what was actually tested and earlier failures. This feature guide describes behavior and scope; it is not a new inference benchmark or evidence that real depth, contact or robot-arm mechanics have been validated.

---

## 中文

本指南介绍 **2.1.0** 保留的用户功能。本版整理既有程序职责，没有新增分析模型、延长估算时限或新增硬件映射。下文默认值指首次配置或“恢复所有默认设置”；原先保存的个人选择可能不同。

### 1. 启动与三类结果

Windows 便携包需完整解压，运行 **Start.cmd** 或 exe，保留旁边的 `_internal` 和其他配套目录。源码使用根目录 **Start.cmd**，需要 Python 3.10 或更新版本。**Start.md** 是说明，不是启动文件。模型及可选 GPU 运行库另行下载。

1. **分析观测**：骨架、画面方向、主体／背景像素支持和画面尺度，在“分析预览”查看。
2. **脚本位置**：经过适用的 Pose 输出处理、输出曲线、行程倍率和反向的归一化位置。录制／导出还可在端点附近延长脚本时间。
3. **最终实时指令**：继续应用设备轴上下限、实时限速／活动／启动处理和适用的轴联动。“输出监视”与模拟器显示这些 TCode 指令。

funscript 不是实时指令流的逐字副本。设备上下限、每次实时更新限速、实时空闲／端点处理与仅 TCode 使用的联动，并非全部写入归一化脚本。曲线平滑不等于识别准确或设备实际按曲线运动。

先用 **Log only** 检查结果，不向硬件发送。现有传输为 SR6/OSR6 TCode 串口或 BLE UART。画面尺度不是真实深度，目标候选不确认接触；机械臂关节映射、逆运动学、碰撞检测与真实位置反馈尚未实现或验证。

### 2. 输入、选区与分析尺寸

在“**展开更多设置 → 输入来源**”选择一项。纯声音输入不同时运行画面分析。

| 功能与入口 | 做什么 | 设置与边界 |
| --- | --- | --- |
| **Screen 屏幕** | 从已选桌面矩形读取新画面，进行实时分析。 | 默认输入。改区域前先停止。尽量不要把程序自己移动的窗口框进素材。 |
| **Video File 视频 → 选择** | 打开本地视频，按播放时间进行实时分析。 | 不把视频音轨自动混入画面输出。处理跟不上时可跳过旧播放帧；离线导出是另一项操作。 |
| **Audio Only 纯声音** | 监听系统声音或所选输入设备，生成 L0。 | 不读屏、不识别人、不从画面判断运动方向。 |
| **框选屏幕区域** | 打开暗化桌面快照，显示明亮选区、青绿边框、屏幕标识和坐标。 | Enter 确认、R 重选、Esc 取消。快照只在内存；确认后开始分析读取新实时帧。取消保留旧区域。 |
| **X／Y／宽／高** | 用数字设置同一个采集矩形。 | 使用桌面物理像素；主屏左／上方显示器可有负坐标。混合 DPI、竖屏与跨屏均使用同一约定。越界或只有屏幕间隙的选区会被拒绝；跨屏间隙填黑。 |
| **采集帧率 FPS** | 设置屏幕采集／分析目标速率。 | 默认 45；1–120。提高会增加资源开销，不能创造额外源视频帧；实际速率受采集、模型和处理成本限制。 |
| **分析预览 → 处理最长边** | 在 Pose／v2 分析前缩小采样画面。 | 320／480／640／960／1280，默认 640。保留完整比例，不放大小图；改变后重建参考。RTM 模型输入尺寸仍固定。旧分析路线中此项禁用。 |
| **高级参数 → 压缩延迟** | 正值缩小旧主分析路线的帧；此值也调整既有 Pose 派生运动几何中的部分短预测项。 | 默认 0，范围 −5…5。非正值在旧路线保留画面细节。Pose／v2 帧尺寸由“处理最长边”决定；Pose 快速 v1 辅助接收同一采样帧，不另按压缩值缩图。此项不是全部 Pose 预测的时限开关、不是端到端延迟测量，也不保证 −5 比 0 更准确。 |

“**采集**”尺寸是实际桌面像素，“**分析尺寸**”是处理图像。预览缩放／留黑只影响显示。很细的选区可以显示，但未必有足够特征可分析。运行中检测到显示器排列或分辨率变化会停止；重新框选后再开始。

纯声音的“**声音分析**”提供：**Audio Level** 将平滑音量映射为位置；**Dynamic Accent** 按音量产生中位以上响应，音量上升参与活动判断；**Beat Pulse** 在音量上升时触发逐渐衰减的脉冲。它们不是音符识别或经过验证的节拍标注。声音设备默认 **System Output**（系统回环），也可选择 Default Input 或列出的输入设备；“刷新”重查设备。声音增益默认 **2.5**、界面范围 **0.2–8**；门槛默认 **0.02**、范围 **0–0.35**；声音平滑默认 **0.25**、范围 **0–0.95**，越大越稳也越慢。声音参数影响声音分析 L0，后续行程／输出处理继续生效。

### 3. 分析模式与输出轴

在侧栏、分析预览或启动确认框选择“**分析模式**”。列表排序不代表默认选择，初始默认是**混合分析 v2**。分析模式影响识别；“**L0 Only／Six Axis**”选择输出轴。

| 模式 | 含义与输出 | 模型／默认／限制 |
| --- | --- | --- |
| **混合分析 v2（推荐-非舞蹈）** | 用分布式像素支持持续跟踪同一主体，独立检查背景运镜，并从左右、上下与画面尺度变化拟合连续运动轴。L0 沿主方向，L1/L2 沿横向方向；不开 RTM 辅助时旋转是画面近似。 | 无需模型，默认模式。不带 RTM 的副轴只跟随已确认的明显变化／反转并平滑，不过滤 L0。背景证据不足仍可能保持或进行有时限接续。 |
| **全／半行程模式（基于混合分析）** | 共用 v2 主体／运镜／参考分析，再按已确认往复幅度和节奏生成余弦 L0：底→1/4→底、底→中→底或底→高→底，节奏逐步匹配。 | 无需模型。1/4／半／全分类自动决定，不是手动选定恒定振荡器。L1/L2 居中，可用 RTM 旋转和 v2 模型辅助；最终倍率仍会改变幅度。 |
| **RTM Pose 2D（推荐-舞蹈）** | 使用二维人体关键点生成 L0；六轴时增加身体派生的辅助信号。同帧配对显示原始／处理后骨架。 | 需要受支持的本地 256×192 RTMPose ONNX；GPU 默认关。是画面分析，不是三维关节重建。RTM Pose 3D 已移除。 |
| **混合分析（推荐-平面大幅动作），v1** | 保留原区域光流 L0 路线，适合比较大幅平面运动。 | 无需模型；即使选 Six Axis 也**只输出 L0**。不继承 v2 模型、融合参考或 v2 旋转辅助。 |
| **Stroke Phase（内测用）** | 依据确认的画面光流方向向对应 L0 端点接近。 | 旧实验路线，不是 v2 的主体／目标／节奏管线。 |
| **Motion Center（内测用）** | 用变化区域的上下中心生成 L0。 | 无关运动和运镜都可能影响。 |
| **Optical Flow（内测用）** | 将上下光流累积成 L0。 | 可能漂移，可能包含运镜。 |
| **Hybrid Motion（内测用）** | 混合变化区域中心与累积光流。 | 独立旧实验，不等于混合 v1／v2。 |
| **Activity Pulse（内测用）** | 根据画面活动产生重复三角形 L0 脉冲。 | 是活动驱动的合成响应，不是实测主体轨迹或已确认往复节奏。 |

初始输出模式为 **L0 Only**。所选路线支持时，**Six Axis 六轴**使用 L0/L1/L2/R0/R1/R2。这些是 TCode 轴名，预览中的立体画面轴不建立真实机械臂坐标。选择六轴不会把纯声音变成六轴运动检测，也不会让 v1 提供副轴运动。

### 4. V2 参考、目标标记与短暂缺测

v2／全半模式中，在“**分析预览 → v2 L0 参考**”（启动框亦有）选择。这影响分析 L0，位于最终用户行程倍率之前。

| 参考 | 含义 |
| --- | --- |
| **融合参考（默认）** | 对齐运动轴、已确认往复中心／相位和可靠交互证据。远近方向确认后，远离 L0 大、靠近 L0 小。独立目标可靠时可使用距离／到达关系；否则仍可分析可见主体往复。 |
| **三维运动轴** | 根据学到的画面主方向位移生成 L0；第三分量为画面尺度，不是真实 Z 距离。 |
| **往复中心点** | 使用已确认的往复中心／相位作为参考。 |
| **交互点候选（实验）** | 使用已有几何交互证据；不确认被接触物体身份或真实接触。 |

切换来源从当前输出续接，避免跳向另一来源的累计位置。方向／参考明显认错或场景改变时，点“**重设参考**”清旧校准与历史。

- **黄主体框／A**：持续跟踪的区域与同一画面锚点。绿色采样组支持主体测量，蓝点支持独立验证的背景。
- **橙色 T?**：用自己图像特征跟踪的独立物体边界候选。到达百分比是画面估计；估计 100% 对应倍率前分析 L0 底部，不等于真实接触。
- **V?**：没有可靠客体时，由已确认主体往复推定的端点／假定客体，不是实测物体，不提供实际接触百分比。
- **灰色 E?／S?／P?**：轨迹端点、局部缩放中心或几何会聚／交互参考，不是已确认接触目标。
- **A?／淡色虚框、虚线轴**：弱跟踪或位置估计，与真实观测分开。画外目标箭头只表示方向，不能把屏幕边缘当到达点。

默认融合参考短暂缺测时，先尝试有像素支持的弱主体跟踪，再沿用已确认节奏。缺测估算**最多 2 秒**，最后 **0.5 秒**减速保持；没有确认往复时，只允许近期稳定速度在 **0.3 秒／倍率前 15% 行程**内短暂接续，不制造反转。偶尔恢复一帧不能重启时限；稳定真实观测恢复后，从当前输出接回。

暂停、切镜、停止、输入／尺寸变化及重设参考清旧规律。全半模式只能接续已建立的行程分类，不会凭空启新周期。三个单独参考保留各自语义，不等同完整融合接续。持续模糊、长遮挡、相似切镜和独立背景不足仍是限制。

### 5. Pose 处理与自动运动

入口为“**RTM Pose 模型设置**”、分析预览或启动框。舞蹈和混合模式分别记忆 FPS、曲线、GPU、骨架处理及适用 L0 选项。舞蹈初始默认：45 FPS、输出曲线开、GPU 关、四项骨架处理开、混合 L0 关且保存权重 30%、自动 L0 开、快速 v1 接管开、pattern 放大关。混合配置的四项骨架处理默认关。

| 控件 | 作用 | 默认与范围 |
| --- | --- | --- |
| **异常过滤** | 拒绝不合理关键点跳变／骨长变化；持续可信观测可重新捕获。 | 舞蹈默认开；启发式也可能错拒真实快动作。 |
| **光流辅助** | 用像素支持跟踪上一帧骨架关键点，补充检测间运动。 | 舞蹈默认开；预测会到期，不是新模型识别。 |
| **卡尔曼融合** | 融合关键点预测与 RTM 观测以降抖。 | 舞蹈默认开；不能确立物理准确率。 |
| **仅微抖平滑** | 平滑约 3 处理像素以内的小位移，大位移直通。 | 舞蹈默认开；可能增加少量滞后。 |
| **混合分析 L0 权重** | 只把 v2 混入直接 Pose 的 L0，剩余为 RTM 权重。 | 默认关、保存 30%，范围 1–100%；来源仅 v2，其他轴仍 Pose。不隐式启用 ViTTrack／NeuFlow。 |
| **L0 静止／小幅时自动生成** | L0 静止约 0.65 秒，或幅度小而旋转明显更大时，先用 R1、再用 R2；中点对应 L0 1/3，两端对应 2/3。旋转静止但其他实测轴仍动时，可生成 1/4–1/2、固定 1 秒周期余弦。 | 默认开，仅直接 Pose 分析运行时。全部观测轴静止／缺失就保持，不启动兜底波；实际 L0 幅度足够时平滑交回。范围／周期在最终倍率与时序前，生成 L0 不再乘 Pose ×10。 |
| **小幅往复渐放大** | L0/R0/R1 各自确认约三个稳定小周期后，约一秒逐渐放大至最多 2×，围绕本次运动中点。 | 默认关；L1/L2/R2 与生成／恢复中的 L0 不参与。实际幅度变大、节奏断或缺测就退出；最终倍率／限制仍作用。 |
| **快速丢点时用混合 v1** | 同批采样帧持续运行 v1；近期有效 Pose 丢失且 v1 有可靠快运动时，从当前 L0 接续后续 v1 变化，Pose 恢复后平滑交回。 | 默认开，仅直接 Pose，增加开销。只接管 L0，不乘 Pose ×10。起始、切镜或只有 Pose 缺失不触发；其他轴保留原缺测处理。 |
| **v2：启用 RTM 2D 旋转辅助** | 在 v2／全半六轴中提供 Pose 旋转信号。 | 默认关，需 RTM 模型；v1 禁用，直接 Pose 隐藏。不替换 v2 L0 或画面平移。 |

骨架点预测最多约 **0.25 秒**，与 v2 最多两秒输出接续不同。明显切镜、整体骨架大跳、尺寸变化或超过约 0.2 秒源帧间隔会清旧 Pose 历史；相似切镜可能漏检，闪光／极快动作可能触发复位。

直接 Pose 的实测 **L0 基础幅度围绕中位 ×10**，再应用用户行程。Pose 旋转为 **R0 ×3、R1/R2 ×1.5**，旋转辅助也使用；这些是输出解释倍率，不修改骨架观测。Pose L0 端点参考复位要求有效双髋明显上移（约画高 2%），停留、下移或微抖不触发；约 0.35 秒回中与重设参考，独立于手动回中和实时端点保护。

### 6. 模型文件、GPU 与 V2 可选辅助

| 入口 | 行为与边界 |
| --- | --- |
| **RTM Pose 模型 → 选择模型／下载** | 准备直接 Pose／v2 旋转辅助所需的受支持二维 ONNX。模型留在包外；文件名相同不代表兼容。 |
| **GPU 设置** | 检测所选后端，按需提供私有可选运行库安装／取消并提示重启。GPU 默认关；CUDA 为 NVIDIA，RTM DirectML 可用兼容 DirectX 12 的 AMD/NVIDIA/Intel。停止后再切后端，安装／切换可能需重启。RTM 可回退 CPU；GPU 不保证更准确或更快。 |
| **分析预览 → + 模型** | 展开默认收起、高度受限且可滚动的 v2 模型区，与侧栏／启动框共用保存值。仅 v2／全半模式使用。 |
| **ViTTrack 主体跟踪** | 原分析先确认主体，再辅助保持区域；可用 CPU。 |
| **NeuFlow v2 光流辅助** | 原稀疏／DIS 证据不足时，自适应补充密集光流。要求明确开启 **NVIDIA CUDA**；本导出图**不支持 DirectML**，RTM DirectML 是另一功能。 |
| 两项各自的**选择／下载／取消** | 选择受支持固定版本文件或下载并验证尺寸／哈希；各自开关与路径独立。勾选不会安装依赖，改变正在使用的选项会停止分析，下次统一生效。 |

两模型**均默认关**，可独立开启；恢复默认关闭开关，但保留下载文件。缺失、不兼容或失败时使用普通 v2 分析。直接 Pose、其 L0 混合及 v1 不会静默继承。跟踪框中心不能直接成为 L0 测量；神经匹配仍需像素和独立运镜验证。辅助可能增加耗时，不保证每片段都更好。模型和可选 CUDA／DirectML 库均不包含在源码／Windows ZIP 中。

### 7. 滤波、行程与最终实时输出

入口为“**更多设置 → 高级参数**”、“**L0 行程**”、“**六轴单轴行程**”或“**测量模式和轴上下限**”。不同阶段职责如下：

| 设置 | 改变什么 | 默认／范围／适用 |
| --- | --- | --- |
| **输出曲线拟合** | One Euro 自适应平滑解释后位置，位于录制和实时映射之前；慢动多平滑、快动更直接。 | 默认开，可能滞后，不修复错误观测；生成 Pose L0 保留已有曲线／过渡，不重复平滑。手动／急停回中绕过。 |
| **平滑／死区／L0 防抽搐** | 旧分析路线的小变化／快速反转滤波。 | 默认开启；平滑 0.28（0–0.95）、死区 0.008（0–0.12）、防抖 0.70（0–1）。不是第二套 Pose 骨架滤波，也不能代替 v2 参考验证；同样配置 Pose 快速 v1 辅助。 |
| **增益／视觉行程／响应曲线** | 旧分析的灵敏度和位置曲线。 | 增益默认 1.35（0.2–4）、视觉行程 0.66（0.35–1.2）、Linear／Soft／Sharp／Ease In。Pose／v2 主管线调最终幅度通常应使用行程倍率。 |
| **L0 总行程倍率** | 分析后围绕中位缩放 L0。 | 0–3×，默认 1×；0 去掉行程，大值可能饱和。录制／导出／实时均使用。 |
| **辅助轴总行程／逐轴倍率** | 围绕中位缩放 L1/L2/R0/R1/R2；逐轴与辅助总倍率相乘，乘积最多 3×。 | 0–3×，默认 1×；不会再放大 L0。录制／导出／实时均使用。 |
| **L0 反向／辅助总反与逐轴反转** | 反转最终位置方向。 | 默认关；辅助总反与单反叠加，两次抵消，不反转实测画面轨迹。 |
| **1–5 档预设** | 将 L0 与辅助总行程设为 0.55／0.75／1／1.15／1.30×。 | 默认／恢复为 3 档；只变最终幅度，保留分析选择及运行分析状态，仍受限制。 |
| **各轴下限／上限** | 把归一化实时位置映射至各轴保存 TCode 范围。 | 0–9999，初始全范围；L0 有简要滑块，六轴各有独立值。是命令范围，不是实测机械限位；脚本仍归一化。 |
| **每帧限速** | 限制每次实时更新 TCode 坐标最大变化。 | 默认开，步长 1300；不是已校准物理速度，受实际更新节奏影响。 |
| **到达时间下限** | TCode `I` 时间下限，实际更新节奏可延长。 | 默认 24 ms；不设发送频率。 |
| **接近上下限时减速** | 接近端点时延长实时到达时间，不改该目标位置；录制／导出相应延长时间戳。 | 默认开、10%，范围 1–50%；远离端点、手动／急停回中不经此减速。脚本可能比视频长。 |
| **活动门控／空闲** | 活动低时实时保持或向中位移动。 | 默认开，阈值 0.0035（0–0.04）；Hold／Center，默认 Hold。是实时处理，不是新视觉检测器。 |
| **启动渐入** | 开始时渐进引入实时运动。 | 默认开、700 ms；不是画面运动测量。 |
| **极端位自动复位／停留时间** | 实时轴长期端点停留时可缓慢离开；部分旧分析也有端点恢复。 | 默认开、850 ms；区别于直接 Pose 双髋上移参考恢复，也不能确定机械安全姿态。 |
| **端点保护／留白** | 在实时输出及受支持旧 L0 分析保留端点缓冲。 | 默认开、10%，可至 25%；保护改位置，末端减速改时间。 |

**直接 Pose 六轴实时指令**的 L1/L2 联动按已受限 L0：**底 0.5 → 1/3 处 1 → 2/3 处 3.5 → 顶 0.5**，节点间线性变化。R1/R2 底部至 2/3 为 1，之后至顶部降至 0.5。**V2 实时平移联动**保持 **1 → 2.5 → 1**，峰值在中位。这些位于 TCode 映射，不修改骨架观测或归一化脚本；R0 不参加 Pose R1/R2 联动。

“**六轴辅助调节（仅混合分析）**”有总强度、降抖、1–10 敏感度、辅助轴倍率／反向及“一键稳六轴”。属于旧混合调节路线，不替代 v2 独立副轴滤波，也不调直接 Pose；界面有此区不代表 v1 能输出副轴。跨模式调最终幅度使用总／逐轴行程。

具名“**安全预设／标准预设／全行程／混合分析灵敏／一键稳态 L0**”比数字五档改得更多，可改限位、速度、滤波、增益、行程；混合灵敏与稳态 L0 选择 v1，全行程选择 L0 Only。“安全”是预设名，不是硬件安全认证；开始前核对修改后模式和数值。

### 8. 连接、手动命令与测试

| 入口 | 做什么 | 限制 |
| --- | --- | --- |
| **输出 → Log only** | 生成／记录指令供检查与模拟器使用，不发硬件。 | 适合先检查分析／设置；不验证设备。 |
| **Serial COM／USB Serial** | 按端口和波特率发 TCode，默认 115200；刷新／检测辅助选择。 | 两项均为串口传输；看到端口不证明兼容。 |
| **BLE UART** | 按保存名称／地址及 UART 服务／写入 UUID 发指令。 | 不是任意蓝牙设备适配；未实现 BLE 轴查询／反馈。 |
| **连接并回中／断开** | 打开／关闭所选传输，连接并回中在成功连接后发回中。 | 回中是命令中位，不是验证过的实际中性姿态。连接／写入失败停止输出并报告，不自动重发失败命令。 |
| **查询设备轴** | 停止实时输出后，通过串口发送固件 `D2` 查询。 | 依赖固件回复；无回复不证明无轴，不是位置反馈。 |
| **居中** | 向当前输出轴发送中位指令。 | 绕过输出曲线与接近端点减速。 |
| **急停并回中** | 停止分析／输出任务，再请求回中（到达 600 ms）。 | 软件命令，不是独立硬件断电；连接故障时不保证动作，也不证明其他机械结构回中安全。 |
| **中等测试／上下全幅测试／六轴轻测** | 发送合成测试运动，结束回中。 | 不使用识别；全幅测试范围明显更大。先用 Log only，实机前检查已存范围。 |
| **测量模式 → 轴／滑块／发送当前位置** | 实时分析停止时，手动向所选轴发送 0–9999 坐标。 | **滑动即发送默认开**；用来找命令范围，不是反馈，也不能假定完全经过实时归一化行程链路。 |
| **保存为下限／上限；当前轴回中** | 将当前手动坐标保存为该轴限位，或对所选轴发送 5000。 | 此处回中明确为 5000，区别于非对称保存范围内的中位；数值需要结合实际机构检查。 |

只提供目前支持的 TCode 传输。已移除商业设备适配、外部服务发现、自定义绑定、Pose 3D，不是可重新打开的隐藏功能；旧配置迁移离开这些路线。

### 9. 录制、导出、输出监视、模拟器与独立 Lab

| 功能与入口 | 含义 |
| --- | --- |
| **开始录制 → 保存脚本** | 开始新的内存录制，保存停止录制并写 `.funscript`；再次开始会清掉上一份未保存录制。小变化合并为脚本动作。录位置，不录屏幕视频或硬件反馈。 |
| **分析视频并保存脚本** | 离线分析本地视频，先停实时。与按播放时间实时视频输入不同；按源时序及配置目标采样（该路径最高 60 FPS），再使用脚本行程／反向／曲线／端点时间处理。取消停止导出，不写不完整结果。 |
| **逐轴脚本文件** | L0 用基础名；L1 `.surge`、L2 `.sway`、R0 `.twist`、R1 `.roll`、R2 `.pitch`，再接 `.funscript`。只有录到动作的轴产文件；后续播放／控制器需另检查设备限位与联动。 |
| **输出监视** | 初始页，显示最终实时 TCode 坐标／指令、近期曲线、行程／限位及录制状态；是命令历史，不是传感器曲线。 |
| **显示预览** | 打开内置参考 3D 模拟器，收到与实时相同、经过倍率／反向／联动／限制／限速后的最终坐标与到达时间。是可视化，不是机械数字孪生或设备反馈。 |
| **分析预览** | 同一次采样画面的 Pose 原始／处理后或原画／当前运动结果、参考详情和观测曲线。相关设置与侧栏／启动框同步；隐藏此页不停止分析。 |
| **分析状态／图表** | 显示推理／处理耗时、源帧间隔、重置次数和主动视频跳帧；不是完整屏幕到设备延迟。曲线为画面 X/Y/尺度，非物理距离；缺测不画成实测零值。 |
| **独立 Pose Preview Lab → `Pose-Preview-Lab/Start.cmd`** | 使用便携运行库或源码 Python 打开独立 **0.2.2-test**。支持屏幕／视频、RTM 骨架、画面平移、画面平移＋尺度；后两项是独立实验，不是主软件 v1／v2。不连接设备、不发指令、不生成脚本。 |

Lab 共用选区／物理采集坐标，设置独立；四项骨架处理默认**关**，与主软件舞蹈默认不同。有最长边对比、重设参考及同帧原始／处理后画面，预测最多 0.25 秒。Lab CPU 耗时／目标帧率不保证实时吞吐；保留完整配套目录，共享屏幕组件／运行库仍需上级程序。

### 10. 保存设置、语言与高 DPI 布局

启动时选择中／英文并记忆；文档语言不改变程序已保存语言。一般修改自动保存，关闭也保存；舞蹈／混合分析配置分别记忆，行程与连接为程序设置。改锁定输入／区域或恢复默认前先停。启动确认框是同一套设置的检查／应用步骤，不是独立未保存配置。

“**恢复所有默认设置**”会先确认，因为覆盖本地保存的选区、连接、限位、倍率、分析／声音及布局。恢复 v2、五档 3、关闭可选模型，不删除已下载文件，也不是恢复某人的旧个人配置。Lab 设置独立。

拖动控制区和预览之间的分隔栏调整侧栏宽，按逻辑单位保存，初始窗口适配显示器工作区。窄栏支持横纵滚动，Shift＋滚轮横滚；普通滚轮不误改下拉选项，Tab 焦点滚入可见区。可选模型初始收起，在受限区域内滚动；恢复默认同时复位栏宽。布局只改呈现，不重缩采集坐标或分析输出。

### 11. 维护者源码入口

除标注根目录外，下列文件均位于 `src/osr_screen_tcode/`。修改功能时同时检查 UI／配置与相应验证；不应把内部类名搬进普通用户流程。`app.py` 与 `analyzer.py` 保留公开类入口，拆出的职责分别由 `application/` 和 `analysis/` 模块承接。

| 职责 | 当前源码入口 |
| --- | --- |
| 公开主程序类与启动 | `app.py`；`__main__.py` |
| 语言、控件翻译与悬停提示 | `application/language.py`；`application/translations.py`；`application/tooltips.py` |
| 初始 UI 状态、设置与分析配置 | `application/state.py`；`application/settings.py`；`config.py`；`analysis_preferences.py` |
| 主面板布局、分析控件与启动确认 | `application/layout.py`；`application/analysis_controls.py`；`application/analysis_options.py`；`application/start_dialog.py` |
| 物理屏幕坐标、输入选择与采集 | `application/sources.py`；`screen_geometry.py`；`region_selector.py`；`capture.py` |
| 启停、屏幕／视频／声音实时处理与 UI 事件 | `application/realtime.py` |
| 同采样 Pose／v2／周期管线与预览 | `visual_pipeline.py`；`integrated_preview.py`；`visual_lab/observations.py`；`visual_lab/stabilizer.py` |
| 原 v1 与内测图像路线 | `analyzer.py`；`analysis/flow.py`；`regional_flow.py`；`motion_focus.py` |
| v2 主体与独立运镜 | `camera_motion.py`；`motion_tracking.py`；`subject_tracking.py`；`motion_layers.py`；`region_support.py` |
| v2 轴、旋转与副轴滤波 | `dominant_motion.py`；`frame_rotation.py`；`secondary_motion.py`；`motion_reference.py` |
| v2 参考、目标与限时接续 | `point_l0.py`；`fused_l0.py`；`reach_target.py`；`interaction_point.py`；`target_baseline.py`；`target_regions.py`；`motion_rhythm.py`；`subject_continuity.py` |
| 1/4／半／全周期 | `stroke_cycle.py`；`visual_pipeline.py`（`StrokeCycleAnalyzer`） |
| Pose 后端、倍率、自动 L0、接管 | `pose_backends.py`；`directml_pose.py`；`analysis/rtm_runtime.py`；`analysis/rtm_geometry.py`；`analysis/pose_motion.py`；`pose_output.py`；`pose_l0_fallback.py`；`pose_pattern.py`；`pose_fast_fallback.py` |
| 模型选择／下载 UI 与来源常量 | `application/models.py`；`application/model_options.py`；`application/model_sources.py` |
| v2 模型登记、文件与辅助 | `v2_models.py`；`v2_model_assets.py`；`v2_model_assist.py` |
| GPU 检测／下载／安装 UI | `gpu_controls.py`；`gpu_runtime.py`；`gpu_downloads.py` |
| 声音输入／音量／强调／脉冲 | `audio.py` |
| 输出解释、曲线、倍率／限位和实时时序 | `application/output.py`；`application/travel_controls.py`；`output_curve.py`；`tcode.py`；`command_cadence.py`；`endpoint_slowdown.py` |
| 具名／五档预设与敏感度操作 | `application/presets.py` |
| 设备面板、传输、连接／手动命令／测试 | `application/device_panel.py`；`application/connection.py`；`application/manual_output.py`；`sinks.py`；`device_controls.py`；`device_test.py` |
| 录制与离线分析 | `application/video_export.py`；`recorder.py`；`analyze_video.py` 命令行路径 |
| 分析叠加画面绘制 | `analysis/preview.py`；`integrated_preview.py`；`motion_reference.py` |
| 最终模拟器与输出监视 | `application/monitor.py`；`preview.py`；`assets/osr_emu_standalone.html` |
| 侧栏、缩放与下拉布局 | `ui_layout.py`；`ui_widgets.py` |
| 独立 Lab 入口与实现 | `preview_lab_launcher.py`；根目录 `Pose-Preview-Lab/` |
| 便携构建／启动与运行检查 | 根目录 `Start.cmd`；根目录 `tools/`；`runtime_check.py`；根目录 `SR6-OSR6-Realtime-Screen-TCode.spec` |

`docs/` 中既有验证记录保留实际检查和早期失败。本指南解释行为与边界，不是新模型跑分，也不代表真实深度、接触或机械臂运动已验证。
