"""Independent image-region proposals along an observed reciprocal path.

These are geometric candidates, not semantic object/contact classifications.
The target is grouped by its own boundaries, never appearance similarity to
the moving source. All returned regions still need temporal tracking checks.
"""
import cv2
import numpy as np


def line_crossings(contour, origin, direction):
    vertices = np.asarray(contour, float).reshape(-1, 2)
    first, second = vertices, np.roll(vertices, -1, axis=0)
    normal = np.array((-direction[1], direction[0]))
    a, b = (first-origin) @ normal, (second-origin) @ normal
    hits = (a*b <= 0) & (abs(a-b) > 1e-6)
    if not hits.any():
        return []
    fraction = a[hits]/(a[hits]-b[hits])
    points = first[hits]+fraction[:, None]*(second[hits]-first[hits])
    return [point for point in points]


def proposals(frame, roi, origin, direction, centers, tracked_points):
    h, w = frame.shape[:2]
    smooth = cv2.GaussianBlur(frame, (9, 9), 0)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB)
    edges = np.zeros((h, w), np.uint8)
    for channel in cv2.split(lab):
        edges |= cv2.Canny(channel, 24, 60)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    origin, centers = np.asarray(origin), np.asarray(centers)
    projected = (centers-origin) @ direction
    low, high = np.quantile(projected, (.02, .98))
    span = high-low
    if span < max(4., min(h, w)*.012):
        return []
    rx1, ry1, rx2, ry2 = roi
    results = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
        area = cv2.contourArea(contour)
        if not .0015*h*w <= area <= .35*h*w:
            continue
        x, y, rw, rh = cv2.boundingRect(contour)
        if min(rw, rh) < 10 or max(rw/rh, rh/rw) > 8:
            continue
        overlap = max(0, min(x+rw, rx2)-max(x, rx1))*max(0, min(y+rh, ry2)-max(y, ry1))
        if overlap > .12*min(area, (rx2-rx1)*(ry2-ry1)):
            continue
        # Wide background envelopes touching several image edges are not
        # distinct target regions. A partially clipped object is allowed.
        touches = sum((x <= 2, y <= 2, x+rw >= w-2, y+rh >= h-2))
        if touches >= 2:
            continue
        support = ((tracked_points[:, 0] >= x) & (tracked_points[:, 0] <= x+rw)
                   & (tracked_points[:, 1] >= y) & (tracked_points[:, 1] <= y+rh))
        if support.sum() < 6:
            continue
        for point in line_crossings(contour, origin, direction):
            coordinate = float((point-origin) @ direction)
            # Reachable candidates lie beyond a stroke end. An interior
            # crossing is a surface the source already sweeps through.
            if low <= coordinate <= high:
                continue
            sign = 1. if coordinate > high else -1.
            nearest = coordinate-high if sign > 0 else low-coordinate
            if nearest > max(span*3, .22*min(h, w)):
                continue
            if np.linalg.norm(point-origin) < .3*min(rx2-rx1, ry2-ry1):
                continue
            score = float(np.exp(-nearest/max(span, .05*min(h, w))))
            score *= min(1., support.sum()/12)
            box = (float(x), float(y), float(x+rw), float(y+rh))
            results.append((score, tuple(point), box, direction*sign, contour.reshape(-1, 2).astype(np.float32)))
    # Nested contour edges belong to one object, not competing targets.
    kept = []
    for candidate in sorted(results, key=lambda item: item[0], reverse=True):
        if not any(np.linalg.norm(np.asarray(candidate[1])-other[1]) < 10 for other in kept):
            kept.append(candidate)
    return kept[:12]
