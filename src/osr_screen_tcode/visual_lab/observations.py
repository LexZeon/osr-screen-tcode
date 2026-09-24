"""Image-space measurements for the standalone viewer, not control signals."""
from collections import deque
from dataclasses import dataclass

import numpy as np

TORSO = (5, 6, 11, 12)


@dataclass(frozen=True)
class Observation:
    timestamp: float
    state: str
    values: tuple[float, float, float] | None = None
    center: tuple[float, float] | None = None


class ImageObservations:
    def __init__(self):
        self.baseline = None
        self.samples = deque(maxlen=240)
        self.last = None
        self.last_valid = None
        self.shape = None

    def update(self, points, scores, rejected, shape, timestamp):
        if not np.isfinite(timestamp):
            return Observation(timestamp, "missing")
        if self.last is not None and timestamp <= self.last.timestamp:
            return self.last
        dimensions = tuple(shape[:2])
        if self.shape != dimensions:
            self.__init__()
            self.shape = dimensions
        height, width = dimensions
        body = np.asarray(points)[list(TORSO), :2]
        confidence = np.asarray(scores)[list(TORSO)]
        valid = (np.isfinite(body).all() and np.isfinite(confidence).all()
                 and (confidence >= 0.35).all()
                 and not np.asarray(rejected)[list(TORSO)].any()
                 and (body >= 0).all() and (body[:, 0] < width).all()
                 and (body[:, 1] < height).all())
        if valid:
            # Average both visible torso side lengths, not shoulder width: this
            # reduces (but cannot eliminate) sensitivity to an in-plane turn.
            scale = float((np.linalg.norm(body[0] - body[2])
                           + np.linalg.norm(body[1] - body[3])) / 2)
            valid = scale > 8
        if not valid:
            self.samples.clear()
            self.last = Observation(timestamp, "missing")
            return self.last
        if self.last_valid is not None and timestamp - self.last_valid > 0.5:
            self.baseline = None
            self.samples.clear()
        self.last_valid = timestamp
        center = body.mean(axis=0)
        sample = (float(center[0] / width), float(center[1] / height), scale)
        if self.baseline is None:
            self.samples.append((timestamp, sample))
            if len(self.samples) >= 5 and timestamp - self.samples[0][0] >= 0.3:
                self.baseline = np.median([s for _, s in self.samples], axis=0)
            else:
                self.last = Observation(timestamp, "calibrating", center=tuple(center))
                return self.last
        x, y, size = self.baseline
        values = ((sample[0] - x) * 100, (y - sample[1]) * 100,
                  (scale / size - 1) * 100)
        self.last = Observation(timestamp, "ready", tuple(values), tuple(center))
        return self.last
