"""A persistent subject anchor and bounded recovery from a verified frame.

Recovery re-matches real subject AND background pixels from the same frame.
It never fills a missing observation with an extrapolated position.
"""
from dataclasses import dataclass
import math

import cv2
import numpy as np

from .motion_tracking import track_pair, _patch_errors
from .region_support import support_seeds, balanced_fit
from .regional_flow import DenseRegionFlow, box_fit, box_scale_uncertainty


def box_corners(box):
    x1, y1, x2, y2 = box
    return np.array(((x1, y1), (x1, y2), (x2, y1), (x2, y2)), float)


def corner_bounds(corners):
    return (*corners.min(axis=0), *corners.max(axis=0))


def move_box(box, transform):
    return corner_bounds(box_corners(box) @ transform[:, :2].T+transform[:, 2])


def scale_uncertainty(a, b, local, ba, bb, camera):
    """Three-sigma resolution of a relative scale fit, in percentage points."""
    uncertainty = 0.
    for start, end, matrix in ((a, b, local), (ba, bb, camera)):
        error = max(.03, float(np.sqrt(np.mean((end-(start @ matrix[:, :2].T+matrix[:, 2]))**2))))
        radius = max(1., float(np.sqrt(np.mean(np.sum((start-start.mean(axis=0))**2, axis=1)))))
        uncertainty += error/(np.sqrt(len(start))*radius)
    return 300*uncertainty


def verified_fit(previous, gray, seeds, *, recover=False, partial=False, min_points=8):
    if seeds is None or len(seeds) < min_points:
        return None
    a, b, _ = track_pair(previous, gray, np.asarray(seeds, np.float32).reshape(-1, 1, 2), recover=recover)
    if len(a) < min_points:
        return None
    # LK round-trip consistency alone can survive texture replacement.
    good = _patch_errors(previous, gray, a, b) < 16
    a, b = a[good], b[good]
    if partial and len(a) < .4*len(seeds):
        return None
    if len(a) < min_points:
        return None
    matrix, good = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC,
        ransacReprojThreshold=.8, maxIters=200)
    if matrix is None or good is None or not np.isfinite(matrix).all():
        return None
    good = good.ravel().astype(bool)
    scale = np.sqrt(abs(np.linalg.det(matrix[:, :2])))
    if good.sum() < (12 if partial else min_points) or good.mean() < (.55 if partial else .8) or not .85 < scale < 1.18:
        return None
    a, b = a[good], b[good]
    if np.linalg.eigvalsh(np.cov(a.T))[0] < 4:
        return None
    if partial and np.any(np.ptp(a, axis=0) < .5*np.ptp(seeds, axis=0)):
        return None
    if np.percentile(np.linalg.norm(b-(a @ matrix[:, :2].T+matrix[:, 2]), axis=1), 90) > .65:
        return None
    return matrix, a, b


@dataclass
class SubjectRecovery:
    source: tuple
    background: tuple
    step: np.ndarray
    values: np.ndarray
    origin: np.ndarray
    box: tuple
    elapsed: float
    groups: tuple = ()
    corners: np.ndarray | None = None


