"""Track an independently supported target and measure source-to-target reach."""
from collections import deque
from dataclasses import dataclass, replace

import cv2
import numpy as np

from .target_regions import proposals
from .subject_tracking import verified_fit
from .region_support import support_seeds


@dataclass(frozen=True)
class ReachObservation:
    state: str = 'unresolved'
    point: tuple | None = None
    box: tuple | None = None
    samples: tuple = ()
    remaining: float | None = None
    distance: float | None = None
    span: float | None = None
    key: int = 0
    delta: float = 0.
    offscreen: bool = False


def inside(points, box):
    x1, y1, x2, y2 = box
    return ((points[:, 0] >= x1) & (points[:, 0] <= x2)
            & (points[:, 1] >= y1) & (points[:, 1] <= y2))


def appearance(frame, points):
    positions = np.round(points).astype(int)
    positions = positions[(positions[:, 0] >= 0) & (positions[:, 0] < frame.shape[1])
                          & (positions[:, 1] >= 0) & (positions[:, 1] < frame.shape[0])]
    if len(positions) < 6:
        return None
    pixels = frame[positions[:, 1], positions[:, 0]][:, None]
    hsv = cv2.cvtColor(pixels, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256]).ravel()
    return histogram/max(1., histogram.sum())


def tracked_region(a, b, box, source_a, source_b, polygon=None, *, current_polygon=False):
    mask = inside(a, box)
    if polygon is not None:
        locations = b if current_polygon else a
        mask = np.array([cv2.pointPolygonTest(np.asarray(polygon, np.float32), tuple(map(float, p)), False) >= 0
                         for p in locations])
    # Pixels belonging to the active mover must not take ownership of the
    # target when it covers part of a different object.
    if len(source_a):
        mask &= np.min(np.linalg.norm(a[:, None]-source_a, axis=2), axis=1) > 1.
    first, last = a[mask], b[mask]
    if len(first) < 6:
        return None
    transform, good = cv2.estimateAffinePartial2D(first, last, method=cv2.RANSAC,
        ransacReprojThreshold=.7, maxIters=200)
    if transform is None or not np.isfinite(transform).all():
        return None
    good = good.ravel().astype(bool)
    if good.sum() < 6 or good.mean() < .8:
        return None
    first, last = first[good], last[good]
    spread = np.linalg.eigvalsh(np.cov(first.T))
    scale = float(np.sqrt(abs(np.linalg.det(transform[:, :2]))))
    if spread[0] < 4 or not .85 < scale < 1.18:
        return None
    error = np.linalg.norm(last-(first @ transform[:, :2].T+transform[:, 2]), axis=1)
    if np.percentile(error, 90) > .6:
        return None
    return transform, first, last


