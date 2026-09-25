# AI Prompting Guide

Without RTM, v2 secondary axes follow confirmed significant motion/reversals and produce smooth output; this filter never changes L0.

不带 RTM 的 v2 对 L1/L2/R0/R1/R2 只跟随确认后的明显变化与方向反转，过滤小幅高频噪声并平滑输出；L0 不受此过滤影响。

## Active 2.0.0 Release

- The user designated test.25's functionality as the official **2.0.0** release. Analysis/output behavior stays at test.25; the locally prepared packaging support is included under 2.0.0, not published as test.26. Read `docs/Validation_2.0.0.md` and `tools/README-Portable.md`. Preserve old tags/packages. Publish matching source and Windows assets from clean committed source, with manifests and checksums; exclude models/GPU downloads/configs/logs and test the extracted app without external Python. Only consolidate previously built historical packages; do not create new EXEs for every old test version. Public notes are English first, then Chinese. Release copy: `docs/Release_2.0.0.md`; test.25 remains a historical source-only prerelease.

- Test.25 source publication: the user explicitly requested publication after removing the former compatibility branding. The display/product name is now `SR6/OSR6 Realtime Screen TCode`, the publication branch is `2.0.0-beta`, and the prerelease tag is `v2.0.0-test.25`. Keep old remote refs/assets and main history; this does not authorize automatic publication of later changes. Source only, no new executable package. Publication validation reran 392 isolated main tests (434.184 s), 38 Lab tests (0.346 s), bilingual/Lab launch and simulator final-command checks; settings stayed unchanged. Third-party MIT notices are included. Future packaging remains a separate task; the existing build helper is not a verified complete test.25 portable/source packager.

- Test.25: read `docs/Test_2.0.0_test25.md`. The user explicitly kept a maximum two-second estimate window. `SubjectContinuity` is a separate pixel-identity/display layer, never a camera or target observation: weak markers use fixed verified subject textures, optional relative steps require independently verified same-pair camera pixels, and pure extrapolation has no step. A? dashed boxes/axes are estimates; do not feed them into `Observation`, DominantMotion training, reach/arrival, RTM or charts. A frozen rejected image for at least .2 s stops output estimation without asserting measured subject stationarity. New-region calibration, cuts, shape/time discontinuity and reference reset clear old estimates. A single ready flash cannot renew the two-second episode; stable reacquisition requires at least three actual frames spanning .2 s.

- Test.25 output: only the default fused reference consumes weak steps. MotionRhythm shares an absolute loss episode across weak/rhythm/velocity paths, reanchors after observed flashes without renewing the deadline, and uses a 15-second period-evidence window. A stable recent velocity may bridge at most .3 s / 15% normalized travel, decelerating without inventing a reversal. Periodic continuation still needs confirmed rhythm and brakes during the last .5 s of the two seconds. Cycle mode follows only already established travel. Direct Pose, v1, other manual reference output semantics, saved/default settings and final output transformations are unchanged. When most corners fail but coarse scene structure still matches, `camera_motion.same_scene_structure` permits bounded missing-data continuation, not a new observation. Keep the hard cut/blank-frame tests. Independent rhythm tests allow 6 s periods, but the complete pipeline still has upstream 3-second center-history limitations; integrated probes confirmed 2.5/4 s improvement, not general 6 s support.

- Test.25 final verification: 392 isolated host tests passed (452.396 s), standalone Lab 38 passed (0.388 s); Chinese/English Start.cmd, Lab startup, simulator final commands and native weak/velocity preview checks passed. Final Log-only capture produced 313 statistics updates with orderly stop/worker exit and no capture or UI callback errors. Personal settings fingerprint stayed unchanged throughout this task. First full run had one missing V? label assertion, then two added display regressions reproduced stale geometry/basis issues before fixes; the final full suite includes all corrections. Source changes are confined to continuity, the camera cut distinction, pipeline integration and display; v1/direct Pose/final output code are unchanged from test.24. Real videos, long slow cycles and hardware remain limited as documented.

- Test.24 final verification: 345 isolated host tests passed (442.480 s), standalone Lab 38 passed; Chinese/English Start.cmd, Lab startup, simulator final commands and final Log-only capture passed (304 statistics updates, orderly worker exit). Native mouse selection matched pixels on the existing 100% main / 150% portrait displays. The unmodified borderless component also passed actual cross-screen capture, black-gap pixels, full virtual-canvas bounds and hidden-parent residual checks. Negative origins/other layouts remain synthetic checks; see the report for temporary diagnostic failures. Tests preserved the user's confirmed newer settings.

