"""Final axis mapping, travel limits and output object construction.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import tkinter as tk
from ..analyzer import SIX_AXES, RealtimeAnalyzer
from ..pose_output import rtm_rotation_amplitudes, rtm_l0_amplitude
from ..output_curve import OutputCurveFilter
from ..config import RTM_POSE_2D_MODE, HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE
from ..visual_pipeline import LabAnalyzer
from ..tcode import MultiAxisSafeOutput


class OutputMixin:
    @staticmethod
    def _generated_l0_axes(analyzer):
        return ("L0",) if (getattr(analyzer, "tracker_mode", "") in (RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE)
                            and getattr(analyzer, "generated_l0", None) is not None) else ()

    def _fit_output_curve(self, positions: dict[str, float], passthrough=()) -> dict[str, float]:
        curve = getattr(self._output_context, "curve", None)
        if curve is None:
            curve = self._output_context.curve = OutputCurveFilter()
        return curve.process(positions, enabled=self._output_curve_enabled, passthrough=passthrough)

    def _analysis_frame_scale(self) -> float:
        try:
            value = max(-5, min(5, int(round(float(self.compression_latency.get())))))
        except (tk.TclError, ValueError):
            return 1.0
        if value <= 0:
            return 1.0
        return max(0.60, 1.0 - value * 0.08)

    def _active_axes(self) -> list[str]:
        hybrid_only = self.source_mode.get() != "Audio Only" and self._tracker_internal(self.tracker_mode.get()) == HYBRID_MODE
        return ["L0"] if hybrid_only or self.output_mode.get() != "Six Axis" else SIX_AXES.copy()

    def _visual_output_positions(self, analyzer: RealtimeAnalyzer, positions: dict[str, float]) -> dict[str, float]:
        if getattr(analyzer, "tracker_mode", "") == HYBRID_MODE:
            return {"L0": positions["L0"]}
        if getattr(analyzer, "tracker_mode", "") == RTM_POSE_2D_MODE:
            positions = rtm_l0_amplitude(positions)
            if getattr(analyzer, "pose_l0_output", None) is not None:
                positions['L0'] = analyzer.pose_l0_output
            if self._generated_l0_axes(analyzer):
                positions["L0"] = analyzer.generated_l0
        if analyzer._rtm_pose_enabled() and analyzer.output_mode == "Six Axis":
            positions = rtm_rotation_amplitudes(positions)
        if (isinstance(analyzer, LabAnalyzer) and analyzer.pose and analyzer.settings.pose_pattern):
            excluded = ('L0',) if analyzer.pose_recovery.transition_at is not None else self._generated_l0_axes(analyzer)
            positions = analyzer.pose_pattern.apply(positions, excluded=excluded)
        return dict(positions) if isinstance(analyzer, LabAnalyzer) else self._apply_six_axis_tuning(positions)

    def _apply_six_axis_tuning(self, positions: dict[str, float]) -> dict[str, float]:
        if self.output_mode.get() != "Six Axis":
            return dict(positions)
        tracker_mode = self._tracker_internal(self.tracker_mode.get())
        if not RealtimeAnalyzer._is_hybrid_analysis_mode(tracker_mode) or self._rtm_pose_mode_active():
            return dict(positions)
        tuned = dict(positions)
        global_gain = max(0.0, min(1.8, self.six_axis_intensity.get() / 100.0))
        damping = max(0.0, min(1.0, self.six_axis_jitter_reduction.get() / 100.0))
        sensitivity = 1.0 - damping * 0.62
        filter_strength = 0.18 + damping * 0.66
        micro_deadband = 0.0005 + damping * 0.0028
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            value = max(0.0, min(1.0, float(tuned.get(axis, 0.5))))
            centered = value - 0.5
            axis_gain = max(0.0, min(2.0, self.six_axis_gain_vars[axis].get() / 100.0))
            centered *= global_gain * axis_gain * sensitivity
            if self.six_axis_invert_vars[axis].get():
                centered *= -1.0
            target = max(0.0, min(1.0, 0.5 + centered))
            previous = self._six_axis_stable_positions.get(axis, 0.5)
            if abs(target - previous) < micro_deadband:
                target = previous
            else:
                target = previous * filter_strength + target * (1.0 - filter_strength)
            self._six_axis_stable_positions[axis] = target
            tuned[axis] = target
        return tuned

    def _axis_limits(self, axes: list[str] | None = None) -> dict[str, tuple[int, int]]:
        selected_axes = axes or SIX_AXES
        return {
            axis: (self.axis_min_vars[axis].get(), self.axis_max_vars[axis].get())
            for axis in selected_axes
        }

    def _axis_position_scales(self) -> dict[str, float]:
        scales = {"L0": max(0.0, min(3.0, float(self.l0_travel_scale.get())))}
        six_axis_scale = max(0.0, min(3.0, float(self.global_travel_scale.get())))
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            axis_scale = max(0.0, min(3.0, float(self.six_axis_travel_scale_vars[axis].get())))
            scales[axis] = max(0.0, min(3.0, six_axis_scale * axis_scale))
        return scales

    def _axis_position_inverts(self) -> dict[str, bool]:
        global_invert = bool(self.six_axis_travel_invert.get())
        return {
            axis: global_invert ^ bool(self.axis_output_invert_vars[axis].get())
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }

    def _positions_with_travel_controls(self, positions: dict[str, float]) -> dict[str, float]:
        scales = self._axis_position_scales()
        inverts = self._axis_position_inverts()
        mapped: dict[str, float] = {}
        for axis, raw_value in positions.items():
            try:
                value = max(0.0, min(1.0, float(raw_value)))
            except (TypeError, ValueError):
                value = 0.5
            scale = scales.get(axis, 1.0)
            value = max(0.0, min(1.0, 0.5 + (value - 0.5) * scale))
            if (axis == "L0" and self.invert.get()) or (axis != "L0" and inverts.get(axis, False)):
                value = 1.0 - value
            mapped[axis] = value
        return mapped

    def _mark_live_output_mapping_dirty(self) -> None:
        self._live_output_mapping_dirty = True

    def _refresh_live_output_mapping(self, output: MultiAxisSafeOutput) -> None:
        if not self._live_output_mapping_dirty:
            return
        self._live_output_mapping_dirty = False
        axes = self._active_axes()
        output.axes = axes
        output.update_mapping(
            min_value=self.min_value.get(),
            max_value=self.max_value.get(),
            invert_l0=self.invert.get(),
            axis_limits=self._axis_limits(axes),
            position_scale=self.global_travel_scale.get(),
            axis_position_scales=self._axis_position_scales(),
            axis_position_inverts=self._axis_position_inverts(),
            max_step=self.max_step.get() if self.enable_speed_limit.get() else 9999,
            endpoint_slowdown=self._endpoint_options[0],
            slowdown_margin=self._endpoint_options[1],
        )

    def _new_output(self, interval_ms: int) -> MultiAxisSafeOutput:
        self._normalize_limits()
        axes = self._active_axes()
        return MultiAxisSafeOutput(
            axes,
            self.min_value.get(),
            self.max_value.get(),
            self.invert.get(),
            interval_ms,
            self.max_step.get() if self.enable_speed_limit.get() else 9999,
            self.min_activity.get() if self.enable_activity_gate.get() else 0.0,
            self.idle_mode.get(),
            axis_limits=self._axis_limits(axes),
            startup_ramp_ms=self.startup_ramp_ms.get() if self.enable_startup_ramp.get() else 0,
            position_scale=self.global_travel_scale.get(),
            axis_position_scales=self._axis_position_scales(),
            axis_position_inverts=self._axis_position_inverts(),
            enable_extreme_reset=self.enable_extreme_reset.get(),
            extreme_hold_ms=self.extreme_hold_ms.get(),
            enable_endpoint_guard=self.enable_endpoint_guard.get(),
            endpoint_margin=self.endpoint_margin_pct.get() / 100.0,
            couple_l0_translation=self.source_mode.get() != "Audio Only" and self._tracker_internal(self.tracker_mode.get()) in (RTM_POSE_2D_MODE, HYBRID_V2_MODE) and self.output_mode.get() == "Six Axis",
            coupling_endpoint_gain=0.5 if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else 1.0,
            coupling_middle_gain=3.5 if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else 2.5,
            coupling_peak_position=2/3 if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else .5,
            coupling_lower_knot=(1/3, 1.0) if self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE else None,
            couple_l0_rotation=self.source_mode.get() != 'Audio Only' and self._tracker_internal(self.tracker_mode.get()) == RTM_POSE_2D_MODE and self.output_mode.get() == 'Six Axis',
            sync_timing=True,
            endpoint_slowdown=self._endpoint_options[0],
            slowdown_margin=self._endpoint_options[1],
        )

    def _normalize_limits(self) -> None:
        for axis in SIX_AXES:
            self._normalize_axis_limit(axis)
        self._refresh_limit_text()

    def _normalize_axis_limit(self, axis: str) -> None:
        try:
            low = max(0, min(9999, int(float(self.axis_min_vars[axis].get()))))
            high = max(0, min(9999, int(float(self.axis_max_vars[axis].get()))))
        except (KeyError, tk.TclError, ValueError):
            return
        if low > high:
            low, high = high, low
        if low != self.axis_min_vars[axis].get():
            self.axis_min_vars[axis].set(low)
        if high != self.axis_max_vars[axis].get():
            self.axis_max_vars[axis].set(high)
        self._refresh_axis_limit_text(axis)

    def _set_all_axis_limits(self, low: int, high: int) -> None:
        for axis in SIX_AXES:
            self.axis_min_vars[axis].set(low)
            self.axis_max_vars[axis].set(high)
        self._normalize_limits()

    def _refresh_axis_limit_text(self, axis: str) -> None:
        if axis == "L0":
            self._refresh_limit_text()

    def _refresh_limit_text(self) -> None:
        try:
            low = int(float(self.min_value.get()))
            high = int(float(self.max_value.get()))
        except (tk.TclError, ValueError):
            return
        self.range_status.set(f"L0 {self._t('下限')} {low} / {self._t('上限')} {high}")
        self._draw_stroke_monitor(self._parse_l0_value(self.output_value.get()) or 5000)
