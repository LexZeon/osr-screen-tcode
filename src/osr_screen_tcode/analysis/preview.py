from __future__ import annotations

import cv2
import numpy as np

from ..pose_backends import RtmPose3dResult


class AnalysisPreviewMixin:
    def _draw_rtm_pose_3d_preview(self, preview: np.ndarray, result: RtmPose3dResult | None = None) -> np.ndarray:
        h, w = preview.shape[:2]
        panel_w = int(max(180, min(300, w * 0.42)))
        panel = np.zeros((h, panel_w, 3), dtype=np.uint8)
        cv2.line(panel, (0, 0), (0, h - 1), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.putText(panel, self._rtm_pose_label(), (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (225, 235, 245), 1, cv2.LINE_AA)
        cv2.putText(panel, "OpenMMLab MMPose / rtmlib", (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (120, 170, 230), 1, cv2.LINE_AA)

        backend = self._rtm_pose_backend()
        if result is None:
            with self._rtm_pose_3d_lock:
                result = self._rtm_pose_3d_last

        if result is None:
            status = backend.status if backend is not None else f"{self._rtm_pose_label()}: off"
            self._put_wrapped_status(panel, status, 10, 66, panel_w - 20, (120, 170, 255))
            self._draw_rtm_pose_3d_stats(panel)
            return np.concatenate((preview, panel), axis=1)

        self._draw_rtm_pose_2d_overlay(preview, result)
        self._draw_rtm_pose_3d_panel(panel, result)
        self._draw_rtm_pose_3d_stats(panel)
        return np.concatenate((preview, panel), axis=1)

    def _draw_rtm_pose_3d_stats(self, panel: np.ndarray) -> None:
        h, _w = panel.shape[:2]
        with self._rtm_pose_3d_lock:
            pending = self._rtm_pose_3d_pending
            last_ms = self._rtm_pose_3d_last_ms
            last_frame = self._rtm_pose_3d_last_frame
            error = self._rtm_pose_3d_last_error
        age = max(0, self._rtm_pose_3d_frame - last_frame)
        mode = f"{self._rtm_pose_label()} async x{self._rtm_pose_3d_infer_interval()}"
        if self.rtm_pose_flow_enabled:
            mode += " flow"
        if self.rtm_pose_kalman_enabled:
            mode += " kalman"
        if pending:
            mode += " running"
        cv2.putText(panel, mode, (10, h - 44), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (130, 190, 235), 1, cv2.LINE_AA)
        cv2.putText(panel, f"infer {last_ms:.0f}ms age {age}f", (10, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (130, 190, 235), 1, cv2.LINE_AA)
        if error:
            self._put_wrapped_status(panel, error, 10, 66, panel.shape[1] - 20, (120, 170, 255))

    @staticmethod
    def _put_wrapped_status(panel: np.ndarray, text: str, x: int, y: int, max_width: int, color: tuple[int, int, int]) -> None:
        words = str(text).replace("\\", "/").split()
        line = ""
        line_height = 15
        for word in words:
            candidate = word if not line else f"{line} {word}"
            width = cv2.getTextSize(candidate, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)[0][0]
            if width > max_width and line:
                cv2.putText(panel, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
                y += line_height
                line = word
            else:
                line = candidate
        if line:
            cv2.putText(panel, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)

    @staticmethod
    def _rtm_pose_body_bones() -> tuple[tuple[int, int], ...]:
        return (
            (5, 6),
            (5, 7),
            (7, 9),
            (6, 8),
            (8, 10),
            (5, 11),
            (6, 12),
            (11, 12),
            (11, 13),
            (13, 15),
            (12, 14),
            (14, 16),
            (0, 5),
            (0, 6),
        )

    def _draw_rtm_pose_2d_overlay(self, preview: np.ndarray, result: RtmPose3dResult) -> None:
        from ..analyzer import RealtimeAnalyzer

        keypoints = np.asarray(result.keypoints2d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32)
        if keypoints.ndim != 2 or keypoints.shape[0] < 17:
            return
        for start, end in RealtimeAnalyzer._rtm_pose_body_bones():
            if start >= len(keypoints) or end >= len(keypoints):
                continue
            if start < len(scores) and end < len(scores) and min(scores[start], scores[end]) < 0.22:
                continue
            a = tuple(np.round(keypoints[start, :2]).astype(int))
            b = tuple(np.round(keypoints[end, :2]).astype(int))
            cv2.line(preview, a, b, (80, 235, 255), 2, cv2.LINE_AA)
        for index in range(min(17, len(keypoints))):
            if index < len(scores) and scores[index] < 0.22:
                continue
            point = tuple(np.round(keypoints[index, :2]).astype(int))
            cv2.circle(preview, point, 3, (80, 255, 170), -1, cv2.LINE_AA)
        core = RealtimeAnalyzer._rtm_pose_3d_virtual_core(result, preview.shape[:2])
        if core is not None:
            hip_mid = tuple(np.round(core["hip_mid_2d"]).astype(int))
            shoulder_mid = tuple(np.round(core["shoulder_mid_2d"]).astype(int))
            cv2.line(preview, tuple(np.round(keypoints[11, :2]).astype(int)), tuple(np.round(keypoints[12, :2]).astype(int)), (255, 80, 210), 2, cv2.LINE_AA)
            cv2.line(preview, hip_mid, shoulder_mid, (0, 220, 255), 2, cv2.LINE_AA)
            previous = self._rtm_pose_3d_l0_reference_sample
            if previous is not None:
                _old_time, old_mid, old_line, old_confidence = previous
                if old_confidence >= 0.20:
                    old_start = tuple(np.round(old_mid - old_line * 0.5).astype(int))
                    old_end = tuple(np.round(old_mid + old_line * 0.5).astype(int))
                    old_center = tuple(np.round(old_mid).astype(int))
                    cv2.line(preview, old_start, old_end, (255, 120, 40), 2, cv2.LINE_AA)
                    cv2.circle(preview, old_center, 5, (255, 120, 40), -1, cv2.LINE_AA)
            previous_axis = self._rtm_pose_3d_axis_reference_sample
            if previous_axis is not None:
                _old_time, old_core, old_confidence = previous_axis
                if old_confidence >= 0.20:
                    old_hip_mid_raw = np.asarray(old_core["hip_mid_2d"], dtype=np.float32)
                    old_shoulder_mid_raw = np.asarray(old_core["shoulder_mid_2d"], dtype=np.float32)
                    old_shoulder_line = np.asarray(old_core["shoulder_line_2d"], dtype=np.float32)
                    old_hip_mid = tuple(np.round(old_hip_mid_raw).astype(int))
                    old_shoulder_mid = tuple(np.round(old_shoulder_mid_raw).astype(int))
                    old_l_shoulder = np.round(old_shoulder_mid_raw - old_shoulder_line * 0.5).astype(int)
                    old_r_shoulder = np.round(old_shoulder_mid_raw + old_shoulder_line * 0.5).astype(int)
                    cv2.line(preview, old_hip_mid, old_shoulder_mid, (255, 120, 40), 1, cv2.LINE_AA)
                    cv2.line(preview, tuple(old_l_shoulder), tuple(old_r_shoulder), (255, 120, 40), 1, cv2.LINE_AA)
            cv2.circle(preview, hip_mid, 5, (255, 80, 210), -1, cv2.LINE_AA)
        cv2.putText(preview, self._rtm_pose_label(), (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (80, 235, 255), 1, cv2.LINE_AA)

    def _draw_rtm_pose_3d_panel(self, panel: np.ndarray, result: RtmPose3dResult) -> None:
        from ..analyzer import RealtimeAnalyzer

        keypoints = np.asarray(result.keypoints3d, dtype=np.float32)
        scores = np.asarray(result.scores, dtype=np.float32)
        h, w = panel.shape[:2]
        if keypoints.ndim != 2 or keypoints.shape[0] < 17 or keypoints.shape[1] < 3:
            cv2.putText(panel, "bad 3D result", (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (80, 120, 255), 1, cv2.LINE_AA)
            return
        body = keypoints[:17, :3].copy()
        valid = np.ones(17, dtype=bool)
        if len(scores) >= 17:
            valid = scores[:17] >= 0.22
        if int(np.count_nonzero(valid)) < 5:
            cv2.putText(panel, "low confidence", (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (80, 120, 255), 1, cv2.LINE_AA)
            return

        origin = np.nanmean(body[valid], axis=0)
        body -= origin
        projected = np.column_stack((body[:, 0] + body[:, 2] * 0.36, body[:, 1] - body[:, 2] * 0.18))
        valid_points = projected[valid]
        min_xy = np.nanmin(valid_points, axis=0)
        max_xy = np.nanmax(valid_points, axis=0)
        span = np.maximum(max_xy - min_xy, 1.0)
        scale = min((w - 36) / max(1.0, span[0]), (h - 82) / max(1.0, span[1]))
        scale = max(0.12, min(8.0, scale))
        center = (min_xy + max_xy) * 0.5
        target = np.array([w * 0.52, h * 0.55], dtype=np.float32)

        def map_projected(point: np.ndarray) -> tuple[int, int]:
            mapped = (point - center) * scale + target
            return int(np.clip(mapped[0], 8, w - 8)), int(np.clip(mapped[1], 56, h - 8))

        def pt(index: int) -> tuple[int, int]:
            return map_projected(projected[index])

        for start, end in RealtimeAnalyzer._rtm_pose_body_bones():
            if valid[start] and valid[end]:
                cv2.line(panel, pt(start), pt(end), (245, 245, 245), 2, cv2.LINE_AA)
        if valid[5] and valid[6] and valid[11] and valid[12]:
            current_hip_mid = (projected[11] + projected[12]) * 0.5
            current_shoulder_mid = (projected[5] + projected[6]) * 0.5
            cv2.line(panel, map_projected(current_hip_mid), map_projected(current_shoulder_mid), (0, 220, 255), 2, cv2.LINE_AA)
        previous = self._rtm_pose_3d_axis_reference_sample
        if previous is not None:
            _old_time, old_core, old_confidence = previous
            old_hip_line = np.asarray(old_core["hip_line_3d"], dtype=np.float32)
            old_shoulder_line = np.asarray(old_core["shoulder_line_3d"], dtype=np.float32)
            old_pelvis = np.asarray(old_core["pelvis_3d"], dtype=np.float32) - origin
            old_shoulder = np.asarray(old_core.get("shoulder_mid_3d", old_core["pelvis_3d"]), dtype=np.float32) - origin
            if old_confidence >= 0.20 and float(np.linalg.norm(old_hip_line)) >= 0.08:
                old_start_3d = old_pelvis - old_hip_line * 0.5
                old_end_3d = old_pelvis + old_hip_line * 0.5
                old_start = np.array([old_start_3d[0] + old_start_3d[2] * 0.36, old_start_3d[1] - old_start_3d[2] * 0.18])
                old_end = np.array([old_end_3d[0] + old_end_3d[2] * 0.36, old_end_3d[1] - old_end_3d[2] * 0.18])
                cv2.line(panel, map_projected(old_start), map_projected(old_end), (255, 120, 40), 2, cv2.LINE_AA)
            if old_confidence >= 0.20 and float(np.linalg.norm(old_shoulder_line)) >= 0.08:
                old_start_3d = old_shoulder - old_shoulder_line * 0.5
                old_end_3d = old_shoulder + old_shoulder_line * 0.5
                old_start = np.array([old_start_3d[0] + old_start_3d[2] * 0.36, old_start_3d[1] - old_start_3d[2] * 0.18])
                old_end = np.array([old_end_3d[0] + old_end_3d[2] * 0.36, old_end_3d[1] - old_end_3d[2] * 0.18])
                old_pelvis_2d = np.array([old_pelvis[0] + old_pelvis[2] * 0.36, old_pelvis[1] - old_pelvis[2] * 0.18])
                old_shoulder_2d = np.array([old_shoulder[0] + old_shoulder[2] * 0.36, old_shoulder[1] - old_shoulder[2] * 0.18])
                cv2.line(panel, map_projected(old_start), map_projected(old_end), (255, 120, 40), 1, cv2.LINE_AA)
                cv2.line(panel, map_projected(old_pelvis_2d), map_projected(old_shoulder_2d), (255, 120, 40), 1, cv2.LINE_AA)
        for index in range(17):
            if not valid[index]:
                continue
            color = (80, 255, 170) if index in {11, 12} else (245, 245, 245)
            radius = 5 if index in {11, 12} else 4
            cv2.circle(panel, pt(index), radius, color, -1, cv2.LINE_AA)
        cv2.putText(panel, result.status, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (130, 170, 210), 1, cv2.LINE_AA)

    @staticmethod
    def _normalize_pose_angle(angle: float) -> float:
        while angle > 90.0:
            angle -= 180.0
        while angle < -90.0:
            angle += 180.0
        return angle

    @staticmethod
    def _centered_clamp(value: float, limit: float) -> float:
        return float(max(-limit, min(limit, value)))

    @staticmethod
    def _draw_axis_boxes(mask: np.ndarray, preview: np.ndarray) -> None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
            if cv2.contourArea(contour) < 24:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 190, 255), 1)

    @staticmethod
    def _draw_preview(preview: np.ndarray, positions: dict[str, float], confidence: float, draw_l0_line: bool = True) -> None:
        h, w = preview.shape[:2]
        if draw_l0_line:
            y = round(positions.get("L0", 0.5) * (h - 1))
            cv2.line(preview, (0, y), (w, y), (80, 255, 80), 2)
        labels = " ".join(f"{axis}:{value:.2f}" for axis, value in positions.items())
        cv2.putText(
            preview,
            f"{labels} conf:{confidence:.2f}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def _pose_v2_split_preview(self, preview: np.ndarray) -> np.ndarray:
        h, w = preview.shape[:2]
        if w < 220 or h < 180:
            return preview
        left_w = w // 2
        right_w = w - left_w
        left = np.zeros((h, left_w, 3), dtype=np.uint8)
        fit_scale = min(left_w / max(1, w), h / max(1, h))
        fit_w = max(1, int(round(w * fit_scale)))
        fit_h = max(1, int(round(h * fit_scale)))
        fitted = cv2.resize(preview, (fit_w, fit_h), interpolation=cv2.INTER_AREA)
        x0 = max(0, (left_w - fit_w) // 2)
        y0 = max(0, (h - fit_h) // 2)
        left[y0 : y0 + fit_h, x0 : x0 + fit_w] = fitted
        panel = np.zeros((h, right_w, 3), dtype=np.uint8)
        cv2.line(panel, (0, 0), (0, h - 1), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.putText(panel, "V2 full", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 230, 240), 1, cv2.LINE_AA)
        skeleton = self._pose_v2_complete_display_skeleton(self._pose_v2_last_skeleton, self._pose_v2_last_edge_notes)
        if not skeleton:
            cv2.putText(panel, "waiting", (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 160, 170), 1, cv2.LINE_AA)
            return np.concatenate((left, panel), axis=1)

        points = np.array(list(skeleton.values()), dtype=np.float32)
        min_xy = points.min(axis=0)
        max_xy = points.max(axis=0)
        span = np.maximum(max_xy - min_xy, 1.0)
        scale = min((right_w - 28) / max(1.0, span[0]), (h - 58) / max(1.0, span[1]))
        scale = max(0.12, min(2.8, scale))
        center = (min_xy + max_xy) * 0.5
        target = np.array([right_w * 0.5, h * 0.52], dtype=np.float32)

        def pt(name: str) -> tuple[int, int]:
            raw = np.array(skeleton[name], dtype=np.float32)
            mapped = (raw - center) * scale + target
            return int(np.clip(mapped[0], 8, right_w - 8)), int(np.clip(mapped[1], 36, h - 8))

        bones = (
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
            ("l_knee", "l_ankle"),
            ("r_knee", "r_ankle"),
            ("l_knee", "l_ankle_ghost"),
            ("r_knee", "r_ankle_ghost"),
        )
        for start, end in bones:
            if start in skeleton and end in skeleton:
                color = (80, 170, 255) if start.endswith("_ghost") or end.endswith("_ghost") else (245, 245, 245)
                cv2.line(panel, pt(start), pt(end), color, 2, cv2.LINE_AA)
        if "chest" in skeleton and "waist" in skeleton:
            cv2.line(panel, pt("chest"), pt("waist"), (60, 255, 180), 3, cv2.LINE_AA)
        if "waist" in skeleton and "pelvis" in skeleton:
            cv2.line(panel, pt("waist"), pt("pelvis"), (60, 255, 180), 3, cv2.LINE_AA)
        for name in skeleton:
            color = (245, 245, 245)
            radius = 4
            if name in {"pelvis", "l_hip", "r_hip"}:
                color = (70, 255, 170)
                radius = 5
            elif name.endswith("_ghost"):
                color = (80, 170, 255)
                radius = 3
            cv2.circle(panel, pt(name), radius, color, -1, cv2.LINE_AA)
        y = 46
        for note in self._pose_v2_last_edge_notes[:3]:
            short_note = note
            short_note = short_note.replace("head/upper body may be cropped", "top cropped")
            short_note = short_note.replace("legs may continue offscreen", "legs offscreen")
            short_note = short_note.replace("left side may be cropped", "left cropped")
            short_note = short_note.replace("right side may be cropped", "right cropped")
            cv2.putText(panel, short_note, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (110, 185, 255), 1, cv2.LINE_AA)
            y += 14
        return np.concatenate((left, panel), axis=1)

    @staticmethod
    def _pose_v2_complete_display_skeleton(
        skeleton: dict[str, tuple[int, int]],
        edge_notes: list[str],
    ) -> dict[str, tuple[int, int]]:
        if not skeleton:
            return {}
        completed = dict(skeleton)
        for side in ("l", "r"):
            hint = completed.get(f"{side}_knee_hint")
            if f"{side}_knee" not in completed and hint is not None:
                completed[f"{side}_knee"] = hint
                completed.pop(f"{side}_knee_hint", None)
            ankle_hint = completed.get(f"{side}_ankle_hint")
            if f"{side}_ankle" not in completed and ankle_hint is not None:
                completed[f"{side}_ankle"] = ankle_hint
                completed.pop(f"{side}_ankle_hint", None)

        bottom_cropped = any("legs may continue" in note for note in edge_notes)
        if bottom_cropped:
            for side in ("l", "r"):
                hip = completed.get(f"{side}_hip")
                knee = completed.get(f"{side}_knee")
                if hip is None or knee is None or f"{side}_ankle" in completed:
                    continue
                dx = knee[0] - hip[0]
                dy = max(12, knee[1] - hip[1])
                completed[f"{side}_ankle"] = (int(round(knee[0] + dx * 0.85)), int(round(knee[1] + dy * 0.92)))
                completed[f"{side}_ankle_ghost"] = completed.pop(f"{side}_ankle")
        return completed

    @staticmethod
    def _append_pose_preview(preview: np.ndarray, positions: dict[str, float], activity: float) -> np.ndarray:
        h, w = preview.shape[:2]
        panel_w = int(max(170, min(260, w * 0.34)))
        panel = np.zeros((h, panel_w, 3), dtype=np.uint8)
        scale = min(panel_w / 220.0, h / 360.0)
        cx = panel_w * 0.5
        base_y = h * 0.53
        l0 = positions.get("L0", 0.5) - 0.5
        l1 = positions.get("L1", 0.5) - 0.5
        l2 = positions.get("L2", 0.5) - 0.5
        r0 = positions.get("R0", 0.5) - 0.5
        r1 = positions.get("R1", 0.5) - 0.5
        r2 = positions.get("R2", 0.5) - 0.5
        sway = (l2 * 72.0 + r0 * 28.0) * scale
        roll = r1 * 78.0 * scale
        pitch = r2 * 44.0 * scale
        depth = 1.0 + l1 * 0.22
        stroke_y = l0 * 94.0 * scale
        shoulder_w = 78.0 * scale * depth
        hip_w = 58.0 * scale * depth
        torso_h = 106.0 * scale * (1.0 - l1 * 0.10)

        neck = np.array([cx - sway * 0.22, base_y - torso_h - stroke_y - pitch])
        hip = np.array([cx + sway, base_y - stroke_y + pitch * 0.28])
        head = neck + np.array([r0 * 18.0 * scale, -36.0 * scale])
        l_sh = neck + np.array([-shoulder_w * 0.5, roll])
        r_sh = neck + np.array([shoulder_w * 0.5, -roll])
        l_hip = hip + np.array([-hip_w * 0.5, -roll * 0.35])
        r_hip = hip + np.array([hip_w * 0.5, roll * 0.35])
        arm_drop = np.array([0.0, 62.0 * scale])
        leg_drop = np.array([0.0, 86.0 * scale])
        l_elbow = l_sh + np.array([-24.0 * scale - sway * 0.08, 34.0 * scale])
        r_elbow = r_sh + np.array([24.0 * scale - sway * 0.08, 34.0 * scale])
        l_hand = l_elbow + arm_drop + np.array([-10.0 * scale, 0.0])
        r_hand = r_elbow + arm_drop + np.array([10.0 * scale, 0.0])
        l_knee = l_hip + np.array([-14.0 * scale + sway * 0.10, 48.0 * scale])
        r_knee = r_hip + np.array([14.0 * scale + sway * 0.10, 48.0 * scale])
        l_foot = l_knee + leg_drop + np.array([-10.0 * scale, 0.0])
        r_foot = r_knee + leg_drop + np.array([10.0 * scale, 0.0])
        joints = {
            "head": head,
            "neck": neck,
            "l_sh": l_sh,
            "r_sh": r_sh,
            "l_elbow": l_elbow,
            "r_elbow": r_elbow,
            "l_hand": l_hand,
            "r_hand": r_hand,
            "l_hip": l_hip,
            "r_hip": r_hip,
            "l_knee": l_knee,
            "r_knee": r_knee,
            "l_foot": l_foot,
            "r_foot": r_foot,
        }

        def pt(name: str) -> tuple[int, int]:
            point = joints[name]
            return int(np.clip(point[0], 8, panel_w - 8)), int(np.clip(point[1], 8, h - 8))

        bones = [
            ("head", "neck"),
            ("neck", "l_sh"),
            ("neck", "r_sh"),
            ("l_sh", "l_elbow"),
            ("l_elbow", "l_hand"),
            ("r_sh", "r_elbow"),
            ("r_elbow", "r_hand"),
            ("neck", "l_hip"),
            ("neck", "r_hip"),
            ("l_hip", "r_hip"),
            ("l_hip", "l_knee"),
            ("l_knee", "l_foot"),
            ("r_hip", "r_knee"),
            ("r_knee", "r_foot"),
        ]
        cv2.putText(panel, "Pose", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(panel, f"{activity:.3f}", (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (160, 180, 200), 1, cv2.LINE_AA)
        for a, b in bones:
            cv2.line(panel, pt(a), pt(b), (245, 245, 245), 3, cv2.LINE_AA)
        for name in joints:
            radius = 6 if name in {"head", "neck"} else 5
            cv2.circle(panel, pt(name), radius, (255, 110, 25), -1, cv2.LINE_AA)
            cv2.circle(panel, pt(name), radius, (255, 220, 120), 1, cv2.LINE_AA)
        return np.concatenate((preview, panel), axis=1)