- Test.24: read `docs/Test_2.0.0_test24.md`. `screen_geometry.py` and `region_selector.py` are shared by the host and standalone Lab 0.2.2. Use signed physical desktop pixels, PMv2 before Tk, and a restored thread DPI context for MSS; never restore the previous global MSS DPI monkey-patch or desktop/primary-size ratios. A selection may span screens with black gaps; reject out-of-desktop/gap-only regions, never clamp negative X/Y. ScreenCapture checks size/topology. The new picker takes one in-memory snapshot after a one-time composition settling step, then releases images on close; real-time capture has no such wait. Keep English/Chinese instructions, confirmation/cancel, narrow-monitor cards and cursor/canvas coordinate separation. The normal Tk event loop must process Configure before asserting canvas size; do not add reentrant update() to native positioning helpers.

- Test.24 integration: GUI validates and snapshots the region before device startup; the screen worker never reads coordinate Tk variables. Region/source changes stop old work, increment visual generation and clear stale frames; input controls lock during live/export runs. Partially typed negative/blank entries preserve the entire previous saved rectangle, while other settings still save. Compression changes reset v1 frame history; uniformly scale thin inputs without upscaling/cropping/zero dimensions. Capture ROI and analysis size are explicitly distinct. No motion/output algorithm or 640 default change. Complete verification is recorded in the test.24 note; use `tests/run_tests.py` for isolated full checks. The user confirmed changing settings during development: preserve that newer config, not the initial hash or a guessed default.

- Test.23: read `docs/Test_2.0.0_test23.md`. `regional_flow.py` adds locally verified, spatially balanced motion of a deforming subject box, borrowing the released v1 ROI/DIS concept without changing v1. Sparse measurements remain preferred; on-demand DIS samples must pass forward/backward and photometric checks. Camera ownership is still independent. Perimeter proposals and bounded retained seeds help a small background; retain extra seeds ONLY for a minority background, since broad-background reseeding changed radial references. Keep the original rigid/patch path when deformation is negligible. Once a box is established, keep its center when cells disappear instead of jumping to a small patch. Main axes and recovery measure at that same origin; scale uncertainty accounts for spatially correlated deformation. Deforming boxes also cache the last verified frame and re-match the entire missing interval, up to 0.25 s, with independent background and dense subject verification; integrate that interval once, never just its last pair or a prediction. A fixed anchor that contradicts a stationary fitted cohort must reject recovery. Yellow now draws the persistent subject box. No new settings/default changes or downstream output changes; cycle and optional RTM share the measurement. The opt-in `python tests/compare_released_hybrid.py` audits v1 against the local v1.1.2 tag without fetching, changing the checkout, loading models or opening hardware. Same-parameter v1 math is unchanged, but released/current app defaults differ. Preserve both that distinction and the new deformation/camera/partial-cell tests.

- Test.23 final verification: 292 isolated main tests passed (420.998 s), standalone preview 28 passed; final-command simulator check, Chinese/English starts and native preview inspections passed. Live Log only: 307 statistics updates, normal stop and worker exit; personal settings fingerprint unchanged. Preserve transported corner coordinates across box updates and recovery, rather than feeding repeatedly enlarged axis-aligned bounds back into tracking. The 151-frame deformation-24 case improved from 5 to 126 ready frames, but final 20-second accumulated-position correlation was 0.789 with center drift about (-14.0, +11.6) px. Far multi-person and 5 FPS real-person samples still lose observations; do not advertise universally accurate tracking. Earlier successful test runs and higher pre-corner-fix metrics are not the final result. See the full version note for failed attempts, limits and public sample sources.

- Test.22: read `docs/Test_2.0.0_test22.md`. `subject_tracking.py` carries a persistent subject anchor A rather than recomputing it from each feature bounding box. Fixed local appearance corrects drift; real subject AND background re-matches against the last verified frame (up to 0.25 s) recover the whole missed interval, never a guessed measurement. Finish initial calibration first using explicit subject confirmation (repeated frames cannot bypass it). A moving recovery that contradicts the primary route waits for another frame; recent anchor pixels may confirm a pause despite initial appearance changes only with sufficient texture/contrast and broad cohort support; moving recovery still requires the persistent anchor. Recovered raw correspondences still feed rotation analysis. Do not confirm exposed background in an old ROI as a paused subject. Relative scale below fit resolution is suppressed consistently on both routes. `reach_target.py` caches independent object pixels, preserving identity across missing source/camera pairs only if its own pixels still verify; no reach ratio without both sides. Fusion marks inferred reciprocal endpoints as V? assumed objects, distinct from T? independently tracked candidates. Neither proves semantic contact. Target flapping must not restart the output offset every frame: after loss, require 0.3 s continuous readiness and at least 0.4 s before re-entry, following subject motion meanwhile. The existing confirmed-rhythm 2 s continuation and cut/pause clearing stay in place. V1/direct Pose/final output and saved/default settings are unchanged; cycle/optional RTM rotations share v2. Full validation and remaining blur/deformation/occlusion limits are in the test.22 document.

