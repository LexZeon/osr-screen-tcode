"""Warm v1 analysis and relative L0 handoff after fast Pose loss."""
import math


class PoseFastFallback:
    def __init__(self, factory):
        self.factory = factory
        self.engine = None
        self.applied_output = None
        self.v1_position = None
        self.stamp = self.last_pose = self.last_fast = None
        self.active = False
        self.value = .5
        self.transition_at = None
        self.transition_from = .5
        self.reference = None
        self.override = None
        self.source = ''

    def remember_output(self, value):
        """Output-domain anchor only; never feed applied gains into recognition."""
        if value is not None and math.isfinite(value):
            self.applied_output = max(0., min(1., value))

    def update(self, frame, stamp, pose_valid, target):
        if not math.isfinite(stamp) or (self.stamp is not None and stamp <= self.stamp):
            return self.override
        gap = 0. if self.stamp is None else stamp-self.stamp
        if gap > .5:
            self.__init__(self.factory)
        # Keep the original v1 engine warm on exactly the same sampled frames,
        # including while Pose is healthy. No second capture/model is started.
        if self.engine is None:
            self.engine = self.factory()
        result = self.engine.process(frame)
        reference = self.engine.motion_reference
        position = result.positions.get('L0')
        ready = (reference is not None and reference.state == 'ready' and result.confidence > 0
                 and position is not None and math.isfinite(position))
        if ready and gap > 0 and math.hypot(*reference.step[:2])/max(.01, gap) >= 12.:
            self.last_fast = stamp
        if pose_valid:
            self.last_pose = stamp
        selected = (not pose_valid and ready and self.last_pose is not None
                    and (self.active or stamp-self.last_pose <= .75)
                    and self.last_fast is not None and stamp-self.last_fast <= .35)
        if selected != self.active:
            self.value = self.applied_output if self.applied_output is not None else self.value
            self.transition_at = None if selected else stamp
            self.transition_from = self.value
        if selected:
            # Ignore v1's accumulated absolute origin. Follow only changes
            # after entry, advancing the reference even at a travel limit so
            # reversing direction never has to unwind a hidden offset.
            if self.active and self.v1_position is not None:
                self.value = max(0., min(1., self.value + position-self.v1_position))
            self.reference = reference
            self.v1_position = position
        else:
            self.v1_position = None
        self.active = selected
        if self.transition_at is not None:
            amount = min(1., (stamp-self.transition_at)/.2)
            blend = amount*amount*(3-2*amount)
            self.value = self.transition_from+(target-self.transition_from)*blend
            if amount >= 1:
                self.transition_at = None
        elif not self.active:
            self.value = target
        self.override = self.value if self.active or self.transition_at is not None else None
        self.source = 'v1' if self.active else 'v1_return' if self.transition_at is not None else ''
        if self.override is None:
            self.reference = None
        self.stamp = stamp
        return self.override
