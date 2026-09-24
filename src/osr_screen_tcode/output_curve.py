"""Causal, speed-adaptive output smoothing; no future-frame buffer.

One Euro filter equations: Casiez, Roussel and Vogel, CHI 2012.
https://gery.casiez.net/publications/CHI2012-casiez.pdf
"""
import math
import time


class OutputCurveFilter:
    def __init__(self, min_cutoff: float = 1.8, beta: float = 3.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self._time: float | None = None
        self._states: dict[str, tuple[float, float, float]] = {}

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        return 1.0 / (1.0 + 1.0 / (2.0 * math.pi * cutoff * dt))

    def process(self, positions: dict[str, float], enabled: bool = True,
                timestamp: float | None = None, passthrough: tuple = ()) -> dict[str, float]:
        now = time.perf_counter() if timestamp is None else timestamp
        if not math.isfinite(now):
            raise ValueError("Invalid curve timestamp")
        dt = None if self._time is None else now - self._time
        result = {}
        for axis, value in positions.items():
            raw = float(value)
            previous = self._states.get(axis)
            if not math.isfinite(raw):
                result[axis] = previous[1] if previous else 0.5
                continue
            raw = max(0.0, min(1.0, raw))
            if axis in passthrough or not enabled or previous is None or dt is None:
                self._states[axis] = (raw, raw, 0.0)
                result[axis] = raw
                continue
            if dt <= 0:
                result[axis] = previous[1]
                continue
            # Bound a long capture stall's first resumed step, rather than extrapolating.
            step = min(0.1, dt)
            last_raw, last_filtered, last_derivative = previous
            derivative = (raw - last_raw) / step
            a_d = self._alpha(1.0, step)
            derivative = last_derivative + a_d * (derivative - last_derivative)
            cutoff = min(20.0, self.min_cutoff + self.beta * abs(derivative))
            value = last_filtered + self._alpha(cutoff, step) * (raw - last_filtered)
            self._states[axis] = (raw, value, derivative)
            result[axis] = value
        if self._time is None or now > self._time:
            self._time = now
        return result