- Test.21: read `docs/Test_2.0.0_test21.md`. In fusion, orange T? now means an independently tracked object-boundary candidate, not test.20's external convergence. `target_regions.py` nominates reachable boundaries beyond the measured source path; `reach_target.py` verifies the target's own distributed points, robust transform and appearance. Different source/target appearance is allowed. Valid axis-origin-to-target Euclidean distance, normalized by observed retreat, drives L0 (arrival 100% = bottom before gains). Never substitute the object front edge, screen edge or |distance to C|. Confirmed target transitions are continuous; passing a candidate invalidates it rather than doubling frequency. Source tracking and target tracking can fail independently; only measured source and target positions produce a reach percentage. Camera-only transport cannot confirm a lost target. Missing camera registration discards its coordinates before re-entry; cuts clear all old target/rhythm evidence. If either/both contact objects were never visible, immediately use visible-object reciprocal motion once measured; never require or invent a target. Unknown reach is labeled as a proxy; only actual motion loss invokes the existing 2 s rhythm continuation. Cycle/RTM-rotation variants share it, retain discrete peaks/cosine shape, and finish confirmed paused arrivals continuously. Saved/default settings and final output path are unchanged. Full verification and limits are in the test.21 document.

- Test.20: read `docs/Test_2.0.0_test20.md`. Do not label an axis-derived trajectory endpoint as T?: E? is a trajectory endpoint, S? an internal expansion center, and T? an external convergence candidate (never semantic contact). This distinction is display-only and must not move point coordinates or change output polarity. `interaction_point.py` uses radial support/uncertainty instead of a fixed per-frame scale threshold and weights point smoothing by uncertainty. `target_baseline.py` re-tracks bounded foreground/background samples against an existing older frame, independently validates its camera fit, and uses it only to locate a candidate. Current-pair radial increments still supply L0; never integrate the longer baseline twice. It disables expensive patch recovery for this extra pass; main tracking retains it. Missing-point camera transport cannot renew confirmation/timeout. v1, direct Pose, final output mappings, saved/default references and 2 s continuation stay intact. Real semantic targets, weak planar motion and occlusion remain limitations.

- Test.19: read `docs/Test_2.0.0_test19.md`. `fusion` is the new default v2 L0 reference; preserve valid saved motion/center/interaction choices. `fused_l0.py` aligns polarity before mixing axis increments, center phase and qualified radial evidence. Away is high L0, toward is low; the individual interaction option is inverted accordingly. Never use absolute distance to C (it doubles frequency). `motion_rhythm.py` learns only observed phase, requires steady reciprocal evidence and stops after 2 s with 0.5 s phase-speed braking. Predictions do not restore observation confidence; `generated_l0` explicitly permits only L0 output through the existing output gate. Pauses/cuts/shape changes/recalibration stop it, re-entry stays continuous. Only handoff anchors may use applied/pre-gain output, never recognition. Cycle mode retains discrete peaks and cosine easing with the same fused phase/continuation. `region_support.py` balances spatial groups and retains measured foreground seeds; keep background/region validation before averaged measurement refinement, preserve seeds across identical frames, and never guess missing points. T? and predicted/held labels must describe actual evidence. Direct Pose/v1 and final hardware mappings remain unchanged; no new model/dependency.

- Test.18: read `docs/Test_2.0.0_test18.md`. `motion_focus.py` selects current reciprocal > formerly reciprocal and still tracked > sustained amplitude, with temporal switching. Both full regions and validated local patches retain endpoint-linked history. Compact fast support still requires independent background and well-distributed inliers; never accept arbitrary jumps. `interaction_point.py` estimates only a radial-flow candidate, not semantic contact. `point_l0.py` provides optional center/interaction L0 with relative source transitions; original motion remains default. `v2_l0_reference` is output-only, must not reset camera analysis or receive final gains as observations. Preserve saved/default/translated controls, full/half discrete stroke behavior and the shared final output chain. Severe blur/deformation and real footage remain limitations.
- Test.17: read `docs/Test_2.0.0_test17.md`. Device writes raise `OutputWriteError`; `_emit_command` queues one sink-tagged failure, `_finish_output_failure` handles it on Tk, disconnects and prompts, ignoring stale sinks. Never auto-retry a rejected device command or broadcast it to the simulator. Disconnected serial/BLE and incomplete serial writes are errors; capture/model errors remain distinct.
- V2 repeated identical frames must retain background ownership/history, report zero step and avoid duplicate integration. Repeated rejected frames cannot restore confidence or extend the existing loss grace period; blank startup frames remain missing features. `motion_dt` measures time between distinct images for cycle activity. `motion_layers.py` additionally validates neighboring residual-flow agreement for non-rigid foregrounds; keep background extent, ownership and uncertainty requirements. When the connected foreground cannot fit one transform, `camera_motion.py` searches bounded affine patches with all-track validation, prioritizing the existing region. Mark `local_model=patch` in actual preview snapshots; never silently imply whole-body or physical 3D tracking. Shared v2/cycle analysis, original v1 and Pose gains remain separate.

