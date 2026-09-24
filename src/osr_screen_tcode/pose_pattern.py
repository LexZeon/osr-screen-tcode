"""Small repeated Pose strokes: evidence before user gains, output-only expansion."""
from collections import deque
import math
from statistics import median


class AxisPattern:
    MIN_SPAN = .016
    MAX_SPAN = .20
    PROMINENCE = .006
    MAX_GAIN = 2.

    def __init__(self):
        self.samples = deque(maxlen=3)
        self.extrema = deque(maxlen=7)
        self.direction = 0
        self.extreme = None
        self.stamp = None
        self.gain = 1.
        self.center = .5
        self.span = 0.
        self.half_period = .5
        self.active = False

    def _release(self):
        self.active = False
        self.extrema.clear()

    def update(self, value, stamp):
        if not math.isfinite(stamp) or (self.stamp is not None and stamp <= self.stamp):
            return
        dt = 0. if self.stamp is None else stamp-self.stamp
        if dt > .5:
            self.__init__()
            dt = 0.
        self.stamp = stamp
        valid = value is not None and math.isfinite(value)
        if valid:
            self.samples.append(value)
            value = median(self.samples)
            if self.extreme is None:
                self.extreme = (stamp, value)
            _, previous = self.extreme
            delta = value-previous
            sign = 1 if delta > 0 else -1
            if self.direction == 0:
                if abs(delta) >= self.PROMINENCE:
                    self.direction = sign
                    self.extrema.append(self.extreme)
                    self.extreme = (stamp, value)
            elif delta*self.direction >= 0:
                self.extreme = (stamp, value)
            elif abs(delta) >= self.PROMINENCE:
                self.extrema.append(self.extreme)
                self.extreme = (stamp, value)
                self.direction = sign
                self._confirm()
            if self.active and (abs(value-self.center) > self.span*.75
                                or stamp-self.extrema[-1][0] > max(.5, self.half_period*1.8)):
                # Growing real motion must not inherit the small-stroke gain.
                self._release()
        else:
            self.samples.clear()
            self.direction = 0
            self.extreme = None
            self._release()
        target = self.MAX_GAIN if self.active else 1.
        # One second from 1× to 2×; release in at most a quarter second.
        step = dt*(1. if target > self.gain else 4.)
        self.gain += max(-step, min(step, target-self.gain))

    def _confirm(self):
        if len(self.extrema) < 7:
            return
        values = list(self.extrema)
        periods = [b[0]-a[0] for a, b in zip(values, values[1:])]
        spans = [abs(b[1]-a[1]) for a, b in zip(values, values[1:])]
        typical_span, typical_period = median(spans), median(periods)
        regular = (.16 <= min(periods) <= max(periods) <= 2.
                   and max(periods) <= min(periods)*1.7
                   and self.MIN_SPAN <= min(spans) <= max(spans) <= self.MAX_SPAN
                   and max(spans) <= min(spans)*1.7)
        if not regular or (self.active and max(spans) > self.span*1.5):
            if self.active:
                self._release()
        elif not self.active:
            self.active = True
            self.span = typical_span
            self.half_period = typical_period
            self.center = median([(a[1]+b[1])*.5 for a, b in zip(values, values[1:])])

    def apply(self, value):
        if self.gain == 1.:
            return value
        return max(0., min(1., self.center+(value-self.center)*self.gain))


class PosePattern:
    def __init__(self):
        self.axes = {axis: AxisPattern() for axis in ('L0', 'R0', 'R1')}

    def update(self, positions, stamp, excluded=()):
        for axis, detector in self.axes.items():
            # Excluded generated axes never seed the detector or keep old gain.
            if axis in excluded:
                self.axes[axis] = AxisPattern()
            else:
                detector.update(positions.get(axis), stamp)

    def apply(self, positions, excluded=()):
        return {axis: self.axes[axis].apply(value) if axis in self.axes and axis not in excluded else value
                for axis, value in positions.items()}

    @property
    def gains(self):
        return tuple((axis, detector.gain) for axis, detector in self.axes.items() if detector.gain > 1.005)
