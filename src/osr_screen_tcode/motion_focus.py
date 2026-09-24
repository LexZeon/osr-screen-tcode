"""Prefer sustained reciprocal regions over texture count or a single spike.

Only validated, camera-compensated candidates enter here. This is motion
selection, not anatomical recognition; it never manufactures observations.
"""
from dataclasses import dataclass, field
from collections import deque

import numpy as np

from .dominant_motion import _StrokeEvidence


def overlap(first, second):
    a, b = np.asarray(first), np.asarray(second)
    area = np.prod(np.maximum(0., np.minimum(a[2:], b[2:])-np.maximum(a[:2], b[:2])))
    union = np.prod(a[2:]-a[:2])+np.prod(b[2:]-b[:2])-area
    return float(area/max(1., union))


@dataclass
class _Region:
    box: tuple
    stamp: float
    value: np.ndarray = field(default_factory=lambda: np.zeros(3))
    evidence: list = field(default_factory=lambda: [_StrokeEvidence() for _ in range(3)])
    strength: float = 0.
    reciprocal: bool = False
    had_reciprocal: bool = False
    amplitude: float = 0.
    history: deque = field(default_factory=lambda: deque(maxlen=90))

    @property
    def priority(self):
        return 2 if self.reciprocal else 1 if self.had_reciprocal else 0

    @property
    def score(self):
        return self.strength if self.reciprocal else self.amplitude


class MotionFocus:
    def __init__(self):
        self.regions = []
        self.selected = None
        self.challenger = None
        self.since = None
        self.changed = False

    def status(self, stamp):
        region = self.selected
        if region is None:
            return ''
        if region.reciprocal and any(e.span is not None and stamp-e.extreme_time < .6
                                     for e in region.evidence):
            return 'reciprocal'
        return 'previous' if region.had_reciprocal else 'amplitude'

    def choose(self, candidates, stamp, preferred=0, anchor=None):
        """Candidates are (previous box, current box, measured XYZ step).

        Match against previous endpoints, so a moving target carries its
        history with it. Each history receives at most one update per frame.
        """
        self.changed = False
        self.regions = [r for r in self.regions if stamp-r.stamp <= .45]
        if not candidates:
            return None
        matches = sorted(((overlap(c[0], r.box), i, j)
                          for i, c in enumerate(candidates) for j, r in enumerate(self.regions)), reverse=True)
        assigned, used = {}, set()
        if anchor is not None and self.selected is not None:
            for j, region in enumerate(self.regions):
                if region is self.selected and overlap(candidates[anchor][0], region.box) >= .3:
                    assigned[anchor] = region
                    used.add(j)
                    break
        for score, i, j in matches:
            if score < .3:
                break
            if i not in assigned and j not in used:
                assigned[i] = self.regions[j]
                used.add(j)
        current = None
        records = []
        for i, (before, after, delta) in enumerate(candidates):
            region = assigned.get(i)
            if region is None:
                region = _Region(tuple(after), stamp)
                self.regions.append(region)
            region.value += delta
            region.strength = sum(e.update(v, stamp) for e, v in zip(region.evidence, region.value))
            region.reciprocal = region.strength > .8 and any(
                e.span is not None and stamp-e.extreme_time < .6 for e in region.evidence)
            region.had_reciprocal |= region.reciprocal
            region.history.append((stamp, region.value.copy()))
            while region.history and stamp-region.history[0][0] > .45:
                region.history.popleft()
            region.amplitude = 0.
            if len(region.history) >= 3 and stamp-region.history[0][0] >= .15:
                values = np.array([v for _, v in region.history])
                travel = np.linalg.norm(np.diff(values, axis=0), axis=1).sum()
                progress = np.linalg.norm(values[-1]-values[0])
                if progress >= .6*travel:
                    region.amplitude = float(progress)
            region.box, region.stamp = tuple(after), stamp
            records.append(region)
            if region is self.selected:
                current = i
        # The existing geometry chooses startup/reacquisition, not saliency
        # from an isolated fast movement. A stronger region must win steadily.
        if current is None:
            current = anchor if anchor is not None else max(
                range(len(records)), key=lambda i: (records[i].priority, records[i].score))
            if records[current].priority == 0 and records[current].score < .2:
                current = preferred
            self.selected = records[current]
            self.challenger = self.since = None
        winner = max(range(len(records)), key=lambda i: (records[i].priority, records[i].score))
        candidate = records[winner]
        better = (candidate.priority > self.selected.priority or
                  (candidate.priority == self.selected.priority and candidate.priority != 1
                   and candidate.score > max(.3, self.selected.score*1.5)))
        if winner != current and better:
            if self.challenger is not candidate:
                self.challenger, self.since = candidate, stamp
            elif stamp-self.since >= .3:
                self.selected, current, self.changed = candidate, winner, True
                self.challenger = self.since = None
        else:
            self.challenger = self.since = None
        # Bound stale competing regions independently of capture duration.
        self.regions = sorted(self.regions, key=lambda r: r.stamp, reverse=True)[:64]
        return current
