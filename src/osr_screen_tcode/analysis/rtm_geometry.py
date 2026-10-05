from __future__ import annotations

import time

import numpy as np

from ..pose_backends import RtmPose3dResult


class RtmGeometryMixin:
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
        timestamp: float | None = None,
    ) -> tuple[dict[str, float] | None, float]:
        core = self._rtm_pose_3d_virtual_core(result, frame_shape)
        if core is None:
            return None, 0.0
        confidence = float(core["confidence"])
        if confidence <= 0.02:
            return None, 0.0
        positions = self._rtm_pose_3d_axes_from_previous_core(core, confidence, timestamp=timestamp)
        return positions, confidence

    def _rtm_pose_3d_axes_from_previous_core(self, core: dict[str, np.ndarray | float], confidence: float, timestamp: float | None = None) -> dict[str, float]:
        now = time.perf_counter() if timestamp is None else timestamp
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
        from ..analyzer import RealtimeAnalyzer

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
