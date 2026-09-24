"""Experimental image-plane rotation/perspective signals, not 3D pose."""
import math

import cv2
import numpy as np


class FrameRotation:
    def __init__(self):
        self.transform = np.eye(3)

    def update(self, vectors, shape):
        if len(vectors) < 12:
            return None
        a, b = (np.asarray(v, np.float32) for v in zip(*vectors))
        matrix, mask = cv2.findHomography(a, b, cv2.RANSAC, 1.5)
        if matrix is None or mask is None or mask.sum() < 12 or mask.mean() < 0.6:
            return None
        h, w = shape[:2]
        # Require coverage so a tiny texture patch cannot determine a screen-
        # wide perspective estimate. Similarity motion alone implies no yaw/pitch.
        span = np.ptp(a[mask.ravel().astype(bool)], axis=0)
        if span[0] < w * 0.25 or span[1] < h * 0.25:
            return None
        cumulative = matrix @ self.transform
        if not np.isfinite(cumulative).all() or abs(cumulative[2, 2]) < 1e-6:
            return None
        cumulative /= cumulative[2, 2]
        corners = np.float32([[[w*.2, h*.2], [w*.8, h*.2], [w*.8, h*.8], [w*.2, h*.8]]])
        projected = cv2.perspectiveTransform(corners, cumulative)[0]
        if not np.isfinite(projected).all() or not cv2.isContourConvex(projected):
            return None
        area = abs(cv2.contourArea(projected)) / (w * h * .36)
        if not 0.25 < area < 4 or np.max(np.abs(projected)) > max(w, h) * 3:
            return None
        top = projected[1] - projected[0]
        bottom = projected[2] - projected[3]
        right = np.linalg.norm(projected[2] - projected[1])
        left = np.linalg.norm(projected[3] - projected[0])
        tw, bw = np.linalg.norm(top), np.linalg.norm(bottom)
        angle = math.atan2((top + bottom)[1], (top + bottom)[0])
        self.transform = cumulative
        return {"R0": float(np.clip(.5 + (right-left) / max(right+left, 1) * 2, 0, 1)),
                "R1": float(np.clip(.5 + angle / math.pi, 0, 1)),
                "R2": float(np.clip(.5 + (tw-bw) / max(tw+bw, 1) * 2, 0, 1))}
