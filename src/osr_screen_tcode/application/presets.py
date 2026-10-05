"""Existing analysis/output presets and play-preset button state.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
from ..analyzer import SIX_AXES
from ..config import HYBRID_MODE


class PresetsMixin:
    def apply_soft_six_axis_preset(self) -> None:
        self.apply_six_axis_sensitivity(5)

    def apply_six_axis_sensitivity(self, level: int, announce: bool = True) -> None:
        presets = {
            1: {"intensity": 28, "jitter": 92, "gains": {"L1": 42, "L2": 28, "R0": 28, "R1": 18, "R2": 32}},
            2: {"intensity": 38, "jitter": 84, "gains": {"L1": 55, "L2": 38, "R0": 38, "R1": 24, "R2": 44}},
            3: {"intensity": 55, "jitter": 70, "gains": {"L1": 75, "L2": 52, "R0": 52, "R1": 34, "R2": 62}},
            4: {"intensity": 75, "jitter": 52, "gains": {"L1": 95, "L2": 72, "R0": 72, "R1": 46, "R2": 84}},
            5: {"intensity": 100, "jitter": 32, "gains": {"L1": 120, "L2": 92, "R0": 92, "R1": 62, "R2": 110}},
            6: {"intensity": 115, "jitter": 24, "gains": {"L1": 135, "L2": 108, "R0": 108, "R1": 72, "R2": 125}},
            7: {"intensity": 130, "jitter": 18, "gains": {"L1": 150, "L2": 124, "R0": 124, "R1": 84, "R2": 142}},
            8: {"intensity": 145, "jitter": 12, "gains": {"L1": 166, "L2": 140, "R0": 140, "R1": 96, "R2": 160}},
            9: {"intensity": 160, "jitter": 7, "gains": {"L1": 184, "L2": 162, "R0": 162, "R1": 112, "R2": 182}},
            10: {"intensity": 180, "jitter": 2, "gains": {"L1": 200, "L2": 190, "R0": 190, "R1": 132, "R2": 200}},
        }
        level = max(1, min(10, int(level)))
        preset = presets[level]
        self.output_mode.set("Six Axis")
        self.six_axis_intensity.set(preset["intensity"])
        self.six_axis_jitter_reduction.set(preset["jitter"])
        for axis, value in preset["gains"].items():
            self.six_axis_gain_vars[axis].set(value)
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            self.six_axis_invert_vars[axis].set(False)
        self.six_axis_sensitivity_level.set(level)
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._refresh_six_axis_sensitivity_buttons()
        if announce:
            self.status.set(f"{self._t('已应用六轴敏感度')} {level} {self._t('档')}")

    def apply_stable_six_axis_preset(self) -> None:
        self.output_mode.set("Six Axis")
        self.six_axis_intensity.set(45)
        self.six_axis_jitter_reduction.set(82)
        values = {"L1": 60, "L2": 42, "R0": 42, "R1": 25, "R2": 48}
        for axis, value in values.items():
            self.six_axis_gain_vars[axis].set(value)
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            self.six_axis_invert_vars[axis].set(False)
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self.six_axis_sensitivity_level.set(1)
        self._refresh_six_axis_sensitivity_buttons()
        self.status.set(self._t("已应用稳六轴：辅助轴更低敏、更少抖"))

    def _refresh_six_axis_sensitivity_buttons(self) -> None:
        if not hasattr(self, "six_axis_sensitivity_buttons"):
            return
        active = self.six_axis_sensitivity_level.get()
        for level, button in self.six_axis_sensitivity_buttons.items():
            button.configure(style="PresetActive.TButton" if level == active else "TButton")

    def apply_safe_preset(self) -> None:
        self._set_all_axis_limits(2500, 7500)
        self.max_step.set(900)
        self.min_activity.set(0.006)
        self.smoothing.set(0.45)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.85)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(700)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(14)
        self.motion_gain.set(0.8)
        self.l0_travel_scale.set(0.55)
        self.global_travel_scale.set(0.55)
        self.status.set(self._t("已应用安全预设"))
        self.play_preset_level.set(1)
        self._refresh_play_preset_buttons()

    def apply_normal_preset(self) -> None:
        self._set_all_axis_limits(500, 9500)
        self.max_step.set(1800)
        self.min_activity.set(0.004)
        self.smoothing.set(0.25)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.70)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(850)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(10)
        self.motion_gain.set(1.25)
        self.l0_travel_scale.set(1.0)
        self.global_travel_scale.set(1.0)
        self.status.set(self._t("已应用标准预设"))
        self.play_preset_level.set(3)
        self._refresh_play_preset_buttons()

    def apply_full_preset(self) -> None:
        self.output_mode.set("L0 Only")
        self._set_all_axis_limits(0, 9999)
        self.max_step.set(9999)
        self.min_activity.set(0.003)
        self.smoothing.set(0.12)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.45)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(1000)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(6)
        self.motion_gain.set(1.6)
        self.l0_travel_scale.set(1.30)
        self.global_travel_scale.set(1.0)
        self.status.set(self._t("已应用上下全行程高速预设"))
        self.play_preset_level.set(5)
        self._refresh_play_preset_buttons()

    def apply_hybrid_analysis_preset(self) -> None:
        self._set_tracker_mode(HYBRID_MODE)
        self.enable_smoothing.set(True)
        self.smoothing.set(0.08)
        self.enable_deadzone.set(True)
        self.deadzone.set(0.006)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.70)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(850)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(10)
        self.enable_activity_gate.set(True)
        self.min_activity.set(0.0025)
        self.enable_speed_limit.set(True)
        self.max_step.set(1800)
        self.motion_gain.set(1.55)
        self.visual_stroke_scale.set(0.68)
        self.l0_travel_scale.set(1.0)
        self.global_travel_scale.set(1.0)
        self.response_curve.set("Linear")
        self.idle_mode.set("Hold")
        self.status.set(self._t("已应用混合分析稳态预设"))
        self.play_preset_level.set(3)
        self._refresh_play_preset_buttons()

    def apply_stable_l0_preset(self) -> None:
        self._set_tracker_mode(HYBRID_MODE)
        self.enable_smoothing.set(True)
        self.smoothing.set(0.30)
        self.enable_deadzone.set(True)
        self.deadzone.set(0.010)
        self.enable_l0_jitter_guard.set(True)
        self.l0_guard_strength.set(0.82)
        self.enable_extreme_reset.set(True)
        self.extreme_hold_ms.set(650)
        self.enable_endpoint_guard.set(True)
        self.endpoint_margin_pct.set(14)
        self.enable_activity_gate.set(True)
        self.min_activity.set(0.0045)
        self.enable_speed_limit.set(True)
        self.max_step.set(1300)
        self.motion_gain.set(1.25)
        self.visual_stroke_scale.set(0.62)
        self.l0_travel_scale.set(0.75)
        self.response_curve.set("Linear")
        self.apply_soft_six_axis_preset()
        self.status.set(self._t("已应用稳态 L0 + 低敏六轴"))

    def apply_play_preset(self, level: int, announce: bool = True) -> None:
        level = max(1, min(5, int(level)))
        travel = {1: 0.55, 2: 0.75, 3: 1.0, 4: 1.15, 5: 1.30}[level]
        # These scales are consumed only by script mapping and final TCode output.
        # Keep the selected analyzer and its running state intact.
        self.l0_travel_scale.set(travel)
        self.global_travel_scale.set(travel)
        self.play_preset_level.set(level)
        self._refresh_play_preset_buttons()
        if announce:
            self.status.set(f"{self._t('已应用')} {level} {self._t('档')} {self._t('预设')}")

    def _refresh_play_preset_buttons(self) -> None:
        if not hasattr(self, "preset_buttons"):
            return
        active = self.play_preset_level.get()
        for level, button in self.preset_buttons.items():
            button.configure(style="PresetActive.TButton" if level == active else "TButton")
