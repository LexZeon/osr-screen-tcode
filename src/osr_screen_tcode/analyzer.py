from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import threading
import time

import cv2
import numpy as np

from .pose_backends import OptionalRtmPose2dBackend, RtmPose3dResult
from .motion_reference import MotionReference, draw_reference, sample_vectors
from .analysis.flow import FlowAnalysisMixin
from .analysis.pose_motion import PoseMotionMixin
from .analysis.rtm_runtime import RtmRuntimeMixin
from .analysis.rtm_geometry import RtmGeometryMixin
from .analysis.preview import AnalysisPreviewMixin


SIX_AXES = ["L0", "L1", "L2", "R0", "R1", "R2"]


@dataclass(frozen=True)
class AxisAnalysis:
    positions: dict[str, float]
    confidence: float
    activity: float
    preview_bgr: np.ndarray


class RealtimeAnalyzer(
    FlowAnalysisMixin,
    PoseMotionMixin,
    RtmRuntimeMixin,
    RtmGeometryMixin,
    AnalysisPreviewMixin,
):
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
        if rtm_pose_3d_enabled:
            raise ValueError("RTM Pose 3D analysis has been removed; select RTM Pose 2D.")
        self.rtm_pose_3d_enabled = False
        self.rtm_pose_3d_weight = max(0.0, min(1.0, float(rtm_pose_3d_weight))) if self._rtm_pose_enabled() else 0.0
        self.rtm_hybrid_l0_enabled = bool(rtm_hybrid_l0_enabled) if self._rtm_pose_enabled() else False
        self.rtm_hybrid_l0_weight = max(0.01, min(1.0, float(rtm_hybrid_l0_weight))) if self.rtm_hybrid_l0_enabled else 0.0
        self.rtm_pose_flow_enabled = bool(rtm_pose_flow_enabled) if self._rtm_pose_enabled() else False
        self.rtm_pose_kalman_enabled = bool(rtm_pose_kalman_enabled) if self._rtm_pose_enabled() else False
        self.rtm_pose_device = ("directml" if rtm_pose_gpu_backend == "directml" else "cuda") if bool(rtm_pose_gpu_enabled) else "cpu"
        self._rtm_pose_2d_backend = OptionalRtmPose2dBackend(rtm_pose_2d_model_path, device=self.rtm_pose_device) if self.rtm_pose_2d_enabled else None
        self._rtm_pose_3d_backend = None  # Legacy shared geometry names do not enable 3D inference.
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
        self.motion_reference = MotionReference("v1") if self._is_hybrid_analysis_mode(self.tracker_mode) else None
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
            self._draw_preview(preview, self._positions, 0.0, draw_l0_line=not self._rtm_pose_enabled() and self.motion_reference is None)
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
        self._draw_preview(preview, active, confidence, draw_l0_line=not self._rtm_pose_enabled() and self.motion_reference is None)
        if self._rtm_pose_enabled():
            preview = self._draw_rtm_pose_3d_preview(preview, pose_result if "pose_result" in locals() else None)
        elif self.pose_v2_dance_six_axis and (self.pose_v2_l0_weight > 0.0 or self.pose_v2_six_axis_weight > 0.0):
            preview = self._pose_v2_split_preview(preview)
        elif self.pose_l0_weight > 0.0 or self.pose_six_axis_weight > 0.0:
            preview = self._append_pose_preview(preview, active, activity)
        if self.motion_reference is not None:
            self.motion_reference = replace(self.motion_reference, l0=float(active["L0"]))
            preview = draw_reference(preview, self.motion_reference)
        return AxisAnalysis(active, confidence, activity, preview)
