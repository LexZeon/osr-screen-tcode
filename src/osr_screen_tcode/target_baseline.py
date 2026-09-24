"""Locate flow convergence over a longer, independently checked frame pair.

Only the point estimate uses this pair. L0 increments always use current-frame
measurements, so a multi-frame displacement is never integrated twice.
"""
import cv2
import numpy as np

from .interaction_point import _radial_fit
from .motion_tracking import track_pair


def long_convergence(current, older, foreground, background):
    if len(foreground) < 12 or len(background) < 8:
        return None
    fg = foreground[np.linspace(0, len(foreground)-1, min(54, len(foreground))).astype(int)]
    bg = background[np.linspace(0, len(background)-1, min(36, len(background))).astype(int)]
    points = np.concatenate((fg, bg)).astype(np.float32).reshape(-1, 1, 2)
    # A secondary point estimate must not add expensive fast-patch searches to
    # the realtime path. Unmatched older features simply provide no evidence.
    now, past, _ = track_pair(current, older, points, recover=False)
    if len(now) < 20:
        return None
    local = np.min(np.linalg.norm(now[:, None]-fg, axis=2), axis=1) < .01
    ba, bb = past[~local], now[~local]
    if len(ba) < 8 or local.sum() < 12:
        return None
    camera, inliers = cv2.estimateAffinePartial2D(ba, bb, method=cv2.RANSAC,
        ransacReprojThreshold=.7, maxIters=300)
    if camera is None or not np.isfinite(camera).all():
        return None
    mask = inliers.ravel().astype(bool)
    if mask.sum() < 8 or mask.mean() < .8 or not .65 < np.sqrt(abs(np.linalg.det(camera[:, :2]))) < 1.5:
        return None
    ba, bb = ba[mask], bb[mask]
    scatter = ba-ba.mean(axis=0)
    eigenvalues = np.linalg.eigvalsh(scatter.T @ scatter/len(ba))
    if eigenvalues[0] < max(4., eigenvalues[-1]*.005):
        return None
    rms = float(np.sqrt(np.mean(np.sum((bb-(ba @ camera[:, :2].T+camera[:, 2]))**2, axis=1))))
    if rms > .25:
        return None
    corrected = (now[local]-camera[:, 2]) @ np.linalg.inv(camera[:, :2]).T
    fit = _radial_fit(past[local], corrected)
    found = None if fit is None else fit.candidate(current.shape)
    if found is None:
        return None
    point, fraction, uncertainty = found
    # Background uncertainty is shared by all local points, so it must not
    # shrink with foreground feature count when extrapolating a distant focus.
    radius = max(1., np.sqrt(np.mean(np.sum(scatter**2, axis=1))))
    camera_error = rms/np.sqrt(len(ba))*(1+np.linalg.norm(point-ba.mean(axis=0))/radius)
    uncertainty = float(np.hypot(uncertainty, camera_error/abs(fit.k)))
    if uncertainty > min(current.shape)*.025:
        return None
    point = camera[:, :2] @ point+camera[:, 2]
    if not ((0, 0) <= point).all() or not (point < current.shape[::-1]).all():
        return None
    return point, fraction, uncertainty