class ReachTarget:
    def __init__(self):
        self.history = deque(maxlen=360)
        self.target = self.box = self.direction = None
        self.polygon = None
        self.signature = None
        self.pixels = None
        self.unregistered = False
        self.selected_at = self.last_seen = None
        self.last_scan = -1e9
        self.serial = 0
        self.support_count = 0
        self.confirmed = False
        self.shape = None
        self.stamp = None
        self.far = None
        self.ranges = deque(maxlen=360)
        self.previous_ratio = None
        self.last = ReachObservation()

    def _snapshot(self, state, shape, *, samples=(), remaining=None, distance=None, delta=0.):
        point = None if self.target is None else tuple(map(float, self.target))
        offscreen = point is not None and not (0 <= point[0] < shape[1] and 0 <= point[1] < shape[0])
        self.last = ReachObservation(state, point, self.box, samples, remaining, distance,
                                     self.far, self.serial, delta, offscreen)
        return self.last

    def _discard_target(self):
        self.target = self.box = self.direction = None
        self.polygon = None
        self.signature = None
        self.pixels = None
        self.selected_at = self.last_seen = None
        self.confirmed = False
        self.support_count = 0
        self.far = self.previous_ratio = None
        self.ranges.clear()

    def _remember_pixels(self, frame, stamp, points):
        self.pixels = (cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), stamp, support_seeds(points),
                       self.target.copy(), self.box, None if self.polygon is None else self.polygon.copy(),
                       self.direction.copy(), self.far, tuple(self.ranges))

    def _pixel_fit(self, frame, stamp):
        if self.pixels is None or not 0 < stamp-self.pixels[1] <= .3:
            return None
        old, _, points, *_ = self.pixels
        if old.shape != frame.shape[:2]:
            return None
        return verified_fit(old, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), points)

    def _restore_pixel_geometry(self):
        _, _, _, point, box, polygon, direction, far, ranges = self.pixels
        self.target, self.box, self.polygon = point.copy(), box, None if polygon is None else polygon.copy()
        self.direction, self.far = direction.copy(), far
        self.ranges = deque(ranges, maxlen=360)

    def _move_target(self, transform):
        self.target = transform[:, :2] @ self.target+transform[:, 2]
        corners = np.array(((self.box[0], self.box[1]), (self.box[0], self.box[3]),
                            (self.box[2], self.box[1]), (self.box[2], self.box[3])))
        corners = corners @ transform[:, :2].T+transform[:, 2]
        self.box = (*corners.min(axis=0), *corners.max(axis=0))
        if self.polygon is not None:
            self.polygon = self.polygon @ transform[:, :2].T+transform[:, 2]
        self.direction = transform[:, :2] @ self.direction
        self.direction /= max(1e-6, np.linalg.norm(self.direction))
        scale = float(np.sqrt(abs(np.linalg.det(transform[:, :2]))))
        if self.far is not None:
            self.far *= scale
            self.ranges = deque(((t, value*scale) for t, value in self.ranges), maxlen=360)

    def _same_appearance(self, frame, support):
        if support is None:
            return False
        current = appearance(frame, support[2])
        return (self.signature is None or (current is not None
            and np.sqrt(max(0., 1-np.sum(np.sqrt(self.signature*current)))) <= .55))

    def update(self, frame, dominant, reference, data, stamp):
        shape = frame.shape[:2]
        dt = 0. if self.stamp is None else stamp-self.stamp
        if (self.shape is not None and self.shape != shape) or dt > .5 or reference.reason == 'jump' or reference.state == 'calibrating':
            self.__init__()
        self.shape, self.stamp = shape, stamp
        if reference.reason == 'jump' or reference.state == 'calibrating':
            return self._snapshot('unresolved', shape)
        if data is None:
            if reference.reason == 'repeated' and self.last.point is not None:
                # Same pixels imply a pause, not another target observation.
                return replace(self.last, delta=0.)
            self.unregistered = True
            support = self._pixel_fit(frame, stamp)
            if self._same_appearance(frame, support):
                self._restore_pixel_geometry()
                self._move_target(support[0])
                self.last_seen = stamp
                self._remember_pixels(frame, stamp, support[2])
                return self._snapshot('holding', shape)  # object seen, subject/camera unresolved
            if self.last_seen is not None and stamp-self.last_seen > 2.:
                self._discard_target()
            self.last = replace(self._snapshot('holding' if self.target is not None else 'unresolved', shape),
                                point=None, box=None, offscreen=False)
            return self.last  # unknown camera: do not paint stale pixel positions
        a, b, camera, source_a, source_b = data
        if self.unregistered:
            if self.pixels is None or stamp-self.pixels[1] > .3:
                self._discard_target()
            self.history.clear()
            self.unregistered = False
        measured = reference.state in ('ready', 'tracking') and reference.roi is not None
        center = (np.array(reference.subject_origin or ((reference.roi[0]+reference.roi[2])/2, (reference.roi[1]+reference.roi[3])/2))
                  if measured else None)
        if reference.reason == 'subject_recovered':
            self.history.clear()  # recovery camera spans several frames; never apply it twice
        self.history = deque(((t, c @ camera[:, :2].T+camera[:, 2]) for t, c in self.history if stamp-t <= 3.), maxlen=360)
        if measured:
            self.history.append((stamp, center))
        support = None
        if self.target is not None:
            own_pixels = self._pixel_fit(frame, stamp)
            if self._same_appearance(frame, own_pixels):
                self._restore_pixel_geometry()
                support = own_pixels
            elif reference.reason != 'subject_recovered':
                support = tracked_region(a, b, self.box, source_a, source_b, self.polygon)
                if not self._same_appearance(frame, support):
                    support = None
            transform = camera if support is None else support[0]
            if support is not None or reference.reason != 'subject_recovered':
                self._move_target(transform)
            if support is None:
                if self.last_seen is not None and stamp-self.last_seen > 2.:
                    self._discard_target()
                else:
                    return self._snapshot('holding', shape)
            else:
                self.last_seen = stamp
                self.support_count += 1
        if self.target is None:
            if (not measured or stamp-self.last_scan < .2 or dominant.stroke_span is None
                    or len(self.history) < 6 or stamp-self.history[0][0] < .4):
                return self._snapshot('unresolved', shape)
            self.last_scan = stamp
            axis = dominant.basis[0]
            direction = np.array((axis[2]*shape[1], -axis[0]*shape[0]))
            if np.linalg.norm(direction) < .15*min(shape):
                return self._snapshot('unresolved', shape)
            direction /= np.linalg.norm(direction)
            centers = np.array([c for _, c in self.history])
            origin = np.median(centers, axis=0)
            candidates = proposals(frame, reference.roi, origin, direction, centers, b)
            qualified = []
            for score, point, box, toward, polygon in candidates:
                # Fit the candidate's own current correspondences by mapping
                # its current bounds back through the known camera transform.
                corners = np.array(((box[0], box[1]), (box[2], box[3])))
                before = (corners-camera[:, 2]) @ np.linalg.inv(camera[:, :2]).T
                prior_box = (*before.min(axis=0), *before.max(axis=0))
                fit = tracked_region(a, b, prior_box, source_a, source_b, polygon, current_polygon=True)
                if fit is None:
                    continue
                own = np.median(fit[2]-fit[1], axis=0)
                mover = np.median(source_b-source_a, axis=0)
                if np.linalg.norm(mover) > .3 and np.linalg.norm(own-mover) < .2:
                    continue
                qualified.append((score, point, box, toward, polygon, fit))
            if not qualified or (len(qualified) > 1 and qualified[1][0] > qualified[0][0]*.9):
                return self._snapshot('unresolved', shape)
            _, point, box, toward, self.polygon, support = qualified[0]
            self.target, self.box, self.direction = np.asarray(point), box, toward
            self.signature = appearance(frame, support[2])
            self.serial += 1
            self.selected_at = self.last_seen = stamp
            self.support_count = 1
            # Seed the retreat end from the observed path. This is a range
            # reference only, not a claim the target was tracked in those frames.
            distances = np.linalg.norm(self.target-centers, axis=1)
            self.far = max(4., float(np.quantile(distances, .98)))
        if self.support_count < 6 or stamp-self.selected_at < .3:
            self._remember_pixels(frame, stamp, support[2])
            return self._snapshot('confirming', shape)
        self.confirmed = True
        if not measured:
            # Target pixels may remain visible while the source is obscured.
            # Keep their measured position, but never claim a reach percentage.
            self._remember_pixels(frame, stamp, support[2])
            return self._snapshot('holding', shape)
        displacement = self.target-center
        signed = float(displacement @ self.direction)
        distance = float(np.linalg.norm(displacement))
        lateral = float(abs(self.direction[0]*displacement[1]-self.direction[1]*displacement[0]))
        if signed < -max(4., self.far*.05) or lateral > max(.25*self.far, .1*min(shape)):
            # A source that passes well beyond or beside the supposed endpoint
            # disproves that candidate. Do not generate a second cycle from |d|.
            self._discard_target()
            return self._snapshot('unresolved', shape)
        if distance <= max(1., min(shape)*.005):
            distance = 0.  # subpixel/point-location tolerance, not a screen edge
        self.ranges.append((stamp, max(0., distance)))
        while self.ranges and stamp-self.ranges[0][0] > 3.:
            self.ranges.popleft()
        observed_far = max(value for _, value in self.ranges)
        # New, farther retreats expand the range immediately. The upper end
        # cannot collapse around the current position while approaching.
        self.far = max(self.far, observed_far, 4.)
        ratio = float(np.clip(distance/self.far, 0., 1.))
        delta = 0. if self.previous_ratio is None else ratio-self.previous_ratio
        self.previous_ratio = ratio
        self._remember_pixels(frame, stamp, support[2])
        samples = tuple(tuple(map(float, p)) for p in support[2][::max(1, len(support[2])//20)])
        return self._snapshot('ready', shape, samples=samples, remaining=ratio, distance=distance, delta=delta)