- Test.16: read `docs/Test_2.0.0_test16.md`. Small signed components must not be discarded by a fixed cardinal amplitude gate. Establish per-component sustained reversals relative to range, then require absolute reciprocal evidence along the combined candidate. Start evidence from observed extremes regardless of initial phase, and reject jitter legs with poor net progress / path-length consistency. Cycle activity is projected main-axis speed using source timestamps (1.2 image percentage points/s), not maximum component displacement per frame. Preserve camera separation, shared v2/cycle analysis, final mapping and preview truth.

- Test.15: read `docs/Test_2.0.0_test15.md`. V2 now fits a continuous orthonormal, right-handed local frame in up/image-scale/right coordinates. Use signed covariance cross terms of reciprocal motion, reject one-way drift and ambiguous directions, and transport transverse axes together with a stable positive end. L0/L1/L2 integrate future motion projected onto this frame; do not remap accumulated offsets. Rotation-proxy increments use the same frame. `primary` and `weights` are diagnostics only: do not restore categorical routing. `StrokeCycle` must use the actual projected `stroke_evidence`, not `evidence[primary]`. Keep no-RTM secondary filtering, exact v1 numerical behavior and direct Pose outputs. The preview shows the actual basis at the ROI and in an oblique inset; scale is not physical depth or robot kinematics.

- `pose_fast_fallback.py` is a separate default-on Pose output option: recent valid Pose loss plus fast v1 ROI motion enables L0-only fallback. Test.14 keeps the unchanged v1 analyzer running on every sampled Pose frame while enabled; no new inference/capture. On entry use the current applied L0 (undo travel/inversion/limits/ramp), or the fitted script position for export, and follow subsequent v1 deltas. Never relocate to the v1 absolute origin or feed applied output into recognition. Cuts/long gaps/static or startup loss do not authorize v1 by absence alone. Preserve truth of Pose observations/confidence, v1 reference display, continuous relative entry and 0.2 s return, and no ×10 gain/pattern feedback for fallback L0.
- For Pose handoff details read `docs/Test_2.0.0_test14.md`. Test.13: read `docs/Test_2.0.0_test13.md`. `pose_l0_fallback.py` generates Pose-only L0 after stillness or when L0 is small and R1/R2 is clearly larger; priority R1 then R2, midpoint→one-third L0, either end→two-thirds. Only when another observed axis is moving may still R1/R2 fall back to a quarter-to-half 1 s cosine. If every observed axis is still/missing, hold the current target and never generate a wave. Do not use generated output as activity evidence. Default on; never reapply the L0 ×10 gain or curve smoothing to generated L0. Keep actual observations/confidence unchanged and label generated sources. Only valid upward hips can trigger stuck-end L0 output-reference rebasing; do not substitute timeout-only recovery.
- `pose_pattern.py` independently detects about three small steady cycles per L0/R0/R1 axis (never L1/L2/R2), then ramps output to at most 2× over 1 s (4x the former growth rate), releasing on growth/rhythm loss/missing observations. Default off. Never detect from generated L0, recovery transitions, user gains or presets. Output-only toggles preserve image references and each other's state. Pose R0 base gain is ×3, R1/R2 ×1.5, direct Pose L0 ×10. Hardware-only Pose L1/L2 coupling adds a low knot: (0, .5), (1/3, 1), (2/3, 3.5), (1, .5). Pose hardware R1/R2 now use 1× at L0 0 and 2/3, then linearly 0.5× at L0 1, computed from the same limited L0. Keep this separate from the ×1.5 base gain and auto-L0 source observations. R0 and V2 stay unchanged. Both UI entry points, saved profiles, defaults, offline/live and simulator routing must remain synchronized.

- Test.12: read-screen fast window dragging is the user's reproduction. `motion_tracking.py` uses measured fine-scale flow and bounded unique patch matches to initialize failed/ambiguous fast tracks; every propagated guess must pass current-pair LK/photometric checks. `camera_motion.py` reserves peripheral samples and requires a strong fit for translations above 6%, with a hard 20% cap and unchanged scale/cut gates. `motion_layers.py` allows up to six groups and independently moving foreground parts. Never replace missing background with raw global motion. Preserve the fast-window, pure-camera, textured-cut and close-up regression scenes.
- Test.12 output: direct Pose L0 is ×10; pose-derived R1/R2 are ×1.5, including optional hybrid/cycle rotations. Other image rotations are unchanged. `command_cadence.py` measures the median of up to five actual live updates; TCode uses this as an arrival-time floor before endpoint slowdown. The saved `output_interval_ms` field still defaults to 24, now labeled Minimum arrival time. It is not a send-rate scheduler. Offline script timestamps remain based on source time; manual/emergency center resets/bypasses cadence. Keep the final sink and simulator identical. See `docs/Test_2.0.0_test12.md` for physical-jitter limitations.