class SubjectMemory:
    def __init__(self):
        self.gray = None
        self.stamp = None
        self.source = self.background = None
        self.origin = self.box = self.values = None
        self.attempted = None
        self.anchor_patch = None
        self.anchor_matched = False
        self.deforming = False
        self.dense_flow = None
        self.corners = None

    def align_origin(self, gray, origin, *, new=False):
        origin = np.asarray(origin, float)
        h, w = gray.shape
        if new:
            self.anchor_patch = None
        self.anchor_matched = False
        if not (8 <= origin[0] < w-8 and 8 <= origin[1] < h-8):
            return origin
        if self.anchor_patch is None:
            origin = np.round(origin)
            patch = cv2.getRectSubPix(gray, (15, 15), tuple(map(float, origin)))
            if patch.std() > 4:
                self.anchor_patch = patch
                self.anchor_matched = True
            return origin
        # Revalidate a fixed local appearance near the transported anchor.
        # This corrects accumulated affine drift when the feature pool changes.
        x, y = np.round(origin).astype(int)
        radius = max(19, min(70, round(min(h, w)*.12)))
        x1, y1, x2, y2 = max(0, x-radius), max(0, y-radius), min(w, x+radius+1), min(h, y+radius+1)
        scores = cv2.matchTemplate(gray[y1:y2, x1:x2], self.anchor_patch, cv2.TM_CCOEFF_NORMED)
        _, peak, _, (px, py) = cv2.minMaxLoc(scores)
        scores[max(0, py-3):py+4, max(0, px-3):px+4] = -1
        if peak >= .85 and peak-float(scores.max()) >= .08:
            self.anchor_matched = True
            return np.array((x1+px+7., y1+py+7.))
        return origin

    def remember(self, gray, stamp, source, background, origin, box, values, *, deforming=False, corners=None):
        if len(source) < 8 or len(background) < (6 if deforming else 8):
            return
        self.deforming = deforming
        self.gray, self.stamp = gray, stamp
        self.source, self.background = support_seeds(source), support_seeds(background)
        self.origin, self.box, self.values = np.array(origin), tuple(box), np.array(values)
        self.corners = (box_corners(box) if corners is None else np.array(corners)) if deforming else None

    def recover(self, gray, stamp):
        if (self.gray is None or self.gray.shape != gray.shape or self.attempted == stamp
                or not 0 < stamp-self.stamp <= .25):
            return None
        self.attempted = stamp
        background = verified_fit(self.gray, gray, self.background, min_points=6 if self.deforming else 8)
        if background is None:
            return None
        camera, ba, bb = background
        groups = ()
        if self.deforming:
            if self.dense_flow is None:
                self.dense_flow = DenseRegionFlow()
            a, b = self.dense_flow.track(self.gray, gray)
            inside = np.all((a >= self.box[:2]) & (a <= self.box[2:]), axis=1)
            error = np.linalg.norm(bb-(ba @ camera[:, :2].T+camera[:, 2]), axis=1)
            region = box_fit(a[inside], b[inside], camera, gray.shape,
                             max(.16, float(np.percentile(error, 85))*2.5), prior=self.box)
            if region is None:
                return None
            a, b, local, groups = region
        else:
            source = verified_fit(self.gray, gray, self.source, recover=True, partial=True)
            if source is None:
                return None
            local, a, b = source
            local, _ = balanced_fit(a, b, local, .8)
        source = (local, a, b)
        # Background uncertainty grows when extrapolated far from its support.
        radius = np.sqrt(np.mean(np.sum((ba-ba.mean(axis=0))**2, axis=1)))
        error = np.sqrt(np.mean((bb-(ba @ camera[:, :2].T+camera[:, 2]))**2))
        uncertainty = error/np.sqrt(len(ba))*(1+np.linalg.norm(self.origin-ba.mean(axis=0))/max(1., radius))
        if uncertainty > .2:
            return None
        relative = np.linalg.solve(camera[:, :2], local[:, :2])
        shift = np.linalg.solve(camera[:, :2], (local-camera) @ np.r_[self.origin, 1.])
        h, w = gray.shape
        step = np.array((shift[0]/w*100, -shift[1]/h*100,
                         100*math.log(np.sqrt(abs(np.linalg.det(relative))))))
        scale_floor = scale_uncertainty(a, b, local, ba, bb, camera)
        if self.deforming:
            scale_floor = max(scale_floor, box_scale_uncertainty(groups, local))
        if abs(step[2]) <= scale_floor:
            step[2] = 0.  # do not turn uncertain scale fits into a false 3D axis
        if not np.isfinite(step).all() or abs(step[:2]).max() > 20 or abs(step[2]) > 6:
            return None
        # Camera-matched stationary pixels must not accumulate fit noise.
        if np.linalg.norm(shift) < max(.18, uncertainty*3) and abs(step[2]) < .04:
            step[:] = 0
        transported = local[:, :2] @ self.origin+local[:, 2]
        if self.deforming:
            corners = self.corners @ local[:, :2].T+local[:, 2]
            return SubjectRecovery(source, background, step, self.values+step,
                                   transported, corner_bounds(corners), stamp-self.stamp, groups, corners)
        origin = self.align_origin(gray, transported)
        if self.anchor_matched and np.linalg.norm(origin-transported) > 2.:
            # The fixed subject patch moving while the fitted cohort stays
            # still means that cohort belongs to exposed background. Matching
            # the anchor elsewhere cannot validate the contradictory fit or
            # justify recording a zero step at the new subject location.
            return None
        if self.anchor_patch is not None and not self.anchor_matched:
            # Recent appearance can verify a pause despite a changed initial
            # template. It cannot justify integrating a moving/deforming fit
            # without the persistent anchor, even if its local pixels agree.
            if np.any(step):
                return None
            recent_error = _patch_errors(self.gray, gray, np.array([self.origin], np.float32),
                                          np.array([transported], np.float32))[0]
            first = cv2.getRectSubPix(self.gray, (15, 15), tuple(map(float, self.origin))).astype(float)
            last = cv2.getRectSubPix(gray, (15, 15), tuple(map(float, transported))).astype(float)
            contrast = last.std()/max(1., first.std())
            first -= first.mean()
            last -= last.mean()
            correlation = float(np.sum(first*last)/max(1., np.linalg.norm(first)*np.linalg.norm(last)))
            if (len(a) < .7*len(self.source) or recent_error >= 12 or
                    not .65 <= contrast <= 1.5 or correlation < .85):
                return None
        return SubjectRecovery(source, background, step, self.values+step,
                               origin, move_box(self.box, local), stamp-self.stamp)
