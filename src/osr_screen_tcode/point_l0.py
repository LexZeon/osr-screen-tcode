"""Optional L0 references; measurements never receive the final output back."""
import math

import numpy as np

from .dominant_motion import DominantMotion
from .fused_l0 import FusedL0


POINT_MODES = ('fusion', 'motion', 'center', 'interaction')


def stroke_center(dominant, roi, shape, origin=None):
    if dominant.stroke_span is None or roi is None or len(dominant.history) < 5:
        return None
    samples = np.array([v for _, v in dominant.history])
    axis = dominant.basis[0]
    projected = samples @ axis
    low, high = np.quantile(projected, (.02, .98))
    if high-low < .75:
        return None
    middle = (low+high)/2
    current = float(dominant.previous @ axis)
    delta = (middle-current)*axis
    h, w = shape
    center = np.array(origin or ((roi[0]+roi[2])/2, (roi[1]+roi[3])/2))
    center += (delta[2]*w/100, -delta[0]*h/100)
    return tuple(center), float(np.clip((current-low)/(high-low), 0., 1.))


class PointL0:
    def __init__(self):
        self.radial = DominantMotion(adaptive_l0=True)
        self.timestamp = None
        self.output = None
        self.source = 'motion'
        self.offset = 0.
        self.center = None
        self.driver = None
        self.fusion = FusedL0()
        self.mode = 'motion'

    def update(self, mode, dominant, reference, point, stamp, shape, ordinary, arrival=None, estimate=None):
        dt = 0. if self.timestamp is None else max(0., stamp-self.timestamp)
        self.timestamp = stamp
        measured = reference.state in ('ready', 'tracking')
        if mode == 'fusion':
            if self.mode != mode:
                self.fusion = FusedL0(ordinary if self.output is None else self.output,
                                      entering=self.output is not None)
            self.mode = mode
            center = stroke_center(dominant, reference.roi, shape, reference.subject_origin) if measured else None
            self.center = None if center is None else center[0]
            if measured and np.any(reference.step) and point.state == 'ready':
                self.radial.update((0., point.value, 0.), stamp)
            elif point.state == 'holding':
                self.radial.hold(stamp)
            elif point.state != 'ready':
                self.radial = DominantMotion(adaptive_l0=True)
            radial = stroke_center(self.radial, reference.roi, shape) if point.state == 'ready' else None
            self.output = self.fusion.update(dominant, reference, point,
                None if radial is None else 1-radial[1], center, stamp, shape, ordinary, arrival, estimate)
            self.driver = self.radial if self.fusion.using_point else None
            self.source = 'fusion'
            return self.output
        self.mode = mode
        if not measured:
            if reference.state != 'holding':
                self.radial = DominantMotion(adaptive_l0=True)
            self.center = None
            self.driver = None
            return ordinary if self.output is None or (mode == 'motion' and self.source == 'motion') else self.output
        center = stroke_center(dominant, reference.roi, shape, reference.subject_origin)
        self.center = None if center is None else center[0]
        if mode != 'motion' and self.output is not None and not np.any(reference.step):
            return self.output
        source, target = 'motion', ordinary
        self.driver = None
        if point.state == 'ready':
            self.radial.update((0., point.value, 0.), stamp)
        elif point.state == 'holding':
            self.radial.hold(stamp)
            if mode == 'interaction' and self.source == 'interaction':
                self.driver = self.radial
                return self.output
        else:
            self.radial = DominantMotion(adaptive_l0=True)
        if mode == 'center' and center is not None:
            source, target = 'center', center[1]
        elif mode == 'interaction' and point.state == 'ready':
            radial = stroke_center(self.radial, reference.roi, shape)
            if radial is not None:
                source, target = 'interaction', 1-radial[1]
                self.driver = self.radial
        if self.output is None:
            self.output = ordinary
        if source != self.source:
            self.offset = self.output-target
            self.source = source
        else:
            self.offset *= math.exp(-min(dt, .1)/.25)
        # Enter/leave from the previous target, then converge to measured phase.
        self.output = float(np.clip(target+self.offset, 0., 1.))
        return self.output
