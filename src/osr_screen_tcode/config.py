from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_DIR = Path.home() / ".osr_screen_tcode"
CONFIG_PATH = APP_DIR / "config.json"
AXES = ("L0", "L1", "L2", "R0", "R1", "R2")
DEFAULT_AXIS_LIMITS = {axis: [0, 9999] for axis in AXES}
DEFAULT_SIX_AXIS_GAINS = {"L1": 85, "L2": 60, "R0": 60, "R1": 38, "R2": 70}
DEFAULT_SIX_AXIS_INVERTS = {"L1": False, "L2": False, "R0": False, "R1": False, "R2": False}


@dataclass
class AppConfig:
    x: int = 100
    y: int = 100
    width: int = 640
    height: int = 480
    fps: int = 45
    min_value: int = 0
    max_value: int = 9999
    axis_limits: dict[str, list[int]] = field(default_factory=lambda: {axis: values.copy() for axis, values in DEFAULT_AXIS_LIMITS.items()})
    smoothing: float = 0.08
    enable_smoothing: bool = True
    deadzone: float = 0.006
    enable_deadzone: bool = True
    tracker_mode: str = "混合分析（推荐）"
    response_curve: str = "Linear"
    motion_gain: float = 1.8
    visual_stroke_scale: float = 0.72
    global_travel_scale: float = 1.0
    min_activity: float = 0.002
    enable_activity_gate: bool = True
    max_step: int = 9999
    enable_speed_limit: bool = True
    idle_mode: str = "Hold"
    invert: bool = False
    enable_startup_ramp: bool = True
    startup_ramp_ms: int = 700
    axis: str = "L0"
    output_interval_ms: int = 20
    serial_port: str = ""
    baudrate: int = 115200
    ble_name: str = ""
    ble_address: str = ""
    ble_service_uuid: str = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    ble_write_uuid: str = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    last_sink: str = "Serial COM"
    audio_mode: str = "Audio Level"
    audio_gain: float = 2.5
    audio_threshold: float = 0.02
    audio_smoothing: float = 0.25
    audio_device: str = "System Output"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "AppConfig":
        if not CONFIG_PATH.exists():
            return cls()
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if "axis_limits" not in data:
            low = data.get("min_value", cls.min_value)
            high = data.get("max_value", cls.max_value)
            data["axis_limits"] = {axis: [low, high] for axis in AXES}
        extra = data.setdefault("extra", {})
        legacy_hybrid_name = "D" + "KAI Flow Light"
        legacy_mode_labels = {
            "Motion Center": "Motion Center（内测用）",
            "Optical Flow": "Optical Flow（内测用）",
            "Hybrid Motion": "Hybrid Motion（内测用）",
            "Stroke Phase": "Stroke Phase（内测用）",
            legacy_hybrid_name: "混合分析（推荐）",
            f"{legacy_hybrid_name}（推荐）": "混合分析（推荐）",
        }
        if data.get("tracker_mode") in legacy_mode_labels:
            data["tracker_mode"] = legacy_mode_labels[data["tracker_mode"]]
        if data.get("tracker_mode") == "混合分析（推荐）" and not extra.get("hybrid_analysis_range_migration_v1"):
            data.setdefault("visual_stroke_scale", 0.72)
            data["response_curve"] = "Linear"
            extra["hybrid_analysis_range_migration_v1"] = True
        data.setdefault("global_travel_scale", 1.0)
        extra.setdefault("play_preset_level", 3)
        extra.setdefault("enable_l0_jitter_guard", True)
        extra.setdefault("l0_guard_strength", 0.70)
        extra.setdefault("enable_extreme_reset", True)
        extra.setdefault("extreme_hold_ms", 900)
        extra.setdefault("enable_endpoint_guard", True)
        extra.setdefault("endpoint_margin_pct", 10)
        extra.setdefault("pose_dance_analysis", False)
        extra.setdefault("pose_l0_analysis", bool(extra.get("pose_dance_analysis", False)))
        extra.setdefault("pose_six_axis_analysis", bool(extra.get("pose_dance_analysis", False)))
        extra.setdefault("pose_l0_weight", 60)
        extra.setdefault("pose_six_axis_weight", 60)
        extra.setdefault("l0_travel_scale", data.get("global_travel_scale", 1.0))
        extra.setdefault("show_more_settings", False)
        extra.setdefault("six_axis_intensity", 65)
        extra.setdefault("six_axis_jitter_reduction", 55)
        extra.setdefault("six_axis_sensitivity_level", 5)
        stored_gains = extra.get("six_axis_gains")
        if not isinstance(stored_gains, dict):
            stored_gains = {}
        extra["six_axis_gains"] = {
            axis: int(stored_gains.get(axis, DEFAULT_SIX_AXIS_GAINS.get(axis, 60)))
            for axis in DEFAULT_SIX_AXIS_GAINS
        }
        stored_inverts = extra.get("six_axis_inverts")
        if not isinstance(stored_inverts, dict):
            stored_inverts = {}
        extra["six_axis_inverts"] = {
            axis: bool(stored_inverts.get(axis, DEFAULT_SIX_AXIS_INVERTS.get(axis, False)))
            for axis in DEFAULT_SIX_AXIS_INVERTS
        }
        if not extra.get("six_axis_soft_default_v1"):
            if int(extra.get("six_axis_intensity", 65)) > 75:
                extra["six_axis_intensity"] = 65
            for axis, value in DEFAULT_SIX_AXIS_GAINS.items():
                if int(extra["six_axis_gains"].get(axis, value)) > value:
                    extra["six_axis_gains"][axis] = value
            extra["six_axis_soft_default_v1"] = True
        if not extra.get("six_axis_visible_default_v1"):
            if int(extra.get("six_axis_intensity", 65)) < 65:
                extra["six_axis_intensity"] = 65
            for axis, value in DEFAULT_SIX_AXIS_GAINS.items():
                if int(extra["six_axis_gains"].get(axis, value)) < value:
                    extra["six_axis_gains"][axis] = value
            extra["six_axis_visible_default_v1"] = True
        extra["six_axis_jitter_reduction"] = max(0, min(100, int(extra.get("six_axis_jitter_reduction", 55))))
        extra["six_axis_sensitivity_level"] = max(1, min(10, int(extra.get("six_axis_sensitivity_level", 5))))
        extra["enable_extreme_reset"] = bool(extra.get("enable_extreme_reset", True))
        extra["extreme_hold_ms"] = max(250, min(3000, int(extra.get("extreme_hold_ms", 900))))
        extra["enable_endpoint_guard"] = bool(extra.get("enable_endpoint_guard", True))
        extra["endpoint_margin_pct"] = max(0, min(25, int(extra.get("endpoint_margin_pct", 10))))
        extra["pose_l0_analysis"] = bool(extra.get("pose_l0_analysis", False))
        extra["pose_six_axis_analysis"] = bool(extra.get("pose_six_axis_analysis", False))
        extra["pose_l0_weight"] = max(0, min(100, int(extra.get("pose_l0_weight", 60))))
        extra["pose_six_axis_weight"] = max(0, min(100, int(extra.get("pose_six_axis_weight", 60))))
        extra["l0_travel_scale"] = max(0.0, min(3.0, float(extra.get("l0_travel_scale", data.get("global_travel_scale", 1.0)))))
        data["global_travel_scale"] = max(0.0, min(3.0, float(data.get("global_travel_scale", 1.0))))
        extra["show_more_settings"] = bool(extra.get("show_more_settings", False))
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
