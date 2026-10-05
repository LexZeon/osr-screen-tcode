from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from ..pose_backends import OptionalRtmPose2dBackend, RtmPose3dResult


class RtmRuntimeMixin:
    def _rtm_pose_3d_only(self) -> bool:
        return self._rtm_pose_enabled() and self.rtm_pose_3d_weight >= 0.999 and not self.rtm_hybrid_l0_enabled

    def _rtm_pose_enabled(self) -> bool:
        return self.rtm_pose_2d_enabled or self.rtm_pose_3d_enabled

    def _rtm_pose_label(self) -> str:
        return "RTM Pose 2D" if self.rtm_pose_2d_enabled else "RTM Pose 3D"

    def _measure_rtm_pose_3d(self, frame_bgr: np.ndarray) -> tuple[dict[str, float] | None, float, RtmPose3dResult | None]:
        backend = self._rtm_pose_backend()
        if backend is None:
            return None, 0.0, None
        self._rtm_pose_3d_frame += 1
        self._apply_rtm_pose_optical_flow(frame_bgr)
        self._start_rtm_pose_3d_infer(frame_bgr)
        return self._latest_rtm_pose_3d_measurement()

    def _rtm_pose_backend(self) -> OptionalRtmPose2dBackend | None:
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

    def _rtm_pose_3d_infer_interval(self) -> int:
        if self.compression_latency <= 0:
            return 1
        return min(6, 1 + self.compression_latency)

    def _rtm_pose_3d_prediction_strength(self) -> float:
        if self.compression_latency <= 0:
            return 0.12
        return min(0.62, 0.18 + self.compression_latency * 0.08)
