"""Short output-only continuation learned exclusively from observed motion."""
from collections import deque
import math

import numpy as np

from .dominant_motion import _StrokeEvidence


class MotionRhythm:
    LIMIT = 2.0
    BRAKE = .5
    HISTORY = 15.0
    BRIDGE = .3
    BRIDGE_TRAVEL = .15

    def __init__(self):
        self.samples = deque(maxlen=2000)
        self.velocity_samples = deque(maxlen=64)
        self.velocity = None
        self.model = None
        self.fitted_at = -math.inf
        self.last_observed = None
        self.loss_at = None
        self.phase = 0.
        self.offset = 0.
        self.state = ''
        self.elapsed = 0.
        self.kind = ''
        self.recovery_started = None
        self.recovery_count = 0
        self.recovery_last = None
        self._loss_model = None
        self._loss_velocity = None
        self._anchor = None
        self._anchor_elapsed = 0.

    def clear(self, *, preserve_episode=False):
        loss_at, elapsed = self.loss_at, self.elapsed
        self.__init__()
        if preserve_episode:
            self.loss_at, self.elapsed = loss_at, elapsed

    def observe(self, stamp, value, *, periodic=True):
        # Never pass generated targets, user gains or device positions here.
        if (not math.isfinite(stamp) or not math.isfinite(value) or not 0 <= value <= 1
                or (self.last_observed is not None and stamp <= self.last_observed)):
            return
        if self.last_observed is not None and stamp-self.last_observed > .3:
            self.samples.clear()
            self.model = None
            self.velocity_samples.clear()
            self.velocity = None
        # A single good frame inside a dropout must not renew its two seconds.
        # begin_loss interrupts this sequence whenever evidence disappears.
        if self.loss_at is not None:
            # A real reappearance can move the applied output. If it vanishes
            # again, start from that value without renewing the old deadline.
            self._anchor = None
            if self.recovery_last is None or stamp-self.recovery_last > .25:
                self.recovery_started, self.recovery_count = stamp, 0
            self.recovery_last = stamp
            self.recovery_count += 1
            if self.recovery_count >= 3 and stamp-self.recovery_started >= .2-1e-9:
                self.loss_at = None
                self.elapsed = 0.
                self._loss_model = self._loss_velocity = self._anchor = None
                self.kind = ''
        self.last_observed = stamp
        if self.loss_at is None:
            self.state = ''
        self.velocity_samples.append((stamp, float(value)))
        while self.velocity_samples and self.velocity_samples[0][0] < stamp-.25:
            self.velocity_samples.popleft()
        self._fit_velocity()
        if not periodic:
            self.samples.clear()
            self.model = None
            return
        self.samples.append((stamp, float(value)))
        while self.samples and self.samples[0][0] < stamp-self.HISTORY:
            self.samples.popleft()
        if stamp-self.fitted_at < .15 or len(self.samples) < 24:
            return
        self.fitted_at = stamp
        times, values = np.asarray(self.samples).T
        # The shared detector normally keeps only three seconds, too short to
        # contain four turns of the slow periods this estimator supports.
        evidence = _StrokeEvidence(excursion=.08)
        evidence.WINDOW_SECONDS = self.HISTORY
        for index, (value, observed_at) in enumerate(zip(values, times)):
            evidence.update(float(value), float(observed_at), summarize=index == len(times)-1)
        beats = np.array([t for t, _ in evidence.legs])
        if len(beats) < 4 or evidence.span is None:
            self.model = None
            return
        intervals = np.diff(beats[-7:])
        period = float(2*np.median(intervals))
        if not .5 <= period <= 6. or np.std(intervals)/np.mean(intervals) > .22:
            self.model = None
            return
        selected = times >= stamp-min(self.HISTORY, period*2.5)
        times, values = times[selected]-stamp, values[selected]
        if len(times) < 24 or np.ptp(times) < period*1.7:
            self.model = None
            return
        best = None
        for trial in np.linspace(max(.5, period*.9), min(6., period*1.1), 21):
            omega = 2*math.pi/trial
            design = np.column_stack((np.ones(len(times)), np.cos(times*omega), np.sin(times*omega)))
            coeff = np.linalg.lstsq(design, values, rcond=None)[0]
            error = float(np.mean((design @ coeff-values)**2))
            if best is None or error < best[0]:
                best = (error, trial, coeff)
        error, period, (middle, cosine, sine) = best
        amplitude = float(math.hypot(cosine, sine))
        if amplitude < .04 or math.sqrt(error) > amplitude*.23:
            self.model = None
            return
        amplitude = min(amplitude, middle, 1-middle)
        if amplitude < .04:
            self.model = None
            return
        # cos(w*t+phase), expressed at this observed timestamp.
        self.model = (stamp, float(period), float(middle), amplitude, math.atan2(-sine, cosine))

    def _fit_velocity(self):
        self.velocity = None
        if len(self.velocity_samples) < 4:
            return
        times, values = np.asarray(self.velocity_samples).T
        if times[-1]-times[0] < .08:
            return
        delta = np.diff(values)
        distance = float(np.sum(np.abs(delta)))
        if distance < .004 or abs(values[-1]-values[0]) < .8*distance:
            return
        speeds = delta/np.diff(times)
        velocity = float(np.median(speeds))
        if (abs(velocity) < .04 or np.mean(speeds*velocity > 0) < .8
                or np.median(np.abs(speeds-velocity)) > max(.015, abs(velocity)*.35)):
            return
        self.velocity = float(np.clip(velocity, -2., 2.))

    def begin_loss(self, stamp):
        """Start or advance one budget, shared by weak pixels and extrapolation."""
        self.recovery_started = self.recovery_last = None
        self.recovery_count = 0
        if self.loss_at is None:
            if self.last_observed is None or not 0 <= stamp-self.last_observed <= .3:
                return False
            self.loss_at = self.last_observed
            self._loss_model = (self.model if self.model is not None
                                and self.last_observed-self.model[0] <= .35 else None)
            self._loss_velocity = self.velocity
            self._anchor = None
            self.kind = ''
        self.elapsed = max(0., stamp-self.loss_at)
        return True

    def brake_gain(self):
        if self.elapsed >= self.LIMIT:
            return 0.
        return (1. if self.elapsed <= self.LIMIT-self.BRAKE else
                .5+.5*math.cos(math.pi*(self.elapsed-(self.LIMIT-self.BRAKE))/self.BRAKE))

    def mark_weak(self):
        self.kind = 'weak'
        self._anchor = None
        self.state = ('continuing' if self.elapsed < self.LIMIT-self.BRAKE else
                      'braking' if self.elapsed < self.LIMIT else 'held')

    @classmethod
    def travel_time(cls, elapsed):
        elapsed = float(np.clip(elapsed, 0, cls.LIMIT))
        start = cls.LIMIT-cls.BRAKE
        if elapsed <= start:
            return elapsed
        t = elapsed-start
        return start+t/2+cls.BRAKE/(2*math.pi)*math.sin(math.pi*t/cls.BRAKE)

    def predict(self, stamp, held):
        if not self.begin_loss(stamp):
            self.state = ''
            return None
        if self._loss_model is None:
            return self._predict_velocity(held)
        fitted, period, middle, amplitude, phase = self._loss_model
        if self.kind != 'rhythm' or self._anchor is None:
            self._anchor_elapsed = self.elapsed if self.kind else 0.
            expected = phase+2*math.pi*(self.loss_at+self._anchor_elapsed-fitted)/period
            angle = math.acos(float(np.clip((held-middle)/amplitude, -1, 1)))
            self.phase = angle if math.sin(expected) >= 0 else -angle
            self.offset = held-(middle+amplitude*math.cos(self.phase))
            self._anchor = held
        self.kind = 'rhythm'
        self.state = 'continuing' if self.elapsed < self.LIMIT-self.BRAKE else 'braking' if self.elapsed < self.LIMIT else 'held'
        elapsed = max(0., self.travel_time(self.elapsed)-self.travel_time(self._anchor_elapsed))
        phase = self.phase+2*math.pi*elapsed/period
        # A held value outside the fitted range enters continuously.
        value = middle+amplitude*math.cos(phase)+self.offset*math.exp(-elapsed/.25)
        return float(np.clip(value, 0, 1))

    def _predict_velocity(self, held):
        velocity = self._loss_velocity
        if velocity is None:
            self.state = 'held' if self.kind else ''
            return None
        horizon = min(self.BRIDGE, 2*self.BRIDGE_TRAVEL/abs(velocity))
        if self.kind != 'velocity' or self._anchor is None:
            self._anchor_elapsed = self.elapsed if self.kind else 0.
            self._anchor = held
        self.kind = 'velocity'

        def distance(elapsed):
            t = float(np.clip(elapsed, 0, horizon))
            return velocity*(t/2+horizon/(2*math.pi)*math.sin(math.pi*t/horizon))

        self.state = 'braking' if self.elapsed < horizon else 'held'
        return float(np.clip(self._anchor+distance(self.elapsed)-distance(self._anchor_elapsed), 0, 1))
