from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np


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
        tracker_mode: str = "混合分析（推荐）",
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

    def process(self, frame_bgr: np.ndarray) -> AxisAnalysis:
        preview = frame_bgr.copy()
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self._prev_gray is None:
            self._prev_gray = gray
            self._draw_preview(preview, self._positions, 0.0)
            if self.pose_l0_weight > 0.0 or self.pose_six_axis_weight > 0.0:
                preview = self._append_pose_preview(preview, self._active_positions(), 0.0)
            return AxisAnalysis(self._active_positions(), 0.0, 0.0, preview)

        diff = cv2.absdiff(gray, self._prev_gray)
        _, mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        mask = self._dominant_motion_mask(mask)
        activity = float(np.count_nonzero(mask)) / float(mask.size)
        flow = self._flow(gray)
        measured, confidence = self._measure(gray, mask, flow, activity, preview)

        for axis, value in measured.items():
            value = self._shape(max(0.0, min(1.0, value)))
            if axis == "L0":
                value = self._stabilize_l0(value, activity)
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

        self._prev_gray = gray
        active = self._active_positions()
        self._draw_preview(preview, active, confidence)
        if self.pose_l0_weight > 0.0 or self.pose_six_axis_weight > 0.0:
            preview = self._append_pose_preview(preview, active, activity)
        return AxisAnalysis(active, confidence, activity, preview)

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
        if self._is_hybrid_analysis_mode(self.tracker_mode):
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
        positions = {"L0": l0}
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
    def _draw_preview(preview: np.ndarray, positions: dict[str, float], confidence: float) -> None:
        h, w = preview.shape[:2]
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
