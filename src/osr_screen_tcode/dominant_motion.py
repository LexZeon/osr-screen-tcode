"""A continuous local motion frame in up/scale/right image-proxy space."""
from collections import deque
import math

import numpy as np


class _StrokeEvidence:
    """Count substantial, sustained legs in both directions, not frame jitter.

    Units are percentage points of the image (scale is only an image proxy).
    A pan/zoom in one direction supplies no reciprocal-motion evidence.
    """
    EXCURSION = 0.75
    LEG_SECONDS = 0.16
    WINDOW_SECONDS = 3.0

    def __init__(self, excursion=EXCURSION):
        self.excursion = excursion
        self.anchor = self.extreme = None
        self.low = self.high = None
        self.previous = None
        self.distance = self.anchor_distance = self.extreme_distance = 0.
        self.started = self.extreme_time = 0.0
        self.direction = 0
        self.legs = deque()
        self.span = None

    def update(self, value, stamp, summarize=True):
        if self.previous is not None:
            self.distance += abs(value-self.previous)
        self.previous = value
        if self.anchor is None:
            self.anchor = self.extreme = value
            self.started = self.extreme_time = stamp
            self.low = self.high = (value, stamp, self.distance)
            return 0.0
        if not self.direction:
            # The first sample can be anywhere within a small stroke. Start
            # from an observed extreme, not forever from that initial point.
            if value < self.low[0]:
                self.low = (value, stamp, self.distance)
            if value > self.high[0]:
                self.high = (value, stamp, self.distance)
            if value-self.low[0] >= self.excursion:
                self.anchor, self.started, self.anchor_distance = self.low
                self.direction = 1
            elif self.high[0]-value >= self.excursion:
                self.anchor, self.started, self.anchor_distance = self.high
                self.direction = -1
            if self.direction:
                self.extreme, self.extreme_time = value, stamp
                self.extreme_distance = self.distance
        elif (value - self.extreme) * self.direction > 0:
            self.extreme, self.extreme_time = value, stamp
            self.extreme_distance = self.distance
        elif (self.extreme - value) * self.direction >= self.excursion:
            if self._sustained_leg():
                self.legs.append((self.extreme_time, self.extreme - self.anchor))
            self.anchor, self.started = self.extreme, self.extreme_time
            self.anchor_distance = self.extreme_distance
            self.direction *= -1
            self.extreme, self.extreme_time = value, stamp
            self.extreme_distance = self.distance
        while self.legs and stamp - self.legs[0][0] > self.WINDOW_SECONDS:
            self.legs.popleft()
        if not summarize:
            return 0.0
        distances = [leg for _, leg in self.legs]
        if (stamp - self.extreme_time <= self.WINDOW_SECONDS
                and self._sustained_leg()
                and abs(self.extreme - self.anchor) >= self.excursion):
            distances.append(self.extreme - self.anchor)
        positive = sum(max(0, leg) for leg in distances)
        negative = sum(max(0, -leg) for leg in distances)
        self.span = float(np.median(np.abs(distances))) if positive > 0 and negative > 0 else None
        return 2 * min(positive, negative) / self.WINDOW_SECONDS

    def _sustained_leg(self):
        # Skipping small jitter reversals must not turn their elapsed time
        # into one long valid leg. Require mostly forward progress to its end.
        travel = self.extreme_distance-self.anchor_distance
        return (self.extreme_time-self.started >= self.LEG_SECONDS
                and abs(self.extreme-self.anchor) >= .6*travel)

    @classmethod
    def measure(cls, values, stamps, excursion=EXCURSION):
        evidence = cls(excursion)
        strength = 0.
        for index, (value, stamp) in enumerate(zip(values, stamps)):
            strength = evidence.update(float(value), float(stamp), summarize=index == len(values)-1)
        return evidence, strength


