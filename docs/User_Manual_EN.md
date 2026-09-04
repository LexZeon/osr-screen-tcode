# OSR6 Realtime Screen TCode User Manual

Current version: `1.1.2`. For version history, see `version log` / `版本日志.txt` in the app folder.

> **Adults only: this software is intended for adults. Minors are prohibited.**
>
> **Six-axis warning: use Six Axis only when lighting is good, the main subject is clear, and the selected screen region is clean.** If the image is dark, crowded, heavily cropped, or full of unrelated motion, start with `L0 Only` or `Log only` preview.
>
> Before your first real session, use Measurement Mode to save comfortable safe upper and lower limits. These limits are stored locally on your computer. If output works normally next time, do not restore defaults again unless you intentionally want to reset everything.

## Overview

OSR6 Realtime Screen TCode is a local Windows tool for OSR/SR6/OSR6-style TCode-compatible devices. It can read a selected screen region, video file, or audio rhythm, then convert the detected motion into realtime TCode output through USB serial or BLE UART.

The app saves the main settings locally, including limits, travel scales, play preset, six-axis sensitivity, serial/BLE information, audio settings, and advanced tuning. On the next launch, the app keeps your previous values.

The recommended non-dance analysis mode is `Hybrid Analysis (Recommended - Non-Dance)`. It uses a lightweight mixed ROI optical-flow approach: it focuses on the main moving region, then estimates direction and strength. In practice, it tends to feel more responsive than simple motion-center tracking and less likely to slam every movement to the extremes than a pure direction detector.

Recommended first-use flow:

1. Before connecting hardware, set output to `Log only` and check that the curve looks stable.
2. Select only the main moving screen region.
3. Start with play preset `3`.
4. Use `L0 Only` first to confirm direction and travel.
5. Connect the OSR6, click `Connect + Center`, then run `Medium Test`.
6. When it feels stable, gradually widen per-axis limits or increase the preset.
7. Click `Show Preview` when you want to inspect the final limited output before driving hardware.

## Startup

In the extracted folder, double-click:

```text
OSR6-Realtime-Screen.exe
```

You can also double-click:

```text
Start.cmd
```

Startup has two dialogs:

1. Adults-only warning. Continue only if you are 18+ and legally allowed to use this type of software in your location.
2. Language selection. Choose `English` or `中文`.

## Device Connection

### USB Serial

1. Connect the OSR6 controller to the computer.
2. In `Device Connection`, set output to `Serial COM`.
3. Click `Refresh`.
4. Choose the correct COM port.
5. Use `115200` baud unless your firmware uses another speed.
6. Click `Connect + Center`.
7. Click `Query Device Axes` to check available firmware axes. A normal OSR6 setup should expose at least `L0/L1/L2/R0/R1/R2`.

If connection fails:

- Unplug and reconnect USB.
- Try another data cable.
- Make sure no other app is using the same COM port.
- Try another baudrate, such as `9600`, `57600`, or `250000`.

### Bluetooth

Bluetooth usually appears in one of two ways:

- Windows maps the device to a COM port. In that case, use `Serial COM`.
- The device exposes BLE UART. In that case, select `BLE UART`, scan, then confirm the write UUID.

If pairing asks for a code, common values are `1234` or `123`.

## Realtime Monitor

The right side of the main window shows the live monitor:

- Current `L0` output value.
- Whether the output is moving toward the lower side, upper side, or staying near the middle.
- Current L0 lower/upper limits.
- Screen activity or audio activity.
- Six-axis bar monitor.
- The recent real output curve.
- The latest TCode command.

The script curve shows the final value after limits, travel scaling, speed limiting, smoothing, deadzone, and six-axis sensitivity. It is not the raw analyzer value.

## Play Presets

The `1 2 3 4 5` buttons at the top are one-click play presets.

- `1`: slower, softer, smaller travel.
- `2`: gentle.
- `3`: default recommended preset.
- `4`: faster and more active.
- `5`: stronger and more intense.

Presets adjust feel parameters such as speed, smoothing, deadzone, activity threshold, visual travel, L0 travel scale, and six-axis travel scale. They do not overwrite per-axis mechanical limits.

## Six-Axis Tuning

`Six-Axis Tuning (Hybrid Analysis Only)` is recommended for `Hybrid Analysis (Recommended - Non-Dance)`. `Six-Axis Sensitivity 1..10` switches to `Six Axis` and adjusts how strongly `L1/L2/R0/R1/R2` follow the L0 rhythm and visual side motion. RTM Pose 3D output does not use these helper sliders.

- `1`: steadiest and least sensitive.
- `5`: current default.
- `6..10`: more sensitive and more intense.

If Six Axis jitters, move `Six-Axis Stabilizer` to the right or click `Stable Six-Axis Preset`. This reduces non-L0 sensitivity and adds smoothing. It does not affect L0.

