"""Keep meaningful secondary motion and reject brief direction reversals."""
import math


class SecondaryMotionFilter:
    AXES = ("L1", "L2", "R0", "R1", "R2")

    def __init__(self, initial=None):
        self.output = {a: float((initial or {}).get(a, .5)) for a in self.AXES}
        self.target = dict(self.output)
        self.direction = dict.fromkeys(self.AXES, 0)
        self.candidate = dict.fromkeys(self.AXES, 0)
        self.since = dict.fromkeys(self.AXES, 0.0)
        self.timestamp = None

    def update(self, positions, timestamp):
        if not math.isfinite(timestamp) or (self.timestamp is not None and timestamp <= self.timestamp):
            return dict(self.output)
        elapsed = 1/30 if self.timestamp is None else timestamp - self.timestamp
        if elapsed > .5:
            self.__init__(self.output)
            elapsed = 1/30
        self.timestamp = timestamp
        dt = min(elapsed, .1)
        alpha = -math.expm1(-dt / .16)
        for axis in self.AXES:
            value = float(positions.get(axis, self.target[axis]))
            if not math.isfinite(value):
                continue
            value = min(1.0, max(0.0, value))
            delta = value - self.target[axis]
            sign = 1 if delta > 0 else -1
            reversing = bool(self.direction[axis] and sign != self.direction[axis])
            threshold = .035 if reversing else .025
            if abs(delta) < threshold:
                self.candidate[axis] = 0
            elif sign == self.direction[axis]:
                self.target[axis] = value
                self.candidate[axis] = 0
            else:
                if self.candidate[axis] != sign:
                    self.candidate[axis], self.since[axis] = sign, timestamp
                elif timestamp - self.since[axis] >= .12:
                    self.target[axis], self.direction[axis] = value, sign
                    self.candidate[axis] = 0
            step = (self.target[axis] - self.output[axis]) * alpha
            self.output[axis] += min(.65 * dt, max(-.65 * dt, step))
        return dict(self.output)