- Test.11: `motion_layers.py` separates competing similarity motions before camera assignment in large-foreground close-ups; a coherent peripheral minority can become the background after two frame-pair confirmations. `camera_motion.py` also uses up to four past frames / 0.2 s for discovery, fitting only CURRENT-pair camera motion for integration. Never accumulate the longer discovery displacement into L0.
- Confirmed minority backgrounds have priority over majority fits. Replenish their corners near the same background patch; never promote the foreground when that patch is occluded. Coherent region tracking measures small motion and propagates the ROI with its transform, avoiding a shrinking corner bounding box. Broad/background-band routes still handle ordinary scenes. Hard cuts clear the background lock. Preserve camera-only, occlusion, quarter-cycle and old direction tests. No new model/dependency is required; default max edge stays 640.

- Test.10: v1 is now Recommended - Large Planar Motion; preserve its exact numerical baseline and migrate both old Internal Test names. V2 accepts spatially coherent background bands and freshly tracked known-background points, preserving references across a maximum 0.45 s brief loss without inventing observations. `DominantMotion.hold` and `StrokeCycle.hold` advance time but do not generate movement. Sustained invalid measurements still reset.
- `camera_motion.py` borrows v1's three-frame median after compensation; retain actual tracked endpoints for rotations. Full/Half Travel now adds quarter travel: minimum reciprocal span .85, quarter→half at 3 / half→quarter below 2.4, full at 8 / back below 6. Keep reciprocal/noise gates, gradual cadence, real export routing and optional pose rotations. See the test.10 guide for validation and unresolved real-clip risks.

- Test.9: `StrokeCycleAnalyzer` subclasses the real v2 `LabAnalyzer`; never copy/fork camera or dominant-motion analysis into the new Full/Half Travel mode. It is listed first, with v2 still selected by default. `stroke_cycle.py` uses confirmed reciprocal span, hysteresis (full at 8 image percentage points, half below 6) and gradual cadence adaptation for cosine L0 cycles. Optional RTM 2D supplies rotations; L1/L2 stay centered.
- `endpoint_slowdown.py` changes final arrival times ONLY, never target coordinates. Main and startup dialog default on with distance 10%, range 1–50%. `tcode.py` extends I times after gains/limits/coupling; the recorder extends final script timestamps with the same approach rule. Keep exact simulator sink-command forwarding, default/save/reset and both languages synchronized. Exported timing may drift from the original video; manual/emergency centering bypasses this layer.
- V2 accepts sparse but spatially supported background features and moving subjects near edges. Keep camera-only rejection tests for both sparse and blurred backgrounds. `MotionReference.reason/counts` explain insufficient evidence; do not fabricate local motion on flat or inseparable images.

