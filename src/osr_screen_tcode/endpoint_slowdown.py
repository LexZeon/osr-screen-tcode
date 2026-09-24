"""Final-output timing only. Target positions and analysis remain unchanged."""
import math


def approach_time_factor(current, target, margin=.1):
    """Integrate travel time: 100% speed at zone entry, 25% at the limit.

    Only the part of a stroke inside the selected zone gets extra time.
    Coordinates are normalized to that axis's own output range.
    """
    current, target = (max(0., min(1., v)) for v in (current, target))
    zone = max(0., min(.5, margin))
    travel = abs(target-current)
    if zone == 0 or travel < 1e-9:
        return 1.
    distance = 1-current if target > current else current
    outside = max(0., distance-zone)
    if travel <= outside:
        return 1.
    start = min(distance, zone)
    end = max(0., distance-travel)
    duration = outside + zone/.75*math.log((start+zone/3)/(end+zone/3))
    return max(1., duration/travel)


class ScriptEndpointTiming:
    def __init__(self):
        self.positions = {}
        self.source_at = None
        self.output_at = 0.

    def timestamp(self, positions, at, enabled=True, margin=.1):
        if self.source_at is None:
            self.output_at = float(at)
        else:
            dt = max(0, at-self.source_at)
            factor = max((approach_time_factor(self.positions.get(a, v), v, margin)
                          for a, v in positions.items()), default=1.) if enabled else 1.
            self.output_at += dt*factor
        self.source_at = at
        self.positions = dict(positions)
        return round(self.output_at)
