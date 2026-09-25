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
    # Do not import app, preview or gpu_runtime above this boundary: they copy
    # these module constants at import time.
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
    with isolated_settings(report):
        _check_dependencies(report)
        if args.model is not None:
            _check_model(args.model, report)
        if args.live_seconds is not None:
            _check_live(args.live_seconds, args.language, args.model, report)


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
        parser.add_argument("--live-seconds", type=float)
        parser.add_argument("--language", choices=("zh", "en"), default="en")
        args = parser.parse_args(argv[1:])
        if args.live_seconds is not None and not 2 <= args.live_seconds <= 30:
            raise ValueError("--live-seconds must be between 2 and 30")
        if args.model is not None:
            args.model = args.model.expanduser().resolve()
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