- Current local source test: `2.0.0-test.24`; historical published BETA is `2.0.0-test.3`, formal release is `1.1.2`. Test.23 verified the v1.1.2 tag read-only; no remote release was updated. Current scope: visual analysis and robot-arm simulation experiments, not verified robot-arm control.
- Test.9 uses `camera_motion.py` for camera-relative local movement. Do not restore whole-frame motion as the v2 control input. Missing independent background/region evidence must not become camera-driven motion. `dominant_motion.py` enables confirmed-stroke calibration only on this compensated path; it does not change user presets or auxiliary observations.
- `motion_reference.py` snapshots the actual ROI/selected vectors/background points for in-image rendering. V1 only adds diagnostics; preserve its recorded numerical regression. Recalibrate clears reference history in both hybrid versions. Keep notes readable without obscuring the right reference image.
- `pose_output.rtm_l0_amplitude` applies dance L0 ×10 once, about center, for both axis modes and shared live/record/export routing. Apply only to tracker mode RTM Pose 2D, not v2 with pose rotation assistance. Keep pose observations and the final simulator sink-command path unchanged.
- `dominant_motion.py` uses sustained reciprocal stroke evidence to fit a continuous 3D image-proxy axis, with vertical only as the unconfirmed starting frame. Do not restore absolute-speed-only selection: one-way camera pans/zooms then steal L0. Remap future increments, not accumulated offsets. Keep single/six-axis L0 identical; true camera/subject separation remains unverified.
- `analysis_preferences.py` saves dance/hybrid settings independently. Dance starts at 45 FPS with all four pose options on, GPU/blending off, blend weight 30% and latency 0. Full/Half Travel is first in the menu, followed by RTM 2D; Hybrid v2 remains the selected default. Conditional dance blending uses v2 only. Keep main/popup/save/reset and both languages synchronized.
- Output Monitor opens by default. Show Preview opens the bundled simulator. Broadcast only the final command accepted by the current sink after all host mapping and limits; do not forward raw analysis or apply gains twice. The HTML direct-command path must suppress OFS/default animation writes. Test with `node tests/test_simulator_stream.cjs` as well as the Python suite. Actual 3D rendering was not visually verified in test.7 because browser policy blocked the local file URL.
- `capture.py` owns a latest-frame-only MSS producer. Create/close MSS on its own thread, keep one frame slot, and never read Tk variables from the producer. Capture FPS is not model inference FPS.
- `pose_output.py` defines RTM output gains. `tcode.py` uses each command's already limited L0 for L1/L2 coupling: direct RTM Pose 2D rises linearly from 0.5 at low L0 to 3.5 at **2/3 travel**, then falls to 0.5 at high L0 (test.11). V2 retains 1/2.5/1 with a central peak, even with pose rotation assistance. Never feed amplified translations back into observations or script analysis data. `output_curve.py` provides optional default-on One Euro smoothing for all analysis outputs. Keep filter state per run/thread, use video timestamps for offline export, and never delay emergency/manual centering through this layer. See `docs/Test_2.0.0_test11.md`.
- Read `docs/Device_Compatibility_2.0.md` before changing device support.
- Commercial-device adapters have been removed. `device_controls.py` contains native SR6/OSR6 TCode UI only. Do not restore removed device profiles from saved settings.
- Preserve the original analysis files and TCode mapper. Keep device I/O asynchronous and test stopping, stale output and reconnect identity.
- Test settings are isolated in `.osr_screen_tcode_2_0_test`. Do not package tests or include models.
- Display the device name as `SR6/OSR6`. Cooperation/copyright contact: `aivnailedeng@gmail.com`.
- 不要宣称已支持机械臂；关节映射、碰撞检查和实际反馈均未验证。
- `visual_pipeline.py` ports Lab 0.2.1 processing into the host; `integrated_preview.py` displays paired frames from that worker. The standalone lab remains a separate reference. Read `docs/Test_2.0.0_test11.md` before touching this route. Hybrid 1 keeps its original L0 core (Recommended - Large Planar Motion). Hybrid v2 (Recommended Non-Dance) uses adaptive dominant image motion for L0 and residual L1/L2, with optional RTM 2D rotation assistance or experimental image rotation estimates. Only the optional blend into RTM remains L0-only. The five presets affect final script/live travel, never analysis settings or state. First use and Reset default to Hybrid v2 without RTM assistance; preserve existing saved choices. RTM 3D is removed; do not restore its backend or model selection.
- Measurement/axis limits default open on first use and reset; preserve a later saved collapse choice.
- `gpu_runtime.py` / `gpu_downloads.py` / `gpu_controls.py` own optional CUDA/DirectML installation for source and portable builds. Frozen builds run bundled pip and GPU probes in hidden child processes via `__main__.py`. Publish only a separately verified runtime overlay in the test user directory, never numpy/OpenCV. Report real downloaded bytes and installation stages. Restart after installation/backend switching; never modify the formal runtime. `directml_pose.py` only adapts the inference session, preserving rtmlib's pose algorithms. Never package downloadable models or optional GPU runtimes.
- Use `ui_widgets.WideCombobox` for new dropdowns so complete option text remains accessible independently of sidebar width. GPU backend choice is a shared, saved preference in both model settings and the start dialog.
- Display the name `SR6/OSR6 Realtime Screen TCode`. The test.25 source publication removes broad-compatibility branding; do not reintroduce unsupported hardware claims. Keep Python/CLI and repository identifiers compatible. Future package filenames replace `/` with `-`; never use literal asterisks.

Use this guide when asking an AI coding assistant to continue work on **SR6/OSR6 Realtime Screen TCode**. It gives the assistant enough project context to make small, careful changes without damaging stable behavior.

## Project Context

- Project name: SR6/OSR6 Realtime Screen TCode.
- Platform: Windows desktop app.
- Current formal version: v1.1.2.
- Main purpose: read a selected screen region in realtime, analyze visible motion with low latency, and output TCode to OSR/SR6/OSR6-compatible devices through USB serial or BLE.
- Important stable feature: L0 output is the most important stable path. Do not rewrite the formal L0 core unless explicitly requested.
- Experimental area: RTM Pose 2D dance analysis, optical-flow assist, Kalman fusion, and six-axis motion quality.

## Good Starting Prompt

