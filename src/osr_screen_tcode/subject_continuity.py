"""Bounded, explicitly uncertain subject continuity after strict v2 observations.

This layer never promotes a weak track to a camera/target observation. Pixel
identity is anchored to the last strict subject; unmeasured display prediction
has no motion step. Neither path renews the two-second strong-evidence limit.
"""
from dataclasses import dataclass
import math

import cv2
import numpy as np

from .motion_tracking import track_pair, _patch_errors
from .region_support import balanced_fit, support_seeds
from .subject_tracking import box_corners, corner_bounds, scale_uncertainty


@dataclass(frozen=True)
class SubjectEstimate:
    state: str
    origin: tuple
    box: tuple
    elapsed: float
    step: tuple | None = None
    # Stop continuation: weak + zero step means a pixel-verified relative
    # pause; held + no step may instead mean the input itself froze >= .2s.
    # The latter must never be promoted to a measured subject observation.
    stationary: bool = False


def _geometry(reference, shape):
    try:
        origin = np.asarray(reference.subject_origin, float)
        box = np.asarray(reference.subject_box, float)
    except (TypeError, ValueError):
        return None
    if (origin.shape != (2,) or box.shape != (4,) or
            not np.isfinite(origin).all() or not np.isfinite(box).all()):
        return None
    h, w = shape
    if (np.any(box[2:]-box[:2] < 8) or np.any(box[:2] >= (w, h)) or
            np.any(box[2:] <= 0) or np.any(origin < box[:2]) or
            np.any(origin > box[2:])):
        return None
    return origin, box


def _pairs(vectors):
    try:
        array = np.asarray(vectors, np.float32)
    except (TypeError, ValueError):
        return None
    if array.ndim != 3 or array.shape[1:] != (2, 2) or not np.isfinite(array).all():
        return None
    return array[:, 0], array[:, 1]


def _appearance(first, last, a, b):
    """Fixed subject textures, not a freshly selected patch of exposed wall."""
    offsets = np.mgrid[-4:5, -4:5].reshape(2, -1)[::-1].T.astype(np.float32)
    am, bm = np.float32(a)[:, None]+offsets, np.float32(b)[:, None]+offsets
    before = cv2.remap(first, am[:, :, 0], am[:, :, 1], cv2.INTER_LINEAR).astype(float)
    after = cv2.remap(last, bm[:, :, 0], bm[:, :, 1], cv2.INTER_LINEAR).astype(float)
    error = np.mean(np.abs(before-after), axis=1)
    sa, sb = before.std(axis=1), after.std(axis=1)
    before -= before.mean(axis=1)[:, None]
    after -= after.mean(axis=1)[:, None]
    correlation = np.sum(before*after, axis=1)/np.maximum(1., np.linalg.norm(before, axis=1)*np.linalg.norm(after, axis=1))
    return (sa >= 5) & (sb >= .45*sa) & (sb <= 1.8*sa) & (correlation >= .7) & (error <= 24)


def _fit(a, b, minimum=6, tolerance=1.5):
    if len(a) < minimum:
        return None
    matrix, mask = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC,
        ransacReprojThreshold=tolerance, maxIters=150)
    if matrix is None or mask is None or not np.isfinite(matrix).all():
        return None
    good = mask.ravel().astype(bool)
    if good.sum() < minimum or good.mean() < .65:
        return None
    a, b = a[good], b[good]
    if np.linalg.eigvalsh(np.cov(a.T))[0] < 4:
        return None
    matrix, _ = balanced_fit(a, b, matrix, tolerance)
    scale = math.sqrt(abs(np.linalg.det(matrix[:, :2])))
    error = np.linalg.norm(b-(a @ matrix[:, :2].T+matrix[:, 2]), axis=1)
    if not .85 < scale < 1.18 or np.percentile(error, 85) > tolerance:
        return None
    return matrix, good


