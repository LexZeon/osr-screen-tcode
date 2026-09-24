"""Match command travel time to observed updates, without resampling targets."""
import math
from collections import deque
from statistics import median


class CommandCadence:
    def __init__(self):
        self.previous = None
        self.intervals = deque(maxlen=5)

    def interval_ms(self, now, minimum):
        if self.previous is not None:
            dt = now-self.previous
            if .001 <= dt <= .5:
                self.intervals.append(dt*1000)
            elif dt > .5 or dt < 0:
                self.intervals.clear()
        self.previous = now
        return max(minimum, math.ceil(median(self.intervals)-1e-6)) if self.intervals else minimum
