from __future__ import annotations

import cv2
import numpy as np


class PoseMotionMixin:
    def _measure_pose_v2_dance(
        self,
        mask: np.ndarray,
        flow: np.ndarray,
        l0: float,
        mean_dx: float,
        pitch_delta: float,
        frame_bgr: np.ndarray,
        preview: np.ndarray,
    ) -> tuple[dict[str, float] | None, float]:
        h, w = mask.shape[:2]
        motion_mask, ignored_top, ignored_bottom = self._pose_v2_clean_motion_mask(mask)
        subject_mask = self._pose_v2_subject_mask(frame_bgr, motion_mask, ignored_top, ignored_bottom)
        body_bounds = self._pose_v2_mask_bounds(subject_mask)
        if body_bounds is None:
            body_bounds = self._pose_v2_mask_bounds(motion_mask)
        if body_bounds is None:
            return None, 0.0
        if not self._pose_v2_body_is_stable(body_bounds, w, h):
            self._pose_v2_last_skeleton = {}
            self._pose_v2_last_edge_notes = []
            self._draw_pose_v2_unstable(preview, ignored_top, ignored_bottom)
            return None, 0.0

        edge_info = self._pose_v2_edge_info(subject_mask, body_bounds, ignored_top, ignored_bottom)
        core_roi, core_confidence, skeleton, edge_notes = self._pose_v2_infer_core_roi(subject_mask, motion_mask, body_bounds, edge_info)
        if core_roi is None or not self._pose_v2_core_is_stable(core_roi, w, h):
            self._pose_v2_last_skeleton = skeleton
            self._pose_v2_last_edge_notes = edge_notes
            self._draw_pose_v2_unstable(preview, ignored_top, ignored_bottom, edge_notes)
            return None, 0.0
        source_label = "Pose v2 edge skeleton"
        hip_x1, hip_y1, hip_x2, hip_y2 = core_roi
        edge_scale = self._pose_v2_edge_confidence_scale(core_roi, body_bounds, w, h, edge_info)
        if edge_scale <= 0.05:
            self._pose_v2_last_skeleton = skeleton
            self._pose_v2_last_edge_notes = edge_notes
            self._draw_pose_v2_skeleton(preview, skeleton, edge_notes, source_label)
            self._draw_pose_v2_unstable(preview, ignored_top, ignored_bottom, edge_notes)
            return None, 0.0

        hip_subject = subject_mask[hip_y1:hip_y2, hip_x1:hip_x2]
        hip_motion = motion_mask[hip_y1:hip_y2, hip_x1:hip_x2]
        hip_mask = hip_motion if np.count_nonzero(hip_motion) >= 18 else np.zeros_like(hip_motion)
        points = cv2.findNonZero(hip_mask)
        if points is None or len(points) < 18:
            cx = (hip_x1 + hip_x2) * 0.5
            cy = (hip_y1 + hip_y2) * 0.5
            rect = ((float(cx), float(cy)), (float(max(12, hip_x2 - hip_x1)), float(max(12, hip_y2 - hip_y1))), 0.0)
            confidence = 0.14 * core_confidence * edge_scale
        else:
            data = points.reshape(-1, 2).astype(np.float32)
            data[:, 0] += hip_x1
            data[:, 1] += hip_y1
            rect = cv2.minAreaRect(data)
            confidence = min(1.0, (0.22 + len(points) / max(18.0, mask.size * 0.010)) * core_confidence * edge_scale)

        (cx, cy), (edge_a, edge_b), angle = rect
        if edge_a < 8 or edge_b < 8:
            return None, 0.0
        if edge_a < edge_b:
            edge_a, edge_b = edge_b, edge_a
            angle += 90.0
        angle = self._normalize_pose_angle(float(angle))

        area_norm = max(0.00001, (edge_a * edge_b) / float(max(1, w * h)))
        aspect = max(edge_a, edge_b) / max(1.0, min(edge_a, edge_b))
        area_base = float(np.median(self._pose_v2_area)) if self._pose_v2_area else area_norm
        aspect_base = float(np.median(self._pose_v2_aspect)) if self._pose_v2_aspect else aspect
        angle_base = float(np.median(self._pose_v2_angle)) if self._pose_v2_angle else angle

        current_cx = float(cx) / max(1, w - 1)
        current_cy = float(cy) / max(1, h - 1)
        previous_cx = self._pose_v2_center_x[-1] if self._pose_v2_center_x else current_cx
        previous_cy = self._pose_v2_center_y[-1] if self._pose_v2_center_y else current_cy
        predict_lead = 0.42 if confidence >= 0.16 else 0.18
        smooth_cx = max(0.0, min(1.0, current_cx + (current_cx - previous_cx) * predict_lead))
        smooth_cy = max(0.0, min(1.0, current_cy + (current_cy - previous_cy) * predict_lead))
        self._pose_v2_center_x.append(current_cx)
        self._pose_v2_center_y.append(current_cy)
        self._pose_v2_area.append(area_norm)
        self._pose_v2_aspect.append(aspect)
        self._pose_v2_angle.append(angle)

        hip_flow = flow[hip_y1:hip_y2, hip_x1:hip_x2]
        flow_support = hip_subject > 0
        if not np.any(flow_support):
            flow_support = hip_motion > 0
        moving = self._pose_v2_moving_pixels(hip_flow, flow_support, hip_motion)
        motion_evidence = self._pose_v2_motion_evidence(hip_flow, moving, flow_support)
        twist = 0.0
        if hip_flow.size and np.any(moving):
            local_x = np.indices(hip_mask.shape)[1]
            left = moving & (local_x < hip_mask.shape[1] * 0.5)
            right = moving & (local_x >= hip_mask.shape[1] * 0.5)
            if np.any(left) and np.any(right):
                left_dx = float(np.median(hip_flow[..., 0][left])) / max(1, w)
                right_dx = float(np.median(hip_flow[..., 0][right])) / max(1, w)
                twist = (left_dx - right_dx) * 52.0 * self.motion_gain

        area_delta = (area_norm / max(0.00001, area_base)) - 1.0
        aspect_delta = (aspect / max(0.1, aspect_base)) - 1.0
        roll_delta = self._normalize_pose_angle(angle - angle_base)
        core_pitch = self._pose_v2_core_pitch(hip_flow, moving, h)

        pose_l0 = self._bounded_l0(0.5 + (smooth_cy - 0.5) * 1.16)
        pose_l1 = 0.5 + self._centered_clamp(area_delta * 0.18, 0.14)
        pose_l2 = 0.5 + self._centered_clamp((smooth_cx - 0.5) * 0.34 + mean_dx * 2.2 * self.motion_gain, 0.24)
        pose_r0 = 0.5 + self._centered_clamp(twist + (smooth_cx - 0.5) * 0.10, 0.24)
        pose_r1 = 0.5 + self._centered_clamp(roll_delta / 58.0, 0.22)
        pose_r2 = 0.5 + self._centered_clamp(core_pitch * 16.0 * self.motion_gain + pitch_delta * 4.0 * self.motion_gain + aspect_delta * 0.12, 0.22)
        pose_r0 = self._pose_v2_release_stuck_axis("R0", pose_r0, motion_evidence + min(0.25, abs(twist) * 1.6))
        pose_r1 = self._pose_v2_release_stuck_axis("R1", pose_r1, motion_evidence + min(0.25, abs(roll_delta) / 22.0))
        pose_r2 = self._pose_v2_release_stuck_axis("R2", pose_r2, motion_evidence + min(0.25, abs(core_pitch) * 260.0))

        self._draw_pose_v2_skeleton(preview, skeleton, edge_notes, source_label)
        self._draw_pose_v2_guides(preview, (hip_x1, hip_y1, hip_x2, hip_y2), ignored_top, ignored_bottom, motion_evidence)
        self._pose_v2_last_skeleton = skeleton
        self._pose_v2_last_edge_notes = edge_notes
        box = cv2.boxPoints(((float(cx), float(cy)), (float(edge_a), float(edge_b)), float(angle)))
        box_i = np.intp(box)
        cv2.polylines(preview, [box_i], True, (255, 0, 180), 2, cv2.LINE_AA)
        for index, point in enumerate(box_i):
            cv2.circle(preview, tuple(point), 3, (255, 210, 255), -1, cv2.LINE_AA)
            cv2.putText(preview, str(index + 1), tuple(point + np.array([4, -4])), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 230, 255), 1, cv2.LINE_AA)
        cv2.putText(preview, "Pose v2 hip plane", (max(6, hip_x1), max(18, hip_y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 0, 180), 1, cv2.LINE_AA)

        positions = {
            "L0": pose_l0,
            "L1": pose_l1,
            "L2": pose_l2,
            "R0": pose_r0,
            "R1": pose_r1,
            "R2": pose_r2,
        }
        return positions, confidence

    @staticmethod
    def _pose_v2_clean_motion_mask(mask: np.ndarray) -> tuple[np.ndarray, int, int]:
        h, w = mask.shape[:2]
        clean = mask.copy()
        ignored_top = int(h * 0.075)
        ignored_bottom = int(h * 0.905)
        side_margin = int(w * 0.025)
        clean[:ignored_top, :] = 0
        clean[ignored_bottom:, :] = 0
        if side_margin > 0:
            clean[:, :side_margin] = 0
            clean[:, w - side_margin :] = 0
        return clean, ignored_top, ignored_bottom

    @staticmethod
    def _pose_v2_subject_mask(frame_bgr: np.ndarray, motion_mask: np.ndarray, ignored_top: int, ignored_bottom: int) -> np.ndarray:
        h, w = motion_mask.shape[:2]
        band_y1 = max(0, min(h - 1, ignored_top))
        band_y2 = max(band_y1 + 1, min(h, ignored_bottom))
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        sat = hsv[..., 1]
        val = hsv[..., 2]
        margin = max(4, int(w * 0.045))
        patch_h = max(4, int((band_y2 - band_y1) * 0.045))
        patches = (
            lab[band_y1:band_y2, :margin],
            lab[band_y1:band_y2, max(0, w - margin) : w],
            lab[band_y1 : min(band_y2, band_y1 + patch_h), :],
            lab[max(band_y1, band_y2 - patch_h) : band_y2, :],
        )
        seeds: list[np.ndarray] = []
        for patch in patches:
            if patch.size == 0:
                continue
            seed = np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)
            if all(float(np.linalg.norm(seed - other)) > 12.0 for other in seeds):
                seeds.append(seed)
        if not seeds:
            return motion_mask

        distances = [np.sqrt(np.sum((lab - seed.reshape(1, 1, 3)) ** 2, axis=2)) for seed in seeds]
        bg_distance = np.min(np.stack(distances, axis=0), axis=0)
        bg_candidate = bg_distance < 28.0
        bg_candidate[:band_y1, :] = True
        bg_candidate[band_y2:, :] = True
        candidate_u8 = bg_candidate.astype(np.uint8)
        count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(candidate_u8, 8)
        if count > 1:
            border_labels: set[int] = set()
            border_labels.update(int(label) for label in np.unique(labels[band_y1, :]) if label > 0)
            border_labels.update(int(label) for label in np.unique(labels[max(band_y1, band_y2 - 1), :]) if label > 0)
            border_labels.update(int(label) for label in np.unique(labels[band_y1:band_y2, 0]) if label > 0)
            border_labels.update(int(label) for label in np.unique(labels[band_y1:band_y2, w - 1]) if label > 0)
            background = np.isin(labels, list(border_labels)) if border_labels else bg_candidate
        else:
            background = bg_candidate
        subject = (~background & (np.arange(h)[:, None] >= band_y1) & (np.arange(h)[:, None] < band_y2)).astype(np.uint8) * 255
        color_subject = (((sat > 34) | (val < 92)) & ~background).astype(np.uint8) * 255
        subject = cv2.bitwise_or(subject, color_subject)
        subject = cv2.bitwise_or(subject, motion_mask)
        subject[:ignored_top, :] = 0
        subject[ignored_bottom:, :] = 0
        subject = cv2.morphologyEx(subject, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        subject = cv2.morphologyEx(subject, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        return subject if np.count_nonzero(subject) >= 32 else motion_mask

    @staticmethod
    def _pose_v2_mask_bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
        if count <= 1:
            return None
        h, w = mask.shape[:2]
        min_area = max(28, int(mask.size * 0.00045))
        kept: list[tuple[int, int, int, int, int]] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            cw = int(stats[label, cv2.CC_STAT_WIDTH])
            ch = int(stats[label, cv2.CC_STAT_HEIGHT])
            center_bias = 1.0 - min(0.65, abs((x + cw * 0.5) / max(1, w) - 0.5) * 0.9)
            lower_bias = 1.0 + min(0.35, max(0.0, (y + ch * 0.5) / max(1, h) - 0.35))
            score = int(area * center_bias * lower_bias)
            kept.append((score, x, y, x + cw, y + ch))
        if not kept:
            return None
        ranked = sorted(kept, reverse=True)
        primary = ranked[0]
        primary_area = max(1, primary[0])
        px1, py1, px2, py2 = primary[1], primary[2], primary[3], primary[4]
        primary_cx = (px1 + px2) * 0.5
        chosen = [primary]
        for item in ranked[1:8]:
            score, x1, y1, x2, y2 = item
            area_ratio = score / primary_area
            cx = (x1 + x2) * 0.5
            close_x = abs(cx - primary_cx) <= max(28.0, (px2 - px1) * 0.65)
            overlaps_y = min(y2, py2) - max(y1, py1) > max(8, min(y2 - y1, py2 - py1) * 0.15)
            near_y = abs(((y1 + y2) * 0.5) - ((py1 + py2) * 0.5)) <= max(36.0, (py2 - py1) * 0.62)
            if area_ratio >= 0.14 and close_x and (overlaps_y or near_y):
                chosen.append(item)
        return (
            min(item[1] for item in chosen),
            min(item[2] for item in chosen),
            max(item[3] for item in chosen),
            max(item[4] for item in chosen),
        )

    @staticmethod
    def _pose_v2_infer_core_roi(
        subject_mask: np.ndarray,
        motion_mask: np.ndarray,
        body_bounds: tuple[int, int, int, int],
        edge_info: dict[str, bool],
    ) -> tuple[tuple[int, int, int, int] | None, float, dict[str, tuple[int, int]], list[str]]:
        from ..analyzer import RealtimeAnalyzer

        h, w = subject_mask.shape[:2]
        edge_notes = RealtimeAnalyzer._pose_v2_edge_notes(edge_info)
        x1, y1, x2, y2 = body_bounds
        body_w = max(1, x2 - x1)
        body_h = max(1, y2 - y1)
        if body_w < 18 or body_h < 44:
            return None, 0.0, {}, edge_notes

        body = subject_mask[y1:y2, x1:x2] > 0
        if np.count_nonzero(body) < 32:
            body = motion_mask[y1:y2, x1:x2] > 0
        if np.count_nonzero(body) < 32:
            return None, 0.0, {}, edge_notes

        row_count = np.count_nonzero(body, axis=1).astype(np.float32)
        if row_count.size < 16 or float(np.max(row_count)) < 4.0:
            return None, 0.0, {}, edge_notes
        kernel = max(5, int(body_h * 0.035) | 1)
        row_smooth = cv2.GaussianBlur(row_count.reshape(-1, 1), (1, kernel), 0).reshape(-1)
        ys = np.arange(body_h)
        ratios = ys / max(1, body_h - 1)
        middle = (ratios >= 0.30) & (ratios <= 0.70)
        middle_pixels = np.where(body[middle, :])[1] if np.any(middle) else np.array([], dtype=np.int64)
        body_center = float(np.median(middle_pixels)) if middle_pixels.size else body_w * 0.5
        upper_trunk = (ratios >= 0.18) & (ratios <= 0.42)
        upper_pixels = np.where(body[upper_trunk, :])[1] if np.any(upper_trunk) else np.array([], dtype=np.int64)
        trunk_center = float(np.median(upper_pixels)) if upper_pixels.size else body_center
        expected_pelvis_x = body_center * 0.35 + trunk_center * 0.65
        pelvis_target = 0.54 if edge_info.get("bottom") else 0.58
        pelvis_high = 0.64 if edge_info.get("bottom") else 0.70
        band = (ratios >= 0.46) & (ratios <= pelvis_high) & (row_smooth > np.max(row_smooth) * 0.14)
        if not np.any(band):
            band = (ratios >= 0.50) & (ratios <= pelvis_high)

        rows = np.where(band)[0]
        centers: list[float] = []
        widths: list[float] = []
        scores: list[float] = []
        max_width = max(1.0, float(np.max(row_smooth)))
        for row in rows:
            row_core = RealtimeAnalyzer._pose_v2_row_core(body, int(row), body_center, 18.0, 82.0)
            if row_core is None:
                continue
            center, width = row_core
            ratio = row / max(1, body_h - 1)
            center_score = 1.0 - min(1.0, abs(center - expected_pelvis_x) / max(8.0, body_w * 0.30))
            raw_width_score = min(1.0, float(row_smooth[row]) / max_width)
            width_ratio = width / max(1.0, body_w)
            if 0.14 <= width_ratio <= 0.32:
                width_shape_score = 1.0
            elif width_ratio < 0.14:
                width_shape_score = max(0.0, width_ratio / 0.14)
            else:
                width_shape_score = max(0.0, 1.0 - (width_ratio - 0.32) / 0.28)
            pelvis_score = 1.0 - min(1.0, abs(ratio - pelvis_target) / 0.18)
            scores.append(raw_width_score * 0.16 + width_shape_score * 0.28 + center_score * 0.30 + pelvis_score * 0.26)
            centers.append(center)
            widths.append(width)
        if not scores:
            return None, 0.0, {}, edge_notes

        best_index = int(np.argmax(np.array(scores, dtype=np.float32)))
        center_y = int(rows[best_index])
        near = (rows >= max(0, center_y - int(body_h * 0.055))) & (rows <= min(body_h - 1, center_y + int(body_h * 0.055)))
        if np.any(near):
            near_rows = rows[near]
            near_cores = [
                row_core
                for row_core in (RealtimeAnalyzer._pose_v2_row_core(body, int(row), body_center, 20.0, 80.0) for row in near_rows)
                if row_core is not None
            ]
            if near_cores:
                center_x = float(np.median([item[0] for item in near_cores]))
                core_width = float(np.median([item[1] for item in near_cores]))
            else:
                center_x = float(centers[best_index])
                core_width = float(widths[best_index])
        else:
            center_x = float(centers[best_index])
            core_width = float(widths[best_index])

        core_width = max(body_w * 0.22, min(core_width * 0.78, body_w * 0.44))
        core_height = max(16.0, min(body_h * 0.13, h * 0.17))
        top = y1 + center_y - core_height * 0.48
        bottom = y1 + center_y + core_height * 0.52
        left = x1 + center_x - core_width * 0.5
        right = x1 + center_x + core_width * 0.5
        roi = (
            max(0, min(w - 1, int(round(left)))),
            max(0, min(h - 1, int(round(top)))),
            max(1, min(w, int(round(right)))),
            max(1, min(h, int(round(bottom)))),
        )
        rx1, ry1, rx2, ry2 = roi
        if rx2 - rx1 < 12 or ry2 - ry1 < 12:
            return None, 0.0, {}, edge_notes
        confidence = max(0.18, min(1.0, float(scores[best_index])))
        skeleton = RealtimeAnalyzer._pose_v2_build_skeleton(
            body,
            row_smooth,
            body_bounds,
            roi,
            center_y,
            center_x,
            core_width,
            edge_info,
        )
        return roi, confidence, skeleton, edge_notes

    @staticmethod
    def _pose_v2_edge_info(
        mask: np.ndarray,
        body_bounds: tuple[int, int, int, int],
        usable_top: int = 0,
        usable_bottom: int | None = None,
    ) -> dict[str, bool]:
        h, w = mask.shape[:2]
        bx1, by1, bx2, by2 = body_bounds
        usable_bottom = h if usable_bottom is None else max(1, min(h, int(usable_bottom)))
        usable_top = max(0, min(usable_bottom - 1, int(usable_top)))
        edge_margin_x = max(4, int(w * 0.018))
        edge_margin_y = max(4, int(h * 0.018))
        bottom_y = max(usable_top, int(usable_bottom - max(edge_margin_y, h * 0.045)))
        top_y = min(usable_bottom, max(usable_top + 1, int(usable_top + max(edge_margin_y, h * 0.045))))
        top_contact_y = min(usable_bottom, usable_top + max(3, int(h * 0.008)))
        left_x = min(w, max(1, int(w * 0.035)))
        right_x = max(0, int(w * 0.965))
        body_w = max(1, bx2 - bx1)
        bottom_band = mask[bottom_y:h, max(0, bx1):min(w, bx2)] > 0
        top_band = mask[usable_top:top_contact_y, max(0, bx1):min(w, bx2)] > 0
        left_band = mask[max(0, by1):min(h, by2), 0:left_x] > 0
        right_band = mask[max(0, by1):min(h, by2), right_x:w] > 0

        def wide_contact(band: np.ndarray, axis: int, scale: float) -> bool:
            if band.size == 0 or not np.any(band):
                return False
            projection = np.count_nonzero(band, axis=axis) > 0
            return int(np.count_nonzero(projection)) >= max(3, int(body_w * scale))

        return {
            "top": by1 <= usable_top + max(3, int(h * 0.006)) and wide_contact(top_band, 0, 0.12),
            "bottom": by2 >= usable_bottom - edge_margin_y or wide_contact(bottom_band, 0, 0.18),
            "left": bx1 <= edge_margin_x or bool(np.count_nonzero(left_band) > max(8, h * 0.010)),
            "right": bx2 >= w - edge_margin_x or bool(np.count_nonzero(right_band) > max(8, h * 0.010)),
        }

    @staticmethod
    def _pose_v2_edge_notes(edge_info: dict[str, bool]) -> list[str]:
        notes: list[str] = []
        if edge_info.get("top"):
            notes.append("head/upper body may be cropped")
        if edge_info.get("bottom"):
            notes.append("legs may continue offscreen")
        if edge_info.get("left"):
            notes.append("left side may be cropped")
        if edge_info.get("right"):
            notes.append("right side may be cropped")
        return notes

    @staticmethod
    def _pose_v2_row_core(body: np.ndarray, row: int, expected_x: float, low_pct: float, high_pct: float) -> tuple[float, float] | None:
        row = max(0, min(body.shape[0] - 1, int(row)))
        xs = np.where(body[row])[0]
        if xs.size < 4:
            return None
        breaks = np.where(np.diff(xs) > 1)[0]
        starts = np.r_[0, breaks + 1]
        ends = np.r_[breaks, xs.size - 1]
        best: np.ndarray | None = None
        best_score = -1.0
        for start, end in zip(starts, ends):
            segment = xs[start : end + 1]
            if segment.size < 4:
                continue
            center = float(np.median(segment))
            length_score = min(1.0, segment.size / max(6.0, body.shape[1] * 0.16))
            center_score = 1.0 - min(1.0, abs(center - expected_x) / max(8.0, body.shape[1] * 0.34))
            score = length_score * 0.46 + center_score * 0.54
            if score > best_score:
                best = segment
                best_score = score
        if best is None:
            return None
        low = float(np.percentile(best, low_pct))
        high = float(np.percentile(best, high_pct))
        return (low + high) * 0.5, max(5.0, high - low)

    @staticmethod
    def _pose_v2_row_segment_near(body: np.ndarray, row: int, expected_x: float) -> tuple[float, float, float] | None:
        row = max(0, min(body.shape[0] - 1, int(row)))
        xs = np.where(body[row])[0]
        if xs.size < 3:
            return None
        breaks = np.where(np.diff(xs) > 1)[0]
        starts = np.r_[0, breaks + 1]
        ends = np.r_[breaks, xs.size - 1]
        best: np.ndarray | None = None
        best_score = -1.0
        for start, end in zip(starts, ends):
            segment = xs[start : end + 1]
            if segment.size < 3:
                continue
            center = float(np.median(segment))
            width = float(segment[-1] - segment[0] + 1)
            proximity = 1.0 - min(1.0, abs(center - expected_x) / max(10.0, body.shape[1] * 0.30))
            width_score = min(1.0, width / max(5.0, body.shape[1] * 0.11))
            score = proximity * 0.78 + width_score * 0.22
            if score > best_score:
                best = segment
                best_score = score
        if best is None or best_score < 0.22:
            return None
        low = float(np.percentile(best, 22.0))
        high = float(np.percentile(best, 78.0))
        return (low + high) * 0.5, max(4.0, high - low), best_score

    @staticmethod
    def _pose_v2_leg_points(
        body: np.ndarray,
        hip_cx: float,
        hip_cy: float,
        hip_w: float,
        edge_info: dict[str, bool],
    ) -> dict[str, tuple[float, float]]:
        from ..analyzer import RealtimeAnalyzer

        body_h, body_w = body.shape[:2]

        def find_leg_point(side: str, low_ratio: float, high_ratio: float, target_ratio: float) -> tuple[float, float] | None:
            side_sign = -1.0 if side == "l" else 1.0
            hip_x = hip_cx + side_sign * hip_w * 0.34
            rows = np.arange(max(0, int(body_h * low_ratio)), min(body_h, int(body_h * high_ratio) + 1))
            if rows.size == 0:
                return None
            target_y = target_ratio * max(1, body_h - 1)
            best: tuple[float, float] | None = None
            best_score = -1.0
            for row in rows[:: max(1, rows.size // 42)]:
                progress = max(0.0, min(1.0, (float(row) - hip_cy) / max(1.0, body_h - hip_cy)))
                expected_x = hip_x + side_sign * body_w * 0.19 * progress
                segment = RealtimeAnalyzer._pose_v2_row_segment_near(body, int(row), expected_x)
                if segment is None:
                    continue
                center, width, segment_score = segment
                side_ok = center <= hip_cx + hip_w * 0.18 if side == "l" else center >= hip_cx - hip_w * 0.18
                if not side_ok:
                    segment_score *= 0.52
                target_score = 1.0 - min(1.0, abs(float(row) - target_y) / max(1.0, body_h * 0.18))
                narrow_score = 1.0 - min(1.0, max(0.0, width / max(1.0, body_w) - 0.28) / 0.24)
                score = segment_score * 0.56 + target_score * 0.30 + narrow_score * 0.14
                if score > best_score:
                    best = (center, float(row))
                    best_score = score
            return best if best_score >= 0.28 else None

        knee_low, knee_high, knee_target = 0.60, 0.83, 0.72
        ankle_low, ankle_high, ankle_target = 0.80, 0.99, 0.92
        points: dict[str, tuple[float, float]] = {}
        for side in ("l", "r"):
            knee = find_leg_point(side, knee_low, knee_high, knee_target)
            ankle = None if edge_info.get("bottom") else find_leg_point(side, ankle_low, ankle_high, ankle_target)
            hip_x = hip_cx + (-1.0 if side == "l" else 1.0) * hip_w * 0.34
            if knee is not None:
                points[f"{side}_knee"] = knee
            else:
                hint_y = min(body_h - 1, hip_cy + max(12.0, body_h * 0.16))
                points[f"{side}_knee_hint"] = (hip_x, hint_y)
            if ankle is not None:
                points[f"{side}_ankle"] = ankle
            elif knee is not None and not edge_info.get("bottom"):
                hint_y = min(body_h - 1, knee[1] + max(14.0, body_h * 0.18))
                outward = -1.0 if side == "l" else 1.0
                points[f"{side}_ankle_hint"] = (knee[0] + outward * body_w * 0.05, hint_y)
        return points

    @staticmethod
    def _pose_v2_build_skeleton(
        body: np.ndarray,
        row_smooth: np.ndarray,
        body_bounds: tuple[int, int, int, int],
        core_roi: tuple[int, int, int, int],
        core_local_y: int,
        core_local_x: float,
        core_width: float,
        edge_info: dict[str, bool],
    ) -> dict[str, tuple[int, int]]:
        from ..analyzer import RealtimeAnalyzer

        x1, y1, x2, y2 = body_bounds
        body_h, body_w = body.shape[:2]

        body_ratios = np.arange(body_h) / max(1, body_h - 1)
        middle = (body_ratios >= 0.30) & (body_ratios <= 0.70)
        middle_pixels = np.where(body[middle, :])[1] if np.any(middle) else np.array([], dtype=np.int64)
        body_center = float(np.median(middle_pixels)) if middle_pixels.size else body_w * 0.5

        def row_stats(local_y: int, low_pct: float = 22.0, high_pct: float = 78.0) -> tuple[float, float, float]:
            local_y = max(0, min(body_h - 1, int(local_y)))
            row_core = RealtimeAnalyzer._pose_v2_row_core(body, local_y, body_center, low_pct, high_pct)
            if row_core is None:
                return core_local_x, max(6.0, core_width), float(local_y)
            center, width = row_core
            return center, width, float(local_y)

        def best_row(low_ratio: float, high_ratio: float, target_ratio: float) -> int:
            rows = np.arange(body_h)
            ratios = rows / max(1, body_h - 1)
            band = (ratios >= low_ratio) & (ratios <= high_ratio) & (row_smooth > np.max(row_smooth) * 0.12)
            if not np.any(band):
                return int(target_ratio * max(1, body_h - 1))
            choices = rows[band]
            target = target_ratio * max(1, body_h - 1)
            widths = row_smooth[choices] / max(1.0, float(np.max(row_smooth)))
            closeness = 1.0 - np.minimum(1.0, np.abs(choices - target) / max(1.0, body_h * 0.18))
            scores = widths * 0.42 + closeness * 0.58
            return int(choices[int(np.argmax(scores))])

        shoulder_y = best_row(0.14, 0.32, 0.23)
        chest_y = best_row(0.28, 0.43, 0.35)
        waist_y = best_row(0.36, 0.54, 0.44)
        shoulder_cx, shoulder_w, _ = row_stats(shoulder_y, 14.0, 86.0)
        chest_cx, _chest_w, _ = row_stats(chest_y)
        waist_cx, waist_w, _ = row_stats(waist_y)

        hip_x1, hip_y1, hip_x2, hip_y2 = core_roi
        hip_cx = (hip_x1 + hip_x2) * 0.5 - x1
        hip_cy = (hip_y1 + hip_y2) * 0.5 - y1
        hip_w = max(core_width, body_w * 0.22)
        shoulder_w = max(shoulder_w, body_w * 0.24)
        waist_w = max(waist_w, body_w * 0.18)

        head_y = max(0, int(body_h * 0.05))
        head_cx, head_w, _ = row_stats(head_y)
        neck_y = int((shoulder_y + head_y) * 0.58)
        neck_x = (shoulder_cx + chest_cx) * 0.5

        skeleton_local = {
            "neck": (neck_x, float(neck_y)),
            "l_shoulder": (shoulder_cx - shoulder_w * 0.42, float(shoulder_y)),
            "r_shoulder": (shoulder_cx + shoulder_w * 0.42, float(shoulder_y)),
            "chest": (chest_cx, float(chest_y)),
            "waist": (waist_cx, float(waist_y)),
            "pelvis": (hip_cx, hip_cy),
            "l_hip": (hip_cx - hip_w * 0.34, hip_cy),
            "r_hip": (hip_cx + hip_w * 0.34, hip_cy),
        }
        if not edge_info.get("top"):
            skeleton_local["head"] = (head_cx, float(head_y))
        skeleton_local.update(RealtimeAnalyzer._pose_v2_leg_points(body, hip_cx, hip_cy, hip_w, edge_info))
        return {
            name: (int(round(x1 + point[0])), int(round(y1 + point[1])))
            for name, point in skeleton_local.items()
        }

    def _pose_v2_body_is_stable(self, bounds: tuple[int, int, int, int], width: int, height: int) -> bool:
        x1, y1, x2, y2 = bounds
        state = (
            ((x1 + x2) * 0.5) / max(1, width),
            ((y1 + y2) * 0.5) / max(1, height),
            (x2 - x1) / max(1, width),
            (y2 - y1) / max(1, height),
        )
        if len(self._pose_v2_body_state) < 4:
            self._pose_v2_body_state.append(state)
            return True
        history = np.array(self._pose_v2_body_state, dtype=np.float32)
        baseline = np.median(history, axis=0)
        center_jump = abs(state[0] - float(baseline[0])) + abs(state[1] - float(baseline[1]))
        width_change = abs(state[2] - float(baseline[2])) / max(0.08, float(baseline[2]))
        height_change = abs(state[3] - float(baseline[3])) / max(0.08, float(baseline[3]))
        unstable = center_jump > 0.20 or width_change > 0.48 or height_change > 0.42
        if unstable:
            return False
        self._pose_v2_body_state.append(state)
        return True

    def _pose_v2_core_is_stable(self, roi: tuple[int, int, int, int], width: int, height: int) -> bool:
        x1, y1, x2, y2 = roi
        state = (
            ((x1 + x2) * 0.5) / max(1, width),
            ((y1 + y2) * 0.5) / max(1, height),
            (x2 - x1) / max(1, width),
            (y2 - y1) / max(1, height),
        )
        if len(self._pose_v2_core_state) < 4:
            self._pose_v2_core_state.append(state)
            return True
        history = np.array(self._pose_v2_core_state, dtype=np.float32)
        baseline = np.median(history, axis=0)
        center_jump = abs(state[0] - float(baseline[0])) + abs(state[1] - float(baseline[1]))
        width_change = abs(state[2] - float(baseline[2])) / max(0.05, float(baseline[2]))
        height_change = abs(state[3] - float(baseline[3])) / max(0.04, float(baseline[3]))
        unstable = center_jump > 0.15 or width_change > 0.42 or height_change > 0.38
        if unstable:
            return False
        self._pose_v2_core_state.append(state)
        return True

    @staticmethod
    def _pose_v2_edge_confidence_scale(
        roi: tuple[int, int, int, int],
        body_bounds: tuple[int, int, int, int],
        width: int,
        height: int,
        edge_info: dict[str, bool],
    ) -> float:
        x1, y1, x2, y2 = roi
        bx1, by1, bx2, by2 = body_bounds
        edge_margin_x = max(4, int(width * 0.018))
        edge_margin_y = max(4, int(height * 0.018))
        core_near_frame_edge = x1 <= edge_margin_x or x2 >= width - edge_margin_x or y1 <= edge_margin_y or y2 >= height - edge_margin_y
        body_cut_side = edge_info.get("left", False) or edge_info.get("right", False) or bx1 <= edge_margin_x or bx2 >= width - edge_margin_x
        body_cut_bottom = edge_info.get("bottom", False) or by2 >= height - edge_margin_y
        lower_body_too_short = (by2 - y1) < max(20, int((by2 - by1) * 0.22))
        if core_near_frame_edge:
            return 0.0
        scale = 1.0
        if body_cut_bottom:
            scale *= 0.58
        if edge_info.get("top", False):
            scale *= 0.78
        if body_cut_side:
            scale *= 0.74
        if body_cut_side and lower_body_too_short:
            scale *= 0.45
        return max(0.0, min(1.0, scale))

    @staticmethod
    def _pose_v2_moving_pixels(flow: np.ndarray, support: np.ndarray, motion_mask: np.ndarray) -> np.ndarray:
        if flow.size == 0 or not np.any(support):
            return motion_mask > 0
        mag, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        supported_mag = mag[support]
        threshold = max(0.10, float(np.percentile(supported_mag, 62))) if supported_mag.size else 0.10
        moving = support & (mag >= threshold)
        if np.count_nonzero(moving) < 8:
            moving = (motion_mask > 0) & support
        return moving

    @staticmethod
    def _pose_v2_motion_evidence(flow: np.ndarray, moving: np.ndarray, support: np.ndarray) -> float:
        support_count = max(1, int(np.count_nonzero(support)))
        moving_count = int(np.count_nonzero(moving))
        if flow.size == 0 or moving_count <= 0:
            return 0.0
        mag, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        median_mag = float(np.median(mag[moving]))
        area_score = min(1.0, moving_count / max(10.0, support_count * 0.10))
        speed_score = min(1.0, median_mag / 1.35)
        return float(area_score * 0.58 + speed_score * 0.42)

    @staticmethod
    def _pose_v2_core_pitch(flow: np.ndarray, moving: np.ndarray, full_height: int) -> float:
        if flow.size == 0 or not np.any(moving):
            return 0.0
        local_h = flow.shape[0]
        top = moving[: local_h // 2, :]
        bottom = moving[local_h // 2 :, :]
        if not np.any(top) or not np.any(bottom):
            return 0.0
        top_dy = float(np.median(flow[: local_h // 2, :, 1][top]))
        bottom_dy = float(np.median(flow[local_h // 2 :, :, 1][bottom]))
        return (top_dy - bottom_dy) / max(1, full_height)

    def _pose_v2_release_stuck_axis(self, axis: str, value: float, evidence: float) -> float:
        history = self._pose_v2_axis_recent.get(axis)
        if history is None:
            return value
        history.append(value)
        if not self.enable_extreme_reset:
            return value
        offset = abs(value - 0.5)
        if offset < 0.13:
            return value
        recent_range = max(history) - min(history) if len(history) >= 8 else 1.0
        weak = evidence < 0.20
        stuck = len(history) >= 8 and recent_range < 0.035
        if not weak and not stuck:
            return value
        strength = 0.14
        if weak:
            strength += min(0.18, (0.20 - evidence) * 0.9)
        if stuck and offset > 0.17:
            strength += 0.12
        return float(value * (1.0 - strength) + 0.5 * strength)

    @staticmethod
    def _draw_pose_v2_guides(
        preview: np.ndarray,
        hip_roi: tuple[int, int, int, int],
        ignored_top: int,
        ignored_bottom: int,
        evidence: float,
    ) -> None:
        h, w = preview.shape[:2]
        x1, y1, x2, y2 = hip_roi
        cv2.line(preview, (0, ignored_top), (w, ignored_top), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.line(preview, (0, ignored_bottom), (w, ignored_bottom), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.rectangle(preview, (x1, y1), (x2, y2), (40, 220, 120), 1, cv2.LINE_AA)
        label_y = min(h - 8, max(18, y2 + 16))
        cv2.putText(preview, f"Pose v2 core {evidence:.2f}", (max(6, x1), label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 220, 120), 1, cv2.LINE_AA)

    @staticmethod
    def _draw_pose_v2_skeleton(
        preview: np.ndarray,
        skeleton: dict[str, tuple[int, int]],
        edge_notes: list[str] | None = None,
        source_label: str = "Edge Skeleton",
    ) -> None:
        if not skeleton:
            return
        links = (
            ("head", "neck"),
            ("neck", "l_shoulder"),
            ("neck", "r_shoulder"),
            ("neck", "chest"),
            ("chest", "waist"),
            ("waist", "pelvis"),
            ("pelvis", "l_hip"),
            ("pelvis", "r_hip"),
            ("l_hip", "l_knee"),
            ("r_hip", "r_knee"),
            ("l_hip", "l_knee_hint"),
            ("r_hip", "r_knee_hint"),
            ("l_knee", "l_ankle"),
            ("r_knee", "r_ankle"),
            ("l_knee", "l_ankle_hint"),
            ("r_knee", "r_ankle_hint"),
        )
        for start, end in links:
            if start in skeleton and end in skeleton:
                cv2.line(preview, skeleton[start], skeleton[end], (255, 220, 70), 2, cv2.LINE_AA)
        for name, point in skeleton.items():
            color = (255, 245, 120)
            radius = 3
            if name in {"pelvis", "l_hip", "r_hip"}:
                color = (50, 255, 180)
                radius = 4
            elif name.endswith("_hint"):
                color = (120, 180, 255)
                radius = 3
            cv2.circle(preview, point, radius, color, -1, cv2.LINE_AA)
        pelvis = skeleton.get("pelvis")
        if pelvis is not None:
            cv2.putText(preview, "V2 skeleton", (max(6, pelvis[0] - 36), max(18, pelvis[1] - 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 245, 120), 1, cv2.LINE_AA)
            cv2.putText(preview, source_label[:54], (max(6, pelvis[0] - 36), min(preview.shape[0] - 8, pelvis[1] + 34)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 245, 120), 1, cv2.LINE_AA)
        if edge_notes:
            h, _w = preview.shape[:2]
            x = 8
            y = max(18, (pelvis[1] + 22) if pelvis is not None else 18)
            for note in edge_notes[:3]:
                if y >= h - 8:
                    break
                cv2.putText(preview, note, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 180, 255), 1, cv2.LINE_AA)
                y += 14

    @staticmethod
    def _draw_pose_v2_unstable(preview: np.ndarray, ignored_top: int, ignored_bottom: int, edge_notes: list[str] | None = None) -> None:
        h, w = preview.shape[:2]
        cv2.line(preview, (0, ignored_top), (w, ignored_top), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.line(preview, (0, ignored_bottom), (w, ignored_bottom), (90, 90, 90), 1, cv2.LINE_AA)
        cv2.putText(preview, "Pose v2 unstable", (8, min(h - 8, max(20, ignored_top + 18))), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (80, 120, 255), 1, cv2.LINE_AA)
        if edge_notes:
            y = min(h - 8, max(36, ignored_top + 34))
            for note in edge_notes[:3]:
                if y >= h - 8:
                    break
                cv2.putText(preview, note, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 180, 255), 1, cv2.LINE_AA)
                y += 14
