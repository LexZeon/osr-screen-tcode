"""Align motion, stroke phase and approach evidence before combining L0."""
from collections import deque
import math

import numpy as np

from .motion_rhythm import MotionRhythm


class FusedL0:
    def __init__(self, value=.5, *, entering=False):
        self.output = float(value)
        self.raw = None
        self.timestamp = None
        self.orientation = 1.
        self.oriented = False
        self.agreement = deque(maxlen=90)
        self.weights = (1., 0., 0.)
        self.rhythm = MotionRhythm()
        self.offset = 0.
        self.key = None if entering else (False, 1.)
        self.target = None
        self.target_kind = ''
        self.predicting = False
        self.continuation_kind = ''
        self.observed_basis = None
        self.observed_step_gain = None
        self.using_point = False
        self.paused_since = None
        self.applied = None
        self.shape = None
        self.arrival_active = False
        self.arrival_transition = 0.
        self.arrival_offset = 0.
        self.arrival_blocked_until = -1e9
        self.arrival_candidate = None
        self.arrival_since = None
        self.assumed_offset = None

    def update(self, dominant, reference, point, radial_phase, center, stamp, shape, ordinary, arrival=None, estimate=None):
        dt = 0. if self.timestamp is None else max(0., stamp-self.timestamp)
        self.timestamp = stamp
        self.predicting = False
        self.continuation_kind = ''
        measured = reference.state in ('ready', 'tracking')
        shape_changed = self.shape is not None and tuple(shape) != self.shape
        self.shape = tuple(shape)
        if (dt > .5 or shape_changed or reference.reason == 'jump'
                or (reference.state == 'calibrating' and reference.roi is not None)):
            value = self.output
            entering = self.raw is not None or value != .5
            self.__init__(value, entering=entering)
            self.timestamp = stamp
            return value
        available = measured and arrival is not None and arrival.state == 'ready' and arrival.remaining is not None
        # An intermittent target must not restart the entry offset every other
        # frame and pin L0 forever. Keep following the subject while it settles.
        if not available:
            self.arrival_candidate = self.arrival_since = None
            if self.arrival_active:
                self.arrival_blocked_until = stamp+.4
        elif self.arrival_candidate != arrival.key:
            self.arrival_candidate, self.arrival_since = arrival.key, stamp
        stable = (self.arrival_blocked_until < 0 or
                  (self.arrival_since is not None and stamp >= self.arrival_blocked_until
                   and stamp-self.arrival_since >= .3))
        reaching = available and stable
        target_lost = self.arrival_active and not reaching
        paused = measured and not np.any(reference.step) and (arrival is None or abs(arrival.delta) < 1e-8)
        if reaching and (not self.arrival_active or abs(self.output-arrival.remaining) > 1e-6):
            paused = False  # finish a continuous arrival transition, including 0
        if not measured:
            self.target = None  # never draw old pixel coordinates on a new frame
            if estimate is not None and estimate.stationary:
                self.rhythm.clear()
                self.observed_basis = self.observed_step_gain = None
                self.key = None
                self.paused_since = stamp
                return self.output
            held = self.output if self.applied is None or self.rhythm.loss_at is not None else self.applied
            weak_step = getattr(estimate, 'step', None)
            weak = (estimate is not None and estimate.state == 'weak' and weak_step is not None
                    and self.observed_basis is not None and self.observed_step_gain is not None)
            step = np.asarray(weak_step, dtype=float) if weak else None
            weak = weak and step.shape == (3,) and np.isfinite(step).all()
            if weak and self.rhythm.begin_loss(stamp):
                self.rhythm.mark_weak()
                movement = float(step[[1, 2, 0]] @ self.observed_basis)
                desired = self.orientation*movement*self.observed_step_gain*self.rhythm.brake_gain()
                # A weak pixel fit cannot jump to a new phase or bypass the
                # deadline by reporting another increment every frame.
                self.output = float(np.clip(held+np.clip(desired, -2*dt, 2*dt), 0, 1))
                predicted = self.output
            else:
                predicted = self.rhythm.predict(stamp, held)
            if predicted is not None:
                self.output = predicted
                self.predicting = True
                self.continuation_kind = self.rhythm.kind
                self.key = None  # re-entry aligns from the continued target
            if arrival is not None and arrival.point is not None:
                self.target, self.target_kind = arrival.point, 'tracked_held'
            elif reference.subject_origin is not None and self.assumed_offset is not None:
                self.target = tuple(np.asarray(reference.subject_origin)+self.assumed_offset)
                self.target_kind = 'assumed_held'
            return self.output
        if paused:
            self._target(dominant, reference, point, center, shape)
            if arrival is not None and arrival.point is not None:
                self.target, self.target_kind = arrival.point, ('tracked' if reaching else
                    'tracked_confirming' if arrival.state in ('ready', 'confirming') else 'tracked_held')
            if self.paused_since is None:
                self.paused_since = stamp
            if stamp-self.paused_since >= .2:
                self.rhythm.clear()
            return self.output
        self.paused_since = None
        self.observed_basis = np.asarray(dominant.basis[0], dtype=float).copy()
        self.observed_step_gain = (1/max(.75, dominant.stroke_span) if dominant.stroke_span is not None else
                                   float(getattr(dominant, 'stroke_gain', 1.))/100)
        if reaching:
            movement = float(np.asarray(reference.step)[[1, 2, 0]] @ dominant.basis[0])
            if abs(movement) > .001 and abs(arrival.delta) > .0001:
                self.agreement.append((stamp, movement, arrival.delta))
                while self.agreement and self.agreement[0][0] < stamp-1.5:
                    self.agreement.popleft()
                if len(self.agreement) >= 8:
                    _, main, outward = np.asarray(self.agreement).T
                    product = np.linalg.norm(main)*np.linalg.norm(outward)
                    if product > 1e-8 and abs(main @ outward/product) > .75:
                        self.orientation = 1. if main @ outward >= 0 else -1.
            key = ('arrival', arrival.key)
            self.raw = float(arrival.remaining)
            if self.key != key:
                self.arrival_offset = self.output-self.raw
                self.arrival_transition = stamp
                self.key = key
                self.rhythm.clear(preserve_episode=True)
            blend = max(0., 1-(stamp-self.arrival_transition)/.3)
            desired = float(np.clip(self.raw+self.arrival_offset*blend, 0., 1.))
            beats = [t for t, _ in dominant.stroke_evidence.legs]
            period = float(2*np.median(np.diff(beats[-5:]))) if len(beats) >= 2 else 1.
            rate = max(3., 1.3*math.pi/max(.5, period))
            self.output += float(np.clip(desired-self.output, -rate*dt, rate*dt))
            self.arrival_active = True
            self.using_point = False  # cycle span remains actual source motion
            self.oriented = True
            self.weights = (0., 0., 1.)
            self.target, self.target_kind = arrival.point, 'tracked'
            if np.any(reference.step) or abs(arrival.delta) > 1e-8:
                self.rhythm.observe(stamp, self.raw)
            else:
                self.rhythm.clear()
            return self.output
        if target_lost:
            # The independently tracked target may be outside/occluded while
            # the visible object's motion is still measured. Use that observed
            # proxy from the current output; do not pretend its phase is reach.
            self.arrival_active = False
            self.key = self.raw = None
            self.rhythm.clear(preserve_episode=True)
        movement = float(np.asarray(reference.step)[[1, 2, 0]] @ dominant.basis[0])
        if point.state == 'ready' and abs(movement) > .001:
            self.agreement.append((stamp, movement, -point.step))
        while self.agreement and self.agreement[0][0] < stamp-1.5:
            self.agreement.popleft()
        coherent = False
        if len(self.agreement) >= 8 and self.agreement[-1][0]-self.agreement[0][0] >= .25:
            _, main, outward = np.asarray(self.agreement).T
            product = np.linalg.norm(main)*np.linalg.norm(outward)
            correlation = float(main @ outward/product) if product > 1e-8 else 0.
            coherent = abs(correlation) > .75
            if coherent and point.state == 'ready':
                sign = 1. if correlation >= 0 else -1.
                if sign != self.orientation:
                    self.raw = None
                    self.rhythm.clear(preserve_episode=True)
                self.orientation, self.oriented = sign, True
        phase = None if center is None else center[1]
        if phase is not None:
            phase = phase if self.orientation > 0 else 1-phase
        point_ok = point.state == 'ready' and radial_phase is not None and coherent
        self.using_point = point_ok
        # Integrate only the measured projected increment; center corrects
        # accumulated drift. Do not average oppositely signed references.
        span = dominant.stroke_span
        if phase is None or span is None:
            motion = ordinary if self.orientation > 0 else 1-ordinary
            target, weights = motion, (1., 0., 0.)
        else:
            motion = phase if self.raw is None else np.clip(self.raw+self.orientation*movement/max(.75, span), 0, 1)
            # P? mainly establishes polarity/target. Its intermittent radial
            # fit must not override a stable phase or cancel the main stroke.
            agreement = max(0., 1-abs(radial_phase-phase)/.3) if point_ok else 0.
            point_weight = .25*agreement
            weights = (.25*(1-point_weight), .75*(1-point_weight), point_weight)
            target = weights[0]*motion+weights[1]*phase
            if point_ok:
                target += point_weight*radial_phase
        self.raw = float(np.clip(target, 0, 1))
        self.weights = weights
        key = (phase is not None, self.orientation)
        if key != self.key:
            self.offset = self.output-self.raw
            self.key = key
        else:
            self.offset *= math.exp(-min(dt, .1)/.2)
        beats = [t for t, _ in dominant.stroke_evidence.legs]
        period = float(2*np.median(np.diff(beats[-5:]))) if len(beats) >= 2 else 1.
        rate = max(3., 1.3*math.pi/max(.5, period))
        desired = float(np.clip(self.raw+self.offset, 0, 1))
        self.output += float(np.clip(desired-self.output, -rate*dt, rate*dt))
        self.rhythm.observe(stamp, self.raw, periodic=phase is not None)
        self._target(dominant, reference, point, center, shape)
        if arrival is not None and arrival.point is not None:
            self.target = arrival.point
            self.target_kind = 'tracked_confirming' if arrival.state in ('ready', 'confirming') else 'tracked_held'
        return self.output

    def _target(self, dominant, reference, point, center, shape):
        self.target, self.target_kind = None, ''
        if reference.subject_origin is not None and center is not None:
            h, w = shape
            delta = -self.orientation*float(dominant.stroke_span or 0)/2*dominant.basis[0]
            self.target = tuple(np.asarray(center[0])+(delta[2]*w/100, -delta[0]*h/100))
            self.assumed_offset = np.asarray(self.target)-reference.subject_origin
            self.target_kind = 'assumed'
            return
        if self.oriented and point.state in ('ready', 'holding') and point.point is not None:
            self.target = tuple(point.point)
            self.target_kind = 'interaction' if point.state == 'ready' else 'interaction_held'
            if reference.roi is not None:
                x1, y1, x2, y2 = reference.roi
                if x1 <= point.point[0] <= x2 and y1 <= point.point[1] <= y2:
                    # A focus within the moving region may just be its own
                    # expansion center. This display distinction never gates
                    # genuine radial measurements or changes L0 polarity.
                    self.target_kind = 'expansion' if point.state == 'ready' else 'expansion_held'
        elif center is not None and reference.roi is not None:
            # The center is a phase origin, NOT a contact point. Draw one
            # near endpoint, never |position-center| (which doubles frequency).
            h, w = shape
            axis = dominant.basis[0]
            delta = -self.orientation*float(dominant.stroke_span or 0)/2*axis
            endpoint = np.array(center[0])+(delta[2]*w/100, -delta[0]*h/100)
            if np.linalg.norm(endpoint-np.asarray(center[0])) >= 3:
                self.target = tuple(endpoint)
                self.target_kind = 'endpoint' if self.oriented else 'unoriented'
