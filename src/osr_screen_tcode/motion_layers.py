"""Separate competing image motions before assigning a camera reference.

Independent implementation using OpenCV similarity fits. A large foreground
must not win the camera estimate solely by corner count. This is a geometric
heuristic, not semantic segmentation or a physical camera/depth measurement.
"""
import cv2
import numpy as np

from .regional_flow import coherent_support


def locally_coherent_motion(points, residual, w, h):
    """Validate deforming foreground by neighboring compensated flows.

    This supplies evidence of an independently moving subject, not a camera
    transform. Random tracks cannot pass just by having large displacements.
    """
    count = len(points)
    if count < 6:
        return np.zeros(count, bool)
    distance = np.sum((points[:, None]-points[None])**2, axis=2)
    np.fill_diagonal(distance, np.inf)
    k = min(6, count-1)
    neighbors = np.argpartition(distance, k-1, axis=1)[:, :k]
    separation = np.take_along_axis(distance, neighbors, axis=1)
    nearby = (separation > 1.) & (separation < (min(w, h)*.14)**2)
    speed = np.linalg.norm(residual, axis=1)
    neighbor_speed = speed[neighbors]
    alignment = np.sum(residual[:, None]*residual[neighbors], axis=2)
    difference = np.linalg.norm(residual[:, None]-residual[neighbors], axis=2)
    agreement = (nearby & (alignment >= .8*speed[:, None]*neighbor_speed)
                 & (difference <= np.maximum(.35, .45*np.minimum(speed[:, None], neighbor_speed))))
    return agreement.sum(axis=1) >= 3


def motion_layers(a, b, tolerance):
    """Peel at most six coherent groups, allowing articulated foregrounds."""
    remaining = np.arange(len(a))
    groups = []
    for _ in range(6):
        if len(remaining) < 6:
            break
        matrix, mask = cv2.estimateAffinePartial2D(a[remaining], b[remaining],
            method=cv2.RANSAC, ransacReprojThreshold=tolerance, maxIters=400)
        if matrix is None or mask is None or not np.isfinite(matrix).all():
            break
        indices = remaining[mask.ravel().astype(bool)]
        if len(indices) < 6 or not .85 < np.sqrt(abs(np.linalg.det(matrix[:, :2]))) < 1.18:
            break
        error = np.linalg.norm(b-(a @ matrix[:, :2].T+matrix[:, 2]), axis=1)
        indices = np.flatnonzero(error <= tolerance)
        groups.append((matrix, indices, error))
        remaining = remaining[error[remaining] > tolerance*1.5]
    return groups