class SubjectContinuity:
    LIMIT = 2.
    PREDICT_LIMIT = .35
    RECONFIRM_TIME = .2
    RECONFIRM_FRAMES = 3
    FREEZE_LIMIT = .2

    def __init__(self):
        self.reset()

    def reset(self):
        self.gray = self.stamp = self.strong_at = None
        self.origin = self.corners = None
        self.anchor_gray = self.anchor_points = self.points = self.point_ids = None
        self.pixel_gray = self.pixel_stamp = None
        self.pixel_origin = self.pixel_corners = None
        self.velocity = np.zeros(2)
        self.last_measured = None
        self.last_stationary = False
        self.episode = False
        self.confirm_at = self.confirm_origin = None
        self.confirm_count = 0
        self.freeze_since = None

    def _seed(self, gray, stamp, reference, geometry):
        origin, box = geometry
        dt = None if self.last_measured is None else stamp-self.last_measured
        repeated = reference.reason == 'repeated'
        if repeated or reference.reason == 'stationary':
            self.velocity[:] = 0
        elif dt is not None and 0 < dt <= .3 and self.pixel_origin is not None:
            # A display prediction is not the previous measured location.
            self._velocity((origin-self.pixel_origin)/dt, gray.shape)
        self.origin, self.corners = origin.copy(), box_corners(box)
        self.last_measured = stamp
        self.last_stationary = repeated or reference.reason == 'stationary'
        # The reference's first vector endpoint is camera compensated. Only
        # its second endpoint is a real current subject pixel.
        pairs = _pairs(reference.vectors)
        seeds = np.empty((0, 2), np.float32) if pairs is None else pairs[1]
        h, w = gray.shape
        if len(seeds):
            inside = np.all((seeds >= np.maximum(box[:2], (5, 5))) &
                            (seeds <= np.minimum(box[2:], (w-6, h-6))), axis=1)
            seeds = np.unique(seeds[inside], axis=0)
            seeds = support_seeds(seeds) if len(seeds) >= 6 else None
        else:
            seeds = None
        self.anchor_gray = gray.copy()
        self.anchor_points = seeds
        self.points = None if seeds is None else seeds.copy()
        self.point_ids = None if seeds is None else np.arange(len(seeds))
        self.pixel_gray, self.pixel_stamp = self.anchor_gray, stamp
        self.pixel_origin, self.pixel_corners = self.origin.copy(), self.corners.copy()

    def _velocity(self, velocity, shape):
        # Display extrapolation is short and bounded even after a fast frame.
        bound = np.array((shape[1], shape[0]))*.6
        self.velocity = np.clip(velocity, -bound, bound)

    def _camera(self, gray, reference, origin):
        pairs = _pairs(reference.background)
        if not reference.camera_model or pairs is None or len(pairs[0]) < 6:
            return None
        a, claimed = pairs
        h, w = gray.shape
        inside = np.all((a >= (5, 5)) & (a < (w-5, h-5)) &
                        (claimed >= (5, 5)) & (claimed < (w-5, h-5)), axis=1)
        a, claimed = a[inside], claimed[inside]
        if len(a) < 6:
            return None
        # Recheck real pixels from THIS consecutive pair. A stale background
        # tuple or a remembered camera transform cannot supply a motion step.
        tracked, b, _ = track_pair(self.gray, gray, a[:, None], recover=False)
        if len(tracked) < 6:
            return None
        ids = np.argmin(np.linalg.norm(tracked[:, None]-a[None], axis=2), axis=1)
        good = (np.linalg.norm(b-claimed[ids], axis=1) <= .75) & _appearance(self.gray, gray, tracked, b)
        a, b = tracked[good], b[good]
        if len(a) < max(6, .75*len(claimed)):
            return None
        fit = _fit(a, b, tolerance=.65)
        if fit is None:
            return None
        matrix, good = fit
        a, b = a[good], b[good]
        radius = np.sqrt(np.mean(np.sum((a-a.mean(axis=0))**2, axis=1)))
        error = np.sqrt(np.mean((b-(a @ matrix[:, :2].T+matrix[:, 2]))**2))
        uncertainty = error/np.sqrt(len(a))*(1+np.linalg.norm(origin-a.mean(axis=0))/max(1., radius))
        if radius < 6 or uncertainty > .2:
            return None
        return matrix, a, b, uncertainty

    def _weak(self, gray, stamp, reference):
        if self.points is None or len(self.points) < 6 or stamp-self.pixel_stamp > .35:
            return None
        a, b, _ = track_pair(self.pixel_gray, gray, self.points[:, None], recover=True)
        if len(a) < 6:
            return None
        ids = np.argmin(np.linalg.norm(a[:, None]-self.points[None], axis=2), axis=1)
        anchor_ids = self.point_ids[ids]
        good = _appearance(self.anchor_gray, gray, self.anchor_points[anchor_ids], b)
        good &= _patch_errors(self.pixel_gray, gray, a, b) <= 24
        a, b, anchor_ids = a[good], b[good], anchor_ids[good]
        if len(a) < max(6, .35*len(self.anchor_points)):
            return None
        fit = _fit(a, b)
        if fit is None:
            return None
        local, good = fit
        a, b, anchor_ids = a[good], b[good], anchor_ids[good]
        # Retain distributed ownership; a surviving tiny edge is not a whole
        # subject, even if it can fit an affine transform perfectly.
        if np.any(np.ptp(self.anchor_points[anchor_ids], axis=0) < .3*np.ptp(self.anchor_points, axis=0)):
            return None
        origin = local[:, :2] @ self.pixel_origin+local[:, 2]
        h, w = gray.shape
        if np.any(np.abs(origin-self.pixel_origin) > np.array((w, h))*.25):
            return None
        corners = self.pixel_corners @ local[:, :2].T+local[:, 2]
        if np.any(corners.max(axis=0) <= (0, 0)) or np.any(corners.min(axis=0) >= (w, h)):
            return None
        step, stationary = None, False
        # A whole-gap subject fit cannot be combined with one-frame camera
        # evidence. It can repair the display, then resume on the next pair.
        if self.pixel_stamp == self.stamp:
            camera = self._camera(gray, reference, self.pixel_origin)
            if camera is not None:
                matrix, ba, bb, uncertainty = camera
                shift = np.linalg.solve(matrix[:, :2], (local-matrix) @ np.r_[self.pixel_origin, 1.])
                relative = np.linalg.solve(matrix[:, :2], local[:, :2])
                measured = np.array((shift[0]/w*100, -shift[1]/h*100,
                    100*math.log(math.sqrt(abs(np.linalg.det(relative))))))
                if abs(measured[2]) <= scale_uncertainty(a, b, local, ba, bb, matrix):
                    measured[2] = 0.
                if np.linalg.norm(shift) <= max(.18, uncertainty*3) and abs(measured[2]) < .04:
                    measured[:] = 0
                    stationary = True
                if np.isfinite(measured).all() and abs(measured[:2]).max() <= 20 and abs(measured[2]) <= 6:
                    step = tuple(map(float, measured))
                else:
                    stationary = False
        self._velocity((origin-self.pixel_origin)/(stamp-self.pixel_stamp), gray.shape)
        self.origin, self.corners = origin, corners
        self.last_measured, self.last_stationary = stamp, stationary
        self.pixel_gray, self.pixel_stamp = gray.copy(), stamp
        self.pixel_origin, self.pixel_corners = origin.copy(), corners.copy()
        self.points, self.point_ids = b.copy(), anchor_ids
        return self._result('weak', stamp, step, stationary)

    def _result(self, state, stamp, step=None, stationary=False):
        return SubjectEstimate(state, tuple(map(float, self.origin)),
            tuple(map(float, corner_bounds(self.corners))), max(0., stamp-self.strong_at), step, stationary)

    def update(self, gray, stamp, reference):
        if (not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8 or
                not math.isfinite(stamp)):
            self.reset()
            return None
        discontinuity = (self.stamp is not None and
            (stamp <= self.stamp or stamp-self.stamp > .5 or self.gray.shape != gray.shape))
        new_region = reference.state == 'calibrating' and reference.roi is not None
        if discontinuity or new_region or reference.reason in ('jump', 'cut', 'scene_cut', 'reset'):
            self.reset()
            return None
        if self.gray is not None and gray.std() < 2 and self.gray.std() >= 8:
            self.reset()
            return None
        repeated = self.gray is not None and np.array_equal(gray, self.gray)
        if repeated:
            if self.freeze_since is None:
                self.freeze_since = self.stamp
        else:
            self.freeze_since = None
        geometry = _geometry(reference, gray.shape)
        strict = reference.state in ('ready', 'tracking') and geometry is not None
        if strict:
            real = reference.reason != 'repeated' and not repeated
            if self.strong_at is None:
                self.strong_at = stamp
            elif not self.episode:
                if real:
                    self.strong_at = stamp
            elif real:
                origin = geometry[0]
                if (self.confirm_at is None or self.confirm_origin is None or
                        np.linalg.norm(origin-self.confirm_origin) > min(gray.shape)*.15):
                    self.confirm_at, self.confirm_count = stamp, 0
                self.confirm_count += 1
                self.confirm_origin = origin.copy()
                if self.confirm_count >= self.RECONFIRM_FRAMES and stamp-self.confirm_at >= self.RECONFIRM_TIME-1e-9:
                    self.episode = False
                    self.strong_at = stamp
                    self.confirm_at, self.confirm_count = None, 0
            else:
                self.confirm_at, self.confirm_count = None, 0
            self._seed(gray, stamp, reference, geometry)
            self.gray, self.stamp = gray.copy(), stamp
            return None
        self.confirm_at, self.confirm_count = None, 0
        if self.strong_at is None:
            self.gray, self.stamp = gray.copy(), stamp
            return None
        self.episode = True
        result = None
        if stamp-self.strong_at <= self.LIMIT+1e-9:
            if repeated:
                # Do not replay the last measured step or extrapolate a frozen
                # rejected frame. Sustained input freezing stops continuation
                # but never proves that the missing subject is stationary.
                self.velocity[:] = 0
                frozen = stamp-self.freeze_since >= self.FREEZE_LIMIT-1e-9
                result = self._result('held', stamp, stationary=self.last_stationary or frozen)
            else:
                result = self._weak(gray, stamp, reference)
                if result is None:
                    age = stamp-self.last_measured
                    previous_age = max(0., self.stamp-self.last_measured)
                    end, start = min(age, self.PREDICT_LIMIT), min(previous_age, self.PREDICT_LIMIT)
                    # Integral of linear braking: reaches zero speed at .35s.
                    distance = (end-end*end/(2*self.PREDICT_LIMIT))-(start-start*start/(2*self.PREDICT_LIMIT))
                    shift = self.velocity*max(0., distance)
                    self.origin += shift
                    self.corners += shift
                    state = 'predicted' if age < self.PREDICT_LIMIT and np.linalg.norm(shift) > .01 else 'held'
                    result = self._result(state, stamp)
        self.gray, self.stamp = gray.copy(), stamp
        return result
