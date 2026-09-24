"""Manual local-screen RTM/Hybrid smoke test; Log only, no saved user changes."""
import argparse
import time
from pathlib import Path
from unittest.mock import patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig, RTM_POSE_2D_MODE


parser = argparse.ArgumentParser()
parser.add_argument("--model", type=Path)
parser.add_argument("--seconds", type=float, default=8.)
args = parser.parse_args()
if args.seconds < 2:
    parser.error('--seconds must be at least 2')
if args.model:
    assert args.model.is_file()
config = AppConfig(last_sink="Log only", fps=120)
if args.model:
    config.tracker_mode = RTM_POSE_2D_MODE
    config.extra["rtm_pose_2d_model_path"] = str(args.model.resolve())
config.extra["output_mode"] = "Six Axis"
stats, errors, callbacks, analyzers = [], [], [], []
with patch.object(AppConfig, "load", return_value=config), patch.object(AppConfig, "save"):
    app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
    app.output_mode.set("Six Axis")
    if args.model:
        app._set_tracker_mode(RTM_POSE_2D_MODE)
        app.rtm_pose_2d_model_path.set(str(args.model.resolve()))
        assert app._rtm_pose_2d_mode_active()
    app.title("Log-only pipeline check - " + app.title())
    app.report_callback_exception = lambda *details: callbacks.append(str(details))
    original = app._queue_latest

    def observe(item):
        if item.get("capture_stats"):
            stats.append(item["capture_stats"])
        if "error" in item:
            errors.append(item["error"])
        return original(item)

    app._queue_latest = observe
    original_process = app._process_frame

    def inspect_analyzer(analyzer, *values, **options):
        if not analyzers:
            analyzers.append(analyzer)
        return original_process(analyzer, *values, **options)

    app._process_frame = inspect_analyzer
    app.connect_sink()
    def begin():
        app._begin_realtime_output()
        print('START', app.connected, bool(app.worker and app.worker.is_alive()), app.status.get())
        # Measure the run after actual startup, not while initial Tk layout
        # competes with capture. Allow a full second for orderly worker exit.
        app.after(round(args.seconds*1000), app.stop)
        app.after(round(args.seconds*1000)+1000, app.quit)
    app.after(500, begin)
    started = time.perf_counter()
    app.mainloop()
    alive = bool(app.worker and app.worker.is_alive())
    print('CHECK', {'updates': len(stats), 'seconds': round(time.perf_counter()-started, 2),
                    'worker_alive': alive, 'analyzers': len(analyzers), 'status': app.status.get()})
    app.on_close()
    assert not errors, errors
    assert not callbacks, callbacks
    assert not alive
    assert len(stats) > 5
    if args.model:
        backend = analyzers[0].backend
        assert backend is not None, "Test did not start in RTM mode"
        assert backend._model is not None, backend.status
        assert analyzers[0].visual_frame is not None, backend.status
        print("MODEL", backend.status, "LAST INFERENCE MS", analyzers[0].visual_frame.inference_ms)
    print("MODE", "RTM Pose 2D CPU" if args.model else "Hybrid")
    print("FRAME UPDATES", len(stats), "LAST CAPTURE/ANALYSIS FPS AND INPUT AGE MS", stats[-1])
    print("No hardware connected; output stopped; user settings unchanged.")