class DominantMotion:
    # Rows are L0/L1/L2 in up/scale/right coordinates. The frame is orthonormal
    # and right-handed; scale is an image measurement, never physical depth.

    def __init__(self, adaptive_l0=False):
        self.adaptive_l0 = adaptive_l0
        self.previous = np.zeros(3)
        self.timestamp = None
        self.energy = np.zeros(3)
        self.filtered = np.zeros(3)
        self.evidence = [_StrokeEvidence() for _ in range(3)]
        self.scores = np.zeros(3)
        self.weights = np.array([1.0, 0.0, 0.0])
        self.primary = 0
        self.challenger = None
        self.challenger_since = None
        self.basis = np.eye(3)
        self.history = deque(maxlen=720)
        self.basis_state = 'learning'
        self.basis_confidence = 0.
        self.stroke_evidence = _StrokeEvidence()
        self.rotation_previous = None
        self.rotation_mapped = np.zeros(3)
        self.mapped = np.zeros(3)
        self.stroke_gain = 1.0
        self.stroke_span = None

    def hold(self, timestamp):
        """Advance time without adding a measurement or deleting stroke history."""
        if self.timestamp is not None and math.isfinite(timestamp) and timestamp > self.timestamp:
            self.timestamp = timestamp
            self.basis_state = 'holding'

    @property
    def axes_xyz(self):
        """Immutable directions for the preview, ordered right/up/scale."""
        return tuple(tuple(float(v) for v in axis[[2, 0, 1]]) for axis in self.basis)

    def _turn_basis(self, target, dt):
        old = self.basis[0]
        dot = float(np.clip(old @ target, -1., 1.))
        # Eigenvectors describe a line: opposite signs are the same axis.
        # Keep the positive end stable across reversals and eigensolver signs.
        if abs(dot) < 1e-8:
            target = target if target[np.argmax(abs(target))] >= 0 else -target
        elif dot < 0:
            target = -target
        cross = np.cross(old, target)
        length = np.linalg.norm(cross)
        if length < 1e-10:
            return
        angle = math.atan2(length, float(old @ target))
        angle = min(angle*(-math.expm1(-dt/.35)), math.radians(120)*dt)
        x, y, z = cross/length
        skew = np.array(((0, -z, y), (z, 0, -x), (-y, x, 0)))
        rotation = np.eye(3)+math.sin(angle)*skew+(1-math.cos(angle))*(skew @ skew)
        # Transport both transverse axes together instead of reselecting their
        # PCA vectors (ambiguous signs/ordering would cause independent flips).
        self.basis = self.basis @ rotation.T

    def _update_basis(self, timestamp, dt):
        samples = np.array([sample for _, sample in self.history])
        stamps = np.array([t for t, _ in self.history])
        self.basis_state = 'holding' if self.basis_state != 'learning' else 'learning'
        self.basis_confidence = 0.
        if len(samples) >= 5 and stamps[-1]-stamps[0] >= .3:
            # Components establish sustained reversals relative to their own
            # range. Apply the absolute excursion gate to the combined line
            # below: a small signed component must not be clipped off a real
            # oblique stroke just because it is below a cardinal threshold.
            allowed = np.zeros(3, dtype=bool)
            for axis, span in enumerate(np.ptp(samples, axis=0)):
                if span > 1e-6:
                    evidence, _ = _StrokeEvidence.measure(samples[:, axis], stamps,
                                                         min(.75, span*.25))
                    allowed[axis] = evidence.span is not None
            intervals = np.diff(stamps)
            velocity = np.diff(samples, axis=0)/intervals[:, None]
            velocity -= np.average(velocity, axis=0, weights=intervals)
            # One-way drift has no reciprocal evidence and cannot tilt the
            # fitted axis. Cross terms retain signed diagonal/oblique motion.
            velocity *= allowed
            covariance = (velocity.T*intervals) @ velocity/intervals.sum()
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            strength = float(eigenvalues[-1])
            distinct = strength > max(.05, float(eigenvalues[-2])*1.4)
            if distinct:
                target = eigenvectors[:, -1]
                candidate, reciprocal = _StrokeEvidence.measure(samples @ target, stamps)
                distinct = candidate.span is not None and reciprocal > .3
            if distinct:
                self.basis_confidence = float((strength-eigenvalues[-2])/max(strength, 1e-9))
                if self.challenger is None or abs(target @ self.challenger) < math.cos(math.radians(20)):
                    self.challenger, self.challenger_since = target.copy(), timestamp
                if timestamp-self.challenger_since >= .3:
                    self._turn_basis(target, dt)
                    self.basis_state = 'tracking'
            else:
                self.challenger = self.challenger_since = None
        else:
            self.challenger = self.challenger_since = None
        self.weights = abs(self.basis[0])/sum(abs(self.basis[0]))
        self.primary = int(np.argmax(self.weights))  # diagnostic only, never routing
        # Measure amplitude/rhythm along the actual 3D line, not whichever
        # screen component happens to be the largest. Cycle mode shares this.
        self.stroke_evidence, strength = _StrokeEvidence.measure(samples @ self.basis[0], stamps)
        self.stroke_span = self.stroke_evidence.span
        return strength

    def map_rotations(self, positions):
        """Express subsequent rotation-proxy changes in the same local frame.

        Default R0/R1/R2 correspond to up/scale/right. These remain heuristic
        signals, not Euler angles or reconstructed physical orientation.
        """
        if positions is None or not all(a in positions for a in ('R0', 'R1', 'R2')):
            return None
        current = np.array([positions[a]-.5 for a in ('R0', 'R1', 'R2')])
        if not np.isfinite(current).all():
            return None
        if self.rotation_previous is not None:
            self.rotation_mapped = np.clip(self.rotation_mapped+self.basis @ (current-self.rotation_previous), -.5, .5)
        self.rotation_previous = current
        return {a: float(.5+v) for a, v in zip(('R0', 'R1', 'R2'), self.rotation_mapped)}

    def update(self, values, timestamp):
        x, y, scale = values
        current = np.asarray((y, scale, x), dtype=float)
        if not np.isfinite(current).all() or not math.isfinite(timestamp):
            return None
        if self.timestamp is not None and timestamp <= self.timestamp:
            return None
        dt = 1 / 30 if self.timestamp is None else timestamp - self.timestamp
        if dt > 0.5:
            self.__init__(self.adaptive_l0)
            dt = 1 / 30
        # CameraRelativeMotion already zeroes its reference on calibration;
        # its first valid value includes a real step which must be preserved.
        delta = current - self.previous
        speed = np.abs(delta) / max(dt, 1e-3)
        if self.timestamp is None:
            self.filtered = current.copy()
        else:
            self.filtered += (current - self.filtered) * (-math.expm1(-dt / 0.06))
        self.previous, self.timestamp = current, timestamp
        self.energy += (speed - self.energy) * (-math.expm1(-dt / 0.4))
        self.history.append((timestamp, self.filtered.copy()))
        while len(self.history) > 2 and self.history[0][0] < timestamp-3.:
            self.history.popleft()
        reciprocal = np.array([item.update(value, timestamp)
                               for item, value in zip(self.evidence, self.filtered)])
        self.scores += (reciprocal - self.scores) * (-math.expm1(-dt / 0.3))
        strength = self._update_basis(timestamp, dt)
        # Blend new motion, not accumulated offsets. Reassigning a direction
        # must never turn an old pan/zoom into an artificial output stroke.
        movement = self.basis @ delta
        if self.adaptive_l0:
            # Calibrate only from substantial legs in BOTH directions, after
            # camera compensation. A small but real image stroke should not
            # automatically mean a tiny script. Output presets remain separate.
            gain = (float(np.clip(75 / self.stroke_span, 1, 40))
                    if self.stroke_span is not None and strength > .3 else 1.0)
            self.stroke_gain += (gain-self.stroke_gain) * (-math.expm1(-dt/.4))
            movement[0] = np.clip(movement[0]*self.stroke_gain, -300*dt, 300*dt)
        self.mapped = np.clip(self.mapped + movement, -50, 50)
        return {axis: float(np.clip(0.5 + value / 100, 0, 1))
                for axis, value in zip(("L0", "L1", "L2"), self.mapped)}