```text
You are the feature-development AI for this SR6/OSR6 Realtime Screen TCode project.
Do not rewrite the whole project. First read the existing source, then make the smallest safe change.
Keep L0 stable unless I explicitly ask to change it.
If UI text changes, update both English and Chinese.
If settings change, update save/load/default behavior.
For test versions, update source and Start.cmd behavior only; do not package unless I ask.
For formal releases, update changelog, README/manuals when needed, build the Windows portable folder and zip, and confirm the zip does not include .git, caches, local models, or private paths.
After finishing, tell me what changed, which files changed, how it was verified, risks, and what to do next.
```

## Files To Read First

- `README.md`: user-facing overview, download notes, and current feature summary.
- `CHANGELOG_CN.txt` and `docs/版本日志.txt`: version history.
- `src/osr_screen_tcode/app.py`: main UI, preview, user controls, realtime start flow.
- `src/osr_screen_tcode/analyzer.py`: screen analysis, pose/RTM position calculation, smoothing, axis output.
- `src/osr_screen_tcode/config.py`: settings defaults and persistence.
- `src/osr_screen_tcode/tcode.py`: TCode formatting and output path.
- `src/osr_screen_tcode/sinks.py`: USB serial and BLE connection handling.
- `src/osr_screen_tcode/pose_backends.py`: local RTM Pose model loading and inference helpers.

## Development Rules

- Keep changes scoped to the requested feature.
- Preserve existing UI style and ordinary-user workflow.
- Keep dangerous device motion protected by limits, speed caps, presets, and output clamping.
- Treat `Log only` as the safest preview/debug mode.
- Do not include local ONNX models in source releases or Git commits.
- Do not push to GitHub or rewrite Git history unless the user explicitly asks.
- Prefer readable, conservative changes over large refactors.

## UI And Settings Rules

- New controls should be visible, clearly named, and have short help text when useful.
- English and Chinese UI strings should stay synchronized.
- New settings need default values, save/load support, and restore-default behavior.
- Fold advanced or mode-specific settings when possible so the main UI stays approachable.
- RTM Pose model controls should appear only when an RTM Pose mode is selected.

## Test Version Rules

- Test versions are for quick iteration.
- Usually no portable zip is needed for test versions.
- Keep a one-click source launcher such as `Start.cmd`.
- Use test version names such as `1.1.1-test.29` until the user approves promotion.

## Formal Release Rules

For a formal release, prepare:

- Windows portable release folder with exe, `Start.cmd`, required dependencies, README, quick start, manuals, changelog, license, and acknowledgements.
- Windows zip named with the approved version, for example `SR6-OSR6-Realtime-Screen-TCode-v2.0.0-Windows.zip` (future formal build).
- Source zip named with the approved version, for example `SR6-OSR6-Realtime-Screen-TCode-v2.0.0-Source.zip` (future formal build).
- No `.git`, cache folders, local privacy paths, model files, `.onnx` files, or development build leftovers in the zips.
- Extract-and-run startup check for the Windows zip when packaging has changed.

## RTM Pose Notes

- RTM Pose 2D is recommended for lower-latency dance analysis.
- RTM Pose 3D has been removed from the active test application.
- GPU acceleration is optional and should default off unless explicitly changed.
- If GPU/CUDA is unavailable, the app should explain the fallback and continue on CPU when possible.
- Optical-flow assist and Kalman fusion are lightweight helpers for smoother keypoints, not replacements for model detection.

## Verification Checklist

- Run the complete main suite with `python tests/run_tests.py -v`; it redirects settings, preview and runtime paths to a temporary directory before GUI imports and checks the original configuration fingerprint. Do not substitute direct discovery for this isolated entry point. Keep GUI cleanup inside any save mock. During test.22 development a delayed cleanup overwrote local test preferences; no original was recoverable, and the local configuration was reset to defaults with Log only. See the incident record in `docs/Test_2.0.0_test22.md`; never describe this as restoring the user's original settings.
- For code changes: run syntax/import checks that the project supports.
- For realtime/start-flow changes: start the app and confirm it does not exit immediately.
- For packaging changes: rebuild the affected zip, scan contents, extract to a temporary folder, and launch the exe.
- For README-only changes: text search is usually enough unless the user asks for packaging.

---

# AI 提示词指南

当你想让 AI 编程助手继续开发 **SR6/OSR6 Realtime Screen TCode** 时，可以把这份指南作为固定上下文。它能帮助 AI 在现有源码基础上做小而稳的修改，避免破坏已经稳定的功能。

## 项目背景

- 项目名称：SR6/OSR6 Realtime Screen TCode。
- 平台：Windows 桌面软件。
- 当前正式版本：v1.1.2。
- 核心用途：实时读取用户框选的屏幕区域，低延迟分析画面运动，并通过 USB 串口或 BLE 向 OSR/SR6/OSR6 兼容设备输出 TCode。
- 重要稳定功能：L0 输出是当前最重要、最稳定的路径。除非明确要求，不要重写正式版 L0 核心逻辑。
- 实验方向：RTM Pose 2D 舞蹈分析、光流辅助、卡尔曼融合、六轴运动质量优化。

