"""Measured sparse tracks for v2, including small patches and fast translation.

Fine-scale flow keeps a small background independent of a large foreground.
Bounded, unambiguous patch matches seed failed fast tracks; they do not supply
camera labels or extrapolated output. No templates survive a frame pair.
"""
import cv2
import numpy as np


def _valid(points, forward, ok, back, reverse, shape):
    h, w = shape
    valid = (ok.ravel() == 1) & (reverse.ravel() == 1)
    valid &= np.isfinite(forward[:, 0]).all(axis=1)
    valid &= np.linalg.norm(back[:, 0]-points[:, 0], axis=1) < .8
    valid &= ((forward[:, 0, 0] >= 0) & (forward[:, 0, 0] < w)
              & (forward[:, 0, 1] >= 0) & (forward[:, 0, 1] < h))
    return valid


def _patch_errors(previous, gray, a, b):
    offsets = np.mgrid[-4:5, -4:5].reshape(2, -1)[::-1].T.astype(np.float32)
    first_map = np.asarray(a, np.float32)[:, None]+offsets
    second_map = np.asarray(b, np.float32)[:, None]+offsets
    finite = np.isfinite(second_map).all(axis=(1, 2))
    second_map[~finite] = 0
    first = cv2.remap(previous, first_map[:, :, 0], first_map[:, :, 1],
                      cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    second = cv2.remap(gray, second_map[:, :, 0], second_map[:, :, 1],
                       cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    errors = np.mean(np.abs(first.astype(np.float32)-second), axis=1)
    errors[~finite] = np.inf
    return errors


def track_pair(previous, gray, points, *, recover=True):
    forward, ok, _ = cv2.calcOpticalFlowPyrLK(previous, gray, points, None)
    if forward is None:
        return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), 0
    back, reverse, _ = cv2.calcOpticalFlowPyrLK(gray, previous, forward, None)
    if back is None:
        return np.empty((0, 2), np.float32), np.empty((0, 2), np.float32), 0
    valid = _valid(points, forward, ok, back, reverse, gray.shape)
    # A textureless pair is also useful to callers injecting known tracks.
    if previous.std() < 2:
        return points[valid, 0], forward[valid, 0], 0
    errors = _patch_errors(previous, gray, points[:, 0], forward[:, 0])
    fine, status, _ = cv2.calcOpticalFlowPyrLK(previous, gray, points, None,
                                            winSize=(11, 11), maxLevel=0)
    if fine is not None:
        back, reverse, _ = cv2.calcOpticalFlowPyrLK(gray, previous, fine, None,
                                                  winSize=(11, 11), maxLevel=0)
        if back is not None:
            good = _valid(points, fine, status, back, reverse, gray.shape)
            cost = _patch_errors(previous, gray, points[:, 0], fine[:, 0])
            choose = good & ((~valid & (cost < 12)) | (cost+.5 < errors*.8))
            forward[choose] = fine[choose]
            valid[choose], errors[choose] = True, cost[choose]
    # Track count alone can look healthy while fast regions have disappeared.
    # Search a spatially distributed subset of failed/poor matches, bounded
    # to 48 patches and 20% of the frame. Repeated text must have a unique peak.
    failed = np.flatnonzero(~valid | (errors > 18))
    rescued = 0
    if recover and len(failed) >= 6:
        h, w = gray.shape
        rx, ry, radius = min(96, round(w*.2)), min(96, round(h*.2)), 7
        chosen = failed[np.linspace(0, len(failed)-1, min(48, len(failed))).astype(int)]
        seeds, selected = [], []
        for index in chosen:
            x, y = np.rint(points[index, 0]).astype(int)
            if not (radius <= x < w-radius and radius <= y < h-radius):
                continue
            patch = previous[y-radius:y+radius+1, x-radius:x+radius+1]
            if patch.std() < 8:
                continue
            x1, y1 = max(0, x-rx-radius), max(0, y-ry-radius)
            x2, y2 = min(w, x+rx+radius+1), min(h, y+ry+radius+1)
            scores = cv2.matchTemplate(gray[y1:y2, x1:x2], patch, cv2.TM_CCOEFF_NORMED)
            _, peak, _, (px, py) = cv2.minMaxLoc(scores)
            if peak < .88:
                continue
            scores[max(0, py-3):py+4, max(0, px-3):px+4] = -1
            if peak-float(scores.max()) < .05:
                continue
            selected.append(index)
            seeds.append(points[index, 0]+(px+x1+radius-x, py+y1+radius-y))
        if selected:
            source = points[selected].copy()
            seed = np.asarray(seeds, np.float32).reshape(-1, 1, 2).copy()
            found, status, _ = cv2.calcOpticalFlowPyrLK(previous, gray, source, seed,
                winSize=(15, 15), maxLevel=0, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
            back, reverse, _ = cv2.calcOpticalFlowPyrLK(gray, previous, found, source.copy(),
                winSize=(15, 15), maxLevel=0, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
            good = _valid(source, found, status, back, reverse, gray.shape)
            good &= _patch_errors(previous, gray, source[:, 0], found[:, 0]) < 12
            indices = np.asarray(selected)[good]
            forward[indices], valid[indices] = found[good], True
            rescued = len(indices)
            if len(indices) >= 6:
                # Repeated text can return a plausible but wrong one-line
                # displacement. Nearby unique matches provide an initial
                # guess, which still has to pass this frame's LK/patch checks.
                source_points = points[indices, 0]
                motions = forward[indices, 0]-source_points
                distances = np.linalg.norm(points[:, 0, None]-source_points[None], axis=2)
                neighbors = np.argsort(distances, axis=1)[:, :3]
                local_motion = np.median(motions[neighbors], axis=1)
                spread = np.max(np.linalg.norm(motions[neighbors]-local_motion[:, None], axis=2), axis=1)
                nearby = np.max(np.take_along_axis(distances, neighbors, axis=1), axis=1) < min(h, w)*.3
                correction = np.linalg.norm(forward[:, 0]-points[:, 0]-local_motion, axis=1) > 3
                use = np.flatnonzero(nearby & (spread < 1.) & correction
                                    & (np.linalg.norm(local_motion, axis=1) > max(6, min(h, w)*.02)))
                if len(use):
                    source = points[use].copy()
                    seed = (source+local_motion[use, None]).astype(np.float32)
                    found, status, _ = cv2.calcOpticalFlowPyrLK(previous, gray, source, seed,
                        winSize=(15, 15), maxLevel=0, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
                    back, reverse, _ = cv2.calcOpticalFlowPyrLK(gray, previous, found, source.copy(),
                        winSize=(15, 15), maxLevel=0, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
                    good = _valid(source, found, status, back, reverse, gray.shape)
                    cost = _patch_errors(previous, gray, source[:, 0], found[:, 0])
                    good &= (cost < 12) & (cost <= np.maximum(3, errors[use]+.5))
                    forward[use[good]], valid[use[good]] = found[good], True
                    rescued += int(good.sum())
    return points[valid, 0], forward[valid, 0], rescued
