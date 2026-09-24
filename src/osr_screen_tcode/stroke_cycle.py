"""Discrete half/full cosine strokes driven by the shared v2 evidence.

Image excursions are percentages of image size, not physical depth. There is
no oscillator output without recent motion and confirmed reciprocal evidence.
"""
import math
import numpy as np


class StrokeCycle:
    FULL_SPAN = 8.0
    HALF_SPAN = 6.0  # hysteresis when returning from full travel
    QUARTER_TO_HALF = 3.0
    HALF_TO_QUARTER = 2.4
    MIN_SPAN = .85
    MIN_SPEED = 1.2  # image percentage points per second along the main axis

    def __init__(self, value=.5):
        self.value = value
        self.state = "stopped"
        self.period = 1.5
        self.peak = .25
        self.timestamp = None
        self.last_motion = None
        self.last_beat = None
        self.phase = 0.
        self.start = value
        self.target = 0.
        self.reference_time = None
        self.reference_offset = 0.
        self.reference_peak = None
        self.was_predicted = False
        self.applied = None
        self.prediction_ended = False

    def follow_phase(self, phase, stamp, *, held=False, predicted=False, entering=False):
        """Fusion keeps discrete travel and cosine easing with observed phase."""
        if held and self.prediction_ended:
            return self.value
        self.prediction_ended = held
        dt = 0. if self.reference_time is None else max(0., stamp-self.reference_time)
        self.reference_time = stamp
        target = self.peak*(.5-.5*math.cos(math.pi*float(np.clip(phase, 0, 1))))
        change = entering or self.reference_peak != self.peak or predicted != self.was_predicted
        if change:
            anchor = self.applied if predicted and self.applied is not None else self.value
            self.reference_offset = anchor-target
        else:
            self.reference_offset *= math.exp(-min(dt, .1)/.2)
        self.reference_peak, self.was_predicted = self.peak, predicted
        desired = float(np.clip(target+self.reference_offset, 0, 1))
        rate = max(3., 1.4*math.pi/max(.5, self.period))
        self.value += float(np.clip(desired-self.value, -rate*dt, rate*dt))
        if held:
            # Once stopped, keep the exact terminal value (including offset).
            self.reference_offset = self.value-target
            self.state = 'stopped'
        return self.value

    def hold(self, stamp):
        # Brief missing measurements freeze the output and cycle phase.
        self.timestamp = stamp
        return self.value

    def update(self, dominant, reference, stamp, valid):
        dt = 0 if self.timestamp is None else max(0, stamp-self.timestamp)
        self.timestamp = stamp
        if dt > .5 or not valid:
            self.state = "stopped"
            self.last_motion = None
            return self.value
        # Use source time and the actual 3D line. A per-frame/cardinal gate
        # misses small diagonal strokes and stops working at higher FPS.
        step = np.asarray(reference.step)[[1, 2, 0]]
        measured_dt = reference.motion_dt or dt
        if measured_dt > 0 and abs(dominant.basis[0] @ step)/measured_dt > self.MIN_SPEED:
            self.last_motion = stamp
        evidence = dominant.stroke_evidence
        span = evidence.span
        beats = [t for t, leg in evidence.legs]
        if len(beats) >= 2 and beats[-1] != self.last_beat:
            measured = float(np.clip(2*np.median(np.diff(beats[-5:])), .5, 6.))
            # Gradual cadence adaptation, never an abrupt phase jump.
            change = float(np.clip(measured-self.period, -.2*self.period, .2*self.period))
            self.period += .5*change
            self.last_beat = beats[-1]
        recent = self.last_motion is not None and stamp-self.last_motion <= max(.4, min(.8, self.period*.4))
        if not recent or span is None or span < self.MIN_SPAN:
            self.state = "stopped"
            return self.value
        if span >= self.FULL_SPAN:
            self.peak = 1.
        elif self.peak == 1. and span < self.HALF_SPAN:
            self.peak = .5
        if span < self.HALF_TO_QUARTER:
            self.peak = .25
        elif self.peak == .25 and span >= self.QUARTER_TO_HALF:
            self.peak = .5
        if self.state == "stopped":
            # Re-enter from the held position with a cosine approach to the
            # bottom, rather than snapping to the start of a generated cycle.
            self.start, self.target, self.phase = self.value, 0., 0.
        self.state = "full" if self.peak == 1. else "half" if self.peak == .5 else "quarter"
        self.phase += dt/max(.25, self.period/2)
        if self.phase >= 1:
            self.value = self.target
            self.start = self.value
            self.target = self.peak if self.target == 0 else 0.
            self.phase = 0.
        else:
            blend = .5-.5*math.cos(math.pi*self.phase)
            self.value = self.start+(self.target-self.start)*blend
        return self.value
