"""Explicit, isolated checks of the actual source or portable runtime.

This is a diagnostic entry point, not a device output mode. No models or
runtime libraries are downloaded; optional live output always uses LogSink.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from importlib import metadata, resources
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch


class _Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _fingerprint(path: Path) -> bytes | None:
    return hashlib.sha256(path.read_bytes()).digest() if path.exists() else None


@contextmanager
def isolated_settings(report: dict):
    # App/preview imports belong inside this boundary. The explicit NeuFlow
    # diagnostic alone selects an existing private GPU runtime beforehand;
    # it does not install libraries or save personal settings.
    from . import config

    personal = config.CONFIG_PATH
    before = _fingerprint(personal)
    with tempfile.TemporaryDirectory(prefix="osr-runtime-check-") as folder:
        temporary = Path(folder)
        with patch.object(config, "APP_DIR", temporary), \
                patch.object(config, "CONFIG_PATH", temporary / "config.json"), \
                patch.object(config.AppConfig, "load", side_effect=lambda: config.AppConfig(last_sink="Log only", fps=120)), \
                patch.object(config.AppConfig, "save"):
            try:
                yield
            finally:
                unchanged = _fingerprint(personal) == before
                report["personal_settings_unchanged"] = unchanged
                if not unchanged:
                    raise RuntimeError("Personal settings changed during the runtime check")


def _version(distribution: str, module=None) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return str(getattr(module, "__version__", "unavailable"))


def _check_dependencies(report: dict) -> None:
    # Static imports intentionally let PyInstaller see the required modules.
    import soundcard
    import sounddevice
    import serial.tools.list_ports
    import rtmlib
    import onnxruntime as ort
    import websockets
    import numpy as np

    if os.name == "nt":
        from bleak.backends.winrt.client import BleakClientWinRT
        from bleak.backends.winrt.scanner import BleakScannerWinRT

        if BleakClientWinRT is None or BleakScannerWinRT is None:
            raise RuntimeError("Windows BLE backend is unavailable")
    report["dependencies"] = {
        "soundcard": _version("soundcard", soundcard),
        "sounddevice": _version("sounddevice", sounddevice),
        "pyserial": _version("pyserial", serial),
        "bleak": _version("bleak"),
        "rtmlib": _version("rtmlib", rtmlib),
        "onnxruntime": ort.__version__,
        "websockets": _version("websockets", websockets),
        "numpy": np.__version__,
    }
    report["checks"].append("dependency_imports")
    html = resources.files("osr_screen_tcode.assets").joinpath("osr_emu_standalone.html").read_text(encoding="utf-8")
    if "OSREmulator" not in html or "__OSR_PREVIEW_CONTEXT__" not in html:
        raise RuntimeError("Embedded simulator resource is missing or incomplete")
    report["checks"].append("embedded_simulator")

    from .gpu_runtime import _GPU_PROBE_MODEL

    session = ort.InferenceSession(_GPU_PROBE_MODEL, providers=["CPUExecutionProvider"])
    result = session.run(None, {"X": np.ones((3, 2), dtype=np.float32)})[0]
    if not np.allclose(result, np.arange(1, 7, dtype=np.float32).reshape(3, 2)):
        raise RuntimeError("CPU inference returned an incorrect result")
    report["providers"] = list(ort.get_available_providers())
    report["cpu_session_providers"] = list(session.get_providers())
    report["checks"].append("cpu_inference")


def _check_model(model: Path, report: dict) -> None:
    import numpy as np
    from .pose_backends import OptionalRtmPose2dBackend

    if not model.is_file() or model.suffix.lower() != ".onnx":
        raise ValueError("The optional model must be an existing ONNX file")
    backend = OptionalRtmPose2dBackend(str(model), device="cpu")
    backend.infer(np.zeros((256, 192, 3), dtype=np.uint8))
    if backend._model is None or "failed" in backend.status.lower():
        raise RuntimeError(backend.status)
    if backend.device != "cpu":
        raise RuntimeError("Model diagnostic unexpectedly selected a GPU")
    report["checks"].append("external_pose_model_cpu_inference")


def _prepare_v2_gpu_runtime() -> None:
    # Resolve the user's already-installed CUDA overlay while APP_DIR still
    # points to it and before dependency imports lock in an ORT installation.
    # Scope the environment override; do not alter the user's backend choice.
    with patch.dict(os.environ, {"OSR_TCODE_GPU_BACKEND": "cuda"}):
        from .gpu_runtime import activate_local_runtime

        activate_local_runtime()


def _validate_window_origin(origin) -> tuple[int, int]:
    from .screen_geometry import screen_monitors

    if len(origin) != 2 or any(type(value) is not int for value in origin):
        raise ValueError("--window-origin requires two signed integer pixel coordinates")
    x, y = origin
    if not any(monitor["left"] <= x < monitor["left"] + monitor["width"]
               and monitor["top"] <= y < monitor["top"] + monitor["height"]
               for monitor in screen_monitors()):
        raise ValueError("--window-origin must be on an available monitor")
    return x, y


@contextmanager
def _live_window_origin(origin):
    """Place only explicitly requested diagnostic roots, never normal startup.

    Tk's negative offsets are edge-relative; the existing native positioning
    helper instead uses signed physical desktop coordinates. Placing the root
    at its first geometry request lets the normal monitor-fitting code size it
    for that monitor. No monitor layout is stored or hardcoded.
    """
    if origin is None:
        yield
        return
    x, y = _validate_window_origin(origin)
    import tkinter as tk
    from .screen_geometry import move_physical_window

    original = tk.Tk.geometry
    placing = False

    def positioned(window, new_geometry=None):
        nonlocal placing
        result = original(window, new_geometry)
        if new_geometry is not None and not placing:
            placing = True
            try:
                move_physical_window(window, x, y)
            finally:
                placing = False
        return result

    with patch.object(tk.Tk, "geometry", positioned):
        yield


def _check_vittrack(model: Path, report: dict) -> None:
    import numpy as np
    from .v2_models import ViTTrackBackend

    rng = np.random.default_rng(19)
    patch_image = rng.integers(0, 255, (80, 80, 3), dtype=np.uint8)
    background = np.full((240, 400, 3), 70, dtype=np.uint8)
    first = background.copy()
    first[80:160, 100:180] = patch_image
    tracker = ViTTrackBackend(str(model), device="cpu")
    initialized = tracker.initialize(first, (100, 80, 80, 80))
    if not initialized.valid:
        raise RuntimeError("ViTTrack diagnostic initialization failed: " + initialized.reason)
    timings, confidence, errors = [], [], []
    for displacement in (3, 6, 9, 12, 15):
        frame = background.copy()
        frame[80:160, 100 + displacement:180 + displacement] = patch_image
        started = time.perf_counter()
        tracked = tracker.update(frame)
        timings.append(time.perf_counter() - started)
        if not tracked.valid or tracked.confidence < .5 or tracked.bbox_xywh is None:
            raise RuntimeError("ViTTrack did not retain the known moving subject")
        x, y, width, height = tracked.bbox_xywh
        error = float(np.linalg.norm((x + width / 2 - 140 - displacement, y + height / 2 - 120)))
        if error > 12:
            raise RuntimeError("ViTTrack returned an incorrect subject location")
        confidence.append(tracked.confidence)
        errors.append(error)
    report["vittrack"] = {"provider": tracker.provider, "image_shape": [240, 400, 3],
                          "tracked_frames": len(timings), "frame_seconds": timings,
                          "minimum_confidence": min(confidence), "maximum_center_error_pixels": max(errors)}
    report["checks"].append("external_vittrack_model_cpu_tracking")


def _check_neuflow(model: Path, report: dict) -> None:
    import numpy as np
    from .v2_models import NeuFlowBackend

    rng = np.random.default_rng(17)
    first = rng.integers(0, 256, (384, 640, 3), dtype=np.uint8)
    second = np.roll(first, 8, axis=1)
    backend = NeuFlowBackend(str(model), device="cuda", require_gpu=True)
    timings, observed = [], []
    for _ in range(2):
        started = time.perf_counter()
        flow = backend.infer(first, second, backward=True)
        timings.append(time.perf_counter() - started)
        if not flow.valid or backend.provider != "CUDAExecutionProvider":
            raise RuntimeError("NeuFlow CUDA diagnostic failed: " + flow.reason)
        for field, expected in ((flow.forward, (8., 0.)), (flow.backward, (-8., 0.))):
            if field is None or field.shape != (384, 640, 2) or not np.isfinite(field).all():
                raise RuntimeError("NeuFlow returned an invalid flow field")
            center = field[48:-48, 48:-48]
            error = np.linalg.norm(center - np.asarray(expected), axis=2)
            if float(np.percentile(error, 95)) > 1.5:
                raise RuntimeError("NeuFlow did not reproduce the known frame translation")
            observed.append(float(np.percentile(error, 95)))
    report["neuflow"] = {"provider": backend.provider, "image_shape": [384, 640, 3],
                         "flow_shape": [384, 640, 2], "pair_seconds": timings,
                         "maximum_95th_percentile_error_pixels": max(observed)}
    report["checks"].append("external_neuflow_model_cuda_bidirectional_flow")


def _check_live(seconds: float, language: str, model: Path | None, report: dict) -> None:
    from .app import OsrScreenApp
    from .config import RTM_POSE_2D_MODE
    from .sinks import BleSink, LogSink, SerialSink

    errors, callbacks, stats = [], [], []
    state = {"started": False, "completed": False, "cancelled": False}
    app = None
    # Even accidental clicks in this temporary UI cannot open real outputs.
    with patch.object(SerialSink, "open", side_effect=RuntimeError("Hardware output is disabled during diagnostics")), \
            patch.object(BleSink, "open", side_effect=RuntimeError("Hardware output is disabled during diagnostics")):
        try:
            app = OsrScreenApp(enforce_age_gate=False, ui_language=language)
            app.title("Portable runtime check - " + app.title())
            app.sink_type.set("Log only")
            app.source_mode.set("Screen")
            app.output_mode.set("Six Axis")
            app.rtm_pose_gpu_enabled.set(False)
            if model is not None:
                app._set_tracker_mode(RTM_POSE_2D_MODE)
                app.rtm_pose_2d_model_path.set(str(model))

            def callback_error(*details):
                callbacks.append(str(details))
                app.quit()

            def cancelled():
                state["cancelled"] = True
                app.quit()

            app.report_callback_exception = callback_error
            app.protocol("WM_DELETE_WINDOW", cancelled)
            original = app._queue_latest

            def observe(item):
                if item.get("capture_stats"):
                    stats.append(item["capture_stats"])
                if "error" in item:
                    errors.append(str(item["error"]))
                return original(item)

            app._queue_latest = observe
            app.connect_sink()
            if not app.connected or not isinstance(app.sink, LogSink):
                raise RuntimeError("The diagnostic did not connect a Log-only sink")

            def await_stop(deadline):
                if not app.worker or not app.worker.is_alive():
                    state["completed"] = True
                    app.quit()
                elif time.monotonic() >= deadline:
                    errors.append("Capture worker did not stop within five seconds")
                    app.quit()
                else:
                    app.after(50, lambda: await_stop(deadline))

            def stop():
                if not app.worker or not app.worker.is_alive():
                    errors.append("Capture ended before the requested duration")
                app.stop()
                await_stop(time.monotonic() + 5)

            def begin():
                app._begin_realtime_output()
                state["started"] = bool(app.worker and app.worker.is_alive())
                if not state["started"]:
                    raise RuntimeError("Log-only screen capture did not start")
                app.after(round(seconds * 1000), stop)

            app.after(500, begin)
            app.mainloop()
        finally:
            if app is not None:
                # Keep both the configuration mocks and hardware guards active
                # through shutdown, including failures and user cancellation.
                try:
                    app.stop()
                    deadline = time.monotonic() + 5
                    while app.worker and app.worker.is_alive() and time.monotonic() < deadline:
                        app.update()
                        time.sleep(0.01)
                finally:
                    alive = bool(app.worker and app.worker.is_alive())
                    try:
                        app.on_close()
                    finally:
                        if alive:
                            errors.append("Capture worker was still alive at shutdown")
    report["live_updates"] = len(stats)
    report["live_seconds"] = seconds
    report["language"] = language
    if state["cancelled"]:
        raise RuntimeError("Live diagnostic was cancelled")
    if errors or callbacks:
        raise RuntimeError("Live diagnostic errors: " + repr(errors + callbacks))
    if not state["started"] or not state["completed"] or len(stats) <= 5:
        raise RuntimeError(f"Live diagnostic incomplete: {len(stats)} statistics updates")
    report["checks"].append("live_screen_log_only")


def _perform_checks(args, report: dict) -> None:
    from . import config

    personal = config.CONFIG_PATH
    before = _fingerprint(personal)
    neuflow_model = getattr(args, "neuflow_model", None)
    vittrack_model = getattr(args, "vittrack_model", None)
    try:
        if neuflow_model is not None:
            _prepare_v2_gpu_runtime()
        with isolated_settings(report):
            _check_dependencies(report)
            if args.model is not None:
                _check_model(args.model, report)
            if vittrack_model is not None:
                _check_vittrack(vittrack_model, report)
            if neuflow_model is not None:
                _check_neuflow(neuflow_model, report)
            if args.live_seconds is not None:
                with _live_window_origin(getattr(args, "window_origin", None)):
                    _check_live(args.live_seconds, args.language, args.model, report)
    finally:
        report["personal_settings_unchanged"] = _fingerprint(personal) == before
        if not report["personal_settings_unchanged"]:
            raise RuntimeError("Personal settings changed during the runtime check")


def _write_report(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_runtime_check(argv: list[str]) -> bool:
    """Return False for other commands; diagnostic commands always exit."""
    if not argv or argv[0] != "--runtime-check":
        return False
    from . import __version__
    from . import config

    report = {"status": "failed", "version": __version__,
              "frozen": bool(getattr(sys, "frozen", False)), "checks": []}
    output = None
    exit_code = 1
    try:
        if len(argv) < 2 or argv[1].startswith("--"):
            raise ValueError("--runtime-check requires an output JSON path")
        candidate = Path(argv[1]).expanduser().resolve()
        if candidate == config.CONFIG_PATH.resolve():
            raise ValueError("Diagnostic output cannot overwrite personal settings")
        if candidate.suffix.lower() != ".json":
            raise ValueError("Diagnostic output must have a .json extension")
        output = candidate
        parser = _Arguments(prog="--runtime-check", add_help=False)
        parser.add_argument("output", type=Path)
        parser.add_argument("--model", type=Path)
        parser.add_argument("--vittrack-model", type=Path)
        parser.add_argument("--neuflow-model", type=Path)
        parser.add_argument("--live-seconds", type=float)
        parser.add_argument("--window-origin", nargs=2, type=int, metavar=("X", "Y"))
        parser.add_argument("--language", choices=("zh", "en"), default="en")
        args = parser.parse_args(argv[1:])
        if args.live_seconds is not None and not 2 <= args.live_seconds <= 30:
            raise ValueError("--live-seconds must be between 2 and 30")
        if args.window_origin is not None:
            if args.live_seconds is None:
                raise ValueError("--window-origin requires --live-seconds")
            args.window_origin = _validate_window_origin(args.window_origin)
        if args.model is not None:
            args.model = args.model.expanduser().resolve()
        for name in ("vittrack_model", "neuflow_model"):
            model = getattr(args, name)
            if model is not None:
                model = model.expanduser().resolve()
                if model.suffix.lower() != ".onnx" or not model.is_file():
                    raise ValueError("Optional v2 diagnostics require an existing ONNX file")
                setattr(args, name, model)
        _perform_checks(args, report)
        report["status"] = "passed"
        exit_code = 0
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if output is not None:
            try:
                _write_report(output, report)
            except Exception as exc:
                exit_code = 1
                if sys.stderr is not None:
                    print(f"Cannot write runtime diagnostic: {exc}", file=sys.stderr)
    raise SystemExit(exit_code)
