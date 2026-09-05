"""Visible UI checks using fake device data, without saving settings or opening hardware."""
import argparse
from unittest.mock import patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig, RTM_POSE_2D_MODE
from osr_screen_tcode.device_backends import IntifaceDevice


parser = argparse.ArgumentParser()
parser.add_argument("case", choices=("custom", "log", "popup", "gpu-progress"))
parser.add_argument("--language", default="zh")
parser.add_argument("--backend", choices=("cuda", "directml"), default="cuda")
args = parser.parse_args()
with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"):
    app = OsrScreenApp(enforce_age_gate=False, ui_language=args.language)
    app.title("UI Check - " + app.title())
    app.geometry("1160x850+50+50")
    if args.case == "custom":
        app.device_family.set(app._device_family_labels["custom"])
        app.intiface_url.set("ws://127.0.0.1:1")
        device = IntifaceDevice.from_message({"DeviceIndex": 1, "DeviceName": "UI Check (simulated)",
            "DeviceMessages": {"LinearCmd": [{"ActuatorType": "Linear"}],
                               "RotateCmd": [{"ActuatorType": "Rotate"}],
                               "ScalarCmd": [{"ActuatorType": "Vibrate"}]}})
        app._finish_device_scan({"device_scan": app._device_scan_generation, "devices": [device]})
        app.external_device.set(next(iter(app._external_devices)))
        app._on_external_device_selected()
        labels = list(app._external_features)
        for axis, label in zip(("L0", "R0", "L2"), labels):
            app.custom_bindings[axis].set(label)
    elif args.case in {"popup", "gpu-progress"}:
        app._set_tracker_mode(RTM_POSE_2D_MODE)
        app.rtm_pose_gpu_backend.set(args.backend)
        app._gpu_result = {"nvidia": args.backend == "cuda", "cuda": False, "reason": "cpu_ort" if args.backend == "cuda" else "dml_missing"}
        app.rtm_pose_gpu_enabled.set(True)
        if args.case == "gpu-progress":
            app._gpu_installing = True
            app._gpu_stage = "downloading"
            app._gpu_progress = {"stage": "downloading", "component": "nvidia-cudnn-cu12", "index": 3,
                "count": 9, "downloaded": 256 * 1024 ** 2, "total": 1024 * 1024 ** 2}
        app.after(800, app._confirm_realtime_start)
    app.after(45000, app.on_close)
    app.mainloop()
    print("Visible UI check closed cleanly:", args.case, args.language)