## 推荐起始提示词

```text
你是这个 SR6/OSR6 Realtime Screen TCode 项目里的功能开发专用 AI。
不要重写整个项目。先读现有源码，再做最小、安全的修改。
除非我明确要求，否则保持 L0 稳定。
如果修改 UI 文字，记得同步中文和英文。
如果修改设置项，记得同步保存、读取和恢复默认逻辑。
测试版只需要源码和 Start.cmd 能运行，除非我要求，否则不要打包。
正式版需要更新版本日志、README/手册，重新生成 Windows 免安装文件夹和 zip，并确认 zip 里没有 .git、缓存、本地模型和隐私路径。
完成后告诉我：改了什么、哪些文件变了、怎么验证、有什么风险、下次可以继续做什么。
```

## 开始前优先阅读的文件

- `README.md`：项目简介、下载说明、当前功能摘要。
- `CHANGELOG_CN.txt` 和 `docs/版本日志.txt`：版本记录。
- `src/osr_screen_tcode/app.py`：主界面、预览、用户控件、实时输出启动流程。
- `src/osr_screen_tcode/analyzer.py`：屏幕分析、pose/RTM 位置计算、平滑、各轴输出。
- `src/osr_screen_tcode/config.py`：设置默认值和本地保存。
- `src/osr_screen_tcode/tcode.py`：TCode 格式和输出路径。
- `src/osr_screen_tcode/sinks.py`：USB 串口和 BLE 连接。
- `src/osr_screen_tcode/pose_backends.py`：本地 RTM Pose 模型加载和推理辅助。

## 开发原则

- 修改范围尽量贴近用户要求。
- 保持现有 UI 风格和普通用户操作流程。
- 危险设备运动必须继续受上下限、限速、预设和输出夹紧保护。
- `Log only` 是最安全的预览和调试模式。
- 不要把本地 ONNX 模型加入源码发布包或 Git 提交。
- 不要主动 push 到 GitHub，不要重写远程历史，除非用户明确要求。
- 优先做保守、可读、可验证的小改动，避免大重构。

## UI 和设置规则

- 新控件要清楚可见，名称直观，必要时加简短说明。
- 英文和中文 UI 文案要同步。
- 新设置需要默认值、保存/读取逻辑，以及恢复默认支持。
- 高级设置或模式专属设置尽量折叠，避免主界面太乱。
- RTM Pose 模型相关控件只应在选择 RTM Pose 模式时展开。

## 测试版规则

- 测试版用于快速迭代。
- 测试版通常不需要重新打 Windows 免安装 zip。
- 保留一键源码启动入口，例如 `Start.cmd`。
- 用户确认通过前，使用类似 `1.1.1-test.29` 的测试版号。

## 正式版打包规则

正式版需要准备：

- Windows 免安装发布文件夹，包含 exe、`Start.cmd`、必要依赖、README、简易教程、用户手册、版本日志、许可证和鸣谢。
- 带批准版本号的 Windows zip，例如 `SR6-OSR6-Realtime-Screen-TCode-v2.0.0-Windows.zip`（后续正式版）。
- 带批准版本号的源码 zip，例如 `SR6-OSR6-Realtime-Screen-TCode-v2.0.0-Source.zip`（后续正式版）。
- zip 里不能包含 `.git`、缓存目录、本地隐私路径、模型文件、`.onnx` 文件、开发构建中间产物。
- 如果重新打包了 Windows zip，要解压到临时目录并启动 exe，确认不会闪退。

## RTM Pose 注意事项

- RTM Pose 2D 更适合低延迟舞蹈分析。
- 当前测试版已移除 RTM Pose 3D，不要恢复该分析入口。
- GPU 加速是可选项，默认应关闭，除非用户明确改变。
- 如果 GPU/CUDA 不可用，软件应显示原因，并尽量自动回退 CPU。
- 光流辅助和卡尔曼融合是让关键点更平滑的轻量辅助，不是完全替代模型检测。

## 验证清单

- 主程序完整检查使用 `python tests/run_tests.py -v`，在界面导入前将设置、预览和运行时路径隔离到临时目录，并核对真实配置指纹。不要用直接发现测试替代此入口；关闭窗口必须发生在写入屏蔽仍有效时。test.22 开发时曾因延后清理覆盖本机测试偏好，未找到可恢复的原配置，已设为默认值并用 Log only。事故见 `docs/Test_2.0.0_test22.md`，不能称为恢复原设置。
- 改代码后：运行项目支持的语法/导入检查。
- 改实时输出或启动流程后：启动软件，确认不会立刻退出。
- 改发布包后：重新生成对应 zip，检查内容，解压到临时目录并启动 exe。
- 只改 README 或普通文档时：通常做文字搜索确认即可，除非用户要求重新打包。