If auxiliary axes are too weak, widen their per-axis limits slightly, raise `Overall Strength`, or increase the individual axis gain.

Hover over buttons, sliders, and parameter labels to see short tooltips explaining what each item does.

`Show More Settings` contains less common controls such as input source, audio, region coordinates, and advanced analysis parameters. For normal use, you can keep it collapsed.

In RTM Pose 2D/3D dance modes, `RTM Optical Flow Assist` and `RTM Kalman Fusion` are enabled by default. Optical flow tracks the existing skeleton keypoints between model detections, and Kalman fusion uses those tracked points as prediction plus RTM detections as correction. `RTM GPU Acceleration` remains off by default; when enabled, the app tries CUDA and falls back to CPU if CUDA is unavailable.

## Starting Realtime Output

When you click `Start Realtime Output`, the app switches to screen realtime mode and opens a confirmation dialog.

In that dialog you can:

- Confirm the screen region.
- Choose `L0 Only` or `Six Axis`.
- Select an analysis mode.
- Enable or disable `Pose Bias for L0` and `Pose Bias for Six Axis`.
- Adjust pose weights.
- Start only after you confirm your safe limits.

`Restore Defaults` is above `Start Realtime Output`. It resets screen region, input source, output method, serial/BLE information, per-axis limits, L0/six-axis travel scales, presets, six-axis tuning, audio settings, and advanced settings. It also overwrites locally saved configuration, so use it intentionally.

`Show Preview` opens the OSR6 3D preview. It shows the same limited TCode output that would be sent to hardware.

## Screen Region Selection

Use `Select Region` to choose the screen area to analyze.

The fullscreen selector shows:

- A dashed blue rectangle for the current saved region.
- Crosshair lines under the mouse.
- Live width, height, X, and Y while dragging.
- A confirmation panel after releasing the mouse.

Shortcuts:

- `Enter`: use the selected region.
- `R`: select again.
- `Esc`: cancel.

Only select the main motion area. Avoid subtitles, comments, player controls, flashing borders, and unrelated movement.

## Input Sources

### Screen

Reads a selected screen region in realtime. This is the normal mode for playing a video while controlling the device.

### Video File

Reads a local video file. You can analyze it directly or export `.funscript` files with `Analyze Video + Save Script`.

### Audio Only

Reads audio only and does not analyze the screen. This is useful for rhythm-heavy videos or music-driven use.

Audio device suggestions:

- `System Output`: listens to sound currently playing on the computer.
- `Default Input`: uses the default microphone or input device.

Audio modes:

- `Audio Level`: louder sound maps to higher output.
- `Dynamic Accent`: follows dynamic audio intensity.
- `Beat Pulse`: reacts to beat-like rises.

## Output Modes

### L0 Only

Outputs only the vertical `L0` axis. This is the most stable mode and the best first test.

### Six Axis

Outputs all six axes:

| Axis | Meaning |
| --- | --- |
| `L0` | Vertical stroke |
| `L1` | Surge |
| `L2` | Sway |
| `R0` | Twist |
| `R1` | Roll |
| `R2` | Pitch |

Six-axis output is a realtime heuristic estimate, not a hand-authored multi-axis script. Tune `L0 Only` first, then try `Six Axis`.

## Travel And Limits

### Per-Axis Limits

Every axis has its own lower and upper limit. These are hard boundaries. The app will not output past them.

Suggested first real-device range:

```text
L0: 2500 .. 7500
Other axes: 4000 .. 6000 or narrower
```

Widen limits slowly after confirming direction and comfort.

### Measurement Mode

Measurement Mode lets you manually move a selected axis and save safe limits.

Use it like this:

1. Stop realtime output.
2. Connect the device and confirm `Emergency Center` works.
3. Choose the axis to measure. Default is `L0`.
4. Move the `Position` slider slowly.
5. When the current position is a safe lower limit, click `Save as Lower`.
6. When the current position is a safe upper limit, click `Save as Upper`.
7. Click `Center Axis` to send the selected axis back to `5000`.

If you do not want dragging to send immediately, disable `Send While Sliding`, then click `Send Current Position` manually.

Measurement Mode sends raw TCode positions from `0..9999`. Start near `5000` and expand slowly.

### L0 Travel Scale / Six-Axis Travel Scale

These sliders scale motion around the center without changing saved limits.

- `L0 Travel Scale`: affects only L0.
- `Six-Axis Travel Scale`: affects L1/L2/R0/R1/R2.
- Left: smaller motion.
- `1.00x`: default.
- Right: larger motion.

Even at high scale, output stays inside each axis limit.

### Visual Travel

`Visual Travel` controls how much detected visual motion becomes device travel.

- Lower values feel closer to the actual visible movement.
- Higher values reach wider travel more easily.

