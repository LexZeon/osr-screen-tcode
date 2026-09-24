"""Standalone image motion visualization; no person-depth or device mapping."""
import cv2
import numpy as np

from observations import Observation


class FrameMotion:
    def __init__(self, scale=False):
        self.scale = scale
        self.gray = None
        self.timestamp = None
        self.transform = np.eye(3)
        self.last = None

    def update(self, gray, timestamp):
        if self.timestamp is not None and timestamp <= self.timestamp:
            return self.last, []
        if self.gray is None or self.gray.shape != gray.shape or timestamp - self.timestamp > 0.5:
            self.gray, self.timestamp = gray.copy(), timestamp
            self.transform = np.eye(3)
            self.last = Observation(timestamp, "calibrating")
            return self.last, []
        previous = self.gray
        self.gray, self.timestamp = gray.copy(), timestamp
        features = cv2.goodFeaturesToTrack(previous, maxCorners=160, qualityLevel=0.01, minDistance=8)
        vectors = []
        estimate = None
        if features is not None and len(features) >= 8:
            forward, ok, _ = cv2.calcOpticalFlowPyrLK(previous, gray, features, None)
            if forward is not None:
                back, reverse_ok, _ = cv2.calcOpticalFlowPyrLK(gray, previous, forward, None)
                if back is not None:
                    valid = (ok.ravel() == 1) & (reverse_ok.ravel() == 1)
                    valid &= np.isfinite(forward[:, 0]).all(axis=1)
                    valid &= np.linalg.norm(back[:, 0] - features[:, 0], axis=1) < 1.5
                    a, b = features[valid, 0], forward[valid, 0]
                    if len(a) >= 8:
                        if self.scale:
                            estimate, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC,
                                                                           ransacReprojThreshold=2,
                                                                           maxIters=150)
                            if estimate is not None:
                                mask = inliers.ravel().astype(bool)
                                size = np.sqrt(abs(np.linalg.det(estimate[:, :2])))
                                if mask.sum() < 8 or mask.mean() < 0.45 or not 0.8 < size < 1.25:
                                    estimate = None
                                else:
                                    a, b = a[mask], b[mask]
                        else:
                            delta = np.median(b - a, axis=0)
                            estimate = np.array([[1, 0, delta[0]], [0, 1, delta[1]]], float)
                        if estimate is not None:
                            vectors = list(zip(a, b))
        if estimate is None or not np.isfinite(estimate).all():
            self.transform = np.eye(3)
            self.last = Observation(timestamp, "missing")
        else:
            step = np.eye(3)
            step[:2] = estimate
            self.transform = step @ self.transform
            h, w = gray.shape
            center = np.array([w / 2, h / 2, 1])
            displacement = self.transform @ center - center
            size = np.sqrt(abs(np.linalg.det(self.transform[:2, :2])))
            self.last = Observation(timestamp, "ready", (float(displacement[0] / w * 100),
                                                         float(-displacement[1] / h * 100),
                                                         float((size - 1) * 100)))
        return self.last, vectors