class MinorityBackground:
    def __init__(self):
        self.pending = None
        self.confirmations = 0
        self.waiting = False
        self.diagnostic = ("groups", 0, 0)

    def reset(self):
        self.pending = None
        self.confirmations = 0
        self.waiting = False
        self.diagnostic = ("groups", 0, 0)

    def select(self, a, b, w, h, match_points=None, foreground=None, camera_eligible=None):
        self.waiting = False
        tolerance = max(.22, max(w, h)/1600)
        groups = motion_layers(a, b, tolerance)
        # A continuously deforming majority may consume all six RANSAC
        # proposals. Give each thin perimeter strip its own camera proposal;
        # it still has to pass every independent ownership check below.
        for subset in (a[:, 1] < .13*h, a[:, 1] > .87*h,
                       a[:, 0] < .13*w, a[:, 0] > .87*w):
            for matrix, _, _ in motion_layers(a[subset], b[subset], tolerance)[:1]:
                error = np.linalg.norm(b-(a @ matrix[:, :2].T+matrix[:, 2]), axis=1)
                members = np.flatnonzero(error <= tolerance)
                if len(members) >= 6:
                    groups.append((matrix, members, error))
        best = None
        stage = -1
        self.diagnostic = ("groups", 0, len(groups))
        def reject(rank, reason, indices):
            nonlocal stage
            if rank > stage or (rank == stage and len(indices) > self.diagnostic[1]):
                stage = rank
                self.diagnostic = (reason, len(indices), len(groups))
        for camera, indices, error in groups:
            if camera_eligible is not None:
                indices = indices[camera_eligible[indices]]
                if len(indices) < 6:
                    reject(0, "texture", indices)
                    continue
                # A handful of interpolated gradients on a blurred wall can
                # agree geometrically yet not locate a small camera patch.
                camera, support = cv2.estimateAffinePartial2D(a[indices], b[indices],
                    method=cv2.RANSAC, ransacReprojThreshold=tolerance, maxIters=200)
                if camera is None or support is None:
                    continue
                indices = indices[support.ravel().astype(bool)]
                if len(indices) < 6:
                    continue
                error = np.linalg.norm(b-(a @ camera[:, :2].T+camera[:, 2]), axis=1)
            ba = a[indices]
            spread = np.ptp(ba, axis=0)/np.array((w, h))
            # A small patch still constrains a similarity if its points span
            # two dimensions. Do not require a fraction of the whole image.
            if max(spread) < .12 or min(spread) < .025:
                reject(0, "extent", indices)
                continue
            normalized = ba/np.array((w, h))
            border_distance = np.minimum(normalized, 1-normalized).min(axis=1)
            peripheral = float(np.mean(border_distance < .13))
            if peripheral < .8:
                reject(1, "periphery", indices)
                continue
            others = np.flatnonzero(error > max(.45, tolerance*2))
            if len(others) < 18:
                reject(2, "separation", indices)
                continue
            fa = a[others]
            area = cv2.contourArea(cv2.convexHull(fa))/(w*h)
            # This route is specifically for a large, coherent foreground.
            # A small peripheral moving object is not evidence of a camera.
            if area < .28:
                reject(3, "foreground_extent", indices)
                continue
            # Different body parts need not share one rigid transform. Count
            # independently coherent, spatially supported foreground layers.
            coherent = np.zeros(len(a), bool)
            for _, members, _ in groups:
                members = np.intersect1d(members, others)
                if len(members) >= 6 and cv2.contourArea(cv2.convexHull(a[members]))/(w*h) >= .025:
                    coherent[members] = True
            if coherent[others].mean() < .65:
                # Articulated/non-rigid subjects need not fit six whole-region
                # similarities. Require local flow agreement instead, keeping
                # all independent camera extent/ownership/uncertainty checks.
                residual = b[others]-(fa @ camera[:, :2].T+camera[:, 2])
                coherent[others] |= locally_coherent_motion(fa, residual, w, h)
                coherent[others] |= coherent_support(fa, residual, (h, w))
            if coherent[others].mean() < .65:
                # Dense, independently verified DIS samples can establish a
                # deforming majority without pretending it is a rigid layer.
                fa = foreground(camera) if foreground is not None else None
                if fa is None or len(fa) < 24 or cv2.contourArea(cv2.convexHull(fa))/(w*h) < .28:
                    reject(4, "foreground_fit", indices)
                    continue
            else:
                fa = a[coherent]
            fg_normalized = fa/np.array((w, h))
            fg_border = np.minimum(fg_normalized, 1-fg_normalized).min(axis=1)
            if np.median(fg_border)-np.median(border_distance) < .07:
                reject(5, "ownership", indices)
                continue
            # Limit extrapolation error from a small patch to the foreground.
            radius = np.linalg.norm(ba-ba.mean(axis=0), axis=1)
            extrapolation = np.linalg.norm(fa.mean(axis=0)-ba.mean(axis=0))/max(1., np.sqrt(np.mean(radius**2)))
            uncertainty = float(np.sqrt(np.mean(error[indices]**2)))*(1+extrapolation)
            if uncertainty > max(.4, max(w, h)/1000):
                reject(6, "uncertainty", indices)
                continue
            score = (peripheral + float(np.median(fg_border)-np.median(border_distance))
                     + .1*np.log1p(len(indices))-.5*uncertainty)
            if best is None or score > best[0]:
                best = (score, camera, indices)
        if best is None:
            self.pending, self.confirmations = None, 0
            return None, None
        _, camera, indices = best
        matched = 0
        if self.pending is not None:
            current_reference = a if match_points is None else match_points
            distances = np.linalg.norm(current_reference[indices, None]-self.pending[None], axis=2)
            matched = int((distances.min(axis=1) < max(3., max(w, h)/160)).sum())
        self.confirmations = self.confirmations+1 if matched >= 4 else 1
        self.pending = b[indices].copy()
        # Two independent frame pairs establish a new minority background;
        # subsequent frames are remeasured using the confirmed background.
        self.waiting = self.confirmations < 2
        self.diagnostic = ("confirm" if self.waiting else "accepted", len(indices), len(groups))
        return (None, None) if self.waiting else (camera, indices)
