"""A conservative image-flow convergence candidate, never contact detection."""
import math
from dataclasses import dataclass, replace

import numpy as np


def convergence(a, b, shape):
    fit = _radial_fit(a, b)
    found = None if fit is None else fit.candidate(shape)
    return None if found is None else found[:2]


@dataclass(frozen=True)
class _RadialFit:
    center: np.ndarray
    offset: np.ndarray
    k: float
    rms: float
    radius: float
    count: float
    fraction: float

    def moved(self, camera):
        linear, shift = camera[:, :2], camera[:, 2]
        scale = float(np.sqrt(abs(np.linalg.det(linear))))
        return replace(self, center=linear @ self.center+shift,
                       offset=linear @ self.offset-self.k*shift,
                       rms=self.rms*scale, radius=self.radius*scale)

    def candidate(self, shape):
        # Replace the old fixed 0.4% scale floor with radial support and
        # extrapolation uncertainty. Near-parallel noisy flow stays unresolved.
        if abs(self.k)*self.radius < max(.02, 4*self.rms/np.sqrt(self.count)):
            return None
        point = -self.offset/self.k
        h, w = shape
        if not ((0, 0) <= point).all() or not (point < (w, h)).all():
            return None
        uncertainty = self.rms/(np.sqrt(self.count)*abs(self.k))*(
            1+np.linalg.norm(point-self.center)/max(1., self.radius))
        if uncertainty > min(shape)*.025:
            return None
        return point, self.fraction, uncertainty


def _radial_fit(a, b):
    """Fit supported radial expansion, rejecting translation/rotation ambiguity."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    flow = b-a
    valid = np.isfinite(flow).all(axis=1) & np.isfinite(a).all(axis=1)
    a, flow = a[valid], flow[valid]
    if len(a) < 12:
        return None
    selected = np.ones(len(a), bool)
    # v = k*x+t: a common expansion about c=-t/k. A robust regional
    # estimate pools subpixel flows instead of intersecting noisy short arrows.
    for _ in range(4):
        if selected.sum() < 12:
            return None
        center, mean = a[selected].mean(axis=0), flow[selected].mean(axis=0)
        radial = a[selected]-center
        spread = np.sum(radial**2)
        if spread < 100:
            return None
        k = float(np.sum(radial*(flow[selected]-mean))/spread)
        offset = mean-k*center
        error = np.linalg.norm(flow-(k*a+offset), axis=1)
        median = float(np.median(error))
        mad = float(np.median(abs(error-median)))
        selected = error <= max(.18, median+2.5*mad)
    if selected.sum() < 12 or selected.mean() < .8:
        return None
    # Refit the final support, not the mask from the previous robust pass.
    center, mean = a[selected].mean(axis=0), flow[selected].mean(axis=0)
    radial = a[selected]-center
    covariance = radial.T @ radial/selected.sum()
    eigenvalues = np.linalg.eigvalsh(covariance)
    if eigenvalues[0] < max(4., eigenvalues[-1]*.02):
        return None  # a narrow line cannot distinguish radial flow from shear
    spread = np.sum(radial**2)
    k = float(np.sum(radial*(flow[selected]-mean))/spread)
    offset = mean-k*center
    error = np.linalg.norm(flow-(k*a+offset), axis=1)
    rms = float(np.sqrt(np.mean(error[selected]**2)))
    radius = float(np.sqrt(spread/selected.sum()))
    speed = float(np.median(np.linalg.norm(flow[selected], axis=1)))
    if rms > max(.15, speed*.25):
        return None
    return _RadialFit(center, offset, k, rms, radius, float(selected.sum()), float(selected.mean()))


class InteractionPoint:
    def __init__(self):
        self.point = None
        self.timestamp = None
        self.since = None
        self.confirmations = 0
        self.state = 'unresolved'
        self.step = 0.
        self.value = 0.
        self.shape = None

    def _transport(self, stamp, camera):
        if self.point is not None:
            self.point = camera[:, :2] @ self.point+camera[:, 2]

    def _miss(self, stamp):
        self.step = 0.
        self.state = 'holding' if self.point is not None and self.confirmations >= 5 else 'unresolved'
        if self.timestamp is not None and stamp-self.timestamp > .45:
            self.point = self.timestamp = self.since = None
            self.confirmations, self.value, self.state = 0, 0., 'unresolved'

    def hold(self, stamp, camera=None):
        # A held point may follow known camera motion; this cannot renew its
        # evidence timestamp or contribute a measured radial increment.
        if camera is not None:
            self._transport(stamp, camera)
        self._miss(stamp)

    def update(self, a, b, camera, stamp, shape, long_candidate=None):
        self.step = 0.
        if self.shape is not None and tuple(shape) != self.shape:
            self.__init__()
        self.shape = tuple(shape)
        self._transport(stamp, camera)
        fit = _radial_fit(a, b)
        found = None if fit is None else fit.moved(camera).candidate(shape)
        if found is None and long_candidate is not None:
            found = long_candidate()
        if found is None:
            self._miss(stamp)
            return
        current, _, uncertainty = found
        predicted = self.point
        point = np.linalg.solve(camera[:, :2], current-camera[:, 2])
        gap = 0. if self.timestamp is None else stamp-self.timestamp
        if (predicted is None or gap > .45 or np.linalg.norm(current-predicted) > min(shape)*.06):
            self.since, self.confirmations, self.value = stamp, 0, 0.
            self.point = current
        else:
            # A weak, distant fit is noisier near reversals. Pool successive
            # confirmations with less weight for uncertain locations, after
            # camera transport; never attract it toward the moving ROI center.
            reliability = 1/(1+(uncertainty/max(1., min(shape)*.005))**2)
            self.point = predicted+(current-predicted)*(-math.expm1(-gap/.15))*reliability
        self.confirmations += 1
        self.timestamp = stamp
        self.state = 'ready' if self.confirmations >= 5 and stamp-self.since >= .25 else 'confirming'
        if self.state == 'ready':
            # Positive means approaching the candidate point. Integrate only
            # matched endpoints, never changes in the estimated point itself.
            before = np.linalg.norm(a-point, axis=1)
            after = np.linalg.norm(b-point, axis=1)
            self.step = float(np.median(before-after)/min(shape)*100)
            self.value += self.step
