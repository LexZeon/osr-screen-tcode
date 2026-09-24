"""Spatially balanced motion of a deforming subject box.

Own implementation using existing OpenCV/NumPy dependencies. Inspired by the
released v1 motion envelope and median-flow tracking: verify neighboring point
motions, then give image regions equal weight instead of requiring one rigid
transform to explain every limb. Camera ownership is verified by the caller.
"""
import cv2
import numpy as np

from .region_support import cells
from .motion_tracking import _patch_errors


class DenseRegionFlow:
    """V1's DIS flow with explicit round-trip/appearance verification.

    Used on demand for deforming or sparsely sampled subjects. No previous
    velocity is passed as a prediction, and point count stays bounded.
    """
    def __init__(self):
        self.forward = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
        self.backward = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
        self.forward.setFinestScale(1)
        self.backward.setFinestScale(1)

    def track(self, previous, gray):
        h, w = gray.shape
        if min(h, w) < 24:
            return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32)
        flow = self.forward.calc(previous, gray, None)
        reverse = self.backward.calc(gray, previous, None)
        stride = max(5, int(np.ceil(np.sqrt(w*h/1200))))
        yy, xx = np.mgrid[7:h-7:stride, 7:w-7:stride]
        a = np.column_stack((xx.ravel(), yy.ravel())).astype(np.float32)
        b = a+flow[yy.ravel(), xx.ravel()]
        back = cv2.remap(reverse, b[:, 0:1], b[:, 1:2], cv2.INTER_LINEAR)[:, 0]
        error = np.linalg.norm(b+back-a, axis=1)
        image = previous.astype(np.float32)
        contrast = np.maximum(0, cv2.blur(image*image, (9, 9))-cv2.blur(image, (9, 9))**2)
        good = (np.isfinite(b).all(axis=1) & (error < .85)
                & (contrast[yy.ravel(), xx.ravel()] > 16)
                & np.all((b >= 5) & (b < (w-5, h-5)), axis=1))
        a, b = a[good], b[good]
        if len(a):
            good = _patch_errors(previous, gray, a, b) < 20
            a, b = a[good], b[good]
        return a, b


def coherent_support(points, displacement, shape):
    """Leave-one-out local affine prediction; never validate a point by itself.

    A smoothly deforming surface can have different velocities at neighboring
    points. Predict the central velocity from neighbors, checking both the
    prediction and its residuals. Random or isolated large flows must fail.
    """
    points, displacement = np.asarray(points, float), np.asarray(displacement, float)
    count = len(points)
    if count < 8:
        return np.zeros(count, bool)
    distance = np.sum((points[:, None]-points[None])**2, axis=2)
    np.fill_diagonal(distance, np.inf)
    k = min(8, count-1)
    neighbors = np.argsort(distance, axis=1)[:, :k]
    offsets = (points[neighbors]-points[:, None])/max(1., min(shape)*.12)
    design = np.concatenate((np.ones((count, k, 1)), offsets), axis=2)
    fits = np.linalg.pinv(design) @ displacement[neighbors]
    predicted = fits[:, 0]
    error = np.linalg.norm(predicted-displacement, axis=1)
    scatter = np.median(np.linalg.norm(design @ fits-displacement[neighbors], axis=2), axis=1)
    radius = np.take_along_axis(distance, neighbors, axis=1)
    # Eight nearby points spanning two dimensions are independent evidence.
    spread = np.linalg.svd(offsets, compute_uv=False)[:, -1]
    limit = np.maximum(.55, np.linalg.norm(displacement, axis=1)*.14)
    return ((radius[:, 5] < (min(shape)*.22)**2) & (spread > .12)
            & (error < limit) & (scatter < limit))


def box_fit(a, b, camera, shape, noise, *, prior=None):
    """Fit the center/scale of one motion envelope from distributed support.

    Returns actual correspondences as well as the fitted box transform. These
    measured point pairs, not synthetic similarity points, feed rotation and
    target analysis. A rigid fit remains preferable when one exists.
    """
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if len(a) < 18:
        return None
    residual = b-(a @ camera[:, :2].T+camera[:, 2])
    # Pixels newly exposed around a moving box can be perfectly tracked
    # background. They must not enter the subject's recovery memory. At an
    # actual pause the caller verifies the previous subject cohort instead.
    independent = np.linalg.norm(residual, axis=1) > max(.06, noise*.5)
    if independent.sum() < 18 or independent.mean() < .55:
        return None
    a, b, residual = a[independent], b[independent], residual[independent]
    support = coherent_support(a, residual, shape)
    if support.sum() < 14 or support.mean() < .6:
        return None
    a, b, residual = a[support], b[support], residual[support]
    h, w = shape
    extent = np.ptp(a, axis=0)
    if np.any(extent < np.array((w, h))*.12):
        return None
    groups = cells(a)
    used = [g for g in np.unique(groups) if np.sum(groups == g) >= 2]
    if len(used) < 5:
        return None
    starts = np.array([np.median(a[groups == g], axis=0) for g in used])
    # Center transport uses median displacement per cell. A dense texture or
    # a moving hand cannot outweigh the rest of the subject just by point count.
    shifts = np.array([np.median((b-a)[groups == g], axis=0) for g in used])
    ca = starts.mean(axis=0)
    dx = starts-ca
    velocities = shifts-shifts.mean(axis=0)
    denominator = np.sum(dx*dx)
    if denominator < 100:
        return None
    scale = 1+np.sum(dx*velocities)/denominator
    turn = np.sum(dx[:, 0]*velocities[:, 1]-dx[:, 1]*velocities[:, 0])/denominator
    linear = np.array(((scale, -turn), (turn, scale)))
    transform = np.column_stack((linear, ca+shifts.mean(axis=0)-linear @ ca))
    if not .9 < np.hypot(scale, turn) < 1.1:
        return None
    # Coherent local deformation is allowed; a mixture of opposite independent
    # motions with no common translation is not a whole-subject displacement.
    center = np.array(((prior[0]+prior[2])/2, (prior[1]+prior[3])/2)) if prior else ca
    relative_shift = (transform-camera) @ np.r_[center, 1.]
    if prior is None and np.linalg.norm(relative_shift) < max(.18, noise*1.25):
        return None
    supports = tuple((tuple(start), tuple(start+shift)) for start, shift in zip(starts, shifts))
    return a, b, transform, supports


def box_scale_uncertainty(groups, transform):
    """Correlated deformation has cell-level, not per-pixel, uncertainty."""
    if len(groups) < 3:
        return float('inf')
    a, b = np.asarray(groups, float).transpose(1, 0, 2)
    residual = b-(a @ transform[:, :2].T+transform[:, 2])
    radius = max(1., np.sqrt(np.mean(np.sum((a-a.mean(axis=0))**2, axis=1))))
    return 300*np.sqrt(np.mean(residual**2))/(np.sqrt(len(a))*radius)
