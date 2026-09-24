"""Standalone image-space pose stabilization. No device or axis mappings."""
from dataclasses import dataclass

import cv2
import numpy as np

EDGES = ((5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11),
         (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))


@dataclass(frozen=True)
class Options:
    reject: bool = True
    flow: bool = True
    kalman: bool = True
    smooth: bool = True


class Stabilizer:
    def __init__(self, options=Options()):
        self.options = options
        self.time = None
        self.gray = None
        self.xy = np.full((17, 2), np.nan, np.float32)
        self.last_seen = np.full(17, -np.inf)
        self.filters = [None] * 17
        self.lengths = {}
        self.rejected = np.zeros(17, bool)
        self.previous_raw = np.full((17, 2), np.nan, np.float32)
        self.flow_points = np.full((17, 2), np.nan, np.float32)
        self.reject_streak = np.zeros(17, int)
        self.reset_reason = ""

    def update(self, gray, points, scores, timestamp):
        # Duplicate/out-of-order samples must not advance filters or derivatives.
        if self.time is not None and timestamp <= self.time:
            return self.xy.copy(), self.rejected.copy()
        self.reset_reason = ""
        if not np.isfinite(timestamp):
            return self.xy.copy(), self.rejected.copy()
        elapsed = timestamp - self.time if self.time is not None else 1 / 30
        reason = ""
        if self.gray is not None and self.gray.shape != gray.shape:
            reason = "size"
        elif elapsed > 0.2:
            reason = "gap"
        elif self.gray is not None:
            before = cv2.resize(self.gray, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
            after = cv2.resize(gray, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
            difference = np.abs(after - before)
            if difference.mean() > 35 and (difference > 30).mean() > 0.55:
                reason = "scene"
        raw = np.full((17, 2), np.nan, np.float32)
        score = np.zeros(17)
        if points is not None:
            n = min(17, len(points), len(scores))
            raw[:n] = np.asarray(points)[:n, :2]
            score[:n] = np.asarray(scores).reshape(-1)[:n]
        valid = np.isfinite(raw).all(axis=1) & (score >= 0.35)
        h, w = gray.shape
        valid &= (raw[:, 0] >= 0) & (raw[:, 0] < w) & (raw[:, 1] >= 0) & (raw[:, 1] < h)
        # Similar-background cuts can evade image differences. A broad pose
        # relocation should also restart tracking, not reject a whole new person.
        paired = valid & (score >= 0.7) & np.isfinite(self.previous_raw).all(axis=1)
        if not reason and paired.sum() >= 6:
            body_scale = np.linalg.norm(self.previous_raw[5] - self.previous_raw[11])
            if not np.isfinite(body_scale):
                body_scale = min(w, h) * 0.25
            moved = np.linalg.norm(raw[paired] - self.previous_raw[paired], axis=1)
            if (moved > max(24, body_scale * 0.5)).mean() >= 0.75:
                reason = "pose"
        if reason:
            self.__init__(self.options)
            self.reset_reason = reason
        dt = min(0.1, elapsed) if not reason else 1 / 30
        fresh = np.isfinite(self.xy).all(axis=1) & (timestamp - self.last_seen < 0.25)
        if not fresh.any():
            self.lengths.clear()
        predicted = self.xy.copy()
        flow_ok = np.zeros(17, bool)
        if self.options.flow and self.gray is not None and fresh.any():
            ids = np.flatnonzero(fresh)
            previous = self.flow_points[ids].reshape(-1, 1, 2).astype(np.float32)
            forward, status, _ = cv2.calcOpticalFlowPyrLK(self.gray, gray, previous, None)
            if forward is not None:
                backward, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, self.gray, forward, None)
                if backward is not None:
                    ok = (status.ravel() == 1) & (back_status.ravel() == 1)
                    ok &= np.linalg.norm(backward[:, 0] - previous[:, 0], axis=1) < 1.5
                    ok &= np.isfinite(forward[:, 0]).all(axis=1)
                    ok &= (forward[:, 0, 0] >= 0) & (forward[:, 0, 0] < w)
                    ok &= (forward[:, 0, 1] >= 0) & (forward[:, 0, 1] < h)
                    flow_ok[ids[ok]] = True
                    predicted[ids[ok]] = forward[ok, 0]
        accepted = valid.copy()
        torso = [self.lengths[e] for e in ((5, 11), (6, 12)) if e in self.lengths]
        scale = float(np.median(torso)) if torso else min(w, h) * 0.25
        reset = ~fresh
        if self.options.reject:
            # A generous velocity gate preserves fast real movements; flow supplies
            # the expected image displacement instead of extrapolating blindly.
            tolerance = max(12, scale * (0.18 + 5 * dt))
            accepted &= ~fresh | (np.linalg.norm(raw - predicted, axis=1) < tolerance)
            for edge, baseline in self.lengths.items():
                a, b = edge
                if accepted[a] and accepted[b]:
                    length = np.linalg.norm(raw[a] - raw[b])
                    if not 0.4 * baseline < length < 2.2 * baseline:
                        accepted[a if score[a] < score[b] else b] = False
            # Repeated, confident observations can reacquire a point after a
            # sudden real movement, rather than remaining locked to old history.
            consistent = np.linalg.norm(raw - self.previous_raw, axis=1) < tolerance
            recover = valid & ~accepted & (score >= 0.7) & consistent & (self.reject_streak >= 1)
            accepted |= recover
            reset |= recover
        self.rejected = valid & ~accepted
        self.reject_streak = np.where(self.rejected, self.reject_streak + 1, 0)
        self.previous_raw = np.where(valid[:, None], raw, np.nan)
        output = np.full_like(raw, np.nan)
        for i in range(17):
            if reset[i]:
                self.filters[i] = None
            if not accepted[i] and not fresh[i]:
                self.filters[i] = None
                continue
            if not accepted[i] and not (self.options.flow or self.options.kalman):
                if self.options.reject and fresh[i]:
                    output[i] = self.xy[i]
                continue
            measurement = raw[i] if accepted[i] else predicted[i]
            if not np.isfinite(measurement).all():
                continue
            if self.options.kalman:
                k = self.filters[i]
                if k is None:
                    k = cv2.KalmanFilter(4, 2)
                    k.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
                    k.statePost = np.array([[measurement[0]], [measurement[1]], [0], [0]], np.float32)
                    k.errorCovPost = np.eye(4, dtype=np.float32) * 20
                    self.filters[i] = k
                k.transitionMatrix = np.array([[1, 0, dt, 0], [0, 1, 0, dt],
                                               [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
                k.processNoiseCov = np.diag([2, 2, 300, 300]).astype(np.float32) * dt
                estimate = k.predict()
                # One correction per prediction. OpenCV correct() reuses the
                # predicted covariance; two successive calls are not fusion.
                if flow_ok[i] and not accepted[i]:
                    k.measurementNoiseCov = np.eye(2, dtype=np.float32) * 18
                    estimate = k.correct(predicted[i].reshape(2, 1))
                if accepted[i]:
                    k.measurementNoiseCov = np.eye(2, dtype=np.float32) * float(2 + 6 * (1 - min(score[i], 1)))
                    estimate = k.correct(raw[i].reshape(2, 1))
                measurement = estimate[:2, 0]
            if self.options.smooth and fresh[i] and not reset[i]:
                distance = np.linalg.norm(measurement - self.xy[i])
                if distance <= 3:
                    alpha = 1 - np.exp(-2 * np.pi * 8 * dt)
                    measurement = self.xy[i] + alpha * (measurement - self.xy[i])
            if accepted[i] and np.linalg.norm(measurement - raw[i]) > max(10, scale * 0.12):
                # Large disagreement is not useful stabilization: prefer the
                # accepted observation and drop stale velocity/covariance.
                measurement = raw[i]
                self.filters[i] = None
            output[i] = measurement
            if accepted[i]:
                self.last_seen[i] = timestamp
        # Do not bridge a newly observed joint to an implausible stale endpoint.
        for a, b in EDGES:
            baseline = self.lengths.get((a, b))
            if baseline is not None and not (accepted[a] and accepted[b]):
                length = np.linalg.norm(output[a] - output[b])
                if np.isfinite(length) and not baseline * 0.45 < length < max(baseline * 1.7, baseline + 12):
                    for i in (a, b):
                        if not accepted[i]:
                            output[i] = np.nan
                            self.filters[i] = None
        inside = np.isfinite(output).all(axis=1)
        inside &= (output[:, 0] >= 0) & (output[:, 0] < w) & (output[:, 1] >= 0) & (output[:, 1] < h)
        output[~inside] = np.nan
        for a, b in EDGES:
            if accepted[a] and accepted[b]:
                length = float(np.linalg.norm(raw[a] - raw[b]))
                if length > 3:
                    self.lengths[(a, b)] = 0.95 * self.lengths.get((a, b), length) + 0.05 * length
        self.time, self.gray, self.xy = timestamp, gray.copy(), output
        self.flow_points = np.where(accepted[:, None], raw, output).astype(np.float32)
        return output.copy(), self.rejected.copy()
