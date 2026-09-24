"""Track local image motion relative to a spatially supported background fit.

No person detector or depth estimate. If background and subject cannot be
separated, hold instead of promoting whole-frame camera motion to a stroke.
"""
import math
from collections import deque
from dataclasses import replace

import cv2
import numpy as np

from .motion_reference import MotionReference, sample_vectors
from .motion_layers import MinorityBackground
from .motion_tracking import track_pair
from .motion_focus import MotionFocus, overlap
from .interaction_point import InteractionPoint
from .target_baseline import long_convergence
from .region_support import balanced_fit, support_seeds
from .subject_tracking import SubjectMemory, move_box, scale_uncertainty, box_corners, corner_bounds
from .regional_flow import box_fit, box_scale_uncertainty, coherent_support, DenseRegionFlow
from .visual_lab.observations import Observation


def same_scene_structure(previous, current):
    """Only soften a failed-track cut when coarse pixels still agree.

    This does not validate motion, camera ownership or a new subject. Strong
    blur can remove nearly all corners while leaving the same scene visible.
    """
    if previous.shape != current.shape or min(current.shape) < 24:
        return False
    frames = [cv2.GaussianBlur(cv2.resize(image, (96, 72), interpolation=cv2.INTER_AREA),
                              (0, 0), 1.2).astype(np.float32) for image in (previous, current)]
    if min(float(image.std()) for image in frames) < 3.:
        return False
    shift, response = cv2.phaseCorrelate(*frames)
    shifts = [(0, 0)]
    if response >= .2 and np.isfinite(shift).all() and max(abs(shift[0])/96, abs(shift[1])/72) < .2:
        shifts.append(tuple(round(v) for v in shift))
    for dx, dy in shifts:
        x0, x1, y0, y1 = max(0, -dx), min(96, 96-dx), max(0, -dy), min(72, 72-dy)
        a = frames[0][y0:y1, x0:x1].ravel()
        b = frames[1][y0+dy:y1+dy, x0+dx:x1+dx].ravel()
        a, b = a-a.mean(), b-b.mean()
        norm = float(np.linalg.norm(a)*np.linalg.norm(b))
        if norm > 1e-6 and float(a @ b)/norm >= .88 and float(np.median(np.abs(a-b))) < 18.:
            return True
    return False


