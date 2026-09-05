from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import time

import cv2
import numpy as np

from .pose_backends import OptionalRtmPose2dBackend, OptionalRtmPose3dBackend, RtmPose3dResult


SIX_AXES = ["L0", "L1", "L2", "R0", "R1", "R2"]


@dataclass(frozen=True)
class AxisAnalysis:
    positions: dict[str, float]
    confidence: float
    activity: float
    preview_bgr: np.ndarray


class RealtimeAnalyzer:
    def __init__(
        self,
        tracker_mode: str = "混合分析（推荐-非舞蹈）",
        output_mode: str = "L0 Only",
        smoothing: float = 0.35,
        deadzone: float = 0.015,
        motion_gain: float = 1.0,
        enable_smoothing: bool = True,
        enable_deadzone: bool = True,
        response_curve: str = "Linear",
        visual_stroke_scale: float = 0.72,
        l0_jitter_guard: bool = True,
        l0_guard_strength: float = 0.65,
        enable_extreme_reset: bool = True,
        enable_endpoint_guard: bool = True,
        endpoint_margin: float = 0.10,
        pose_dance_mode: bool = False,
        pose_dance_l0: bool | None = None,
        pose_dance_six_axis: bool | None = None,
        pose_l0_weight: float = 0.60,
        pose_six_axis_weight: float = 0.60,
        pose_v2_dance_six_axis: bool = False,
        pose_v2_l0_weight: float | None = None,
        pose_v2_six_axis_weight: float | None = None,
        rtm_pose_2d_enabled: bool = False,
        rtm_pose_2d_model_path: str = "",
        rtm_pose_3d_enabled: bool = False,
        rtm_pose_3d_model_path: str = "",
        rtm_pose_3d_weight: float = 1.0,
        rtm_hybrid_l0_enabled: bool = False,
        rtm_hybrid_l0_weight: float = 0.30,
        rtm_pose_gpu_enabled: bool = False,
        rtm_pose_flow_enabled: bool = False,
        rtm_pose_kalman_enabled: bool = False,
        compression_latency: int = 0,
        rtm_pose_gpu_backend: str = "cuda",
    ) -> None:
        self.tracker_mode = tracker_mode
        self.output_mode = output_mode
        self.smoothing = max(0.0, min(0.98, smoothing))
        self.deadzone = max(0.0, min(0.25, deadzone))
        self.motion_gain = max(0.1, min(8.0, motion_gain))
        self.visual_stroke_scale = max(0.2, min(1.4, visual_stroke_scale))
        self.enable_smoothing = enable_smoothing
        self.enable_deadzone = enable_deadzone
        self.response_curve = response_curve
        self.l0_jitter_guard = l0_jitter_guard
        self.l0_guard_strength = max(0.0, min(1.0, l0_guard_strength))
        self.enable_extreme_reset = enable_extreme_reset
        self.enable_endpoint_guard = enable_endpoint_guard
        self.endpoint_margin = max(0.0, min(0.25, endpoint_margin))
        self.pose_dance_l0 = bool(pose_dance_mode if pose_dance_l0 is None else pose_dance_l0)
        self.pose_dance_six_axis = bool(pose_dance_mode if pose_dance_six_axis is None else pose_dance_six_axis)
        self.pose_l0_weight = max(0.0, min(1.0, float(pose_l0_weight))) if self.pose_dance_l0 else 0.0
        self.pose_six_axis_weight = max(0.0, min(1.0, float(pose_six_axis_weight))) if self.pose_dance_six_axis else 0.0
        self.pose_v2_dance_six_axis = bool(pose_v2_dance_six_axis)
        v2_l0_weight = self.pose_l0_weight if pose_v2_l0_weight is None else float(pose_v2_l0_weight)
        v2_six_axis_weight = self.pose_six_axis_weight if pose_v2_six_axis_weight is None else float(pose_v2_six_axis_weight)
        self.pose_v2_l0_weight = max(0.0, min(1.0, v2_l0_weight)) if self.pose_v2_dance_six_axis else 0.0
        self.pose_v2_six_axis_weight = max(0.0, min(1.0, v2_six_axis_weight)) if self.pose_v2_dance_six_axis else 0.0
        self.rtm_pose_2d_enabled = bool(rtm_pose_2d_enabled)
        self.rtm_pose_3d_enabled = bool(rtm_pose_3d_enabled) and not self.rtm_pose_2d_enabled
        self.rtm_pose_3d_weight = max(0.0, min(1.0, float(rtm_pose_3d_weight))) if self._rtm_pose_enabled() else 0.0
        self.rtm_hybrid_l0_enabled = bool(rtm_hybrid_l0_enabled) if self._rtm_pose_enabled() else False
        self.rtm_hybrid_l0_weight = max(0.01, min(1.0, float(rtm_hybrid_l0_weight))) if self.rtm_hybrid_l0_enabled else 0.0
        self.rtm_pose_flow_enabled = bool(rtm_pose_flow_enabled) if self._rtm_pose_enabled() else False
        self.rtm_pose_kalman_enabled = bool(rtm_pose_kalman_enabled) if self._rtm_pose_enabled() else False
        self.rtm_pose_device = ("directml" if rtm_pose_gpu_backend == "directml" else "cuda") if bool(rtm_pose_gpu_enabled) else "cpu"
        self._rtm_pose_2d_backend = OptionalRtmPose2dBackend(rtm_pose_2d_model_path, device=self.rtm_pose_device) if self.rtm_pose_2d_enabled else None
        self._rtm_pose_3d_backend = OptionalRtmPose3dBackend(rtm_pose_3d_model_path, device=self.rtm_pose_device) if self.rtm_pose_3d_enabled else None
        self._rtm_pose_3d_last: RtmPose3dResult | None = None
        self._rtm_pose_3d_last_positions: dict[str, float] | None = None
        self._rtm_pose_3d_last_confidence = 0.0
        self._rtm_pose_3d_last_frame = 0
        self._rtm_pose_3d_velocity = {axis: 0.0 for axis in SIX_AXES}
        self._rtm_pose_3d_body_scale = 0.0
        self._rtm_pose_3d_l0_reference_y: float | None = None
        self._rtm_pose_3d_l0_raw = 0.5
        self._rtm_pose_3d_axis_raw = {axis: 0.5 for axis in SIX_AXES}
        self._rtm_pose_3d_r0_front_width = 0.0
        self._rtm_pose_3d_r0_side_hint = 0.0
        self._rtm_pose_3d_previous_hip_sample: tuple[float, np.ndarray, np.ndarray, float] | None = None
        self._rtm_pose_3d_l0_reference_sample: tuple[float, np.ndarray, np.ndarray, float] | None = None
        self._rtm_pose_3d_previous_axis_sample: tuple[float, dict[str, np.ndarray | float], float] | None = None
        self._rtm_pose_3d_axis_reference_sample: tuple[float, dict[str, np.ndarray | float], float] | None = None
        self._rtm_pose_3d_lock = threading.Lock()
        self._rtm_pose_3d_pending = False
        self._rtm_pose_3d_last_ms = 0.0
        self._rtm_pose_3d_last_error = ""
        self._rtm_pose_3d_frame = 0
        self._rtm_pose_3d_last_detection_frame = 0
        self._rtm_pose_flow_gray: np.ndarray | None = None
        self._rtm_pose_kalman_state: np.ndarray | None = None
        self._rtm_pose_kalman_cov: np.ndarray | None = None
        self._rtm_pose_kalman_time: float | None = None
        self.compression_latency = max(-5, min(5, int(compression_latency)))
        self._prev_gray: np.ndarray | None = None
        self._positions = {axis: 0.5 for axis in SIX_AXES}
        self._phase = 0.0
        self._stroke_direction = 0
        self._direction_score = 0.0
        self._velocity_y = 0.0
        self._flow_position = 0.5
        self._flow_history_dy: deque[float] = deque(maxlen=3)
        self._flow_history_dx: deque[float] = deque(maxlen=3)
        self._center_history_x: deque[float] = deque(maxlen=5)
        self._pose_v2_center_x: deque[float] = deque(maxlen=6)
        self._pose_v2_center_y: deque[float] = deque(maxlen=6)
        self._pose_v2_area: deque[float] = deque(maxlen=18)
        self._pose_v2_angle: deque[float] = deque(maxlen=8)
        self._pose_v2_aspect: deque[float] = deque(maxlen=18)
        self._pose_v2_body_state: deque[tuple[float, float, float, float]] = deque(maxlen=10)
        self._pose_v2_core_state: deque[tuple[float, float, float, float]] = deque(maxlen=10)
        self._pose_v2_axis_recent = {axis: deque(maxlen=14) for axis in ("R0", "R1", "R2")}
        self._pose_v2_last_skeleton: dict[str, tuple[int, int]] = {}
        self._pose_v2_last_edge_notes: list[str] = []
        self._angle_history: deque[float] = deque(maxlen=5)
        self._activity_history: deque[float] = deque(maxlen=5)
        self._roi: tuple[int, int, int, int] | None = None
        self._roi_missing_frames = 0
        self._dis_flow = None
        self._last_l0 = 0.5
        self._stroke_velocity = 0.0
        self._stroke_side = 1.0
        self._last_stroke_direction = 0
        self._six_axis_targets = {axis: 0.5 for axis in SIX_AXES}
        self._l0_guard_direction = 0
        self._l0_flip_hold = 0
        self._flow_edge_frames = 0
        self._ambiguous_l0_frames = 0
        self._l0_recent: deque[float] = deque(maxlen=18)

    @property
    def axes(self) -> list[str]:
        return ["L0"] if self.output_mode != "Six Axis" else SIX_AXES.copy()

    def reset(self) -> None:
        self._prev_gray = None
        self._positions = {axis: 0.5 for axis in SIX_AXES}
        self._phase = 0.0
        self._stroke_direction = 0
        self._direction_score = 0.0
        self._velocity_y = 0.0
        self._flow_position = 0.5
        self._flow_history_dy.clear()
        self._flow_history_dx.clear()
        self._center_history_x.clear()
        self._pose_v2_center_x.clear()
        self._pose_v2_center_y.clear()
        self._pose_v2_area.clear()
        self._pose_v2_angle.clear()
        self._pose_v2_aspect.clear()
        self._pose_v2_body_state.clear()
        self._pose_v2_core_state.clear()
        for history in self._pose_v2_axis_recent.values():
            history.clear()
        self._pose_v2_last_skeleton = {}
        self._pose_v2_last_edge_notes = []
        self._angle_history.clear()
        self._activity_history.clear()
        self._roi = None
        self._roi_missing_frames = 0
        self._last_l0 = 0.5
        self._stroke_velocity = 0.0
        self._stroke_side = 1.0
        self._last_stroke_direction = 0
        self._six_axis_targets = {axis: 0.5 for axis in SIX_AXES}
        self._l0_guard_direction = 0
        self._l0_flip_hold = 0
        self._flow_edge_frames = 0
        self._ambiguous_l0_frames = 0
        self._l0_recent.clear()
        self._rtm_pose_3d_last = None
        self._rtm_pose_3d_last_positions = None
        self._rtm_pose_3d_last_confidence = 0.0
        self._rtm_pose_3d_last_frame = 0
        self._rtm_pose_3d_velocity = {axis: 0.0 for axis in SIX_AXES}
        self._rtm_pose_3d_body_scale = 0.0
        self._rtm_pose_3d_l0_reference_y = None
        self._rtm_pose_3d_l0_raw = 0.5
        self._rtm_pose_3d_axis_raw = {axis: 0.5 for axis in SIX_AXES}
        self._rtm_pose_3d_r0_front_width = 0.0
        self._rtm_pose_3d_r0_side_hint = 0.0
        self._rtm_pose_3d_previous_hip_sample = None
        self._rtm_pose_3d_l0_reference_sample = None
        self._rtm_pose_3d_previous_axis_sample = None
        self._rtm_pose_3d_axis_reference_sample = None
        self._rtm_pose_3d_pending = False
        self._rtm_pose_3d_last_ms = 0.0
        self._rtm_pose_3d_last_error = ""
        self._rtm_pose_3d_frame = 0
        self._rtm_pose_3d_last_detection_frame = 0
        self._rtm_pose_flow_gray = None
        self._rtm_pose_kalman_state = None
        self._rtm_pose_kalman_cov = None
        self._rtm_pose_kalman_time = None

    def process(self, frame_bgr: np.ndarray) -> AxisAnalysis:
        preview = frame_bgr.copy()
        if self._rtm_pose_3d_only():
            measured, confidence, pose_result = self._measure_rtm_pose_3d(frame_bgr)
            if measured is None:
                measured = self._active_positions()
                confidence = 0.0
            activity = max(0.0, min(1.0, confidence))
            self._apply_measured_positions(measured, confidence, activity=activity)
            active = self._active_positions()
            self._draw_preview(preview, active, confidence, draw_l0_line=False)
            preview = self._draw_rtm_pose_3d_preview(preview, pose_result)
            return AxisAnalysis(active, confidence, activity, preview)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self._prev_gray is None:
            self._prev_gray = gray
            self._draw_preview(preview, self._positions, 0.0, draw_l0_line=not self._rtm_pose_enabled())
            if self._rtm_pose_enabled():
                preview = self._draw_rtm_pose_3d_preview(preview)
            elif self.pose_l0_weight > 0.0 or self.pose_six_axis_weight > 0.0:
                preview = self._append_pose_preview(preview, self._active_positions(), 0.0)
            return AxisAnalysis(self._active_positions(), 0.0, 0.0, preview)

        diff = cv2.absdiff(gray, self._prev_gray)
        _, mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        mask = self._dominant_motion_mask(mask)
        activity = float(np.count_nonzero(mask)) / float(mask.size)
        flow = self._flow(gray)
        if self._rtm_pose_enabled() and self.rtm_hybrid_l0_enabled:
            l0, confidence = self._measure_l0(gray, mask, flow, activity, preview, "混合分析（推荐-非舞蹈）")
            measured = self._active_positions()
            measured["L0"] = l0
        else:
            measured, confidence = self._measure(gray, mask, flow, activity, preview)
        if self._rtm_pose_enabled() and self.rtm_pose_3d_weight > 0.0:
            rtm_positions, rtm_confidence, pose_result = self._measure_rtm_pose_3d(frame_bgr)
            if rtm_positions is not None:
                blend = min(1.0, self.rtm_pose_3d_weight * max(0.0, min(1.0, rtm_confidence)))
                for axis in self.axes:
                    if axis in rtm_positions:
                        if axis == "L0" and self.rtm_hybrid_l0_enabled:
                            hybrid_weight = self.rtm_hybrid_l0_weight
                            measured[axis] = measured.get(axis, self._positions[axis]) * hybrid_weight + rtm_positions[axis] * (1.0 - hybrid_weight)
                        else:
                            measured[axis] = measured.get(axis, self._positions[axis]) * (1.0 - blend) + rtm_positions[axis] * blend
                confidence = max(confidence, rtm_confidence)
                activity = max(activity, rtm_confidence * blend)
        self._apply_measured_positions(measured, confidence, activity)

        self._prev_gray = gray
        active = self._active_positions()
        self._draw_preview(preview, active, confidence, draw_l0_line=not self._rtm_pose_enabled())
        if self._rtm_pose_enabled():
            preview = self._draw_rtm_pose_3d_preview(preview, pose_result if "pose_result" in locals() else None)
        elif self.pose_v2_dance_six_axis and (self.pose_v2_l0_weight > 0.0 or self.pose_v2_six_axis_weight > 0.0):
            preview = self._pose_v2_split_preview(preview)
        elif self.pose_l0_weight > 0.0 or self.pose_six_axis_weight > 0.0:
            preview = self._append_pose_preview(preview, active, activity)
        return AxisAnalysis(active, confidence, activity, preview)

    def _rtm_pose_3d_only(self) -> bool:
        return self._rtm_pose_enabled() and self.rtm_pose_3d_weight >= 0.999 and not self.rtm_hybrid_l0_enabled

    def _rtm_pose_enabled(self) -> bool:
        return self.rtm_pose_2d_enabled or self.rtm_pose_3d_enabled

    def _rtm_pose_label(self) -> str:
        return "RTM Pose 2D" if self.rtm_pose_2d_enabled else "RTM Pose 3D"

    def _apply_measured_positions(self, measured: dict[str, float], confidence: float, activity: float) -> None:
        for axis, value in measured.items():
            value = self._shape(max(0.0, min(1.0, value)))
            if axis == "L0":
                value = self._stabilize_l0(value, activity if activity > 0.0 else max(0.01, confidence))
                value = self._soft_limit_l0(value)
                self._l0_recent.append(value)
            delta = value - self._positions[axis]
            axis_deadzone = self.deadzone if axis == "L0" else min(self.deadzone * 0.25, 0.002)
            if not self.enable_deadzone or abs(delta) >= axis_deadzone:
                if self.enable_smoothing:
                    axis_smoothing = self.smoothing if axis == "L0" else min(self.smoothing, 0.30)
                    self._positions[axis] = self._positions[axis] * axis_smoothing + value * (1.0 - axis_smoothing)
                else:
                    self._positions[axis] = value

    def _active_positions(self) -> dict[str, float]:
        return {axis: self._positions[axis] for axis in self.axes}

    def _shape(self, value: float) -> float:
        centered = (value - 0.5) * 2.0
        mode = self.response_curve.lower()
        if mode.startswith("soft"):
            centered = float(np.tanh(centered * 1.35) / np.tanh(1.35))
        elif mode.startswith("sharp"):
            centered = np.sign(centered) * (abs(centered) ** 0.68)
        elif mode.startswith("ease"):
            centered = np.sign(centered) * (abs(centered) ** 1.45)
        return max(0.0, min(1.0, 0.5 + centered * 0.5))

    def _stabilize_l0(self, value: float, activity: float) -> float:
        if not self.l0_jitter_guard:
            return value
        current = self._positions["L0"]
        delta = value - current
        abs_delta = abs(delta)
        strength = self.l0_guard_strength
        micro = max(self.deadzone * (1.4 + strength * 2.2), 0.004 + strength * 0.010)
        if abs_delta < micro:
            return current
        if activity < 0.0009 and abs_delta < 0.08:
            return current

        direction = 1 if delta > 0 else -1
        if self._l0_guard_direction and direction != self._l0_guard_direction and abs_delta < 0.075:
            self._l0_flip_hold = max(self._l0_flip_hold, 2 + round(strength * 4))
        self._l0_guard_direction = direction

        if self._l0_flip_hold > 0 and abs_delta < 0.09:
            self._l0_flip_hold -= 1
            return current + delta * (0.10 + 0.16 * (1.0 - strength))

        if abs_delta < 0.055:
            alpha = 0.22 + (abs_delta / 0.055) * 0.28
            alpha *= 1.0 - strength * 0.42
            return current + delta * max(0.08, alpha)
        return value

    def _flow(self, gray: np.ndarray) -> np.ndarray:
        if self._is_hybrid_analysis_mode(self.tracker_mode) or (self._rtm_pose_enabled() and self.rtm_hybrid_l0_enabled):
            try:
                if self._dis_flow is None:
                    self._dis_flow = cv2.DISOpticalFlow.create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
                return self._dis_flow.calc(self._prev_gray, gray, None)
            except (AttributeError, cv2.error):
                pass
        return cv2.calcOpticalFlowFarneback(
            self._prev_gray,
            gray,
            None,
            0.5,
            3,
            21,
            3,
            5,
            1.2,
            0,
        )

    def _measure(
        self,
        gray: np.ndarray,
        mask: np.ndarray,
        flow: np.ndarray,
        activity: float,
        preview: np.ndarray,
    ) -> tuple[dict[str, float], float]:
        mode = self.tracker_mode.lower()
        source_bgr = preview.copy()
        l0, confidence = self._measure_l0(gray, mask, flow, activity, preview, mode)
        if self.output_mode != "Six Axis":
            return {"L0": l0}, confidence

        center_x, center_y = self._motion_center(mask)
        mean_dx, mean_dy, pitch_delta = self._flow_summary(flow, mask)
        angle = self._motion_angle(mask)
        if center_x is not None:
            self._center_history_x.append(center_x)
        self._angle_history.append(angle)
        self._activity_history.append(activity)
        smooth_center_x = float(np.median(self._center_history_x)) if self._center_history_x else 0.5
        smooth_angle = float(np.median(self._angle_history)) if self._angle_history else 0.0
        smooth_activity = float(np.median(self._activity_history)) if self._activity_history else activity

        l0_centered = l0 - 0.5
        l0_delta = l0 - self._last_l0
        self._last_l0 = l0
        self._stroke_velocity = self._stroke_velocity * 0.68 + l0_delta * 0.32
        stroke_direction = 1 if self._stroke_velocity > 0.003 else -1 if self._stroke_velocity < -0.003 else self._last_stroke_direction
        if stroke_direction and self._last_stroke_direction and stroke_direction != self._last_stroke_direction:
            self._stroke_side *= -1.0
        if stroke_direction:
            self._last_stroke_direction = stroke_direction
        activity_drive = min(1.0, max(0.0, smooth_activity * 18.0))
        stroke_amount = min(1.0, abs(l0_centered) * 2.0)
        stroke_sway = self._stroke_side * (0.06 + 0.10 * stroke_amount + 0.04 * activity_drive)
        visual_lateral = (smooth_center_x - 0.5) * 0.16 + mean_dx * 1.8 * self.motion_gain
        if self.pose_six_axis_weight > 0.0:
            weight = self.pose_six_axis_weight
            stroke_sway *= 1.0 + 0.30 * weight
            visual_lateral *= 1.0 + 0.70 * weight
            l0_centered *= 1.0 - 0.28 * weight
        raw_positions = {
            "L0": l0,
            "L1": 0.5 + self._centered_clamp(-l0_centered * (0.34 + activity_drive * 0.10) + self._stroke_velocity * 0.35, 0.34),
            "L2": 0.5 + self._centered_clamp(stroke_sway * 0.92 + visual_lateral, 0.30),
            "R0": 0.5 + self._centered_clamp(-stroke_sway * 0.98 + mean_dx * 1.4 * self.motion_gain, 0.30),
            "R1": 0.5 + self._centered_clamp(stroke_sway * 0.46 + smooth_angle / 520.0, 0.20),
            "R2": 0.5 + self._centered_clamp(-l0_centered * (0.30 + 0.08 * activity_drive) + pitch_delta * 1.8 * self.motion_gain, 0.30),
        }
        if self.pose_v2_dance_six_axis and self.pose_v2_six_axis_weight > 0.0:
            pose_positions, pose_confidence = self._measure_pose_v2_dance(
                mask,
                flow,
                l0,
                mean_dx,
                pitch_delta,
                source_bgr,
                preview,
            )
            if pose_positions:
                blend = min(0.78, self.pose_v2_six_axis_weight * pose_confidence)
                for axis in ("L1", "L2", "R0", "R1", "R2"):
                    raw_positions[axis] = raw_positions[axis] * (1.0 - blend) + pose_positions[axis] * blend
                if self.pose_v2_l0_weight > 0.0:
                    l0_blend = min(0.42, self.pose_v2_l0_weight * pose_confidence)
                    raw_positions["L0"] = raw_positions["L0"] * (1.0 - l0_blend) + pose_positions["L0"] * l0_blend

        positions = {"L0": raw_positions["L0"]}
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            previous = self._six_axis_targets.get(axis, 0.5)
            target = raw_positions[axis]
            positions[axis] = previous * 0.76 + target * 0.24
            self._six_axis_targets[axis] = positions[axis]
        self._draw_axis_boxes(mask, preview)
        return positions, confidence

    def _measure_l0(
        self,
        gray: np.ndarray,
        mask: np.ndarray,
        flow: np.ndarray,
        activity: float,
        preview: np.ndarray,
        mode: str,
    ) -> tuple[float, float]:
        confidence = min(1.0, activity * 14.0)
        if self._is_hybrid_analysis_mode(mode):
            value = self._measure_hybrid_analysis_flow(mask, flow, activity, preview)
        elif mode.startswith("stroke"):
            value = self._measure_stroke_phase(mask, flow, activity)
        elif mode.startswith("optical"):
            _mean_dx, mean_dy, _pitch = self._flow_summary(flow, mask)
            value = self._bounded_l0(self._positions["L0"] + mean_dy * 3.2 * self.motion_gain)
        elif mode.startswith("hybrid"):
            center = self._motion_center(mask)
            _mean_dx, mean_dy, _pitch = self._flow_summary(flow, mask)
            center_y = center[1] if center[1] is not None else self._positions["L0"]
            optical_y = self._positions["L0"] + mean_dy * 3.0 * self.motion_gain
            value = self._bounded_l0(center_y * 0.62 + optical_y * 0.38)
        elif mode.startswith("activity"):
            if confidence < 0.04:
                value = self._positions["L0"]
            else:
                speed = 0.08 + min(0.42, activity * 8.0) * self.motion_gain
                amplitude = min(0.42, 0.10 + activity * 7.0)
                self._phase = (self._phase + speed) % 1.0
                triangle = 1.0 - abs(self._phase * 2.0 - 1.0)
                value = self._bounded_l0(0.5 - amplitude + triangle * amplitude * 2.0)
        else:
            center = self._motion_center(mask)
            if center[1] is None:
                value = self._positions["L0"]
            else:
                value = self._bounded_l0(center[1])
        return self._center_if_repetitive_l0(value, flow, mask, activity), confidence

    def _measure_stroke_phase(self, mask: np.ndarray, flow: np.ndarray, activity: float) -> float:
        _mean_dx, mean_dy, _pitch = self._flow_summary(flow, mask)
        velocity = float(mean_dy)
        self._velocity_y = self._velocity_y * 0.72 + velocity * 0.28
        threshold = max(0.00055, 0.0019 / self.motion_gain)

        direction = 0
        if activity >= 0.001 and abs(self._velocity_y) >= threshold:
            direction = 1 if self._velocity_y > 0.0 else -1

        if direction:
            self._direction_score = self._direction_score * 0.62 + direction * 0.38
            if self._direction_score > 0.24:
                self._stroke_direction = 1
            elif self._direction_score < -0.24:
                self._stroke_direction = -1
        else:
            self._direction_score *= 0.82
            if abs(self._direction_score) < 0.10:
                self._stroke_direction = 0

        if self._stroke_direction == 1:
            target = self.endpoint_margin if self.enable_endpoint_guard else 0.0
        elif self._stroke_direction == -1:
            target = 1.0 - self.endpoint_margin if self.enable_endpoint_guard else 1.0
        else:
            target = self._positions["L0"] * 0.92 + 0.5 * 0.08

        strength = min(1.0, max(0.0, abs(self._velocity_y) / (threshold * 7.5)))
        alpha = 0.18 + strength * 0.46
        if activity < 0.001:
            alpha *= 0.25
        return self._bounded_l0(self._positions["L0"] * (1.0 - alpha) + target * alpha)

    @staticmethod
    def _is_hybrid_analysis_mode(mode: str) -> bool:
        lowered = mode.lower()
        legacy_prefix = "d" + "kai"
        return lowered.startswith("混合分析") or lowered.startswith(legacy_prefix)

    def _measure_hybrid_analysis_flow(self, mask: np.ndarray, flow: np.ndarray, activity: float, preview: np.ndarray) -> float:
        roi = self._update_roi(mask, preview)
        if roi is None or activity < 0.00035:
            self._relax_flow_position(activity)
            return self._flow_position

        x1, y1, x2, y2 = roi
        roi_flow = flow[y1:y2, x1:x2]
        roi_mask = mask[y1:y2, x1:x2] > 0
        if roi_flow.size == 0 or not np.any(roi_mask):
            return self._flow_position

        mag, _angle = cv2.cartToPolar(roi_flow[..., 0], roi_flow[..., 1])
        moving = roi_mask & (mag > max(0.18, np.percentile(mag[roi_mask], 55)))
        if not np.any(moving):
            return self._flow_position

        h, w = flow.shape[:2]
        dx = float(np.median(roi_flow[..., 0][moving])) / max(1, w)
        dy = float(np.median(roi_flow[..., 1][moving])) / max(1, h)
        self._flow_history_dx.append(dx)
        self._flow_history_dy.append(dy)
        smooth_dx = float(np.median(self._flow_history_dx))
        smooth_dy = float(np.median(self._flow_history_dy))

        sensitivity = 5.2 * self.motion_gain
        delta = -smooth_dy * sensitivity
        if self.pose_l0_weight > 0.0:
            weight = self.pose_l0_weight
            horizontal = abs(smooth_dx)
            vertical = abs(smooth_dy)
            if horizontal > vertical * 1.15 and horizontal > 0.00035:
                delta *= 1.0 - 0.62 * weight
            elif horizontal > vertical * 0.80 and vertical < 0.0011:
                delta *= 1.0 - 0.38 * weight
        magnitude = abs(delta)
        if magnitude > 0.10:
            delta *= 1.28
        elif magnitude > 0.035:
            delta *= 1.18
        noise_floor = max(0.0025, self.deadzone * 0.18)
        if self.l0_jitter_guard:
            noise_floor = max(noise_floor, 0.0035 + self.l0_guard_strength * 0.0045, self.deadzone * (0.48 + self.l0_guard_strength * 0.42))
        if magnitude < noise_floor:
            delta = 0.0

        self._flow_position = self._bounded_l0(self._flow_position + self._edge_damped_delta(delta))
        self._relax_flow_position(activity)
        self._release_flow_edge(delta, activity)
        activity_scale = min(1.0, activity * 35.0 + abs(smooth_dy) * 48.0)
        scale = min(1.4, self.visual_stroke_scale * (0.72 + activity_scale * 0.38))
        position = 0.5 + (self._flow_position - 0.5) * scale
        cv2.rectangle(preview, (x1, y1), (x2, y2), (255, 170, 20), 2)
        return self._bounded_l0(position)

    def _bounded_l0(self, value: float) -> float:
        if not self.enable_endpoint_guard:
            return max(0.0, min(1.0, value))
        margin = self.endpoint_margin
        return max(margin, min(1.0 - margin, value))

    def _center_if_repetitive_l0(self, value: float, flow: np.ndarray, mask: np.ndarray, activity: float) -> float:
        if not self.enable_extreme_reset:
            return value
        mean_dx, mean_dy, pitch_delta = self._flow_summary(flow, mask)
        vertical = abs(mean_dy) + abs(pitch_delta) * 0.35
        lateral = abs(mean_dx) + abs(pitch_delta) * 0.18
        weak_vertical = vertical < max(0.00055, self.deadzone * 0.075)
        lateral_dominant = lateral > vertical * 1.65 and lateral > 0.00045
        if self.pose_l0_weight > 0.0:
            weight = self.pose_l0_weight
            weak_vertical = vertical < max(0.00055 + 0.00025 * weight, self.deadzone * (0.075 + 0.035 * weight))
            lateral_dominant = lateral > vertical * (1.65 - 0.53 * weight) and lateral > 0.00045 - 0.00017 * weight
        near_edge = abs(self._positions["L0"] - 0.5) > 0.34 or abs(value - 0.5) > 0.36
        recent_flat = len(self._l0_recent) >= 8 and (max(self._l0_recent) - min(self._l0_recent)) < 0.055

        if activity < 0.00055 or (near_edge and weak_vertical) or (lateral_dominant and (near_edge or recent_flat)):
            self._ambiguous_l0_frames = min(60, self._ambiguous_l0_frames + (2 if self.pose_l0_weight > 0.0 and lateral_dominant else 1))
        elif self.pose_l0_weight > 0.0 and lateral_dominant and activity < 0.012:
            self._ambiguous_l0_frames = min(60, self._ambiguous_l0_frames + 1)
        else:
            self._ambiguous_l0_frames = max(0, self._ambiguous_l0_frames - 2)

        release_after = 4 if self.pose_l0_weight > 0.0 else 6
        if self._ambiguous_l0_frames < release_after:
            return value
        alpha_cap = 0.18 + 0.06 * self.pose_l0_weight
        alpha = min(alpha_cap, 0.035 + self._ambiguous_l0_frames * 0.006)
        if near_edge:
            alpha += 0.035
        return self._bounded_l0(value * (1.0 - alpha) + 0.5 * alpha)

    def _soft_limit_l0(self, value: float) -> float:
        if not self.enable_endpoint_guard:
            return value
        margin = self.endpoint_margin
        if value < margin:
            return margin + (value - margin) * 0.18
        if value > 1.0 - margin:
            return 1.0 - margin + (value - (1.0 - margin)) * 0.18
        return value

    def _edge_damped_delta(self, delta: float) -> float:
        if not self.enable_extreme_reset:
            return delta
        margin = max(0.035, self.endpoint_margin * 0.65)
        low_zone = self._flow_position <= margin and delta < 0.0
        high_zone = self._flow_position >= 1.0 - margin and delta > 0.0
        if low_zone or high_zone:
            return delta * 0.22
        return delta

    def _relax_flow_position(self, activity: float) -> None:
        if not self.enable_extreme_reset:
            return
        distance_from_center = abs(self._flow_position - 0.5)
        if distance_from_center < 0.12:
            return
        strength = 0.008 + self.l0_guard_strength * 0.012
        if activity < 0.00035 and distance_from_center > 0.42:
            strength += 0.018
        self._flow_position += (0.5 - self._flow_position) * strength

    def _release_flow_edge(self, delta: float, activity: float) -> None:
        if not self.enable_extreme_reset:
            return
        at_low = self._flow_position <= 0.025
        at_high = self._flow_position >= 0.975
        outward_or_still = (at_low and delta <= 0.0015) or (at_high and delta >= -0.0015)
        if not outward_or_still:
            self._flow_edge_frames = 0
            return
        self._flow_edge_frames += 1
        threshold = 10 if activity < 0.0015 else 22
        if self._flow_edge_frames < threshold:
            return
        release = 0.012 + self.l0_guard_strength * 0.014
        self._flow_position += (0.5 - self._flow_position) * release

    def _update_roi(self, mask: np.ndarray, preview: np.ndarray) -> tuple[int, int, int, int] | None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [contour for contour in contours if cv2.contourArea(contour) >= max(20, mask.size * 0.00018)]
        h, w = mask.shape[:2]
        if contours:
            x1 = w
            y1 = h
            x2 = 0
            y2 = 0
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:4]:
                x, y, cw, ch = cv2.boundingRect(contour)
                x1 = min(x1, x)
                y1 = min(y1, y)
                x2 = max(x2, x + cw)
                y2 = max(y2, y + ch)
            pad = max(16, round(min(h, w) * 0.04))
            new_roi = self._clamp_roi((x1 - pad, y1 - pad, x2 + pad, y2 + pad), h, w)
            if self._roi is not None:
                old = np.array(self._roi, dtype=np.float32)
                new = np.array(new_roi, dtype=np.float32)
                new_roi = tuple(int(v) for v in old * 0.58 + new * 0.42)
                new_roi = self._clamp_roi(new_roi, h, w)
            self._roi = new_roi
            self._roi_missing_frames = 0
        elif self._roi is not None and self._roi_missing_frames < 15:
            self._roi_missing_frames += 1
        else:
            self._roi = None

        if self._roi is not None:
            x1, y1, x2, y2 = self._roi
            cv2.rectangle(preview, (x1, y1), (x2, y2), (30, 220, 255), 1)
        return self._roi

    @staticmethod
    def _motion_center(mask: np.ndarray) -> tuple[float | None, float | None]:
        moments = cv2.moments(mask)
        if moments["m00"] <= 1.0:
            return None, None
        y = moments["m01"] / moments["m00"]
        x = moments["m10"] / moments["m00"]
        return x / max(1, mask.shape[1] - 1), y / max(1, mask.shape[0] - 1)

    @staticmethod
    def _clamp_roi(roi: tuple[int, int, int, int], img_h: int, img_w: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = roi
        x1 = max(0, min(img_w - 1, int(x1)))
        y1 = max(0, min(img_h - 1, int(y1)))
        x2 = max(x1 + 1, min(img_w, int(x2)))
        y2 = max(y1 + 1, min(img_h, int(y2)))
        min_size = min(40, img_w, img_h)
        if x2 - x1 < min_size:
            cx = (x1 + x2) // 2
            x1 = max(0, cx - min_size // 2)
            x2 = min(img_w, x1 + min_size)
        if y2 - y1 < min_size:
            cy = (y1 + y2) // 2
            y1 = max(0, cy - min_size // 2)
            y2 = min(img_h, y1 + min_size)
        return x1, y1, x2, y2

    @staticmethod
    def _dominant_motion_mask(mask: np.ndarray) -> np.ndarray:
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
        if count <= 1:
            return mask
        clean = np.zeros_like(mask)
        min_area = max(20, int(mask.size * 0.00018))
        areas = [(label, int(stats[label, cv2.CC_STAT_AREA])) for label in range(1, count)]
        kept = 0
        for label, area in sorted(areas, key=lambda item: item[1], reverse=True):
            if area < min_area or kept >= 5:
                continue
            clean[labels == label] = 255
            kept += 1
        return clean if kept else np.zeros_like(mask)

    @staticmethod
    def _flow_summary(flow: np.ndarray, mask: np.ndarray | None = None) -> tuple[float, float, float]:
        mag, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        moving = mag > max(0.25, np.percentile(mag, 76))
        if mask is not None:
            moving &= mask > 0
        if not np.any(moving):
            return 0.0, 0.0, 0.0
        h, w = flow.shape[:2]
        dx = float(np.median(flow[..., 0][moving])) / max(1, w)
        dy = float(np.median(flow[..., 1][moving])) / max(1, h)
        top = flow[: h // 2, :, 1]
        bottom = flow[h // 2 :, :, 1]
        pitch = (float(np.median(top)) - float(np.median(bottom))) / max(1, h)
        return dx, dy, pitch

    @staticmethod
    def _motion_angle(mask: np.ndarray) -> float:
        points = cv2.findNonZero(mask)
        if points is None or len(points) < 12:
            return 0.0
        data = points.reshape(-1, 2).astype(np.float32)
        mean, eigenvectors = cv2.PCACompute(data, mean=None, maxComponents=2)
        _ = mean
        vx, vy = eigenvectors[0]
        angle = float(np.degrees(np.arctan2(vy, vx)))
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180
        return angle

    def _measure_pose_v2_dance(
        self,
        mask: np.ndarray,
        flow: np.ndarray,
        l0: float,
        mean_dx: float,
        pitch_delta: float,
        frame_bgr: np.ndarray,
        preview: np.ndarray,
    ) -> tuple[dict[str, float] | None, float]:
        h, w = mask.shape[:2]
        motion_mask, ignored_top, ignored_bottom = self._pose_v2_clean_motion_mask(mask)
        subject_mask = self._pose_v2_subject_mask(frame_bgr, motion_mask, ignored_top, ignored_bottom)
        body_bounds = self._pose_v2_mask_bounds(subject_mask)
        if body_bounds is None:
            body_bounds = self._pose_v2_mask_bounds(motion_mask)
        if body_bounds is None:
            return None, 0.0
        if not self._pose_v2_body_is_stable(body_bounds, w, h):
            self._pose_v2_last_skeleton = {}
            self._pose_v2_last_edge_notes = []
            self._draw_pose_v2_unstable(preview, ignored_top, ignored_bottom)
            return None, 0.0

        edge_info = self._pose_v2_edge_info(subject_mask, body_bounds, ignored_top, ignored_bottom)
        core_roi, core_confidence, skeleton, edge_notes = self._pose_v2_infer_core_roi(subject_mask, motion_mask, body_bounds, edge_info)
        if core_roi is None or not self._pose_v2_core_is_stable(core_roi, w, h):
            self._pose_v2_last_skeleton = skeleton
            self._pose_v2_last_edge_notes = edge_notes
            self._draw_pose_v2_unstable(preview, ignored_top, ignored_bottom, edge_notes)
            return None, 0.0
        source_label = "Pose v2 edge skeleton"
        hip_x1, hip_y1, hip_x2, hip_y2 = core_roi
        edge_scale = self._pose_v2_edge_confidence_scale(core_roi, body_bounds, w, h, edge_info)
        if edge_scale <= 0.05:
            self._pose_v2_last_skeleton = skeleton
            self._pose_v2_last_edge_notes = edge_notes
            self._draw_pose_v2_skeleton(preview, skeleton, edge_notes, source_label)
            self._draw_pose_v2_unstable(preview, ignored_top, ignored_bottom, edge_notes)
            return None, 0.0

        hip_subject = subject_mask[hip_y1:hip_y2, hip_x1:hip_x2]
        hip_motion = motion_mask[hip_y1:hip_y2, hip_x1:hip_x2]
        hip_mask = hip_motion if np.count_nonzero(hip_motion) >= 18 else np.zeros_like(hip_motion)
        points = cv2.findNonZero(hip_mask)
        if points is None or len(points) < 18:
            cx = (hip_x1 + hip_x2) * 0.5
            cy = (hip_y1 + hip_y2) * 0.5
            rect = ((float(cx), float(cy)), (float(max(12, hip_x2 - hip_x1)), float(max(12, hip_y2 - hip_y1))), 0.0)
            confidence = 0.14 * core_confidence * edge_scale
        else:
            data = points.reshape(-1, 2).astype(np.float32)
            data[:, 0] += hip_x1
            data[:, 1] += hip_y1
            rect = cv2.minAreaRect(data)
            confidence = min(1.0, (0.22 + len(points) / max(18.0, mask.size * 0.010)) * core_confidence * edge_scale)

        (cx, cy), (edge_a, edge_b), angle = rect
        if edge_a < 8 or edge_b < 8:
            return None, 0.0
        if edge_a < edge_b:
            edge_a, edge_b = edge_b, edge_a
            angle += 90.0
        angle = self._normalize_pose_angle(float(angle))

        area_norm = max(0.00001, (edge_a * edge_b) / float(max(1, w * h)))
        aspect = max(edge_a, edge_b) / max(1.0, min(edge_a, edge_b))
        area_base = float(np.median(self._pose_v2_area)) if self._pose_v2_area else area_norm
        aspect_base = float(np.median(self._pose_v2_aspect)) if self._pose_v2_aspect else aspect
        angle_base = float(np.median(self._pose_v2_angle)) if self._pose_v2_angle else angle

        current_cx = float(cx) / max(1, w - 1)
        current_cy = float(cy) / max(1, h - 1)
        previous_cx = self._pose_v2_center_x[-1] if self._pose_v2_center_x else current_cx
        previous_cy = self._pose_v2_center_y[-1] if self._pose_v2_center_y else current_cy
        predict_lead = 0.42 if confidence >= 0.16 else 0.18
        smooth_cx = max(0.0, min(1.0, current_cx + (current_cx - previous_cx) * predict_lead))
        smooth_cy = max(0.0, min(1.0, current_cy + (current_cy - previous_cy) * predict_lead))
        self._pose_v2_center_x.append(current_cx)
        self._pose_v2_center_y.append(current_cy)
        self._pose_v2_area.append(area_norm)
        self._pose_v2_aspect.append(aspect)
        self._pose_v2_angle.append(angle)

        hip_flow = flow[hip_y1:hip_y2, hip_x1:hip_x2]
        flow_support = hip_subject > 0
        if not np.any(flow_support):
            flow_support = hip_motion > 0
        moving = self._pose_v2_moving_pixels(hip_flow, flow_support, hip_motion)
        motion_evidence = self._pose_v2_motion_evidence(hip_flow, moving, flow_support)
        twist = 0.0
        if hip_flow.size and np.any(moving):
            local_x = np.indices(hip_mask.shape)[1]
            left = moving & (local_x < hip_mask.shape[1] * 0.5)
            right = moving & (local_x >= hip_mask.shape[1] * 0.5)
            if np.any(left) and np.any(right):
                left_dx = float(np.median(hip_flow[..., 0][left])) / max(1, w)
                right_dx = float(np.median(hip_flow[..., 0][right])) / max(1, w)
                twist = (left_dx - right_dx) * 52.0 * self.motion_gain

        area_delta = (area_norm / max(0.00001, area_base)) - 1.0
        aspect_delta = (aspect / max(0.1, aspect_base)) - 1.0
        roll_delta = self._normalize_pose_angle(angle - angle_base)
        core_pitch = self._pose_v2_core_pitch(hip_flow, moving, h)

        pose_l0 = self._bounded_l0(0.5 + (smooth_cy - 0.5) * 1.16)
        pose_l1 = 0.5 + self._centered_clamp(area_delta * 0.18, 0.14)
        pose_l2 = 0.5 + self._centered_clamp((smooth_cx - 0.5) * 0.34 + mean_dx * 2.2 * self.motion_gain, 0.24)
        pose_r0 = 0.5 + self._centered_clamp(twist + (smooth_cx - 0.5) * 0.10, 0.24)
        pose_r1 = 0.5 + self._centered_clamp(roll_delta / 58.0, 0.22)
        pose_r2 = 0.5 + self._centered_clamp(core_pitch * 16.0 * self.motion_gain + pitch_delta * 4.0 * self.motion_gain + aspect_delta * 0.12, 0.22)
        pose_r0 = self._pose_v2_release_stuck_axis("R0", pose_r0, motion_evidence + min(0.25, abs(twist) * 1.6))
        pose_r1 = self._pose_v2_release_stuck_axis("R1", pose_r1, motion_evidence + min(0.25, abs(roll_delta) / 22.0))
        pose_r2 = self._pose_v2_release_stuck_axis("R2", pose_r2, motion_evidence + min(0.25, abs(core_pitch) * 260.0))

        self._draw_pose_v2_skeleton(preview, skeleton, edge_notes, source_label)
        self._draw_pose_v2_guides(preview, (hip_x1, hip_y1, hip_x2, hip_y2), ignored_top, ignored_bottom, motion_evidence)
        self._pose_v2_last_skeleton = skeleton
        self._pose_v2_last_edge_notes = edge_notes
        box = cv2.boxPoints(((float(cx), float(cy)), (float(edge_a), float(edge_b)), float(angle)))
        box_i = np.intp(box)
        cv2.polylines(preview, [box_i], True, (255, 0, 180), 2, cv2.LINE_AA)
        for index, point in enumerate(box_i):
            cv2.circle(preview, tuple(point), 3, (255, 210, 255), -1, cv2.LINE_AA)
            cv2.putText(preview, str(index + 1), tuple(point + np.array([4, -4])), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 230, 255), 1, cv2.LINE_AA)
        cv2.putText(preview, "Pose v2 hip plane", (max(6, hip_x1), max(18, hip_y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 0, 180), 1, cv2.LINE_AA)

        positions = {
            "L0": pose_l0,
            "L1": pose_l1,
            "L2": pose_l2,
            "R0": pose_r0,
            "R1": pose_r1,
            "R2": pose_r2,
        }
        return positions, confidence

    @staticmethod
    def _pose_v2_clean_motion_mask(mask: np.ndarray) -> tuple[np.ndarray, int, int]:
        h, w = mask.shape[:2]
        clean = mask.copy()
        ignored_top = int(h * 0.075)
        ignored_bottom = int(h * 0.905)
        side_margin = int(w * 0.025)
        clean[:ignored_top, :] = 0
        clean[ignored_bottom:, :] = 0
        if side_margin > 0:
            clean[:, :side_margin] = 0
            clean[:, w - side_margin :] = 0
        return clean, ignored_top, ignored_bottom

    @staticmethod
    def _pose_v2_subject_mask(frame_bgr: np.ndarray, motion_mask: np.ndarray, ignored_top: int, ignored_bottom: int) -> np.ndarray:
        h, w = motion_mask.shape[:2]
        band_y1 = max(0, min(h - 1, ignored_top))
        band_y2 = max(band_y1 + 1, min(h, ignored_bottom))
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        sat = hsv[..., 1]
        val = hsv[..., 2]
        margin = max(4, int(w * 0.045))
        patch_h = max(4, int((band_y2 - band_y1) * 0.045))
        patches = (
            lab[band_y1:band_y2, :margin],
            lab[band_y1:band_y2, max(0, w - margin) : w],
            lab[band_y1 : min(band_y2, band_y1 + patch_h), :],
            lab[max(band_y1, band_y2 - patch_h) : band_y2, :],
        )
        seeds: list[np.ndarray] = []
        for patch in patches:
            if patch.size == 0:
                continue
            seed = np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)
            if all(float(np.linalg.norm(seed - other)) > 12.0 for other in seeds):
                seeds.append(seed)
        if not seeds:
            return motion_mask

        distances = [np.sqrt(np.sum((lab - seed.reshape(1, 1, 3)) ** 2, axis=2)) for seed in seeds]
        bg_distance = np.min(np.stack(distances, axis=0), axis=0)
        bg_candidate = bg_distance < 28.0
        bg_candidate[:band_y1, :] = True
        bg_candidate[band_y2:, :] = True
        candidate_u8 = bg_candidate.astype(np.uint8)
        count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(candidate_u8, 8)
        if count > 1:
            border_labels: set[int] = set()
            border_labels.update(int(label) for label in np.unique(labels[band_y1, :]) if label > 0)
            border_labels.update(int(label) for label in np.unique(labels[max(band_y1, band_y2 - 1), :]) if label > 0)
            border_labels.update(int(label) for label in np.unique(labels[band_y1:band_y2, 0]) if label > 0)
            border_labels.update(int(label) for label in np.unique(labels[band_y1:band_y2, w - 1]) if label > 0)
            background = np.isin(labels, list(border_labels)) if border_labels else bg_candidate
        else:
            background = bg_candidate
        subject = (~background & (np.arange(h)[:, None] >= band_y1) & (np.arange(h)[:, None] < band_y2)).astype(np.uint8) * 255
        color_subject = (((sat > 34) | (val < 92)) & ~background).astype(np.uint8) * 255
        subject = cv2.bitwise_or(subject, color_subject)
        subject = cv2.bitwise_or(subject, motion_mask)
        subject[:ignored_top, :] = 0
        subject[ignored_bottom:, :] = 0
        subject = cv2.morphologyEx(subject, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        subject = cv2.morphologyEx(subject, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        return subject if np.count_nonzero(subject) >= 32 else motion_mask

    @staticmethod
    def _pose_v2_mask_bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
        if count <= 1:
            return None
        h, w = mask.shape[:2]
        min_area = max(28, int(mask.size * 0.00045))
        kept: list[tuple[int, int, int, int, int]] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            cw = int(stats[label, cv2.CC_STAT_WIDTH])
            ch = int(stats[label, cv2.CC_STAT_HEIGHT])
            center_bias = 1.0 - min(0.65, abs((x + cw * 0.5) / max(1, w) - 0.5) * 0.9)
            lower_bias = 1.0 + min(0.35, max(0.0, (y + ch * 0.5) / max(1, h) - 0.35))
            score = int(area * center_bias * lower_bias)
            kept.append((score, x, y, x + cw, y + ch))
        if not kept:
            return None
        ranked = sorted(kept, reverse=True)
        primary = ranked[0]
        primary_area = max(1, primary[0])
        px1, py1, px2, py2 = primary[1], primary[2], primary[3], primary[4]
        primary_cx = (px1 + px2) * 0.5
        chosen = [primary]
        for item in ranked[1:8]:
            score, x1, y1, x2, y2 = item
            area_ratio = score / primary_area
            cx = (x1 + x2) * 0.5
            close_x = abs(cx - primary_cx) <= max(28.0, (px2 - px1) * 0.65)
            overlaps_y = min(y2, py2) - max(y1, py1) > max(8, min(y2 - y1, py2 - py1) * 0.15)
            near_y = abs(((y1 + y2) * 0.5) - ((py1 + py2) * 0.5)) <= max(36.0, (py2 - py1) * 0.62)
            if area_ratio >= 0.14 and close_x and (overlaps_y or near_y):
                chosen.append(item)
        return (
            min(item[1] for item in chosen),
            min(item[2] for item in chosen),
            max(item[3] for item in chosen),
            max(item[4] for item in chosen),
        )

    @staticmethod
    def _pose_v2_infer_core_roi(
        subject_mask: np.ndarray,
        motion_mask: np.ndarray,
        body_bounds: tuple[int, int, int, int],
        edge_info: dict[str, bool],
    ) -> tuple[tuple[int, int, int, int] | None, float, dict[str, tuple[int, int]], list[str]]:
        h, w = subject_mask.shape[:2]
        edge_notes = RealtimeAnalyzer._pose_v2_edge_notes(edge_info)
        x1, y1, x2, y2 = body_bounds
        body_w = max(1, x2 - x1)
        body_h = max(1, y2 - y1)
        if body_w < 18 or body_h < 44:
            return None, 0.0, {}, edge_notes

        body = subject_mask[y1:y2, x1:x2] > 0
        if np.count_nonzero(body) < 32:
            body = motion_mask[y1:y2, x1:x2] > 0
        if np.count_nonzero(body) < 32:
            return None, 0.0, {}, edge_notes

        row_count = np.count_nonzero(body, axis=1).astype(np.float32)
        if row_count.size < 16 or float(np.max(row_count)) < 4.0:
            return None, 0.0, {}, edge_notes
        kernel = max(5, int(body_h * 0.035) | 1)
        row_smooth = cv2.GaussianBlur(row_count.reshape(-1, 1), (1, kernel), 0).reshape(-1)
        ys = np.arange(body_h)
        ratios = ys / max(1, body_h - 1)
        middle = (ratios >= 0.30) & (ratios <= 0.70)
        middle_pixels = np.where(body[middle, :])[1] if np.any(middle) else np.array([], dtype=np.int64)
        body_center = float(np.median(middle_pixels)) if middle_pixels.size else body_w * 0.5
        upper_trunk = (ratios >= 0.18) & (ratios <= 0.42)
        upper_pixels = np.where(body[upper_trunk, :])[1] if np.any(upper_trunk) else np.array([], dtype=np.int64)
        trunk_center = float(np.median(upper_pixels)) if upper_pixels.size else body_center
        expected_pelvis_x = body_center * 0.35 + trunk_center * 0.65
        pelvis_target = 0.54 if edge_info.get("bottom") else 0.58
        pelvis_high = 0.64 if edge_info.get("bottom") else 0.70
        band = (ratios >= 0.46) & (ratios <= pelvis_high) & (row_smooth > np.max(row_smooth) * 0.14)
        if not np.any(band):
            band = (ratios >= 0.50) & (ratios <= pelvis_high)

        rows = np.where(band)[0]
        centers: list[float] = []
        widths: list[float] = []
        scores: list[float] = []
        max_width = max(1.0, float(np.max(row_smooth)))
        for row in rows:
            row_core = RealtimeAnalyzer._pose_v2_row_core(body, int(row), body_center, 18.0, 82.0)
            if row_core is None:
                continue
            center, width = row_core
            ratio = row / max(1, body_h - 1)
            center_score = 1.0 - min(1.0, abs(center - expected_pelvis_x) / max(8.0, body_w * 0.30))
            raw_width_score = min(1.0, float(row_smooth[row]) / max_width)
            width_ratio = width / max(1.0, body_w)
            if 0.14 <= width_ratio <= 0.32:
                width_shape_score = 1.0
            elif width_ratio < 0.14:
                width_shape_score = max(0.0, width_ratio / 0.14)
            else:
                width_shape_score = max(0.0, 1.0 - (width_ratio - 0.32) / 0.28)
            pelvis_score = 1.0 - min(1.0, abs(ratio - pelvis_target) / 0.18)
            scores.append(raw_width_score * 0.16 + width_shape_score * 0.28 + center_score * 0.30 + pelvis_score * 0.26)
            centers.append(center)
            widths.append(width)
        if not scores:
            return None, 0.0, {}, edge_notes

        best_index = int(np.argmax(np.array(scores, dtype=np.float32)))
        center_y = int(rows[best_index])
        near = (rows >= max(0, center_y - int(body_h * 0.055))) & (rows <= min(body_h - 1, center_y + int(body_h * 0.055)))
        if np.any(near):
            near_rows = rows[near]
            near_cores = [
                row_core
                for row_core in (RealtimeAnalyzer._pose_v2_row_core(body, int(row), body_center, 20.0, 80.0) for row in near_rows)
                if row_core is not None
            ]
            if near_cores:
                center_x = float(np.median([item[0] for item in near_cores]))
                core_width = float(np.median([item[1] for item in near_cores]))
            else:
                center_x = float(centers[best_index])
                core_width = float(widths[best_index])
        else:
            center_x = float(centers[best_index])
            core_width = float(widths[best_index])

        core_width = max(body_w * 0.22, min(core_width * 0.78, body_w * 0.44))
        core_height = max(16.0, min(body_h * 0.13, h * 0.17))
        top = y1 + center_y - core_height * 0.48
        bottom = y1 + center_y + core_height * 0.52
        left = x1 + center_x - core_width * 0.5
        right = x1 + center_x + core_width * 0.5
        roi = (
            max(0, min(w - 1, int(round(left)))),
            max(0, min(h - 1, int(round(top)))),
            max(1, min(w, int(round(right)))),
            max(1, min(h, int(round(bottom)))),
        )
        rx1, ry1, rx2, ry2 = roi
        if rx2 - rx1 < 12 or ry2 - ry1 < 12:
            return None, 0.0, {}, edge_notes
        confidence = max(0.18, min(1.0, float(scores[best_index])))
        skeleton = RealtimeAnalyzer._pose_v2_build_skeleton(
            body,
            row_smooth,
            body_bounds,
            roi,
            center_y,
            center_x,
            core_width,
            edge_info,
        )
        return roi, confidence, skeleton, edge_notes

    @staticmethod
    def _pose_v2_edge_info(
        mask: np.ndarray,
        body_bounds: tuple[int, int, int, int],
        usable_top: int = 0,
        usable_bottom: int | None = None,
    ) -> dict[str, bool]:
        h, w = mask.shape[:2]
        bx1, by1, bx2, by2 = body_bounds
        usable_bottom = h if usable_bottom is None else max(1, min(h, int(usable_bottom)))
        usable_top = max(0, min(usable_bottom - 1, int(usable_top)))
        edge_margin_x = max(4, int(w * 0.018))
        edge_margin_y = max(4, int(h * 0.018))
        bottom_y = max(usable_top, int(usable_bottom - max(edge_margin_y, h * 0.045)))
        top_y = min(usable_bottom, max(usable_top + 1, int(usable_top + max(edge_margin_y, h * 0.045))))
        top_contact_y = min(usable_bottom, usable_top + max(3, int(h * 0.008)))
        left_x = min(w, max(1, int(w * 0.035)))
        right_x = max(0, int(w * 0.965))
        body_w = max(1, bx2 - bx1)
        bottom_band = mask[bottom_y:h, max(0, bx1):min(w, bx2)] > 0
        top_band = mask[usable_top:top_contact_y, max(0, bx1):min(w, bx2)] > 0
        left_band = mask[max(0, by1):min(h, by2), 0:left_x] > 0
        right_band = mask[max(0, by1):min(h, by2), right_x:w] > 0

        def wide_contact(band: np.ndarray, axis: int, scale: float) -> bool:
            if band.size == 0 or not np.any(band):
                return False
            projection = np.count_nonzero(band, axis=axis) > 0
            return int(np.count_nonzero(projection)) >= max(3, int(body_w * scale))

        return {
            "top": by1 <= usable_top + max(3, int(h * 0.006)) and wide_contact(top_band, 0, 0.12),
            "bottom": by2 >= usable_bottom - edge_margin_y or wide_contact(bottom_band, 0, 0.18),
            "left": bx1 <= edge_margin_x or bool(np.count_nonzero(left_band) > max(8, h * 0.010)),
            "right": bx2 >= w - edge_margin_x or bool(np.count_nonzero(right_band) > max(8, h * 0.010)),
        }

    @staticmethod
    def _pose_v2_edge_notes(edge_info: dict[str, bool]) -> list[str]:
        notes: list[str] = []
        if edge_info.get("top"):
            notes.append("head/upper body may be cropped")
        if edge_info.get("bottom"):
            notes.append("legs may continue offscreen")
        if edge_info.get("left"):
            notes.append("left side may be cropped")
        if edge_info.get("right"):
            notes.append("right side may be cropped")
        return notes

    @staticmethod
    def _pose_v2_row_core(body: np.ndarray, row: int, expected_x: float, low_pct: float, high_pct: float) -> tuple[float, float] | None:
        row = max(0, min(body.shape[0] - 1, int(row)))
        xs = np.where(body[row])[0]
        if xs.size < 4:
            return None
        breaks = np.where(np.diff(xs) > 1)[0]
        starts = np.r_[0, breaks + 1]
        ends = np.r_[breaks, xs.size - 1]
        best: np.ndarray | None = None
        best_score = -1.0
        for start, end in zip(starts, ends):
            segment = xs[start : end + 1]
            if segment.size < 4:
                continue
            center = float(np.median(segment))
            length_score = min(1.0, segment.size / max(6.0, body.shape[1] * 0.16))
            center_score = 1.0 - min(1.0, abs(center - expected_x) / max(8.0, body.shape[1] * 0.34))
            score = length_score * 0.46 + center_score * 0.54
            if score > best_score:
                best = segment
                best_score = score
        if best is None:
            return None
        low = float(np.percentile(best, low_pct))
        high = float(np.percentile(best, high_pct))
        return (low + high) * 0.5, max(5.0, high - low)

    @staticmethod
    def _pose_v2_row_segment_near(body: np.ndarray, row: int, expected_x: float) -> tuple[float, float, float] | None:
        row = max(0, min(body.shape[0] - 1, int(row)))
        xs = np.where(body[row])[0]
        if xs.size < 3:
            return None
        breaks = np.where(np.diff(xs) > 1)[0]
        starts = np.r_[0, breaks + 1]
        ends = np.r_[breaks, xs.size - 1]
        best: np.ndarray | None = None
        best_score = -1.0
        for start, end in zip(starts, ends):
            segment = xs[start : end + 1]
            if segment.size < 3:
                continue
            center = float(np.median(segment))
            width = float(segment[-1] - segment[0] + 1)
            proximity = 1.0 - min(1.0, abs(center - expected_x) / max(10.0, body.shape[1] * 0.30))
            width_score = min(1.0, width / max(5.0, body.shape[1] * 0.11))
            score = proximity * 0.78 + width_score * 0.22
            if score > best_score:
                best = segment
                best_score = score
        if best is None or best_score < 0.22:
            return None
        low = float(np.percentile(best, 22.0))
        high = float(np.percentile(best, 78.0))
        return (low + high) * 0.5, max(4.0, high - low), best_score

    @staticmethod
    def _pose_v2_leg_points(
        body: np.ndarray,
        hip_cx: float,
        hip_cy: float,
        hip_w: float,
        edge_info: dict[str, bool],
    ) -> dict[str, tuple[float, float]]:
        body_h, body_w = body.shape[:2]

        def find_leg_point(side: str, low_ratio: float, high_ratio: float, target_ratio: float) -> tuple[float, float] | None:
            side_sign = -1.0 if side == "l" else 1.0
            hip_x = hip_cx + side_sign * hip_w * 0.34
            rows = np.arange(max(0, int(body_h * low_ratio)), min(body_h, int(body_h * high_ratio) + 1))
            if rows.size == 0:
                return None
            target_y = target_ratio * max(1, body_h - 1)
            best: tuple[float, float] | None = None
            best_score = -1.0
            for row in rows[:: max(1, rows.size // 42)]:
                progress = max(0.0, min(1.0, (float(row) - hip_cy) / max(1.0, body_h - hip_cy)))
                expected_x = hip_x + side_sign * body_w * 0.19 * progress
                segment = RealtimeAnalyzer._pose_v2_row_segment_near(body, int(row), expected_x)
                if segment is None:
                    continue
                center, width, segment_score = segment
                side_ok = center <= hip_cx + hip_w * 0.18 if side == "l" else center >= hip_cx - hip_w * 0.18
                if not side_ok:
                    segment_score *= 0.52
                target_score = 1.0 - min(1.0, abs(float(row) - target_y) / max(1.0, body_h * 0.18))
                narrow_score = 1.0 - min(1.0, max(0.0, width / max(1.0, body_w) - 0.28) / 0.24)
                score = segment_score * 0.56 + target_score * 0.30 + narrow_score * 0.14
                if score > best_score:
                    best = (center, float(row))
                    best_score = score
            return best if best_score >= 0.28 else None

        knee_low, knee_high, knee_target = 0.60, 0.83, 0.72
        ankle_low, ankle_high, ankle_target = 0.80, 0.99, 0.92
        points: dict[str, tuple[float, float]] = {}
        for side in ("l", "r"):
            knee = find_leg_point(side, knee_low, knee_high, knee_target)
            ankle = None if edge_info.get("bottom") else find_leg_point(side, ankle_low, ankle_high, ankle_target)
            hip_x = hip_cx + (-1.0 if side == "l" else 1.0) * hip_w * 0.34
            if knee is not None:
                points[f"{side}_knee"] = knee
            else:
                hint_y = min(body_h - 1, hip_cy + max(12.0, body_h * 0.16))
                points[f"{side}_knee_hint"] = (hip_x, hint_y)
            if ankle is not None:
                points[f"{side}_ankle"] = ankle
            elif knee is not None and not edge_info.get("bottom"):
                hint_y = min(body_h - 1, knee[1] + max(14.0, body_h * 0.18))
                outward = -1.0 if side == "l" else 1.0
                points[f"{side}_ankle_hint"] = (knee[0] + outward * body_w * 0.05, hint_y)
        return points

    @staticmethod
    def _pose_v2_build_skeleton(
        body: np.ndarray,
        row_smooth: np.ndarray,
        body_bounds: tuple[int, int, int, int],
        core_roi: tuple[int, int, int, int],
        core_local_y: int,
        core_local_x: float,
        core_width: float,
        edge_info: dict[str, bool],
    ) -> dict[str, tuple[int, int]]:
        x1, y1, x2, y2 = body_bounds
        body_h, body_w = body.shape[:2]

        body_ratios = np.arange(body_h) / max(1, body_h - 1)
        middle = (body_ratios >= 0.30) & (body_ratios <= 0.70)
        middle_pixels = np.where(body[middle, :])[1] if np.any(middle) else np.array([], dtype=np.int64)
        body_center = float(np.median(middle_pixels)) if middle_pixels.size else body_w * 0.5

        def row_stats(local_y: int, low_pct: float = 22.0, high_pct: float = 78.0) -> tuple[float, float, float]:
            local_y = max(0, min(body_h - 1, int(local_y)))
            row_core = RealtimeAnalyzer._pose_v2_row_core(body, local_y, body_center, low_pct, high_pct)
            if row_core is None:
                return core_local_x, max(6.0, core_width), float(local_y)
            center, width = row_core
            return center, width, float(local_y)

        def best_row(low_ratio: float, high_ratio: float, target_ratio: float) -> int:
            rows = np.arange(body_h)
            ratios = rows / max(1, body_h - 1)
            band = (ratios >= low_ratio) & (ratios <= high_ratio) & (row_smooth > np.max(row_smooth) * 0.12)
            if not np.any(band):
                return int(target_ratio * max(1, body_h - 1))
            choices = rows[band]
            target = target_ratio * max(1, body_h - 1)
            widths = row_smooth[choices] / max(1.0, float(np.max(row_smooth)))
            closeness = 1.0 - np.minimum(1.0, np.abs(choices - target) / max(1.0, body_h * 0.18))
            scores = widths * 0.42 + closeness * 0.58
            return int(choices[int(np.argmax(scores))])

        shoulder_y = best_row(0.14, 0.32, 0.23)
        chest_y = best_row(0.28, 0.43, 0.35)
        waist_y = best_row(0.36, 0.54, 0.44)
        shoulder_cx, shoulder_w, _ = row_stats(shoulder_y, 14.0, 86.0)
        chest_cx, _chest_w, _ = row_stats(chest_y)
        waist_cx, waist_w, _ = row_stats(waist_y)

        hip_x1, hip_y1, hip_x2, hip_y2 = core_roi
        hip_cx = (hip_x1 + hip_x2) * 0.5 - x1
        hip_cy = (hip_y1 + hip_y2) * 0.5 - y1
        hip_w = max(core_width, body_w * 0.22)
        shoulder_w = max(shoulder_w, body_w * 0.24)
        waist_w = max(waist_w, body_w * 0.18)

        head_y = max(0, int(body_h * 0.05))
        head_cx, head_w, _ = row_stats(head_y)
        neck_y = int((shoulder_y + head_y) * 0.58)
        neck_x = (shoulder_cx + chest_cx) * 0.5

        skeleton_local = {
            "neck": (neck_x, float(neck_y)),
            "l_shoulder": (shoulder_cx - shoulder_w * 0.42, float(shoulder_y)),
            "r_shoulder": (shoulder_cx + shoulder_w * 0.42, float(shoulder_y)),
            "chest": (chest_cx, float(chest_y)),
            "waist": (waist_cx, float(waist_y)),
            "pelvis": (hip_cx, hip_cy),
            "l_hip": (hip_cx - hip_w * 0.34, hip_cy),
            "r_hip": (hip_cx + hip_w * 0.34, hip_cy),
        }
        if not edge_info.get("top"):
            skeleton_local["head"] = (head_cx, float(head_y))
        skeleton_local.update(RealtimeAnalyzer._pose_v2_leg_points(body, hip_cx, hip_cy, hip_w, edge_info))
        return {
            name: (int(round(x1 + point[0])), int(round(y1 + point[1])))
            for name, point in skeleton_local.items()
        }

    def _pose_v2_body_is_stable(self, bounds: tuple[int, int, int, int], width: int, height: int) -> bool:
        x1, y1, x2, y2 = bounds
        state = (
            ((x1 + x2) * 0.5) / max(1, width),
            ((y1 + y2) * 0.5) / max(1, height),
            (x2 - x1) / max(1, width),
            (y2 - y1) / max(1, height),
        )
        if len(self._pose_v2_body_state) < 4:
            self._pose_v2_body_state.append(state)
            return True
        history = np.array(self._pose_v2_body_state, dtype=np.float32)
        baseline = np.median(history, axis=0)
        center_jump = abs(state[0] - float(baseline[0])) + abs(state[1] - float(baseline[1]))
        width_change = abs(state[2] - float(baseline[2])) / max(0.08, float(baseline[2]))
        height_change = abs(state[3] - float(baseline[3])) / max(0.08, float(baseline[3]))
        unstable = center_jump > 0.20 or width_change > 0.48 or height_change > 0.42
        if unstable:
            return False
        self._pose_v2_body_state.append(state)
        return True

    def _pose_v2_core_is_stable(self, roi: tuple[int, int, int, int], width: int, height: int) -> bool:
        x1, y1, x2, y2 = roi
        state = (
            ((x1 + x2) * 0.5) / max(1, width),
            ((y1 + y2) * 0.5) / max(1, height),
            (x2 - x1) / max(1, width),
            (y2 - y1) / max(1, height),
        )
        if len(self._pose_v2_core_state) < 4:
            self._pose_v2_core_state.append(state)
            return True
        history = np.array(self._pose_v2_core_state, dtype=np.float32)
        baseline = np.median(history, axis=0)
        center_jump = abs(state[0] - float(baseline[0])) + abs(state[1] - float(baseline[1]))
        width_change = abs(state[2] - float(baseline[2])) / max(0.05, float(baseline[2]))
        height_change = abs(state[3] - float(baseline[3])) / max(0.04, float(baseline[3]))
        unstable = center_jump > 0.15 or width_change > 0.42 or height_change > 0.38
        if unstable:
            return False
        self._pose_v2_core_state.append(state)
        return True

    @staticmethod
    def _pose_v2_edge_confidence_scale(
        roi: tuple[int, int, int, int],
        body_bounds: tuple[int, int, int, int],
        width: int,
        height: int,
        edge_info: dict[str, bool],
    ) -> float:
        x1, y1, x2, y2 = roi
        bx1, by1, bx2, by2 = body_bounds
        edge_margin_x = max(4, int(width * 0.018))
        edge_margin_y = max(4, int(height * 0.018))
        core_near_frame_edge = x1 <= edge_margin_x or x2 >= width - edge_margin_x or y1 <= edge_margin_y or y2 >= height - edge_margin_y
        body_cut_side = edge_info.get("left", False) or edge_info.get("right", False) or bx1 <= edge_margin_x or bx2 >= width - edge_margin_x
        body_cut_bottom = edge_info.get("bottom", False) or by2 >= height - edge_margin_y
        lower_body_too_short = (by2 - y1) < max(20, int((by2 - by1) * 0.22))
        if core_near_frame_edge:
            return 0.0
        scale = 1.0
        if body_cut_bottom:
            scale *= 0.58
        if edge_info.get("top", False):
            scale *= 0.78
        if body_cut_side:
            scale *= 0.74
        if body_cut_side and lower_body_too_short:
            scale *= 0.45
        return max(0.0, min(1.0, scale))

    @staticmethod
    def _pose_v2_moving_pixels(flow: np.ndarray, support: np.ndarray, motion_mask: np.ndarray) -> np.ndarray:
        if flow.size == 0 or not np.any(support):
            return motion_mask > 0
        mag, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        supported_mag = mag[support]
        threshold = max(0.10, float(np.percentile(supported_mag, 62))) if supported_mag.size else 0.10
        moving = support & (mag >= threshold)
        if np.count_nonzero(moving) < 8:
            moving = (motion_mask > 0) & support
        return moving

    @staticmethod
    def _pose_v2_motion_evidence(flow: np.ndarray, moving: np.ndarray, support: np.ndarray) -> float:
        support_count = max(1, int(np.count_nonzero(support)))
        moving_count = int(np.count_nonzero(moving))
        if flow.size == 0 or moving_count <= 0:
            return 0.0
        mag, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        median_mag = float(np.median(mag[moving]))
        area_score = min(1.0, moving_count / max(10.0, support_count * 0.10))
        speed_score = min(1.0, median_mag / 1.35)
        return float(area_score * 0.58 + speed_score * 0.42)

    @staticmethod
    def _pose_v2_core_pitch(flow: np.ndarray, moving: np.ndarray, full_height: int) -> float:
        if flow.size == 0 or not np.any(moving):
            return 0.0
        local_h = flow.shape[0]
        top = moving[: local_h // 2, :]
        bottom = moving[local_h // 2 :, :]
        if not np.any(top) or not np.any(bottom):
            return 0.0
        top_dy = float(np.median(flow[: local_h // 2, :, 1][top]))
        bottom_dy = float(np.median(flow[local_h // 2 :, :, 1][bottom]))
        return (top_dy - bottom_dy) / max(1, full_height)

    def _pose_v2_release_stuck_axis(self, axis: str, value: float, evidence: float) -> float:
        history = self._pose_v2_axis_recent.get(axis)
        if history is None:
            return value
        history.append(value)
        if not self.enable_extreme_reset:
            return value
        offset = abs(value - 0.5)
        if offset < 0.13:
            return value
        recent_range = max(history) - min(history) if len(history) >= 8 else 1.0
        weak = evidence < 0.20
        stuck = len(history) >= 8 and recent_range < 0.035
        if not weak and not stuck:
            return value
        strength = 0.14
        if weak:
            strength += min(0.18, (0.20 - evidence) * 0.9)
        if stuck and offset > 0.17:
            strength += 0.12
        return float(value * (1.0 - strength) + 0.5 * strength)

    @staticmethod
    def _draw_pose_v2_guides(
        preview: np.ndarray,
        hip_roi: tuple[int, int, int, int],
        ignored_top: int,
        ignored_bottom: int,
        evidence: float,
    ) -> None:
        h, w = preview.shape[:2]
        x1, y1, x2, y2 = hip_roi
        cv2.line(preview, (0, ignored_top), (w, ignored_top), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.line(preview, (0, ignored_bottom), (w, ignored_bottom), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.rectangle(preview, (x1, y1), (x2, y2), (40, 220, 120), 1, cv2.LINE_AA)
        label_y = min(h - 8, max(18, y2 + 16))
        cv2.putText(preview, f"Pose v2 core {evidence:.2f}", (max(6, x1), label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 220, 120), 1, cv2.LINE_AA)

    @staticmethod
    def _draw_pose_v2_skeleton(
        preview: np.ndarray,
        skeleton: dict[str, tuple[int, int]],
        edge_notes: list[str] | None = None,
        source_label: str = "Edge Skeleton",
    ) -> None:
        if not skeleton:
            return
        links = (
            ("head", "neck"),
            ("neck", "l_shoulder"),
            ("neck", "r_shoulder"),
            ("neck", "chest"),
            ("chest", "waist"),
            ("waist", "pelvis"),
            ("pelvis", "l_hip"),
            ("pelvis", "r_hip"),
            ("l_hip", "l_knee"),
            ("r_hip", "r_knee"),
            ("l_hip", "l_knee_hint"),
            ("r_hip", "r_knee_hint"),
            ("l_knee", "l_ankle"),
            ("r_knee", "r_ankle"),
            ("l_knee", "l_ankle_hint"),
            ("r_knee", "r_ankle_hint"),
        )
        for start, end in links:
            if start in skeleton and end in skeleton:
                cv2.line(preview, skeleton[start], skeleton[end], (255, 220, 70), 2, cv2.LINE_AA)
        for name, point in skeleton.items():
            color = (255, 245, 120)
            radius = 3
            if name in {"pelvis", "l_hip", "r_hip"}:
                color = (50, 255, 180)
                radius = 4
            elif name.endswith("_hint"):
                color = (120, 180, 255)
                radius = 3
            cv2.circle(preview, point, radius, color, -1, cv2.LINE_AA)
        pelvis = skeleton.get("pelvis")
        if pelvis is not None:
            cv2.putText(preview, "V2 skeleton", (max(6, pelvis[0] - 36), max(18, pelvis[1] - 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 245, 120), 1, cv2.LINE_AA)
            cv2.putText(preview, source_label[:54], (max(6, pelvis[0] - 36), min(preview.shape[0] - 8, pelvis[1] + 34)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 245, 120), 1, cv2.LINE_AA)
        if edge_notes:
            h, _w = preview.shape[:2]
            x = 8
            y = max(18, (pelvis[1] + 22) if pelvis is not None else 18)
            for note in edge_notes[:3]:
                if y >= h - 8:
                    break
                cv2.putText(preview, note, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 180, 255), 1, cv2.LINE_AA)
                y += 14

    @staticmethod
    def _draw_pose_v2_unstable(preview: np.ndarray, ignored_top: int, ignored_bottom: int, edge_notes: list[str] | None = None) -> None:
        h, w = preview.shape[:2]
        cv2.line(preview, (0, ignored_top), (w, ignored_top), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.line(preview, (0, ignored_bottom), (w, ignored_bottom), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.putText(preview, "Pose v2 unstable", (8, min(h - 8, max(20, ignored_top + 18))), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (80, 120, 255), 1, cv2.LINE_AA)
        if edge_notes:
            y = min(h - 8, max(36, ignored_top + 34))
            for note in edge_notes[:3]:
                if y >= h - 8:
                    break
                cv2.putText(preview, note, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 180, 255), 1, cv2.LINE_AA)
                y += 14

    def _measure_rtm_pose_3d(self, frame_bgr: np.ndarray) -> tuple[dict[str, float] | None, float, RtmPose3dResult | None]:
        backend = self._rtm_pose_backend()
        if backend is None:
            return None, 0.0, None
        self._rtm_pose_3d_frame += 1
        self._apply_rtm_pose_optical_flow(frame_bgr)
        self._start_rtm_pose_3d_infer(frame_bgr)
        return self._latest_rtm_pose_3d_measurement()

    def _rtm_pose_backend(self) -> OptionalRtmPose2dBackend | OptionalRtmPose3dBackend | None:
        if self.rtm_pose_2d_enabled:
            return self._rtm_pose_2d_backend
        return self._rtm_pose_3d_backend

    def _apply_rtm_pose_optical_flow(self, frame_bgr: np.ndarray) -> None:
        if not self.rtm_pose_flow_enabled:
            return
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        with self._rtm_pose_3d_lock:
            previous_gray = self._rtm_pose_flow_gray
            previous_result = self._rtm_pose_3d_last
            self._rtm_pose_flow_gray = gray
            frame_index = self._rtm_pose_3d_frame
        if previous_gray is None or previous_result is None:
            return

        keypoints = np.asarray(previous_result.keypoints2d, dtype=np.float32)
        scores = np.asarray(previous_result.scores, dtype=np.float32).reshape(-1)
        if keypoints.ndim != 2 or keypoints.shape[0] < 17 or keypoints.shape[1] < 2:
            return
        count = min(17, len(keypoints), len(scores))
        valid_indices = np.flatnonzero((scores[:count] >= 0.22) & np.isfinite(keypoints[:count, 0]) & np.isfinite(keypoints[:count, 1]))
        if len(valid_indices) < 5:
            return

        prev_points = keypoints[valid_indices, :2].reshape(-1, 1, 2).astype(np.float32)
        try:
            next_points, status, err = cv2.calcOpticalFlowPyrLK(
                previous_gray,
                gray,
                prev_points,
                None,
                winSize=(21, 21),
                maxLevel=2,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 12, 0.03),
            )
        except cv2.error:
            return
        if next_points is None or status is None:
            return

        h, w = gray.shape[:2]
        tracked = keypoints.copy()
        tracked_scores = scores.copy()
        flow_ok = status.reshape(-1).astype(bool)
        if err is not None:
            flow_ok &= err.reshape(-1) <= 32.0
        usable = 0
        for source_index, ok, point in zip(valid_indices, flow_ok, next_points.reshape(-1, 2)):
            inside = -8.0 <= point[0] <= w + 8.0 and -8.0 <= point[1] <= h + 8.0
            if ok and inside:
                tracked[source_index, :2] = point
                tracked_scores[source_index] = min(0.92, max(0.0, tracked_scores[source_index] * 0.94))
                usable += 1
            else:
                tracked_scores[source_index] *= 0.55
        if usable < 5:
            return

        result = self._rtm_pose_result_with_keypoints2d(previous_result, tracked, tracked_scores, f"{previous_result.status} + Flow")
        if self.rtm_pose_kalman_enabled:
            result = self._rtm_pose_kalman_predict_with_flow(result)
        positions, confidence = (
            self._positions_from_rtm_pose_2d(result, frame_bgr.shape[:2])
            if self.rtm_pose_2d_enabled
            else self._positions_from_rtm_pose_3d(result, frame_bgr.shape[:2])
        )
        if positions is not None:
            self._store_rtm_pose_sample(result, positions, confidence * 0.92, frame_index, None, "")

    def _store_rtm_pose_sample(
        self,
        result: RtmPose3dResult | None,
        positions: dict[str, float] | None,
        confidence: float,
        frame_index: int,
        elapsed_ms: float | None,
        error: str,
        *,
        detection: bool = False,
    ) -> None:
        with self._rtm_pose_3d_lock:
            old_positions = self._rtm_pose_3d_last_positions
            old_frame = self._rtm_pose_3d_last_frame
            if detection:
                self._rtm_pose_3d_last_detection_frame = max(self._rtm_pose_3d_last_detection_frame, frame_index)
            if result is not None:
                self._rtm_pose_3d_last = result
            if positions is not None:
                frame_delta = max(1, frame_index - old_frame)
                if old_positions:
                    for axis, value in positions.items():
                        previous = old_positions.get(axis, value)
                        velocity = (value - previous) / frame_delta
                        self._rtm_pose_3d_velocity[axis] = self._rtm_pose_3d_velocity.get(axis, 0.0) * 0.45 + velocity * 0.55
                self._rtm_pose_3d_last_positions = positions
                self._rtm_pose_3d_last_confidence = confidence
                self._rtm_pose_3d_last_frame = max(self._rtm_pose_3d_last_frame, frame_index)
            if elapsed_ms is not None:
                self._rtm_pose_3d_last_ms = elapsed_ms
            self._rtm_pose_3d_last_error = error

    def _rtm_pose_result_with_keypoints2d(
        self,
        result: RtmPose3dResult,
        keypoints2d: np.ndarray,
        scores: np.ndarray,
        status: str,
    ) -> RtmPose3dResult:
        points2d = np.asarray(keypoints2d, dtype=np.float32).copy()
        points3d = np.asarray(result.keypoints3d, dtype=np.float32).copy()
        if self.rtm_pose_2d_enabled and points3d.ndim == 2 and points3d.shape[0] >= points2d.shape[0] and points3d.shape[1] >= 2:
            points3d[: points2d.shape[0], :2] = points2d[:, :2]
        return RtmPose3dResult(points3d, points2d, np.asarray(scores, dtype=np.float32).reshape(-1), status=status)

    def _rtm_pose_kalman_predict_with_flow(self, result: RtmPose3dResult) -> RtmPose3dResult:
        keypoints = np.asarray(result.keypoints2d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32).reshape(-1)
        if keypoints.ndim != 2 or keypoints.shape[0] < 17:
            return result
        now = time.perf_counter()
        with self._rtm_pose_3d_lock:
            fused = self._rtm_pose_kalman_predict_with_flow_locked(keypoints, scores, now)
        return self._rtm_pose_result_with_keypoints2d(result, fused, scores, f"{result.status} + Kalman")

    def _rtm_pose_kalman_correct_detection(self, result: RtmPose3dResult) -> RtmPose3dResult:
        if not self.rtm_pose_kalman_enabled:
            return result
        keypoints = np.asarray(result.keypoints2d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32).reshape(-1)
        if keypoints.ndim != 2 or keypoints.shape[0] < 17:
            return result
        now = time.perf_counter()
        with self._rtm_pose_3d_lock:
            fused = self._rtm_pose_kalman_correct_locked(keypoints, scores, now)
        return self._rtm_pose_result_with_keypoints2d(result, fused, scores, f"{result.status} + Kalman")

    def _rtm_pose_kalman_init_locked(self, keypoints: np.ndarray) -> None:
        count = int(keypoints.shape[0])
        self._rtm_pose_kalman_state = np.zeros((count, 4), dtype=np.float32)
        self._rtm_pose_kalman_state[:, :2] = keypoints[:, :2]
        self._rtm_pose_kalman_cov = np.repeat(np.eye(4, dtype=np.float32)[None, :, :] * 4.0, count, axis=0)
        self._rtm_pose_kalman_time = time.perf_counter()

    def _rtm_pose_kalman_predict_locked(self, now: float) -> float:
        if self._rtm_pose_kalman_state is None or self._rtm_pose_kalman_cov is None:
            return 1.0 / 45.0
        last_time = self._rtm_pose_kalman_time if self._rtm_pose_kalman_time is not None else now
        dt = max(1.0 / 120.0, min(0.20, now - last_time))
        state = self._rtm_pose_kalman_state
        cov = self._rtm_pose_kalman_cov
        state[:, 0] += state[:, 2] * dt
        state[:, 1] += state[:, 3] * dt
        transition = np.array(((1.0, 0.0, dt, 0.0), (0.0, 1.0, 0.0, dt), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)), dtype=np.float32)
        process_noise = np.diag((0.35, 0.35, 18.0, 18.0)).astype(np.float32) * dt
        for index in range(cov.shape[0]):
            cov[index] = transition @ cov[index] @ transition.T + process_noise
        self._rtm_pose_kalman_time = now
        return dt

    def _rtm_pose_kalman_predict_with_flow_locked(self, keypoints: np.ndarray, scores: np.ndarray, now: float) -> np.ndarray:
        if self._rtm_pose_kalman_state is None or self._rtm_pose_kalman_cov is None or self._rtm_pose_kalman_state.shape[0] != keypoints.shape[0]:
            self._rtm_pose_kalman_init_locked(keypoints)
            return keypoints.copy()
        state = self._rtm_pose_kalman_state
        cov = self._rtm_pose_kalman_cov
        previous_xy = state[:, :2].copy()
        dt = self._rtm_pose_kalman_predict_locked(now)
        valid = (scores[: keypoints.shape[0]] >= 0.12) & np.isfinite(keypoints[:, 0]) & np.isfinite(keypoints[:, 1])
        if np.any(valid):
            blend = 0.78
            state[valid, :2] = state[valid, :2] * (1.0 - blend) + keypoints[valid, :2] * blend
            state[valid, 2:4] = state[valid, 2:4] * 0.50 + ((state[valid, :2] - previous_xy[valid]) / max(dt, 1e-3)) * 0.50
            cov[valid, :2, :2] *= 0.82
        return state[:, :2].copy()

    def _rtm_pose_kalman_correct_locked(self, keypoints: np.ndarray, scores: np.ndarray, now: float) -> np.ndarray:
        if self._rtm_pose_kalman_state is None or self._rtm_pose_kalman_cov is None or self._rtm_pose_kalman_state.shape[0] != keypoints.shape[0]:
            self._rtm_pose_kalman_init_locked(keypoints)
            return keypoints.copy()
        self._rtm_pose_kalman_predict_locked(now)
        state = self._rtm_pose_kalman_state
        cov = self._rtm_pose_kalman_cov
        observation = np.array(((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)), dtype=np.float32)
        identity = np.eye(4, dtype=np.float32)
        count = min(keypoints.shape[0], len(scores))
        for index in range(count):
            confidence = float(scores[index])
            if confidence < 0.05 or not np.isfinite(keypoints[index, 0]) or not np.isfinite(keypoints[index, 1]):
                continue
            measurement_noise = max(0.45, 12.0 * (1.0 - max(0.0, min(1.0, confidence))) ** 2 + 0.35)
            r = np.eye(2, dtype=np.float32) * measurement_noise
            innovation = keypoints[index, :2] - observation @ state[index]
            innovation_cov = observation @ cov[index] @ observation.T + r
            gain = cov[index] @ observation.T @ np.linalg.inv(innovation_cov)
            state[index] = state[index] + gain @ innovation
            cov[index] = (identity - gain @ observation) @ cov[index]
        return state[:, :2].copy()

    def _start_rtm_pose_3d_infer(self, frame_bgr: np.ndarray) -> None:
        backend = self._rtm_pose_backend()
        if backend is None:
            return
        interval = self._rtm_pose_3d_infer_interval()
        with self._rtm_pose_3d_lock:
            if self._rtm_pose_3d_pending:
                return
            if self._rtm_pose_3d_last is not None and self._rtm_pose_3d_frame - self._rtm_pose_3d_last_detection_frame < interval:
                return
            self._rtm_pose_3d_pending = True
            frame_index = self._rtm_pose_3d_frame
            frame = frame_bgr.copy()
            frame_shape = frame_bgr.shape[:2]

        def worker() -> None:
            started = time.perf_counter()
            result: RtmPose3dResult | None = None
            positions: dict[str, float] | None = None
            confidence = 0.0
            error = ""
            try:
                result = backend.infer(frame)
                if result is None:
                    error = backend.status
                else:
                    result = self._rtm_pose_kalman_correct_detection(result)
                    positions, confidence = (
                        self._positions_from_rtm_pose_2d(result, frame_shape)
                        if self.rtm_pose_2d_enabled
                        else self._positions_from_rtm_pose_3d(result, frame_shape)
                    )
                    if positions is None:
                        error = result.status
            except Exception as exc:
                error = f"{self._rtm_pose_label()} worker failed: {exc}"
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            with self._rtm_pose_3d_lock:
                self._rtm_pose_3d_last_ms = elapsed_ms
                self._rtm_pose_3d_pending = False
            store_frame = max(frame_index, self._rtm_pose_3d_frame)
            self._store_rtm_pose_sample(result, positions, confidence, store_frame, elapsed_ms, error, detection=True)

        threading.Thread(target=worker, daemon=True).start()

    def _latest_rtm_pose_3d_measurement(self) -> tuple[dict[str, float] | None, float, RtmPose3dResult | None]:
        with self._rtm_pose_3d_lock:
            result = self._rtm_pose_3d_last
            positions = dict(self._rtm_pose_3d_last_positions) if self._rtm_pose_3d_last_positions else None
            confidence = self._rtm_pose_3d_last_confidence
            age = max(0, self._rtm_pose_3d_frame - self._rtm_pose_3d_last_frame)
            velocity = dict(self._rtm_pose_3d_velocity)
        if positions is None:
            return None, 0.0, result
        if age > 0:
            prediction = self._rtm_pose_3d_prediction_strength()
            decay = max(0.30, 1.0 - age / max(8.0, self._rtm_pose_3d_infer_interval() * 5.0))
            max_shift = 0.012 + max(0, self.compression_latency) * 0.010
            horizon = min(float(age), 1.0 + max(0, self.compression_latency) * 0.7)
            for axis in list(positions):
                shift = velocity.get(axis, 0.0) * horizon * prediction
                positions[axis] = max(0.0, min(1.0, positions[axis] + self._centered_clamp(shift, max_shift)))
            confidence *= decay
        return positions, confidence, result

    def _positions_from_rtm_pose_3d(
        self,
        result: RtmPose3dResult,
        frame_shape: tuple[int, int],
    ) -> tuple[dict[str, float] | None, float]:
        core = self._rtm_pose_3d_virtual_core(result, frame_shape)
        if core is None:
            return None, 0.0

        _h, _w = frame_shape
        hip_mid = core["hip_mid_2d"]
        confidence = float(core["confidence"])
        if confidence <= 0.02:
            return None, 0.0

        positions = self._rtm_pose_3d_axes_from_previous_core(core, confidence)
        return positions, confidence

    def _positions_from_rtm_pose_2d(
        self,
        result: RtmPose3dResult,
        frame_shape: tuple[int, int],
    ) -> tuple[dict[str, float] | None, float]:
        core = self._rtm_pose_3d_virtual_core(result, frame_shape)
        if core is None:
            return None, 0.0
        confidence = float(core["confidence"])
        if confidence <= 0.02:
            return None, 0.0
        positions = self._rtm_pose_3d_axes_from_previous_core(core, confidence)
        return positions, confidence

    def _rtm_pose_3d_axes_from_previous_core(self, core: dict[str, np.ndarray | float], confidence: float) -> dict[str, float]:
        now = time.perf_counter()
        hip_mid = np.asarray(core["hip_mid_2d"], dtype=np.float32)
        hip_line = np.asarray(core["hip_line_2d"], dtype=np.float32)
        hip_width = max(1.0, float(np.linalg.norm(hip_line)))
        current_core = self._rtm_pose_3d_copy_core(core)
        current_hip_sample = (now, hip_mid.copy(), hip_line.copy(), float(confidence))
        current_axis_sample = (now, current_core, float(confidence))
        previous = self._rtm_pose_3d_previous_hip_sample
        previous_axis = self._rtm_pose_3d_previous_axis_sample

        if previous is None or previous_axis is None:
            self._rtm_pose_3d_previous_hip_sample = current_hip_sample
            self._rtm_pose_3d_previous_axis_sample = current_axis_sample
            return self._active_positions()

        old_time, old_mid, old_line, old_confidence = previous
        self._rtm_pose_3d_l0_reference_sample = previous
        self._rtm_pose_3d_axis_reference_sample = previous_axis
        self._rtm_pose_3d_previous_hip_sample = current_hip_sample
        self._rtm_pose_3d_previous_axis_sample = current_axis_sample

        if old_confidence < 0.20:
            return self._active_positions()
        old_width = max(1.0, float(np.linalg.norm(old_line)))
        if old_width < 8.0:
            return self._active_positions()
        dt = now - old_time
        if dt < 0.010 or dt > 0.450:
            return self._active_positions()

        signed_distance = self._rtm_pose_3d_predicted_hip_delta_y(hip_mid, old_mid, dt)
        noise_floor = max(0.45, min(1.8, (hip_width + old_width) * 0.0035))
        if abs(signed_distance) < noise_floor:
            l0_target = 0.5
        else:
            distance_scale = max(9.0, (hip_width + old_width) * 0.17)
            l0_target = 0.5 + self._centered_clamp((signed_distance / distance_scale) * 0.62, 0.42)

        positions = {"L0": self._rtm_pose_3d_update_axis_raw("L0", self._bounded_l0(l0_target), confidence, primary=True)}
        self._rtm_pose_3d_l0_raw = positions["L0"]
        if self.output_mode == "Six Axis":
            _old_axis_time, old_core, _old_axis_confidence = previous_axis
            positions.update(self._rtm_pose_3d_six_axis_from_core_delta(current_core, old_core, dt, confidence))
        return positions

    @staticmethod
    def _rtm_pose_3d_copy_core(core: dict[str, np.ndarray | float]) -> dict[str, np.ndarray | float]:
        copied: dict[str, np.ndarray | float] = {}
        for key, value in core.items():
            copied[key] = value.copy() if isinstance(value, np.ndarray) else float(value)
        return copied

    def _rtm_pose_3d_six_axis_from_core_delta(
        self,
        core: dict[str, np.ndarray | float],
        old_core: dict[str, np.ndarray | float],
        dt: float,
        confidence: float,
    ) -> dict[str, float]:
        hip_mid = np.asarray(core["hip_mid_2d"], dtype=np.float32)
        old_hip_mid = np.asarray(old_core["hip_mid_2d"], dtype=np.float32)
        hip_line_2d = np.asarray(core["hip_line_2d"], dtype=np.float32)
        old_hip_line_2d = np.asarray(old_core["hip_line_2d"], dtype=np.float32)
        shoulder_line = np.asarray(core["shoulder_line_2d"], dtype=np.float32)
        old_shoulder_line = np.asarray(old_core["shoulder_line_2d"], dtype=np.float32)
        pelvis_3d = np.asarray(core["pelvis_3d"], dtype=np.float32)
        old_pelvis_3d = np.asarray(old_core["pelvis_3d"], dtype=np.float32)
        hip_line_3d = np.asarray(core["hip_line_3d"], dtype=np.float32)
        old_hip_line_3d = np.asarray(old_core["hip_line_3d"], dtype=np.float32)
        shoulder_line_3d = np.asarray(core["shoulder_line_3d"], dtype=np.float32)
        old_shoulder_line_3d = np.asarray(old_core["shoulder_line_3d"], dtype=np.float32)
        torso_up_3d = np.asarray(core["torso_up_3d"], dtype=np.float32)
        old_torso_up_3d = np.asarray(old_core["torso_up_3d"], dtype=np.float32)
        torso_up_2d = np.asarray(core["torso_up_2d"], dtype=np.float32)
        body_scale_2d = max(1.0, float(core["body_scale_2d"]))
        old_body_scale_2d = max(1.0, float(old_core["body_scale_2d"]))
        scale_2d = (body_scale_2d + old_body_scale_2d) * 0.5
        scale_3d = max(0.08, (float(core["scale_3d"]) + float(old_core["scale_3d"])) * 0.5)

        if self.rtm_pose_2d_enabled:
            return self._rtm_pose_2d_six_axis_from_core_delta(core, old_core, dt, confidence, scale_2d)

        x_delta = self._rtm_pose_3d_predicted_scalar_delta(float(hip_mid[0] - old_hip_mid[0]), dt, 3.2)
        z_delta = self._rtm_pose_3d_predicted_scalar_delta(float(pelvis_3d[2] - old_pelvis_3d[2]), dt, scale_3d * 0.14)
        r0_target = self._rtm_pose_3d_r0_from_hip_depth_balance(
            hip_line_3d,
            old_hip_line_3d,
            shoulder_line_3d,
            old_shoulder_line_3d,
            hip_line_2d,
            old_hip_line_2d,
            scale_2d,
            dt,
        )
        r1_target = self._rtm_pose_3d_r1_from_body_centerline(torso_up_2d, core, confidence)
        r2_delta = self._rtm_pose_3d_predicted_angle_delta(
            self._angle_delta_deg(self._rtm_pose_3d_pitch_angle(torso_up_3d), self._rtm_pose_3d_pitch_angle(old_torso_up_3d)),
            dt,
            4.0,
        )
        shoulder_width_delta = self._rtm_pose_3d_predicted_scalar_delta(
            float(np.linalg.norm(shoulder_line) - np.linalg.norm(old_shoulder_line)),
            dt,
            max(1.8, scale_2d * 0.018),
        )
        targets = {
            "L1": 0.5 + self._centered_clamp((-z_delta / scale_3d) * 0.62, 0.46),
            "L2": 0.5 + self._centered_clamp((x_delta / max(10.0, scale_2d * 0.16)) * 0.38, 0.26),
            "R0": r0_target,
            "R1": r1_target,
            "R2": 0.5
            + self._centered_clamp(
                (r2_delta / 28.0) * 0.22 + (shoulder_width_delta / max(8.0, scale_2d * 0.10)) * 0.24,
                0.30,
            ),
        }
        return {axis: self._rtm_pose_3d_update_axis_raw(axis, value, confidence, primary=False) for axis, value in targets.items()}

    def _rtm_pose_2d_six_axis_from_core_delta(
        self,
        core: dict[str, np.ndarray | float],
        old_core: dict[str, np.ndarray | float],
        dt: float,
        confidence: float,
        scale_2d: float,
    ) -> dict[str, float]:
        hip_mid = np.asarray(core["hip_mid_2d"], dtype=np.float32)
        old_hip_mid = np.asarray(old_core["hip_mid_2d"], dtype=np.float32)
        hip_line = np.asarray(core["hip_line_2d"], dtype=np.float32)
        old_hip_line = np.asarray(old_core["hip_line_2d"], dtype=np.float32)
        shoulder_line = np.asarray(core["shoulder_line_2d"], dtype=np.float32)
        old_shoulder_line = np.asarray(old_core["shoulder_line_2d"], dtype=np.float32)
        torso_up = np.asarray(core["torso_up_2d"], dtype=np.float32)
        body_scale = float(core["body_scale_2d"])
        old_body_scale = float(old_core["body_scale_2d"])
        hip_width = float(np.linalg.norm(hip_line))
        old_hip_width = float(np.linalg.norm(old_hip_line))
        shoulder_width = float(np.linalg.norm(shoulder_line))
        old_shoulder_width = float(np.linalg.norm(old_shoulder_line))

        x_delta = self._rtm_pose_3d_predicted_scalar_delta(float(hip_mid[0] - old_hip_mid[0]), dt, 3.2)
        scale_delta = self._rtm_pose_3d_predicted_scalar_delta(body_scale - old_body_scale, dt, max(1.8, scale_2d * 0.018))
        hip_width_delta = self._rtm_pose_3d_predicted_scalar_delta(hip_width - old_hip_width, dt, max(1.8, scale_2d * 0.018))
        shoulder_width_delta = self._rtm_pose_3d_predicted_scalar_delta(shoulder_width - old_shoulder_width, dt, max(1.8, scale_2d * 0.018))

        if self._rtm_pose_3d_r0_front_width <= 0.0:
            self._rtm_pose_3d_r0_front_width = max(8.0, hip_width, old_hip_width)
        elif hip_width > self._rtm_pose_3d_r0_front_width:
            self._rtm_pose_3d_r0_front_width = self._rtm_pose_3d_r0_front_width * 0.82 + hip_width * 0.18
        else:
            self._rtm_pose_3d_r0_front_width = max(8.0, self._rtm_pose_3d_r0_front_width * 0.996)
        front_width = max(8.0, self._rtm_pose_3d_r0_front_width)
        width_narrow = max(0.0, min(1.0, (front_width - hip_width) / max(8.0, front_width * 0.55)))
        torso_side = self._centered_clamp(float(torso_up[0]) / max(20.0, scale_2d * 0.28), 1.0)
        if abs(torso_side) > 0.08:
            self._rtm_pose_3d_r0_side_hint = 1.0 if torso_side > 0.0 else -1.0
        side = self._rtm_pose_3d_r0_side_hint or (1.0 if hip_width_delta < 0.0 else -1.0)
        r0_target = 0.5 + self._centered_clamp(side * width_narrow * 0.34 - (hip_width_delta / max(8.0, front_width * 0.45)) * 0.12, 0.34)

        r1_target = self._rtm_pose_3d_r1_from_body_centerline(torso_up, core, confidence)
        r2_signal = (
            (shoulder_width_delta / max(8.0, scale_2d * 0.10)) * 0.20
            + (scale_delta / max(10.0, scale_2d * 0.14)) * 0.12
        )
        targets = {
            "L1": 0.5 + self._centered_clamp((scale_delta / max(12.0, scale_2d * 0.16)) * 0.16, 0.14),
            "L2": 0.5 + self._centered_clamp((x_delta / max(10.0, scale_2d * 0.16)) * 0.38, 0.26),
            "R0": r0_target,
            "R1": r1_target,
            "R2": 0.5 + self._centered_clamp(r2_signal, 0.22),
        }
        return {axis: self._rtm_pose_3d_update_axis_raw(axis, value, confidence, primary=False) for axis, value in targets.items()}

    def _rtm_pose_3d_r1_from_body_centerline(
        self,
        torso_up_2d: np.ndarray,
        core: dict[str, np.ndarray | float],
        confidence: float,
    ) -> float:
        shoulder_confidence = float(core.get("shoulder_confidence", 0.0))
        torso_len = float(np.linalg.norm(torso_up_2d))
        if confidence < 0.20 or shoulder_confidence < 0.24 or torso_len < 12.0:
            return self._rtm_pose_3d_axis_raw.get("R1", 0.5)
        roll_angle = self._rtm_pose_3d_torso_roll_angle_2d(torso_up_2d)
        return 0.5 + self._centered_clamp(roll_angle / 60.0, 0.5)

    def _rtm_pose_3d_update_axis_raw(self, axis: str, target: float, confidence: float, primary: bool = False) -> float:
        if axis == "R0":
            blend = 0.88 if confidence >= 0.55 else 0.62
        elif axis == "R1":
            blend = 0.86 if confidence >= 0.55 else 0.64
        else:
            blend = 0.82 if primary and confidence >= 0.55 else 0.60 if primary else 0.68 if confidence >= 0.55 else 0.48
        previous = self._rtm_pose_3d_axis_raw.get(axis, 0.5)
        value = previous * (1.0 - blend) + max(0.0, min(1.0, target)) * blend
        self._rtm_pose_3d_axis_raw[axis] = value
        return value

    def _rtm_pose_3d_predicted_scalar_delta(self, delta: float, dt: float, max_prediction: float) -> float:
        velocity = delta / max(0.001, dt)
        horizon = 0.016
        if self.compression_latency > 0:
            horizon += min(0.050, self.compression_latency * 0.008)
        elif self.compression_latency < 0:
            horizon *= 0.45
        predicted_extra = max(-max_prediction, min(max_prediction, velocity * horizon))
        return delta + predicted_extra

    def _rtm_pose_3d_predicted_angle_delta(self, delta: float, dt: float, max_prediction: float) -> float:
        predicted = self._rtm_pose_3d_predicted_scalar_delta(delta, dt, max_prediction)
        return self._angle_delta_deg(predicted, 0.0)

    def _rtm_pose_3d_r0_from_hip_depth_balance(
        self,
        hip_line: np.ndarray,
        old_hip_line: np.ndarray,
        shoulder_line: np.ndarray,
        old_shoulder_line: np.ndarray,
        hip_line_2d: np.ndarray,
        old_hip_line_2d: np.ndarray,
        scale_2d: float,
        dt: float,
    ) -> float:
        hip_balance = self._rtm_pose_3d_depth_balance(hip_line)
        old_hip_balance = self._rtm_pose_3d_depth_balance(old_hip_line)
        shoulder_balance = self._rtm_pose_3d_depth_balance(shoulder_line)
        old_shoulder_balance = self._rtm_pose_3d_depth_balance(old_shoulder_line)
        hip_delta = self._rtm_pose_3d_predicted_scalar_delta(hip_balance - old_hip_balance, dt, 0.16)
        shoulder_delta = self._rtm_pose_3d_predicted_scalar_delta(shoulder_balance - old_shoulder_balance, dt, 0.10)
        predicted_hip = max(-1.0, min(1.0, hip_balance + hip_delta * 0.22))
        predicted_shoulder = max(-1.0, min(1.0, shoulder_balance + shoulder_delta * 0.12))
        depth_signal = predicted_hip * 0.76 + predicted_shoulder * 0.14

        scale_2d = max(1.0, float(scale_2d))
        hip_width = float(np.linalg.norm(hip_line_2d)) / scale_2d
        old_hip_width = float(np.linalg.norm(old_hip_line_2d)) / scale_2d
        if self._rtm_pose_3d_r0_front_width <= 0.0:
            self._rtm_pose_3d_r0_front_width = max(0.04, hip_width, old_hip_width)
        elif hip_width > self._rtm_pose_3d_r0_front_width:
            self._rtm_pose_3d_r0_front_width = self._rtm_pose_3d_r0_front_width * 0.82 + hip_width * 0.18
        else:
            self._rtm_pose_3d_r0_front_width = max(0.04, self._rtm_pose_3d_r0_front_width * 0.996)

        front_width = max(0.04, self._rtm_pose_3d_r0_front_width)
        width_narrow = max(0.0, min(1.0, (front_width - hip_width) / max(0.04, front_width * 0.56)))
        width_delta = max(-1.0, min(1.0, (old_hip_width - hip_width) / max(0.04, front_width * 0.42)))

        if abs(depth_signal) >= 0.012:
            self._rtm_pose_3d_r0_side_hint = 1.0 if depth_signal > 0.0 else -1.0
        elif self._rtm_pose_3d_r0_side_hint == 0.0 and abs(width_delta) >= 0.018:
            self._rtm_pose_3d_r0_side_hint = 1.0

        side = self._rtm_pose_3d_r0_side_hint
        width_signal = side * width_narrow * 0.36 + self._centered_clamp(width_delta * 0.18, 0.10)
        combined = depth_signal * 0.58 + width_signal
        if abs(combined) < 0.010:
            combined = 0.0
        return 0.5 + self._centered_clamp(combined, 0.46)

    @staticmethod
    def _rtm_pose_3d_depth_balance(line: np.ndarray) -> float:
        length = float(np.linalg.norm(line))
        if length < 1e-5:
            return 0.0
        return float(max(-1.0, min(1.0, line[2] / length)))

    @staticmethod
    def _angle_delta_deg(current: float, previous: float) -> float:
        delta = current - previous
        while delta > 180.0:
            delta -= 360.0
        while delta < -180.0:
            delta += 360.0
        return float(delta)

    @staticmethod
    def _rtm_pose_3d_line_angle_2d(line: np.ndarray) -> float:
        if float(np.linalg.norm(line)) < 1e-5:
            return 0.0
        return RealtimeAnalyzer._normalize_pose_angle(float(np.degrees(np.arctan2(line[1], line[0]))))

    @staticmethod
    def _rtm_pose_3d_torso_roll_angle_2d(line: np.ndarray) -> float:
        if float(np.linalg.norm(line)) < 1e-5:
            return 0.0
        return float(np.degrees(np.arctan2(line[0], -line[1])))

    @staticmethod
    def _rtm_pose_3d_horizontal_angle(vector: np.ndarray) -> float:
        if float(np.linalg.norm(vector[[0, 2]])) < 1e-5:
            return 0.0
        return float(np.degrees(np.arctan2(vector[2], vector[0])))

    @staticmethod
    def _rtm_pose_3d_pitch_angle(vector: np.ndarray) -> float:
        flat = float(np.linalg.norm(vector[:2]))
        if flat < 1e-5:
            return 0.0
        return float(np.degrees(np.arctan2(vector[2], flat)))

    def _rtm_pose_3d_predicted_hip_delta_y(self, hip_mid: np.ndarray, previous_mid: np.ndarray, dt: float) -> float:
        delta_y = float(hip_mid[1] - previous_mid[1])
        velocity_y = delta_y / max(0.001, dt)
        horizon = 0.018
        if self.compression_latency > 0:
            horizon += min(0.055, self.compression_latency * 0.009)
        elif self.compression_latency < 0:
            horizon *= 0.45
        max_prediction = 2.8 + max(0, self.compression_latency) * 0.9
        predicted_extra = max(-max_prediction, min(max_prediction, velocity_y * horizon))
        return delta_y + predicted_extra

    def _rtm_pose_3d_stable_l0_reference_y(self, hip_y: float, virtual_half_len: float, confidence: float) -> float:
        if self._rtm_pose_3d_l0_reference_y is None:
            self._rtm_pose_3d_l0_reference_y = hip_y
            return hip_y
        reference_y = float(self._rtm_pose_3d_l0_reference_y)
        distance = hip_y - reference_y
        drift_window = max(8.0, virtual_half_len * 0.65)
        if confidence >= 0.45 and abs(distance) <= drift_window:
            alpha = 0.004 if self.compression_latency <= 0 else 0.0025
            self._rtm_pose_3d_l0_reference_y = reference_y + distance * alpha
        return float(self._rtm_pose_3d_l0_reference_y)

    @staticmethod
    def _rtm_pose_3d_virtual_core(result: RtmPose3dResult | None, frame_shape: tuple[int, int]) -> dict[str, np.ndarray | float] | None:
        if result is None:
            return None
        keypoints2d = np.asarray(result.keypoints2d, dtype=np.float32)
        keypoints3d = np.asarray(result.keypoints3d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32)
        if keypoints2d.ndim != 2 or keypoints2d.shape[0] < 17 or keypoints3d.ndim != 2 or keypoints3d.shape[0] < 17:
            return None
        required = (11, 12, 13, 14)
        if len(scores) < 17 or any(float(scores[index]) < 0.24 for index in required):
            return None

        l_sh, r_sh = keypoints2d[5, :2], keypoints2d[6, :2]
        l_hip, r_hip = keypoints2d[11, :2], keypoints2d[12, :2]
        l_knee, r_knee = keypoints2d[13, :2], keypoints2d[14, :2]
        shoulder_mid = (l_sh + r_sh) * 0.5
        hip_mid = (l_hip + r_hip) * 0.5
        hip_line = r_hip - l_hip
        shoulder_line = r_sh - l_sh
        left_thigh_mid = (l_hip + l_knee) * 0.5
        right_thigh_mid = (r_hip + r_knee) * 0.5
        thigh_midline = right_thigh_mid - left_thigh_mid
        thigh_midline_mid = (left_thigh_mid + right_thigh_mid) * 0.5
        left_thigh_len = float(np.linalg.norm(l_knee - l_hip))
        right_thigh_len = float(np.linalg.norm(r_knee - r_hip))
        torso_up = shoulder_mid - hip_mid
        torso_len = float(np.linalg.norm(torso_up))
        hip_width = float(np.linalg.norm(hip_line))
        shoulder_width = float(np.linalg.norm(shoulder_line))
        thigh_scale = max(left_thigh_len, right_thigh_len, hip_width)
        if hip_width < 8.0 or thigh_scale < 14.0:
            return None

        virtual_axis_dir = np.array([0.0, 1.0], dtype=np.float32)
        virtual_half_len = max(torso_len * 0.10, min(torso_len * 0.24, hip_width * 0.52))
        virtual_axis_start = hip_mid - virtual_axis_dir * virtual_half_len
        virtual_axis_end = hip_mid + virtual_axis_dir * virtual_half_len
        virtual_axis_mid = hip_mid

        pelvis_3d = (keypoints3d[11, :3] + keypoints3d[12, :3]) * 0.5
        shoulder_3d = (keypoints3d[5, :3] + keypoints3d[6, :3]) * 0.5
        torso_up_3d = shoulder_3d - pelvis_3d
        hip_line_3d = keypoints3d[12, :3] - keypoints3d[11, :3]
        shoulder_line_3d = keypoints3d[6, :3] - keypoints3d[5, :3]
        torso_len_3d = float(np.linalg.norm(torso_up_3d))
        hip_width_3d = float(np.linalg.norm(hip_line_3d))
        shoulder_width_3d = float(np.linalg.norm(shoulder_line_3d))
        scale_3d = max(0.08, torso_len_3d + hip_width_3d * 0.45 + shoulder_width_3d * 0.20)
        virtual_3d = pelvis_3d + hip_line_3d / max(0.08, hip_width_3d) * max(0.04, hip_width_3d * 0.42)

        body_confidence = float(np.nanmean(scores[:17]))
        core_confidence = float(min(scores[index] for index in required))
        shoulder_confidence = float(min(scores[5], scores[6]))
        confidence = max(0.0, min(1.0, ((body_confidence * 0.55 + core_confidence * 0.45) - 0.20) / 0.54))

        return {
            "shoulder_mid_2d": shoulder_mid,
            "hip_mid_2d": hip_mid,
            "left_thigh_mid_2d": left_thigh_mid,
            "right_thigh_mid_2d": right_thigh_mid,
            "thigh_midline_2d": thigh_midline,
            "thigh_midline_mid_2d": thigh_midline_mid,
            "virtual_axis_start_2d": virtual_axis_start,
            "virtual_axis_end_2d": virtual_axis_end,
            "virtual_axis_mid_2d": virtual_axis_mid,
            "virtual_axis_dir_2d": virtual_axis_dir,
            "hip_line_2d": hip_line,
            "shoulder_line_2d": shoulder_line,
            "torso_up_2d": torso_up,
            "pelvis_3d": pelvis_3d,
            "shoulder_mid_3d": shoulder_3d,
            "virtual_3d": virtual_3d,
            "torso_up_3d": torso_up_3d,
            "hip_line_3d": hip_line_3d,
            "shoulder_line_3d": shoulder_line_3d,
            "scale_3d": float(scale_3d),
            "virtual_axis_half_len_2d": float(virtual_half_len),
            "thigh_scale_2d": float(max(24.0, hip_width * 1.35)),
            "body_scale_2d": float(max(1.0, torso_len + hip_width * 0.45 + shoulder_width * 0.20)),
            "body_height_2d": float(max(24.0, torso_len * 1.8)),
            "shoulder_confidence": shoulder_confidence,
            "confidence": float(confidence),
        }

    def _rtm_pose_3d_infer_interval(self) -> int:
        if self.compression_latency <= 0:
            return 1
        return min(6, 1 + self.compression_latency)

    def _rtm_pose_3d_prediction_strength(self) -> float:
        if self.compression_latency <= 0:
            return 0.12
        return min(0.62, 0.18 + self.compression_latency * 0.08)

    def _draw_rtm_pose_3d_preview(self, preview: np.ndarray, result: RtmPose3dResult | None = None) -> np.ndarray:
        h, w = preview.shape[:2]
        panel_w = int(max(180, min(300, w * 0.42)))
        panel = np.zeros((h, panel_w, 3), dtype=np.uint8)
        cv2.line(panel, (0, 0), (0, h - 1), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.putText(panel, self._rtm_pose_label(), (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (225, 235, 245), 1, cv2.LINE_AA)
        cv2.putText(panel, "OpenMMLab MMPose / rtmlib", (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (120, 170, 230), 1, cv2.LINE_AA)

        backend = self._rtm_pose_backend()
        if result is None:
            with self._rtm_pose_3d_lock:
                result = self._rtm_pose_3d_last

        if result is None:
            status = backend.status if backend is not None else f"{self._rtm_pose_label()}: off"
            self._put_wrapped_status(panel, status, 10, 66, panel_w - 20, (120, 170, 255))
            self._draw_rtm_pose_3d_stats(panel)
            return np.concatenate((preview, panel), axis=1)

        self._draw_rtm_pose_2d_overlay(preview, result)
        self._draw_rtm_pose_3d_panel(panel, result)
        self._draw_rtm_pose_3d_stats(panel)
        return np.concatenate((preview, panel), axis=1)

    def _draw_rtm_pose_3d_stats(self, panel: np.ndarray) -> None:
        h, _w = panel.shape[:2]
        with self._rtm_pose_3d_lock:
            pending = self._rtm_pose_3d_pending
            last_ms = self._rtm_pose_3d_last_ms
            last_frame = self._rtm_pose_3d_last_frame
            error = self._rtm_pose_3d_last_error
        age = max(0, self._rtm_pose_3d_frame - last_frame)
        mode = f"{self._rtm_pose_label()} async x{self._rtm_pose_3d_infer_interval()}"
        if self.rtm_pose_flow_enabled:
            mode += " flow"
        if self.rtm_pose_kalman_enabled:
            mode += " kalman"
        if pending:
            mode += " running"
        cv2.putText(panel, mode, (10, h - 44), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (130, 190, 235), 1, cv2.LINE_AA)
        cv2.putText(panel, f"infer {last_ms:.0f}ms age {age}f", (10, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (130, 190, 235), 1, cv2.LINE_AA)
        if error:
            self._put_wrapped_status(panel, error, 10, 66, panel.shape[1] - 20, (120, 170, 255))

    @staticmethod
    def _put_wrapped_status(panel: np.ndarray, text: str, x: int, y: int, max_width: int, color: tuple[int, int, int]) -> None:
        words = str(text).replace("\\", "/").split()
        line = ""
        line_height = 15
        for word in words:
            candidate = word if not line else f"{line} {word}"
            width = cv2.getTextSize(candidate, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)[0][0]
            if width > max_width and line:
                cv2.putText(panel, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
                y += line_height
                line = word
            else:
                line = candidate
        if line:
            cv2.putText(panel, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)

    @staticmethod
    def _rtm_pose_body_bones() -> tuple[tuple[int, int], ...]:
        return (
            (5, 6),
            (5, 7),
            (7, 9),
            (6, 8),
            (8, 10),
            (5, 11),
            (6, 12),
            (11, 12),
            (11, 13),
            (13, 15),
            (12, 14),
            (14, 16),
            (0, 5),
            (0, 6),
        )

    def _draw_rtm_pose_2d_overlay(self, preview: np.ndarray, result: RtmPose3dResult) -> None:
        keypoints = np.asarray(result.keypoints2d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32)
        if keypoints.ndim != 2 or keypoints.shape[0] < 17:
            return
        for start, end in RealtimeAnalyzer._rtm_pose_body_bones():
            if start >= len(keypoints) or end >= len(keypoints):
                continue
            if start < len(scores) and end < len(scores) and min(scores[start], scores[end]) < 0.22:
                continue
            a = tuple(np.round(keypoints[start, :2]).astype(int))
            b = tuple(np.round(keypoints[end, :2]).astype(int))
            cv2.line(preview, a, b, (80, 235, 255), 2, cv2.LINE_AA)
        for index in range(min(17, len(keypoints))):
            if index < len(scores) and scores[index] < 0.22:
                continue
            point = tuple(np.round(keypoints[index, :2]).astype(int))
            cv2.circle(preview, point, 3, (80, 255, 170), -1, cv2.LINE_AA)
        core = RealtimeAnalyzer._rtm_pose_3d_virtual_core(result, preview.shape[:2])
        if core is not None:
            hip_mid = tuple(np.round(core["hip_mid_2d"]).astype(int))
            shoulder_mid = tuple(np.round(core["shoulder_mid_2d"]).astype(int))
            cv2.line(preview, tuple(np.round(keypoints[11, :2]).astype(int)), tuple(np.round(keypoints[12, :2]).astype(int)), (255, 80, 210), 2, cv2.LINE_AA)
            cv2.line(preview, hip_mid, shoulder_mid, (0, 220, 255), 2, cv2.LINE_AA)
            previous = self._rtm_pose_3d_l0_reference_sample
            if previous is not None:
                _old_time, old_mid, old_line, old_confidence = previous
                if old_confidence >= 0.20:
                    old_start = tuple(np.round(old_mid - old_line * 0.5).astype(int))
                    old_end = tuple(np.round(old_mid + old_line * 0.5).astype(int))
                    old_center = tuple(np.round(old_mid).astype(int))
                    cv2.line(preview, old_start, old_end, (255, 120, 40), 2, cv2.LINE_AA)
                    cv2.circle(preview, old_center, 5, (255, 120, 40), -1, cv2.LINE_AA)
            previous_axis = self._rtm_pose_3d_axis_reference_sample
            if previous_axis is not None:
                _old_time, old_core, old_confidence = previous_axis
                if old_confidence >= 0.20:
                    old_hip_mid_raw = np.asarray(old_core["hip_mid_2d"], dtype=np.float32)
                    old_shoulder_mid_raw = np.asarray(old_core["shoulder_mid_2d"], dtype=np.float32)
                    old_shoulder_line = np.asarray(old_core["shoulder_line_2d"], dtype=np.float32)
                    old_hip_mid = tuple(np.round(old_hip_mid_raw).astype(int))
                    old_shoulder_mid = tuple(np.round(old_shoulder_mid_raw).astype(int))
                    old_l_shoulder = np.round(old_shoulder_mid_raw - old_shoulder_line * 0.5).astype(int)
                    old_r_shoulder = np.round(old_shoulder_mid_raw + old_shoulder_line * 0.5).astype(int)
                    cv2.line(preview, old_hip_mid, old_shoulder_mid, (255, 120, 40), 1, cv2.LINE_AA)
                    cv2.line(preview, tuple(old_l_shoulder), tuple(old_r_shoulder), (255, 120, 40), 1, cv2.LINE_AA)
            cv2.circle(preview, hip_mid, 5, (255, 80, 210), -1, cv2.LINE_AA)
        cv2.putText(preview, self._rtm_pose_label(), (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (80, 235, 255), 1, cv2.LINE_AA)

    def _draw_rtm_pose_3d_panel(self, panel: np.ndarray, result: RtmPose3dResult) -> None:
        keypoints = np.asarray(result.keypoints3d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32)
        h, w = panel.shape[:2]
        if keypoints.ndim != 2 or keypoints.shape[0] < 17 or keypoints.shape[1] < 3:
            cv2.putText(panel, "bad 3D result", (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (80, 120, 255), 1, cv2.LINE_AA)
            return
        body = keypoints[:17, :3].copy()
        valid = np.ones(17, dtype=bool)
        if len(scores) >= 17:
            valid = scores[:17] >= 0.22
        if int(np.count_nonzero(valid)) < 5:
            cv2.putText(panel, "low confidence", (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (80, 120, 255), 1, cv2.LINE_AA)
            return

        origin = np.nanmean(body[valid], axis=0)
        body -= origin
        projected = np.column_stack((body[:, 0] + body[:, 2] * 0.36, body[:, 1] - body[:, 2] * 0.18))
        valid_points = projected[valid]
        min_xy = np.nanmin(valid_points, axis=0)
        max_xy = np.nanmax(valid_points, axis=0)
        span = np.maximum(max_xy - min_xy, 1.0)
        scale = min((w - 36) / max(1.0, span[0]), (h - 82) / max(1.0, span[1]))
        scale = max(0.12, min(8.0, scale))
        center = (min_xy + max_xy) * 0.5
        target = np.array([w * 0.52, h * 0.55], dtype=np.float32)

        def map_projected(point: np.ndarray) -> tuple[int, int]:
            mapped = (point - center) * scale + target
            return int(np.clip(mapped[0], 8, w - 8)), int(np.clip(mapped[1], 56, h - 8))

        def pt(index: int) -> tuple[int, int]:
            return map_projected(projected[index])

        for start, end in RealtimeAnalyzer._rtm_pose_body_bones():
            if valid[start] and valid[end]:
                cv2.line(panel, pt(start), pt(end), (245, 245, 245), 2, cv2.LINE_AA)
        if valid[5] and valid[6] and valid[11] and valid[12]:
            current_hip_mid = (projected[11] + projected[12]) * 0.5
            current_shoulder_mid = (projected[5] + projected[6]) * 0.5
            cv2.line(panel, map_projected(current_hip_mid), map_projected(current_shoulder_mid), (0, 220, 255), 2, cv2.LINE_AA)
        previous = self._rtm_pose_3d_axis_reference_sample
        if previous is not None:
            _old_time, old_core, old_confidence = previous
            old_hip_line = np.asarray(old_core["hip_line_3d"], dtype=np.float32)
            old_shoulder_line = np.asarray(old_core["shoulder_line_3d"], dtype=np.float32)
            old_pelvis = np.asarray(old_core["pelvis_3d"], dtype=np.float32) - origin
            old_shoulder = np.asarray(old_core.get("shoulder_mid_3d", old_core["pelvis_3d"]), dtype=np.float32) - origin
            if old_confidence >= 0.20 and float(np.linalg.norm(old_hip_line)) >= 0.08:
                old_start_3d = old_pelvis - old_hip_line * 0.5
                old_end_3d = old_pelvis + old_hip_line * 0.5
                old_start = np.array([old_start_3d[0] + old_start_3d[2] * 0.36, old_start_3d[1] - old_start_3d[2] * 0.18])
                old_end = np.array([old_end_3d[0] + old_end_3d[2] * 0.36, old_end_3d[1] - old_end_3d[2] * 0.18])
                cv2.line(panel, map_projected(old_start), map_projected(old_end), (255, 120, 40), 2, cv2.LINE_AA)
            if old_confidence >= 0.20 and float(np.linalg.norm(old_shoulder_line)) >= 0.08:
                old_start_3d = old_shoulder - old_shoulder_line * 0.5
                old_end_3d = old_shoulder + old_shoulder_line * 0.5
                old_start = np.array([old_start_3d[0] + old_start_3d[2] * 0.36, old_start_3d[1] - old_start_3d[2] * 0.18])
                old_end = np.array([old_end_3d[0] + old_end_3d[2] * 0.36, old_end_3d[1] - old_end_3d[2] * 0.18])
                old_pelvis_2d = np.array([old_pelvis[0] + old_pelvis[2] * 0.36, old_pelvis[1] - old_pelvis[2] * 0.18])
                old_shoulder_2d = np.array([old_shoulder[0] + old_shoulder[2] * 0.36, old_shoulder[1] - old_shoulder[2] * 0.18])
                cv2.line(panel, map_projected(old_start), map_projected(old_end), (255, 120, 40), 1, cv2.LINE_AA)
                cv2.line(panel, map_projected(old_pelvis_2d), map_projected(old_shoulder_2d), (255, 120, 40), 1, cv2.LINE_AA)
        for index in range(17):
            if not valid[index]:
                continue
            color = (80, 255, 170) if index in {11, 12} else (245, 245, 245)
            radius = 5 if index in {11, 12} else 4
            cv2.circle(panel, pt(index), radius, color, -1, cv2.LINE_AA)
        cv2.putText(panel, result.status, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (130, 170, 210), 1, cv2.LINE_AA)

    @staticmethod
    def _normalize_pose_angle(angle: float) -> float:
        while angle > 90.0:
            angle -= 180.0
        while angle < -90.0:
            angle += 180.0
        return angle

    @staticmethod
    def _centered_clamp(value: float, limit: float) -> float:
        return float(max(-limit, min(limit, value)))

    @staticmethod
    def _draw_axis_boxes(mask: np.ndarray, preview: np.ndarray) -> None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
            if cv2.contourArea(contour) < 24:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 190, 255), 1)

    @staticmethod
    def _draw_preview(preview: np.ndarray, positions: dict[str, float], confidence: float, draw_l0_line: bool = True) -> None:
        h, w = preview.shape[:2]
        if draw_l0_line:
            y = round(positions.get("L0", 0.5) * (h - 1))
            cv2.line(preview, (0, y), (w, y), (80, 255, 80), 2)
        labels = " ".join(f"{axis}:{value:.2f}" for axis, value in positions.items())
        cv2.putText(
            preview,
            f"{labels} conf:{confidence:.2f}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def _pose_v2_split_preview(self, preview: np.ndarray) -> np.ndarray:
        h, w = preview.shape[:2]
        if w < 220 or h < 180:
            return preview
        left_w = w // 2
        right_w = w - left_w
        left = np.zeros((h, left_w, 3), dtype=np.uint8)
        fit_scale = min(left_w / max(1, w), h / max(1, h))
        fit_w = max(1, int(round(w * fit_scale)))
        fit_h = max(1, int(round(h * fit_scale)))
        fitted = cv2.resize(preview, (fit_w, fit_h), interpolation=cv2.INTER_AREA)
        x0 = max(0, (left_w - fit_w) // 2)
        y0 = max(0, (h - fit_h) // 2)
        left[y0 : y0 + fit_h, x0 : x0 + fit_w] = fitted
        panel = np.zeros((h, right_w, 3), dtype=np.uint8)
        cv2.line(panel, (0, 0), (0, h - 1), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.putText(panel, "V2 full", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 230, 240), 1, cv2.LINE_AA)
        skeleton = self._pose_v2_complete_display_skeleton(self._pose_v2_last_skeleton, self._pose_v2_last_edge_notes)
        if not skeleton:
            cv2.putText(panel, "waiting", (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 160, 170), 1, cv2.LINE_AA)
            return np.concatenate((left, panel), axis=1)

        points = np.array(list(skeleton.values()), dtype=np.float32)
        min_xy = points.min(axis=0)
        max_xy = points.max(axis=0)
        span = np.maximum(max_xy - min_xy, 1.0)
        scale = min((right_w - 28) / max(1.0, span[0]), (h - 58) / max(1.0, span[1]))
        scale = max(0.12, min(2.8, scale))
        center = (min_xy + max_xy) * 0.5
        target = np.array([right_w * 0.5, h * 0.52], dtype=np.float32)

        def pt(name: str) -> tuple[int, int]:
            raw = np.array(skeleton[name], dtype=np.float32)
            mapped = (raw - center) * scale + target
            return int(np.clip(mapped[0], 8, right_w - 8)), int(np.clip(mapped[1], 36, h - 8))

        bones = (
            ("head", "neck"),
            ("neck", "l_shoulder"),
            ("neck", "r_shoulder"),
            ("neck", "chest"),
            ("chest", "waist"),
            ("waist", "pelvis"),
            ("pelvis", "l_hip"),
            ("pelvis", "r_hip"),
            ("l_hip", "l_knee"),
            ("r_hip", "r_knee"),
            ("l_knee", "l_ankle"),
            ("r_knee", "r_ankle"),
            ("l_knee", "l_ankle_ghost"),
            ("r_knee", "r_ankle_ghost"),
        )
        for start, end in bones:
            if start in skeleton and end in skeleton:
                color = (80, 170, 255) if start.endswith("_ghost") or end.endswith("_ghost") else (245, 245, 245)
                cv2.line(panel, pt(start), pt(end), color, 2, cv2.LINE_AA)
        if "chest" in skeleton and "waist" in skeleton:
            cv2.line(panel, pt("chest"), pt("waist"), (60, 255, 180), 3, cv2.LINE_AA)
        if "waist" in skeleton and "pelvis" in skeleton:
            cv2.line(panel, pt("waist"), pt("pelvis"), (60, 255, 180), 3, cv2.LINE_AA)
        for name in skeleton:
            color = (245, 245, 245)
            radius = 4
            if name in {"pelvis", "l_hip", "r_hip"}:
                color = (70, 255, 170)
                radius = 5
            elif name.endswith("_ghost"):
                color = (80, 170, 255)
                radius = 3
            cv2.circle(panel, pt(name), radius, color, -1, cv2.LINE_AA)
        y = 46
        for note in self._pose_v2_last_edge_notes[:3]:
            short_note = note
            short_note = short_note.replace("head/upper body may be cropped", "top cropped")
            short_note = short_note.replace("legs may continue offscreen", "legs offscreen")
            short_note = short_note.replace("left side may be cropped", "left cropped")
            short_note = short_note.replace("right side may be cropped", "right cropped")
            cv2.putText(panel, short_note, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (110, 185, 255), 1, cv2.LINE_AA)
            y += 14
        return np.concatenate((left, panel), axis=1)

    @staticmethod
    def _pose_v2_complete_display_skeleton(
        skeleton: dict[str, tuple[int, int]],
        edge_notes: list[str],
    ) -> dict[str, tuple[int, int]]:
        if not skeleton:
            return {}
        completed = dict(skeleton)
        for side in ("l", "r"):
            hint = completed.get(f"{side}_knee_hint")
            if f"{side}_knee" not in completed and hint is not None:
                completed[f"{side}_knee"] = hint
                completed.pop(f"{side}_knee_hint", None)
            ankle_hint = completed.get(f"{side}_ankle_hint")
            if f"{side}_ankle" not in completed and ankle_hint is not None:
                completed[f"{side}_ankle"] = ankle_hint
                completed.pop(f"{side}_ankle_hint", None)

        bottom_cropped = any("legs may continue" in note for note in edge_notes)
        if bottom_cropped:
            for side in ("l", "r"):
                hip = completed.get(f"{side}_hip")
                knee = completed.get(f"{side}_knee")
                if hip is None or knee is None or f"{side}_ankle" in completed:
                    continue
                dx = knee[0] - hip[0]
                dy = max(12, knee[1] - hip[1])
                completed[f"{side}_ankle"] = (int(round(knee[0] + dx * 0.85)), int(round(knee[1] + dy * 0.92)))
                completed[f"{side}_ankle_ghost"] = completed.pop(f"{side}_ankle")
        return completed

    @staticmethod
    def _append_pose_preview(preview: np.ndarray, positions: dict[str, float], activity: float) -> np.ndarray:
        h, w = preview.shape[:2]
        panel_w = int(max(170, min(260, w * 0.34)))
        panel = np.zeros((h, panel_w, 3), dtype=np.uint8)
        scale = min(panel_w / 220.0, h / 360.0)
        cx = panel_w * 0.5
        base_y = h * 0.53
        l0 = positions.get("L0", 0.5) - 0.5
        l1 = positions.get("L1", 0.5) - 0.5
        l2 = positions.get("L2", 0.5) - 0.5
        r0 = positions.get("R0", 0.5) - 0.5
        r1 = positions.get("R1", 0.5) - 0.5
        r2 = positions.get("R2", 0.5) - 0.5
        sway = (l2 * 72.0 + r0 * 28.0) * scale
        roll = r1 * 78.0 * scale
        pitch = r2 * 44.0 * scale
        depth = 1.0 + l1 * 0.22
        stroke_y = l0 * 94.0 * scale
        shoulder_w = 78.0 * scale * depth
        hip_w = 58.0 * scale * depth
        torso_h = 106.0 * scale * (1.0 - l1 * 0.10)

        neck = np.array([cx - sway * 0.22, base_y - torso_h - stroke_y - pitch])
        hip = np.array([cx + sway, base_y - stroke_y + pitch * 0.28])
        head = neck + np.array([r0 * 18.0 * scale, -36.0 * scale])
        l_sh = neck + np.array([-shoulder_w * 0.5, roll])
        r_sh = neck + np.array([shoulder_w * 0.5, -roll])
        l_hip = hip + np.array([-hip_w * 0.5, -roll * 0.35])
        r_hip = hip + np.array([hip_w * 0.5, roll * 0.35])
        arm_drop = np.array([0.0, 62.0 * scale])
        leg_drop = np.array([0.0, 86.0 * scale])
        l_elbow = l_sh + np.array([-24.0 * scale - sway * 0.08, 34.0 * scale])
        r_elbow = r_sh + np.array([24.0 * scale - sway * 0.08, 34.0 * scale])
        l_hand = l_elbow + arm_drop + np.array([-10.0 * scale, 0.0])
        r_hand = r_elbow + arm_drop + np.array([10.0 * scale, 0.0])
        l_knee = l_hip + np.array([-14.0 * scale + sway * 0.10, 48.0 * scale])
        r_knee = r_hip + np.array([14.0 * scale + sway * 0.10, 48.0 * scale])
        l_foot = l_knee + leg_drop + np.array([-10.0 * scale, 0.0])
        r_foot = r_knee + leg_drop + np.array([10.0 * scale, 0.0])
        joints = {
            "head": head,
            "neck": neck,
            "l_sh": l_sh,
            "r_sh": r_sh,
            "l_elbow": l_elbow,
            "r_elbow": r_elbow,
            "l_hand": l_hand,
            "r_hand": r_hand,
            "l_hip": l_hip,
            "r_hip": r_hip,
            "l_knee": l_knee,
            "r_knee": r_knee,
            "l_foot": l_foot,
            "r_foot": r_foot,
        }

        def pt(name: str) -> tuple[int, int]:
            point = joints[name]
            return int(np.clip(point[0], 8, panel_w - 8)), int(np.clip(point[1], 8, h - 8))

        bones = [
            ("head", "neck"),
            ("neck", "l_sh"),
            ("neck", "r_sh"),
            ("l_sh", "l_elbow"),
            ("l_elbow", "l_hand"),
            ("r_sh", "r_elbow"),
            ("r_elbow", "r_hand"),
            ("neck", "l_hip"),
            ("neck", "r_hip"),
            ("l_hip", "r_hip"),
            ("l_hip", "l_knee"),
            ("l_knee", "l_foot"),
            ("r_hip", "r_knee"),
            ("r_knee", "r_foot"),
        ]
        cv2.putText(panel, "Pose", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(panel, f"{activity:.3f}", (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (160, 180, 200), 1, cv2.LINE_AA)
        for a, b in bones:
            cv2.line(panel, pt(a), pt(b), (245, 245, 245), 3, cv2.LINE_AA)
        for name in joints:
            radius = 6 if name in {"head", "neck"} else 5
            cv2.circle(panel, pt(name), radius, (255, 110, 25), -1, cv2.LINE_AA)
            cv2.circle(panel, pt(name), radius, (255, 220, 120), 1, cv2.LINE_AA)
        return np.concatenate((preview, panel), axis=1)
