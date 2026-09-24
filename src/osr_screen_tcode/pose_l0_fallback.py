"""Pose-only generated L0 targets, separate from observations and user gains."""
import math
from collections import deque
from statistics import median

from .pose_output import rtm_l0_amplitude, rtm_rotation_amplitudes


class MotionEvidence:
    def __init__(self, threshold):
        self.threshold = threshold
        self.samples = deque(maxlen=3)
        self.anchor = None
        self.last_motion = None
        self.valid = False

    def update(self, value, stamp):
        self.valid = value is not None and math.isfinite(value)
        if not self.valid:
            self.samples.clear()
            self.anchor = None
            return
        self.samples.append(value)
        current = median(self.samples)
        if self.anchor is not None and len(self.samples) == 3 and abs(current-self.anchor) >= self.threshold:
            self.last_motion = stamp
            self.anchor = current
        elif self.anchor is None:
            self.anchor = current

    def moving(self, stamp):
        return self.valid and self.last_motion is not None and stamp-self.last_motion < .65


def rotation_l0(position):
    """Each rotation midpoint maps to one-third L0; either end to two-thirds."""
    position = max(0., min(1., position))
    return 1/3+abs(2*position-1)/3


class PoseL0Fallback:
    QUIET_SECONDS = .65
    TRANSITION_SECONDS = .2

    def __init__(self):
        self.evidence = {axis: MotionEvidence(threshold) for axis, threshold in
                         (('L0', .001), ('L1', .002), ('L2', .002), ('R0', .003), ('R1', .005), ('R2', .005))}
        self.started = self.timestamp = None
        self.source = 'waiting'
        self.output = .5
        self.generated = None
        self.holding_generated = False
        self.transition_at = None
        self.transition_from = .5
        self.wave_origin = 0.
        self.wave_phase = 0.
        self.wave_entry_from = .5
        self.wave_entry_target = .5
        self.wave_entry_at = None
        self.direction = 0.
        self.last_l0_motion = None
        self.amplitudes = {axis: deque() for axis in ('L0', 'R1', 'R2')}

    def _small_l0_rotation(self, l0, rotations, stamp):
        scaled = rtm_rotation_amplitudes(rotations)
        if l0 is not None and math.isfinite(l0):
            scaled['L0'] = rtm_l0_amplitude({'L0': l0})['L0']
        spans = {}
        for axis, history in self.amplitudes.items():
            value = scaled.get(axis)
            if value is None or not math.isfinite(value):
                history.clear()
                continue
            history.append((stamp, value))
            while history and stamp-history[0][0] > .85:
                history.popleft()
            if len(history) >= 3 and stamp-history[0][0] >= .6:
                values = sorted(v for _, v in history)
                # Trim isolated endpoints so one bad sample is not a large stroke.
                trim = max(1, len(values)//10)
                spans[axis] = values[-trim-1]-values[trim]
        l0_span = spans.get('L0')
        if l0_span is None:
            return None
        for axis in ('R1', 'R2'):
            staying = self.source == axis
            if (l0_span <= (.14 if staying else .10) and self.evidence[axis].moving(stamp)
                    and spans.get(axis, 0) >= max(.12 if staying else .16, l0_span*(1.5 if staying else 2.))):
                return axis
        return None

    def _start_wave(self, stamp):
        self.wave_entry_from = self.output
        self.wave_entry_target = max(.25, min(.5, self.output))
        self.wave_phase = math.acos(max(-1., min(1., (self.wave_entry_target-.375)/.125)))
        if self.direction > 0:
            self.wave_phase = 2*math.pi-self.wave_phase
        outside = abs(self.wave_entry_target-self.output) > 1e-9
        self.wave_entry_at = stamp if outside else None
        self.wave_origin = stamp+(.35 if outside else 0.)

    def _wave(self, stamp):
        if self.wave_entry_at is not None and stamp < self.wave_origin:
            amount = max(0., (stamp-self.wave_entry_at)/.35)
            blend = amount*amount*(3-2*amount)
            return self.wave_entry_from+(self.wave_entry_target-self.wave_entry_from)*blend
        return .375+.125*math.cos(2*math.pi*(stamp-self.wave_origin)+self.wave_phase)

    def update(self, l0, rotations, stamp, held_l0=.5, base_l0=None):
        if not math.isfinite(stamp) or (self.timestamp is not None and stamp <= self.timestamp):
            return self.generated
        if self.timestamp is not None and stamp-self.timestamp > .5:
            self.__init__()
        if self.started is None:
            self.started = self.last_l0_motion = stamp
        self.timestamp = stamp
        self.evidence['L0'].update(l0, stamp)
        for axis in ('L1', 'L2', 'R0', 'R1', 'R2'):
            self.evidence[axis].update(rotations.get(axis), stamp)
        stronger_rotation = self._small_l0_rotation(l0, rotations, stamp)
        moved_at = self.evidence['L0'].last_motion
        if moved_at is not None:
            self.last_l0_motion = max(self.last_l0_motion, moved_at)
        base = rtm_l0_amplitude({'L0': held_l0})['L0'] if base_l0 is None else base_l0
        if stamp-self.last_l0_motion < self.QUIET_SECONDS and stronger_rotation is None:
            source = 'detected' if moved_at is not None else 'waiting'
            target = base
        else:
            source = stronger_rotation or next((a for a in ('R1', 'R2') if self.evidence[a].moving(stamp)), 'wave')
            if source == 'wave' and not any(axis.moving(stamp) for axis in self.evidence.values()):
                source, target = 'idle', self.output
            elif source == 'wave':
                if self.source != 'wave':
                    self._start_wave(stamp)
                target = self._wave(stamp)
            else:
                rotation = rtm_rotation_amplitudes({source: rotations[source]})[source]
                target = rotation_l0(rotation)
        if source != self.source and (source in ('R1', 'R2', 'wave') or self.holding_generated):
            self.transition_from, self.transition_at = self.output, stamp
            if source in ('wave', 'idle'):
                # Wave entry already starts at the previous position/phase.
                self.transition_at = None
        self.source = source
        previous_output = self.output
        if self.transition_at is not None:
            amount = min(1., (stamp-self.transition_at)/self.TRANSITION_SECONDS)
            blend = amount*amount*(3-2*amount)
            self.output = self.transition_from+(target-self.transition_from)*blend
            if amount >= 1:
                self.transition_at = None
        else:
            self.output = target
        delta = self.output-previous_output
        if abs(delta) > 1e-6:
            self.direction = delta
        # During return to real L0, finish the short transition before handing
        # routing back to the ordinary ×10 base gain. Never multiply this again.
        if source in ('R1', 'R2', 'wave'):
            self.holding_generated = True
        elif source in ('waiting', 'detected') and self.transition_at is None:
            self.holding_generated = False
        self.generated = self.output if self.holding_generated or self.transition_at is not None else None
        return self.generated


class PoseL0Recovery:
    """Rebase stuck L0 only after a clearly upward, valid hip-line observation."""
    def __init__(self):
        self.stamp = None
        self.since = None
        self.side = 0
        self.offset = 0.
        self.value = .5
        self.transition_at = None
        self.transition_from = .5
        self.count = 0
        self.hips = deque(maxlen=3)
        self.hip_anchor = None

    def update(self, raw, stamp, hip_y=None):
        if not math.isfinite(stamp) or (self.stamp is not None and stamp <= self.stamp):
            return self.value
        if self.stamp is not None and stamp-self.stamp > .5:
            self.__init__()
        self.stamp = stamp
        if hip_y is None or not math.isfinite(hip_y):
            self.hips.clear()
            self.hip_anchor = None
        else:
            self.hips.append(hip_y)
        target = rtm_l0_amplitude({'L0': raw-self.offset})['L0']
        side = -1 if target <= .01 else 1 if target >= .99 else 0
        if side != self.side or side == 0:
            self.since = stamp if side else None
            self.side = side
            self.hip_anchor = None
        hip = median(self.hips) if len(self.hips) == 3 else None
        if side and hip is not None:
            self.hip_anchor = hip if self.hip_anchor is None else max(self.hip_anchor, hip)
        # Image y decreases upwards. Require three valid samples, at least
        # 300 ms at the same output end, and a 2%-of-frame upward hip change.
        upward = hip is not None and self.hip_anchor is not None and self.hip_anchor-hip >= .02
        if self.since is not None and stamp-self.since >= .3 and upward:
            self.offset = raw-.5
            target = .5
            self.transition_from, self.transition_at = self.value, stamp
            self.since, self.side = None, 0
            self.hip_anchor = None
            self.count += 1
        if self.transition_at is not None:
            amount = min(1., (stamp-self.transition_at)/.35)
            blend = amount*amount*(3-2*amount)
            self.value = self.transition_from+(target-self.transition_from)*blend
            if amount >= 1:
                self.transition_at = None
        else:
            self.value = target
        return self.value