If the on-screen motion is not full range but L0 keeps reaching both extremes, reduce `Visual Travel` or `L0 Travel Scale`.

## Analysis Modes

The realtime confirmation dialog also lets you adjust analysis mode and pose bias.

Pose bias is useful for full-body dance or side-to-side movement. Higher pose weight makes L0 less likely to treat side motion as full vertical travel, while auxiliary six-axis output can show more body angle and sway.

When pose bias is enabled, the right side of the captured screen preview can show a black skeleton estimate: white bones and blue joints. This is a fast visual trend estimate, not a slow human keypoint model.

### Hybrid Analysis (Recommended - Non-Dance)

Default recommended mode. It uses ROI optical-flow style analysis and is suitable for most realtime screen and video analysis.

### Stroke Phase (Beta)

Tracks the main vertical direction. It is stable but can simplify motion into endpoint-to-endpoint movement.

### Motion Center (Beta)

Tracks the center of the changing visual region. It works best with a clear subject and clean background.

### Optical Flow (Beta)

Follows global optical flow. It can become unstable if the whole frame shakes.

### Hybrid Motion (Beta)

Combines motion center and optical flow. Useful for experiments, not the default.

### Activity Pulse (Beta)

Generates rhythm from visual activity strength. Useful when position is hard to detect but motion intensity is clear.

## Advanced Parameters

### FPS

Screen analysis frame rate. Higher FPS is more responsive but uses more CPU. Typical range: `30..60`.

### Interval ms

TCode command interval. Lower values update faster. Typical range: `20..33`.

### Frame Speed Limit

Limits maximum value change per frame to reduce sudden jumps.

### Smoothing

Makes motion smoother. Too much smoothing increases delay.

### Endpoint Auto Reset / Endpoint Guard

Endpoint Auto Reset eases L0 back toward the middle if it stays near a limit too long. Endpoint Guard leaves a buffer near L0 extremes. If you want larger travel, reduce endpoint margin gradually instead of disabling protection immediately.

### Deadzone

Ignores very small movement. Too high can miss subtle motion; too low can jitter.

### Activity Gate

When visual activity is below the threshold, the app holds or centers instead of chasing noise.

### Response Curve

- `Linear`: natural and recommended.
- `Soft`: gentler.
- `Sharp`: more sensitive near the middle and more likely to reach endpoints.
- `Ease In`: more restrained near the middle.

`Hybrid Analysis (Recommended - Non-Dance)` with `Linear` is the default non-dance recommendation.

### Idle Mode

- `Hold`: keep the current position when useful motion is low.
- `Center`: return toward center when useful motion is low.

### Startup Ramp

Gradually enters motion from center when realtime output starts.

### Invert

Reverses L0 direction if the perceived direction is wrong.

## Video Analysis And Script Export

1. Set input source to `Video File`.
2. Click `Browse` and choose a video.
3. Choose `L0 Only` or `Six Axis`.
4. Use `Hybrid Analysis (Recommended - Non-Dance)` first.
5. Click `Analyze Video + Save Script`.

Six Axis exports companion funscript files:

- `.funscript`
- `.surge.funscript`
- `.sway.funscript`
- `.twist.funscript`
- `.roll.funscript`
- `.pitch.funscript`

## Recording Realtime Output

Click `Start Recording` to record realtime output.

Click `Save Script` to save the recording as funscript files.

## Tuning Recipes

### Too Jittery

Try in order:

1. Select a smaller, cleaner screen region.
2. Use preset `2` or `1`.
3. Increase smoothing.
4. Increase deadzone.
5. Increase activity threshold.

### Motion Too Small

Try in order:

1. Use preset `4`.
2. Increase `L0 Travel Scale`.
3. Increase `Visual Travel`.
4. Widen L0 limits gradually.

### Always Hits Limits

Try in order:

1. Reduce `Visual Travel`.
2. Reduce `L0 Travel Scale`.
3. Use preset `2` or `3`.
4. Use `Linear`, not `Sharp`.

### Delay Too Noticeable

Try in order:

1. Lower smoothing.
2. Lower interval ms.
3. Raise FPS.
4. Use USB serial instead of Bluetooth.

## Safety

- First real-device use should start with narrow limits.
- Use `Connect + Center` before motion tests.
- Use `Emergency Center` immediately if anything feels wrong.
- `Full L0 Test` uses the real saved L0 limits; confirm your setup before using it.
- In Six Axis, keep non-L0 axes narrow at first.

## Contact

For infringement concerns, license corrections, suggestions, or collaboration: aivnailedeng@gmail.com

Discord community: https://discord.gg/E7RY3rdKw

Discord note: if you join the community, follow the adults-only restriction. The server/relevant channels should be configured as age-restricted so minors cannot access adult content.
