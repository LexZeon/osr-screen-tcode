"""Spatially balanced, measured support within one already validated region."""
import numpy as np


def cells(points):
    points = np.asarray(points).reshape(-1, 2)
    low = points.min(axis=0)
    size = np.maximum(1., np.ptp(points, axis=0))
    grid = np.clip(((points-low)/size*3).astype(int), 0, 2)
    return grid[:, 1]*3+grid[:, 0]


def support_seeds(points):
    points = np.asarray(points, np.float32).reshape(-1, 2)
    if len(points) < 4:
        return None
    groups = cells(points)
    keep = []
    for cell in np.unique(groups):
        indices = np.flatnonzero(groups == cell)
        keep.extend(indices[np.linspace(0, len(indices)-1, min(6, len(indices))).astype(int)])
    return points[keep].copy()


def balanced_fit(a, b, fallback, tolerance):
    """Equal cell weight prevents texture density from controlling the mean.

    Inputs have already passed LK, background separation and regional RANSAC.
    This never restores rejected points or mixes separate motion regions.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 8:
        return fallback, ()
    groups = cells(a)
    unique, counts = np.unique(groups, return_counts=True)
    if len(unique) < 3:
        return fallback, ()
    weights = np.zeros(len(a))
    for group, count in zip(unique, counts):
        weights[groups == group] = 1/count
    base_weights = weights.copy()
    for _ in range(3):
        weights /= weights.sum()
        ca, cb = weights @ a, weights @ b
        x, y = a-ca, b-cb
        denominator = np.sum(weights*np.sum(x*x, axis=1))
        if denominator < 25:
            return fallback, ()
        scale = np.sum(weights*np.sum(x*y, axis=1))/denominator
        turn = np.sum(weights*(x[:, 0]*y[:, 1]-x[:, 1]*y[:, 0]))/denominator
        matrix = np.array(((scale, -turn), (turn, scale)))
        transform = np.column_stack((matrix, cb-matrix @ ca))
        residual = b-(a @ matrix.T+transform[:, 2])
        group_error = np.array([np.linalg.norm(residual[groups == group].mean(axis=0)) for group in unique])
        cutoff = max(.08, 2.5*float(np.median(group_error)))
        weights = base_weights.copy()
        for group, error in zip(unique, group_error):
            weights[groups == group] *= min(1., cutoff/max(error, 1e-9))**2
    error = np.linalg.norm(b-(a @ matrix.T+transform[:, 2]), axis=1)
    if not .85 < np.hypot(scale, turn) < 1.18 or np.percentile(error, 85) > max(.4, tolerance):
        return fallback, ()
    # Actual averaged endpoints, useful for the preview and regression checks.
    supports = tuple((tuple(a[groups == group].mean(axis=0)),
                      tuple(b[groups == group].mean(axis=0))) for group in unique)
    return transform, supports