class CameraRelativeMotion:
    def __init__(self):
        self.gray = None
        self.timestamp = None
        self.measured_at = None
        self.values = np.zeros(3)
        self.roi = None
        self.last_subject = None
        self.last = None
        self.reference = MotionReference("v2")
        self.needs_reference = True
        self.counts = (0, 0, 0, 0)
        self.reason = ""
        self.loss_since = None
        self.background_points = None
        self.camera_transform = None
        self.region_tracks = None
        self.step_history = deque(maxlen=3)
        self.layers = MinorityBackground()
        self.long_layers = MinorityBackground()
        self.gray_history = deque(maxlen=4)
        self.discovery_pair = None
        self.discovery_cooldown = 0
        self.camera_source = ""
        self.local_model = ""
        self.tracking_rescued = 0
        self.background_diagnostic = ()
        self.region_focus = MotionFocus()
        self.patch_focus = MotionFocus()
        self.focus_switched = False
        self.interaction = InteractionPoint()
        self.foreground_points = None
        self.target_data = None
        self.subject = SubjectMemory()
        self.subject_confirmed = False
        self.subject_origin = self.subject_box = None
        self.subject_corners = None
        self.box_tracking = False
        self.dense_flow = None
        self.dense_tracks = None
        self.previous_gray = None

    def _dense_points(self):
        if self.dense_tracks is None:
            if self.previous_gray is None or self.gray is None:
                return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32)
            if self.dense_flow is None:
                self.dense_flow = DenseRegionFlow()
            self.dense_tracks = self.dense_flow.track(self.previous_gray, self.gray)
        return self.dense_tracks

    def _dense_foreground(self, camera, w, h):
        a, b = self._dense_points()
        residual = b-(a @ camera[:, :2].T+camera[:, 2])
        moving = np.linalg.norm(residual, axis=1) > .5
        a, residual = a[moving], residual[moving]
        good = coherent_support(a, residual, (h, w))
        return a[good] if len(good) and good.mean() >= .65 else None

    def _dense_box(self, camera, noise, selected, prior):
        da, db = self._dense_points()
        if len(selected) == 0:
            return None
        low, high = (np.asarray(prior[:2]), np.asarray(prior[2:])) if prior else (selected.min(axis=0), selected.max(axis=0))
        inside = np.all((da >= low) & (da <= high), axis=1)
        # Keep genuine low-speed subject samples at reversals. Camera labels
        # remain independent; initialization still needs a moving envelope.
        if prior is None:
            residual = db-(da @ camera[:, :2].T+camera[:, 2])
            inside &= np.linalg.norm(residual, axis=1) > noise
        return box_fit(da[inside], db[inside], camera, self.gray.shape, noise, prior=prior)

    @staticmethod
    def _features(gray):
        h, w = gray.shape
        points = []
        # Spatial sampling prevents a single highly textured patch from
        # becoming the background merely because it contains more corners.
        for row in range(6):
            for column in range(8):
                x1, x2 = column*w//8, (column+1)*w//8
                y1, y2 = row*h//6, (row+1)*h//6
                found = cv2.goodFeaturesToTrack(gray[y1:y2, x1:x2], 8, .015, max(4, min(h, w)/70))
                if found is not None:
                    points.extend(found[:, 0] + (x1, y1))
        # A fast large window/subject can enter the top grid row and displace
        # all small-background corners there. Reserve samples within thin
        # perimeter strips, independently of the foreground's corner strength.
        strip = max(8, round(h*.1))
        for column in range(8):
            x1, x2 = column*w//8, (column+1)*w//8
            for y1, y2 in ((0, strip), (h-strip, h)):
                found = cv2.goodFeaturesToTrack(gray[y1:y2, x1:x2], 4, .015, max(4, min(h, w)/70))
                if found is not None:
                    for point in found[:, 0]+(x1, y1):
                        if not points or np.min(np.linalg.norm(np.asarray(points)-point, axis=1)) > 3:
                            points.append(point)
        return np.asarray(points, np.float32).reshape(-1, 1, 2)

    @staticmethod
    def _fit(a, b, tolerance):
        if len(a) < 4:
            return None, None
        matrix, mask = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC,
                                                 ransacReprojThreshold=tolerance, maxIters=300)
        if matrix is None or not np.isfinite(matrix).all():
            return None, None
        scale = np.sqrt(abs(np.linalg.det(matrix[:, :2])))
        if not .85 < scale < 1.18:
            return None, None
        return matrix, mask.ravel().astype(bool)

    def _discover_layers(self, a, b, w, h):
        eligible = None
        if self.previous_gray is not None:
            image = self.previous_gray.astype(np.float32)
            variance = np.maximum(0, cv2.blur(image*image, (9, 9))-cv2.blur(image, (9, 9))**2)
            xy = np.clip(np.round(a).astype(int), (0, 0), (w-1, h-1))
            eligible = variance[xy[:, 1], xy[:, 0]] >= 9.
        camera, indices = self.layers.select(a, b, w, h,
            foreground=lambda camera: self._dense_foreground(camera, w, h), camera_eligible=eligible)
        self.background_diagnostic = self.layers.diagnostic
        if camera is not None or self.layers.waiting:
            return camera, indices, self.layers.waiting
        # Small strokes can be below pairwise flow noise. Classify motion over
        # a longer baseline, then fit ONLY the current frame pair's camera.
        # This discovers labels, never integrates the same motion twice.
        if self.discovery_pair is None or len(a) < 12:
            return None, None, False
        if self.discovery_cooldown:
            self.discovery_cooldown -= 1
            return None, None, False
        previous, older = self.discovery_pair
        past, ok, _ = cv2.calcOpticalFlowPyrLK(previous, older, a[:, None], None)
        if past is None:
            return None, None, False
        back, reverse, _ = cv2.calcOpticalFlowPyrLK(older, previous, past, None)
        if back is None:
            return None, None, False
        valid = (ok.ravel() == 1) & (reverse.ravel() == 1)
        valid &= np.isfinite(past[:, 0]).all(axis=1)
        valid &= np.linalg.norm(back[:, 0]-a, axis=1) < .8
        candidates = np.flatnonzero(valid)
        _, selected = self.long_layers.select(past[valid, 0], b[valid], w, h, match_points=a[valid],
            camera_eligible=None if eligible is None else eligible[valid])
        if selected is not None or self.long_layers.waiting:
            self.background_diagnostic = self.long_layers.diagnostic
        if selected is None:
            if not self.long_layers.waiting:
                self.discovery_cooldown = 2
            return None, None, self.long_layers.waiting
        indices = candidates[selected]
        camera, support = self._fit(a[indices], b[indices], max(.25, max(w, h)/1600))
        if camera is None or support.sum() < 6 or support.mean() < .8:
            return None, None, False
        return camera, indices[support], False

    def _camera(self, a, b, edge, tolerance, w, h):
        if self.camera_source != "minority":
            camera, indices, waiting = self._discover_layers(a, b, w, h)
            if camera is not None:
                self.camera_source = "minority"
                # A previous majority may have been the large foreground.
                self.needs_reference = True
                self.roi = None
                return camera, indices
            if waiting:
                self.reason = "background_confirm"
                return None, None
            camera, indices = self._spatial_camera(a, b, edge, tolerance, w, h)
            if camera is not None:
                return camera, indices
        # A confirmed background gets first refusal, before a larger subject
        # can take over a new majority fit around a pause or reversal.
        if self.background_points is not None and len(a):
            distances = np.linalg.norm(a[:, None]-self.background_points[None], axis=2)
            known = distances.min(axis=1) <= max(3, max(w, h)/160)
            if self.roi is not None and self.camera_source != "minority":
                x1, y1, x2, y2 = self.roi
                pad = min(w, h)*.04
                known &= ~((a[:, 0] >= x1-pad) & (a[:, 0] <= x2+pad)
                           & (a[:, 1] >= y1-pad) & (a[:, 1] <= y2+pad))
            camera, support = self._fit(a[known], b[known], max(.25, tolerance*.5))
            if camera is not None and support.sum() >= 4 and support.mean() >= .8:
                indices = np.flatnonzero(known)[support]
                spread = np.ptp(a[indices], axis=0)/np.array((w, h))
                center = np.array((w/2, h/2, 1))
                change = np.linalg.norm((camera-self.camera_transform) @ center)
                scale_change = abs(np.linalg.det(camera[:, :2])-np.linalg.det(self.camera_transform[:, :2]))
                if max(spread) >= .12 and min(spread) >= .025 and change <= max(2, max(w, h)/160) and scale_change <= .02:
                    # Replenish background corners agreeing with this frame's
                    # fit outside the foreground. Reusing only surviving old
                    # corners would shrink even a broad background to four.
                    if self.roi is not None:
                        x1, y1, x2, y2 = self.roi
                        pad = min(w, h)*.025
                        outside = ~((a[:, 0] >= x1-pad) & (a[:, 0] <= x2+pad)
                                    & (a[:, 1] >= y1-pad) & (a[:, 1] <= y2+pad))
                        error = np.linalg.norm(b-(a @ camera[:, :2].T+camera[:, 2]), axis=1)
                        renewed = outside & (error <= max(.25, tolerance*.5))
                        if self.camera_source == "minority":
                            renewed &= distances.min(axis=1) <= max(8, min(w, h)*.04)
                        renewed[indices] = True
                        indices = np.flatnonzero(renewed)
                    return camera, indices
        if self.camera_source == "minority":
            camera, indices, waiting = self._discover_layers(a, b, w, h)
            if camera is not None:
                return camera, indices
            if waiting:
                self.reason = "background_confirm"
            # Do not relabel the large foreground as the camera when a small
            # established background is momentarily occluded or blurred.
            return None, None
        return None, None

    def _spatial_camera(self, a, b, edge, tolerance, w, h):
        # Prefer the perimeter, but do not require 18 corners on it. A few
        # independent, well spread background patches are sufficient. When
        # those patches lie farther inward, fit outside the tracked region.
        outside = np.ones(len(a), bool)
        if self.roi is not None:
            x1, y1, x2, y2 = self.roi
            pad = min(w, h)*.04
            outside = ~((a[:, 0] >= x1-pad) & (a[:, 0] <= x2+pad)
                        & (a[:, 1] >= y1-pad) & (a[:, 1] <= y2+pad))
        for candidates in (edge & outside, outside):
            camera, support = self._fit(a[candidates], b[candidates], tolerance)
            if camera is None:
                continue
            indices = np.flatnonzero(candidates)[support]
            ba = a[indices]
            coverage = cv2.contourArea(cv2.convexHull(ba))/(h*w)
            spread = np.ptp(ba, axis=0)/np.array((w, h))
            quadrants = {(int(x >= w/2), int(y >= h/2)) for x, y in ba}
            # Keep independent spatial support: one moving subject must not
            # become the camera model simply because it has many features.
            if (len(ba) >= 6 and support.mean() >= .6 and coverage >= .18
                    and min(spread) >= .45 and len(quadrants) >= 3):
                self.camera_source = "broad"
                return camera, indices
            # A long background band can constrain a similarity transform
            # without occupying three quadrants (e.g. a wall above a subject).
            # Require extent along the band and across it, plus perimeter
            # support, rather than treating low hull area as total failure.
            if (len(ba) >= 6 and support.mean() >= .7 and coverage >= .04
                    and max(spread) >= .6 and min(spread) >= .08
                    and edge[indices].mean() >= .8):
                self.camera_source = "band"
                return camera, indices
        return None, None

    def _hold(self, stamp, state, background=(), camera=(0., 0., 0.), *, hard=False, preserve_points=False):
        if not hard and not preserve_points:
            recovered = self._recover_subject(stamp)
            if recovered is not None:
                return recovered
        if not preserve_points:
            self.foreground_points = None
        self.interaction.hold(stamp)
        self.step_history.clear()
        if self.loss_since is None:
            self.loss_since = stamp
        if not hard and not self.needs_reference and stamp-self.loss_since <= .45:
            # Preserve the reference through a brief measurement failure,
            # but do not invent an observation or integrate unmeasured motion.
            state = "holding"
        else:
            self.needs_reference = True
            self.roi = None
            self.subject_origin = self.subject_box = None
            self.subject_corners = None
            self.subject = SubjectMemory()
            self.subject_confirmed = False
            self.box_tracking = False
            self.local_model = ""
            # Losing a deforming subject does not invalidate a camera fit
            # verified in this same pair. Keep those independent pixel labels.
            if hard or self.reason not in ("region", "region_fit", "fast_support"):
                self.background_points = self.camera_transform = None
            self.region_focus = MotionFocus()
            self.patch_focus = MotionFocus()
            self.interaction = InteractionPoint()
            if hard:
                self.camera_source = ""
                self.layers.reset()
                self.long_layers.reset()
                self.gray_history.clear()
                self.discovery_pair = None
        self.reference = MotionReference("v2", state, self.roi, background=background,
                                         camera_step=camera, reason=self.reason, counts=self.counts,
                                         camera_model=self.camera_source,
                                         background_diagnostic=self.background_diagnostic,
                                         rescued=self.tracking_rescued, local_model=self.local_model,
                                         focus=self._focus_status(stamp), subject_origin=self.subject_origin,
                                         subject_box=self.subject_box)
        self.last = Observation(stamp, state)
        return self.last, []

    def _recover_subject(self, stamp):
        if not self.subject_confirmed:
            return None  # finish initial geometry/ownership confirmation first
        recovered = self.subject.recover(self.gray, stamp) if self.gray is not None else None
        if recovered is None:
            return None
        if self.last is not None and self.last.values is not None and np.any(recovered.step):
            # A moving fit that contradicts the primary route needs another
            # frame. Re-match that whole interval before accepting the handoff.
            return None
        local, a, b = recovered.source
        camera, ba, bb = recovered.background
        deforming = self.subject.deforming
        self.values = recovered.values
        self.roi = tuple(map(float, recovered.box))
        self.subject_origin, self.subject_box = tuple(recovered.origin), self.roi
        self.subject_corners = recovered.corners
        if not deforming:
            aligned = self.subject.align_origin(self.gray, self.subject_origin)
            offset = aligned-self.subject_origin
            self.subject_origin = tuple(aligned)
            self.subject_box = tuple(np.asarray(self.subject_box)+np.tile(offset, 2))
        self.needs_reference, self.loss_since, self.last_subject = False, None, stamp
        self.foreground_points, self.background_points = support_seeds(b), bb.copy()
        self.camera_transform = camera.copy()
        # Verified whole-interval pixel recovery can return to the precise
        # rigid route. Do not lock a briefly blurred small object into a
        # deforming-box fitter whose minimum distributed support it lacks.
        self.box_tracking = deforming
        self.local_model = "box" if deforming else "region"
        self.step_history.clear()
        corrected = (b-camera[:, 2]) @ np.linalg.inv(camera[:, :2]).T
        self.interaction.update(a, corrected, camera, stamp, self.gray.shape, None)
        self.target_data = (np.concatenate((a, ba)), np.concatenate((b, bb)), camera, a, b)
        self.counts = (len(self.subject.source)+len(self.subject.background), len(a)+len(ba), len(ba), len(a))
        h, w = self.gray.shape
        center = np.array((w/2, h/2, 1.))
        camera_shift = camera @ center-center[:2]
        camera_step = (camera_shift[0]/w*100, -camera_shift[1]/h*100,
                       100*math.log(np.sqrt(abs(np.linalg.det(camera[:, :2])))))
        self.reference = MotionReference('v2', 'ready', self.roi,
            vectors=sample_vectors(b-(corrected-a), b), background=sample_vectors(ba, bb),
            step=tuple(recovered.step), camera_step=camera_step, reason='subject_recovered', counts=self.counts,
            camera_model=self.camera_source, motion_dt=recovered.elapsed,
            local_model=self.local_model, focus=self._focus_status(stamp),
            subject_origin=self.subject_origin, subject_box=self.subject_box, support_groups=recovered.groups)
        self.subject.remember(self.gray, stamp, b, bb, self.subject_origin, self.subject_box, self.values,
                              deforming=deforming, corners=self.subject_corners)
        self.last = Observation(stamp, 'ready', tuple(self.values), self.subject_origin)
        return self.last, list(zip(a, corrected))

    def _focus_status(self, stamp):
        focus = self.patch_focus if self.local_model == 'patch' else self.region_focus
        return focus.status(stamp)

    @staticmethod
    def _focus_candidate(a, b, local, camera, w, h):
        relative = np.linalg.solve(camera[:, :2], local[:, :2])
        center = np.r_[a.mean(axis=0), 1.]
        shift = np.linalg.solve(camera[:, :2], (local-camera) @ center)
        step = np.array((shift[0]/w*100, -shift[1]/h*100,
                         100*math.log(np.sqrt(abs(np.linalg.det(relative))))))
        return ((*a.min(axis=0), *a.max(axis=0)),
                (*b.min(axis=0), *b.max(axis=0)), step)

    def _focus_region(self, a, b, masks, preferred, camera, tolerance, w, h, stamp):
        candidates, accepted = [], []
        # Bound extra fitting even on a busy image. Always include the prior.
        masks = [preferred]+sorted((m for m in masks if m is not preferred),
                                    key=lambda m: int(m.sum()), reverse=True)[:7]
        if self.roi is not None:
            covered = any(overlap((*a[m].min(axis=0), *a[m].max(axis=0)), self.roi) >= .5
                          for m in masks)
            if not covered:
                x1, y1, x2, y2 = self.roi
                prior = ((a[:, 0] >= x1) & (a[:, 0] <= x2)
                         & (a[:, 1] >= y1) & (a[:, 1] <= y2))
                masks.append(prior)
        for mask in masks:
            local, support = self._fit(a[mask], b[mask], tolerance)
            rigid = local is not None and support.sum() >= 8 and support.mean() >= .7
            if rigid:
                fa, fb = a[mask][support], b[mask][support]
                rigid = (np.ptp(fa[:, 0]) >= .08*w and np.ptp(fa[:, 1]) >= .08*h
                         and self._region_agreement(a, b, fa, local, tolerance))
            if not rigid:
                regional = box_fit(a[mask], b[mask], camera, (h, w), self.region_tracks[2])
                if regional is None:
                    continue
                fa, fb, local, _ = regional
            candidate = self._focus_candidate(fa, fb, local, camera, w, h)
            if abs(candidate[2][:2]).max() > 20 or abs(candidate[2][2]) > 6:
                continue
            candidates.append(candidate)
            accepted.append(mask)
        selected = self.region_focus.choose(candidates, stamp)
        self.focus_switched = self.region_focus.changed
        return preferred if selected is None else accepted[selected]

    def _local_patch(self, a, b, moving, tolerance, w, h, camera, stamp):
        """Find a supported part of a deforming region, not a rigid whole body."""
        points = a[moving]
        if len(points) < 8:
            return None
        centers = [(x, y) for x in np.quantile(points[:, 0], (.25, .5, .75))
                   for y in np.quantile(points[:, 1], (.25, .5, .75))]
        if self.roi is not None:
            x1, y1, x2, y2 = self.roi
            centers.insert(0, ((x1+x2)/2, (y1+y2)/2))
        results, observations, scores = [], [], []
        preferred = None
        candidates = [(center, radius) for center in centers for radius in (.16, .11)]
        for index, (center, radius) in enumerate(candidates):
            selected = np.all(abs(a-center) <= min(w, h)*radius, axis=1)
            if selected.sum() < 8 or moving[selected].mean() < .65:
                continue
            fa, fb = a[selected], b[selected]
            # A small body part can shear or change aspect ratio. Use a local
            # affine fit; the independent camera still uses similarity only.
            local, support = cv2.estimateAffine2D(fa, fb, method=cv2.RANSAC,
                ransacReprojThreshold=max(.25, tolerance*.45), maxIters=200)
            if local is None or support is None or not np.isfinite(local).all():
                continue
            support = support.ravel().astype(bool)
            singular = np.linalg.svd(local[:, :2], compute_uv=False)
            if (support.sum() < 8 or support.mean() < .7 or np.linalg.det(local[:, :2]) <= 0
                    or singular.min() < .75 or singular.max() > 1.3):
                continue
            spread = np.ptp(fa[support], axis=0)
            if spread[0] < .08*w or spread[1] < .08*h:
                continue
            if not self._region_agreement(a, b, fa[support], local, tolerance):
                continue
            if self.roi is not None and index < 2 and preferred is None:
                preferred = len(results)
            score = float(support.sum())
            if self.roi is not None:
                inside = ((fa[support, 0] >= x1) & (fa[support, 0] <= x2)
                          & (fa[support, 1] >= y1) & (fa[support, 1] <= y2))
                score *= 1+3*inside.mean()
            results.append((fa, fb, local, support))
            observations.append(self._focus_candidate(fa[support], fb[support], local, camera, w, h))
            scores.append(score)
        if not results:
            return None
        selected = self.patch_focus.choose(observations, stamp,
            preferred if preferred is not None else int(np.argmax(scores)), anchor=preferred)
        self.focus_switched |= self.patch_focus.changed
        return results[selected]

    @staticmethod
    def _region_agreement(a, b, selected, local, tolerance):
        lower, upper = selected.min(axis=0)-2, selected.max(axis=0)+2
        inside = np.all((a >= lower) & (a <= upper), axis=1)
        error = np.linalg.norm(b[inside]-(a[inside] @ local[:, :2].T+local[:, 2]), axis=1)
        return bool(len(error) and np.mean(error <= max(.25, tolerance*.45)) >= .65)

    def _pause_region(self, stamp, state, background, camera_step, camera):
        recovered = self._recover_subject(stamp)
        if recovered is not None:
            return recovered
        self.interaction.hold(stamp, camera)
        if self.subject.gray is not None:
            # Background newly exposed inside an old ROI is not proof that
            # the subject stopped. Its own pixels must establish a pause.
            return self._hold(stamp, state, background, camera_step)
        # Near a turn, coherent local velocity may fall below the noise floor.
        # Hold the accumulated measurement briefly instead of erasing the very
        # reversal history used to recognize a stroke. Never integrate noise.
        if self.roi is not None and self.region_tracks is not None:
            x1, y1, x2, y2 = self.roi
            a, b, noise = self.region_tracks
            inside = ((a[:, 0] >= x1) & (a[:, 0] <= x2) & (a[:, 1] >= y1) & (a[:, 1] <= y2))
            ra, rb = a[inside], b[inside]
            if len(ra) >= 4:
                residual = np.linalg.norm(rb-(ra @ camera[:, :2].T+camera[:, 2]), axis=1)
                stationary = residual <= noise*1.25
                if stationary.mean() >= .7 and stationary.sum() >= 4:
                    moved = np.array(((x1, y1), (x1, y2), (x2, y1), (x2, y2))) @ camera[:, :2].T+camera[:, 2]
                    self.roi = (*moved.min(axis=0), *moved.max(axis=0))
                    if self.subject_origin is not None:
                        self.subject_origin = tuple(camera[:, :2] @ self.subject_origin+camera[:, 2])
                        if self.subject_corners is not None:
                            self.subject_corners = self.subject_corners @ camera[:, :2].T+camera[:, 2]
                            self.subject_box = corner_bounds(self.subject_corners)
                            self.roi = self.subject_box
                        else:
                            self.subject_box = move_box(self.subject_box, camera)
                    self.last_subject, self.loss_since = stamp, None
                    self.step_history.clear()
                    self.counts = (*self.counts[:3], int(stationary.sum()))
                    self.reference = MotionReference("v2", "tracking", self.roi,
                        vectors=sample_vectors(rb[stationary], rb[stationary]),
                        background=background, camera_step=camera_step,
                        reason="stationary", counts=self.counts, camera_model=self.camera_source,
                        rescued=self.tracking_rescued, local_model=self.local_model,
                        focus=self._focus_status(stamp), subject_origin=self.subject_origin,
                        subject_box=self.subject_box)
                    self.last = Observation(stamp, "ready", tuple(self.values))
                    self.target_data = (a, b, camera, ra[stationary], rb[stationary])
                    return self.last, []
        return self._hold(stamp, state, background, camera_step)

    def update(self, gray, timestamp):
        self.target_data = None
        if not math.isfinite(timestamp) or (self.timestamp is not None and timestamp <= self.timestamp):
            return self.last, []
        self.interaction.step = 0.
        if self.gray is None or self.gray.shape != gray.shape or timestamp-self.timestamp > .5:
            self.__init__()
            self.gray, self.timestamp = gray.copy(), timestamp
            self.measured_at = timestamp
            self.gray_history.append((self.gray, timestamp))
            return self._hold(timestamp, "calibrating")
        if np.array_equal(gray, self.gray):
            # Screen capture often sees a decoded video frame more than once.
            # A zero-flow pair cannot confirm/reject ownership of motion layers.
            # Retain labels/history and never integrate the previous step again.
            self.timestamp = timestamp
            if self.needs_reference and self.last.state == "calibrating":
                # A blank startup image is missing evidence, not a valid pause.
                count = len(self._features(gray))
                if count < 6:
                    self.reason, self.counts = "features", (count, 0, 0, 0)
                    return self._hold(timestamp, "missing")
            valid = not self.needs_reference and self.last.values is not None
            if not valid and not self.needs_reference:
                # Repeating an occluded/rejected frame cannot restore confidence
                # or indefinitely extend the short reference-loss grace period.
                self._hold(timestamp, "missing", preserve_points=True)
            state = "tracking" if valid else self.reference.state
            self.reference = replace(self.reference, state=state,
                reason="repeated" if valid or state == "calibrating" else self.reference.reason,
                step=(0., 0., 0.), camera_step=(0., 0., 0.), rescued=0,
                motion_dt=0.,
                focus=self._focus_status(timestamp),
                vectors=tuple((end, end) for _, end in self.reference.vectors),
                background=tuple((end, end) for _, end in self.reference.background))
            self.last = Observation(timestamp, "ready" if valid else self.last.state,
                                    tuple(self.values) if valid else None)
            return self.last, []
        previous = self.gray
        self.previous_gray = previous
        self.dense_tracks = None
        measurement_dt = timestamp-self.measured_at
        self.measured_at = timestamp
        self.gray, self.timestamp = gray.copy(), timestamp
        self.discovery_pair = ((previous, self.gray_history[0][0])
            if len(self.gray_history) >= 3 and timestamp-self.gray_history[0][1] <= .2 else None)
        self.gray_history.append((self.gray, timestamp))
        self.region_tracks = None
        self.tracking_rescued = 0
        self.background_diagnostic = ()
        self.focus_switched = False
        # An empty/flat replacement frame is not a short corner dropout.
        if gray.std() < 2 and previous.std() >= 8:
            self.reason = "jump"
            self.counts = (0, 0, 0, 0)
            return self._hold(timestamp, "missing", hard=True)
        if self.last is not None and self.last.values is None and not self.needs_reference:
            recovered = self._recover_subject(timestamp)
            if recovered is not None:
                return recovered
        points = self._features(previous)
        background_seeds = self.background_points if self.camera_source == "minority" else None
        if background_seeds is None and self.layers.waiting:
            background_seeds = self.layers.pending
        if background_seeds is not None:
            # Sparse background identity must survive detector resampling too.
            # These are previous measured endpoints, never assumed new tracks.
            fresh = points.reshape(-1, 2)
            seeds = support_seeds(background_seeds) if len(background_seeds) > 72 else background_seeds
            if len(fresh):
                seeds = seeds[np.min(np.linalg.norm(seeds[:, None]-fresh[None], axis=2), axis=1) > 3]
            points = np.concatenate((fresh, seeds)).astype(np.float32).reshape(-1, 1, 2)
        if self.foreground_points is not None:
            # Retain distributed successful endpoints and replenish with the
            # normal grid. Every seed must pass current-pair tracking again.
            fresh = points.reshape(-1, 2)
            seeds = self.foreground_points
            if len(fresh):
                novel = np.min(np.linalg.norm(seeds[:, None]-fresh[None, :], axis=2), axis=1) > 3
                seeds = seeds[novel]
            points = np.concatenate((fresh, seeds)).astype(np.float32).reshape(-1, 1, 2)
            self.foreground_points = None
        self.counts = (len(points), 0, 0, 0)
        self.reason = "features"
        if len(points) < (4 if self.background_points is not None else 6):
            return self._hold(timestamp, "missing")
        self.reason = "tracking"
        h, w = gray.shape
        a, b, self.tracking_rescued = track_pair(previous, gray, points)
        self.counts = (len(points), len(a), 0, 0)
        if len(points) >= 12 and len(a) < max(4, len(points)*.1):
            if same_scene_structure(previous, gray):
                self.reason = 'fast_support'
                return self._hold(timestamp, 'missing')
            self.reason = "jump"
            return self._hold(timestamp, "missing", hard=True)
        edge = (a[:, 0] < .2*w) | (a[:, 0] > .8*w) | (a[:, 1] < .18*h) | (a[:, 1] > .82*h)
        tolerance = max(.7, max(h, w)/640)
        self.reason = "background"
        camera, indices = self._camera(a, b, edge, tolerance, w, h)
        if camera is None:
            return self._hold(timestamp, "missing")
        ba, bb = a[indices], b[indices]
        self.background_points, self.camera_transform = bb.copy(), camera.copy()
        self.counts = (len(points), len(a), len(ba), 0)
        bg_vectors = sample_vectors(ba, bb)
        center = np.array([w/2, h/2, 1])
        camera_shift = camera @ center - center[:2]
        camera_scale = np.sqrt(abs(np.linalg.det(camera[:, :2])))
        camera_step = (float(camera_shift[0]/w*100), float(-camera_shift[1]/h*100), float(100*math.log(camera_scale)))
        predicted = a @ camera[:, :2].T + camera[:, 2]
        residual = b-predicted
        bg_error = np.linalg.norm(bb-(ba @ camera[:, :2].T+camera[:, 2]), axis=1)
        noise = max(.16, float(np.percentile(bg_error, 85))*2.5)
        self.region_tracks = (a, b, noise)
        # Target ownership has its own fit. Keep valid camera correspondences
        # available even when the active motion region briefly fails below.
        source_mask = np.zeros(len(a), bool)
        if self.roi is not None:
            x1, y1, x2, y2 = self.roi
            source_mask = ((a[:, 0] >= x1) & (a[:, 0] <= x2)
                           & (a[:, 1] >= y1) & (a[:, 1] <= y2))
        self.target_data = (a, b, camera, a[source_mask], b[source_mask])
        # Moving foreground can reach an edge. Exclude camera inliers rather
        # than throwing out the entire perimeter of the image.
        moving = np.linalg.norm(residual, axis=1) > noise
        moving[indices] = False
        # The outer few pixels can be newly revealed/clipped by camera motion.
        moving &= ((a[:, 0] > .03*w) & (a[:, 0] < .97*w)
                   & (a[:, 1] > .03*h) & (a[:, 1] < .97*h))
        # Choose a connected spatial region, with preference for the existing
        # reference. This avoids mixing different independently moving objects.
        mask = np.zeros((h, w), np.uint8)
        for point in a[moving]:
            cv2.circle(mask, tuple(np.round(point).astype(int)), max(8, round(min(h, w)*.07)), 255, -1)
        count, labels = cv2.connectedComponents(mask)
        best, best_score = None, 0
        region_masks = []
        following_region = False
        if self.camera_source == "minority" and self.roi is not None:
            x1, y1, x2, y2 = self.roi
            prior = ((a[:, 0] >= x1) & (a[:, 0] <= x2) & (a[:, 1] >= y1) & (a[:, 1] <= y2))
            local, support = self._fit(a[prior], b[prior], tolerance)
            if local is not None and support.sum() >= 8 and support.mean() >= .7:
                chosen = np.flatnonzero(prior)[support]
                local_prediction = a[chosen] @ local[:, :2].T+local[:, 2]
                error = b[chosen]-local_prediction
                radius = np.sqrt(np.mean(np.sum((ba-ba.mean(axis=0))**2, axis=1)))
                reach = np.linalg.norm(a[chosen].mean(axis=0)-ba.mean(axis=0))/max(1., radius)
                uncertainty = (np.sqrt(np.mean(error**2))/np.sqrt(len(chosen))
                    + np.sqrt(np.mean(bg_error**2))/np.sqrt(len(ba))*(1+reach))
                threshold = max(.06, uncertainty*2.5)
                coherent = np.median(np.linalg.norm(local_prediction-predicted[chosen], axis=1))
                if coherent > threshold:
                    # The mean motion of an established coherent region can
                    # be measured below individual-point flow noise. Preserve
                    # small strokes without accepting arbitrary noisy points.
                    best = np.zeros(len(a), bool)
                    best[chosen] = True
                    best_score = float("inf")
                    following_region = True
                    noise = threshold/1.25
        for label in range(1, count):
            selected = moving & (labels[np.clip(a[:, 1].astype(int), 0, h-1), np.clip(a[:, 0].astype(int), 0, w-1)] == label)
            if selected.sum() < 4:
                continue
            region_masks.append(selected)
            score = float(selected.sum())
            if self.roi is not None:
                x1, y1, x2, y2 = self.roi
                overlap = ((a[selected, 0] >= x1) & (a[selected, 0] <= x2)
                           & (a[selected, 1] >= y1) & (a[selected, 1] <= y2)).mean()
                score *= 1+3*overlap
            if score > best_score:
                best, best_score = selected, score
        if best is None:
            self.reason = "region"
            return self._pause_region(timestamp, "camera_only", bg_vectors, camera_step, camera)
        focused = self._focus_region(a, b, region_masks, best, camera, tolerance, w, h, timestamp)
        following_region &= focused is best
        best = focused
        fa, fb = a[best], b[best]
        if self.box_tracking and self.roi is not None and not self.focus_switched:
            # Reversal changes which pixels pass the motion threshold, not
            # which object is being followed. Use all surviving subject cells.
            low, high = np.asarray(self.roi[:2]), np.asarray(self.roi[2:])
            owned = np.all((a >= low) & (a <= high), axis=1)
            owned[indices] = False
            fa, fb = a[owned], b[owned]
        self.reason = "region_fit"
        local, support = self._fit(fa, fb, max(tolerance, noise*2))
        stable = local is not None and support.sum() >= 4 and support.mean() >= .5
        regional = None
        if (self.box_tracking or not stable or (not following_region and
                not self._region_agreement(a, b, fa[support], local, tolerance))):
            # V1's whole motion envelope is more useful than an arbitrary
            # rigid patch when limbs/surfaces deform. Validate local coherence
            # across that envelope before falling back to a small rigid part.
            regional = box_fit(fa, fb, camera, (h, w), noise, prior=self.roi)
            if regional is None:
                regional = self._dense_box(camera, noise, fa, self.roi if self.box_tracking else None)
            if regional is not None and not self.box_tracking:
                ra, rb, transform, _ = regional
                deformation = np.median(np.linalg.norm(rb-(ra @ transform[:, :2].T+transform[:, 2]), axis=1))
                if deformation < .35:
                    # A noisy boundary around a rigid object is not an
                    # articulated subject. Preserve the precise established
                    # rigid/patch route, including radial/target measurements.
                    regional = None
            if regional is not None:
                fa, fb, local, support_groups = regional
                support = np.ones(len(fa), bool)
                self.local_model = "box"
                self.box_tracking = True
                following_region = self.roi is not None and not self.focus_switched
            else:
                if self.box_tracking:
                    # A hand/edge patch is not a replacement for an established
                    # whole-subject center. Briefly hold that identity instead.
                    return self._pause_region(timestamp, "missing", bg_vectors, camera_step, camera)
                patch = self._local_patch(a, b, moving, tolerance, w, h, camera, timestamp)
                if patch is None:
                    return self._pause_region(timestamp, "missing", bg_vectors, camera_step, camera)
                fa, fb, local, support = patch
                following_region = False
                self.local_model = "patch"
        elif not following_region:
            self.local_model = "region"
        fa, fb = fa[support], fb[support]
        if regional is None:
            averaged_local, support_groups = balanced_fit(fa, fb, local, max(tolerance, noise*2))
        else:
            averaged_local = local
        if not following_region and regional is None:
            # Validate a new region against ALL tracks in it, not only the
            # residual tail that nominated it. A handful of correlated LK
            # errors inside an otherwise rigid image is not a foreground.
            if (len(fa) < (6 if self.needs_reference else 4)
                    or not self._region_agreement(a, b, fa, local, tolerance)):
                return self._pause_region(timestamp, "camera_only", bg_vectors, camera_step, camera)
        self.counts = (len(points), len(a), len(ba), len(fa))
        used_residual = fb-(fa @ camera[:, :2].T+camera[:, 2])
        fitted_residual = fa @ (local[:, :2]-camera[:, :2]).T+local[:, 2]-camera[:, 2]
        # Large residual magnitudes alone can be mutually cancelling LK
        # errors. The fitted region must also move differently from camera.
        if regional is None and min(np.median(np.linalg.norm(used_residual, axis=1)),
               np.median(np.linalg.norm(fitted_residual, axis=1))) < noise*1.25:
            return self._pause_region(timestamp, "camera_only", bg_vectors, camera_step, camera)
        box = (*np.min(fb, axis=0), *np.max(fb, axis=0))
        if following_region:
            # A fresh corner grid samples inside the old ROI. Its bounding
            # box shrinks every frame; propagate the tracked region instead.
            # Carry the original corners, not an ever-expanding axis-aligned
            # envelope. Even alternating tiny rotations otherwise inflate it.
            corners = self.subject_corners if self.box_tracking and self.subject_corners is not None else box_corners(self.roi)
            moved = corners @ local[:, :2].T+local[:, 2]
            box = (*np.maximum((0, 0), moved.min(axis=0)),
                   *np.minimum((w-1, h-1), moved.max(axis=0)))
        if (box[2]-box[0]) < .08*w or (box[3]-box[1]) < .08*h:
            return self._pause_region(timestamp, "missing", bg_vectors, camera_step, camera)
        # Validate ownership against the original robust fit. Balanced averaging
        # is a measurement refinement and must not reject a deforming region
        # that has already passed the neighboring-track checks.
        local = averaged_local
        background_transform, local_transform = np.eye(3), np.eye(3)
        background_transform[:2], local_transform[:2] = camera, local
        relative = np.linalg.inv(background_transform) @ local_transform
        # All axes measure the same transported subject center. A fresh
        # feature centroid moves when points disappear and leaks zoom/rotation
        # into translation even when the subject itself has not translated.
        focal = np.r_[self.subject_origin if self.subject_origin is not None else np.mean(fa, axis=0), 1]
        shift = relative @ focal - focal
        step = np.array((shift[0]/w*100, -shift[1]/h*100,
                         100*math.log(np.sqrt(abs(np.linalg.det(relative[:2, :2]))))))
        scale_floor = scale_uncertainty(fa, fb, local, ba, bb, camera)
        if regional is not None:
            scale_floor = max(scale_floor, box_scale_uncertainty(support_groups, local))
        if abs(step[2]) <= scale_floor:
            step[2] = 0.
        # Speed alone is not a cut. Large translations need a broad, strongly
        # agreeing local fit; scale jumps retain the stricter cut threshold.
        fast = abs(step[:2]).max() > 6
        fit_error = np.linalg.norm(fb-(fa @ local[:, :2].T+local[:, 2]), axis=1)
        fast_supported = (len(fa) >= 12 and support.mean() >= .65
            and np.percentile(fit_error, 85) <= max(.4, tolerance*.7)
            and cv2.contourArea(cv2.convexHull(fa))/(w*h) >= .04)
        # A compact body part need not cover 4% of the entire image. Demand
        # stronger agreement and a genuinely two-dimensional set of tracks.
        spread = np.ptp(fa, axis=0)
        compact_supported = (len(fa) >= 12 and len(ba) >= 8 and support.mean() >= .75
            and np.percentile(fit_error, 85) <= max(.3, tolerance*.4)
            and spread[0] >= .08*w and spread[1] >= .08*h
            and cv2.contourArea(cv2.convexHull(fa)) >= .45*spread[0]*spread[1])
        if regional is not None:
            fast_supported = len(fa) >= 24 and len(support_groups) >= 6 and len(ba) >= 8
        if not np.isfinite(step).all() or abs(step[2]) > 6 or abs(step[:2]).max() > 20:
            self.reason = "jump"
            return self._hold(timestamp, "missing", bg_vectors, camera_step, hard=True)
        if fast and not (fast_supported or compact_supported):
            self.reason = "fast_support"
            return self._hold(timestamp, "missing", bg_vectors, camera_step)
        # Nearby parts share an image reference; switch only future measured
        # increments. Do not erase stroke history for overlapping patch fits.
        changed_region = False
        if self.roi is not None:
            old_center = np.array(((self.roi[0]+self.roi[2])/2, (self.roi[1]+self.roi[3])/2))
            expected_center = camera[:, :2] @ old_center + camera[:, 2]
            overlap_w = max(0, min(box[2], self.roi[2])-max(box[0], self.roi[0]))
            overlap_h = max(0, min(box[3], self.roi[3])-max(box[1], self.roi[1]))
            before_matches = np.mean((fa[:, 0] >= self.roi[0]) & (fa[:, 0] <= self.roi[2])
                                    & (fa[:, 1] >= self.roi[1]) & (fa[:, 1] <= self.roi[3]))
            changed_region |= (before_matches < .5 and overlap_w*overlap_h == 0
                              and np.linalg.norm(np.mean(fb, axis=0)-expected_center) > .2*min(h, w))
        if self.needs_reference or changed_region:
            self.subject_confirmed = False
            self.subject_origin = tuple((np.asarray(box[:2])+box[2:])/2)
            self.subject_box = tuple(box)
            self.subject_corners = box_corners(box) if regional is not None else None
            if regional is None:
                self.subject_origin = tuple(self.subject.align_origin(gray, self.subject_origin, new=True))
            else:
                self.subject.anchor_patch = None
            self.values[:] = 0
            self.step_history.clear()
            state = "calibrating"
        else:
            if self.subject_origin is not None:
                self.subject_origin = tuple(local[:, :2] @ self.subject_origin+local[:, 2])
                if self.local_model == "box":
                    if self.subject_corners is None:
                        self.subject_corners = box_corners(self.subject_box)
                    self.subject_corners = self.subject_corners @ local[:, :2].T+local[:, 2]
                    self.subject_box = corner_bounds(self.subject_corners)
                else:
                    self.subject_corners = None
                    self.subject_box = move_box(self.subject_box, local)
                if self.local_model != "box":
                    aligned = self.subject.align_origin(gray, self.subject_origin)
                    offset = aligned-self.subject_origin
                    self.subject_origin = tuple(aligned)
                    self.subject_box = tuple(np.asarray(self.subject_box)+np.tile(offset, 2))
            # V1's short median history rejects isolated translation spikes.
            # Apply it only after camera compensation and jump validation;
            # raw tracked endpoints remain intact for rotation estimation.
            self.step_history.append(step.copy())
            step = np.median(self.step_history, axis=0)
            self.values += step
            state = "ready"
            self.subject_confirmed = True
        self.roi, self.last_subject = tuple(float(v) for v in box), timestamp
        self.foreground_points = support_seeds(fb)
        self.needs_reference = False
        self.loss_since = None
        # Unwarp the actual tracked endpoints, not the fitted similarity.
        # Preserve local perspective/deformation for the existing R0/R2
        # estimator and for honest reference arrows in the preview.
        corrected = (fb-camera[:, 2]) @ np.linalg.inv(camera[:, :2]).T
        if state == 'calibrating':
            self.interaction = InteractionPoint()
        longer = (None if state != 'ready' or self.discovery_pair is None else
                  lambda: long_convergence(gray, self.discovery_pair[1], fb, bb))
        self.interaction.update(fa, corrected, camera, timestamp, (h, w), longer)
        self.target_data = (a, b, camera, fa, fb)
        self.subject.remember(gray, timestamp, fb, bb, self.subject_origin, self.subject_box, self.values,
                              deforming=self.box_tracking, corners=self.subject_corners)
        # Display compensated vectors at the actual current feature locations.
        self.reference = MotionReference("v2", state, self.roi,
            sample_vectors(fb-(corrected-fa), fb), bg_vectors, tuple(step), camera_step,
            counts=self.counts, camera_model=self.camera_source, rescued=self.tracking_rescued,
            local_model=self.local_model, motion_dt=measurement_dt, focus=self._focus_status(timestamp),
            support_groups=support_groups, subject_origin=self.subject_origin, subject_box=self.subject_box)
        self.last = Observation(timestamp, state, tuple(self.values) if state == "ready" else None,
                                self.subject_origin)
        return self.last, list(zip(fa, corrected)) if state == "ready" else []
