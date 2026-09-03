from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class TrackingResult:
    position: float
    confidence: float
    activity: float
    preview_bgr: np.ndarray


class MotionTracker:
    def __init__(
        self,
        smoothing: float = 0.35,
        deadzone: float = 0.015,
        mode: str = "Motion Center",
        motion_gain: float = 1.0,
    ) -> None:
        self.smoothing = max(0.0, min(0.98, smoothing))
        self.deadzone = max(0.0, min(0.25, deadzone))
        self.mode = mode
        self.motion_gain = max(0.1, min(8.0, motion_gain))
        self._prev_gray: np.ndarray | None = None
        self._position = 0.5
        self._phase = 0.0

    def reset(self) -> None:
        self._prev_gray = None
        self._position = 0.5
        self._phase = 0.0

    def process(self, frame_bgr: np.ndarray) -> TrackingResult:
        preview = frame_bgr.copy()
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._draw_preview(preview, self._position, 0.0)
            return TrackingResult(self._position, 0.0, 0.0, preview)

        diff = cv2.absdiff(gray, self._prev_gray)
        _, mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        activity = float(np.count_nonzero(mask)) / float(mask.size)

        mode = self.mode.lower()
        if mode.startswith("optical"):
            measured, confidence = self._optical_flow(gray, preview, activity)
        elif mode.startswith("activity"):
            measured, confidence = self._activity_pulse(activity)
        else:
            measured, confidence = self._motion_center(mask, preview, activity)

        delta = measured - self._position
        if abs(delta) >= self.deadzone:
            self._position = self._position * self.smoothing + measured * (1.0 - self.smoothing)

        self._prev_gray = gray
        self._draw_preview(preview, self._position, confidence)
        return TrackingResult(self._position, confidence, activity, preview)

    def _motion_center(
        self,
        mask: np.ndarray,
        preview: np.ndarray,
        activity: float,
    ) -> tuple[float, float]:
        measured = self._position
        confidence = min(1.0, activity * 12.0)
        moments = cv2.moments(mask)
        if moments["m00"] > 1.0:
            center_y = moments["m01"] / moments["m00"]
            measured = center_y / max(1, mask.shape[0] - 1)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
                if cv2.contourArea(contour) < 24:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 190, 255), 1)
        return measured, confidence

    def _optical_flow(
        self,
        gray: np.ndarray,
        preview: np.ndarray,
        activity: float,
    ) -> tuple[float, float]:
        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray,
            gray,
            None,
            0.5,
            3,
            21,
            3,
            5,
            1.2,
            0,
        )
        mag, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        moving = mag > max(0.25, np.percentile(mag, 75))
        confidence = min(1.0, float(np.mean(mag)) * 0.55 + activity * 6.0)
        if not np.any(moving):
            return self._position, confidence

        dy = float(np.median(flow[..., 1][moving]))
        h = max(1, gray.shape[0])
        step = (dy / h) * self.motion_gain * 3.5
        measured = max(0.0, min(1.0, self._position + step))

        center_x = gray.shape[1] // 2
        center_y = gray.shape[0] // 2
        cv2.arrowedLine(
            preview,
            (center_x, center_y),
            (center_x, round(center_y + dy * 8)),
            (255, 180, 60),
            2,
            tipLength=0.25,
        )
        return measured, confidence

    def _activity_pulse(self, activity: float) -> tuple[float, float]:
        confidence = min(1.0, activity * 18.0)
        if confidence < 0.04:
            return self._position, confidence
        speed = 0.08 + min(0.42, activity * 8.0) * self.motion_gain
        amplitude = min(0.48, 0.12 + activity * 8.5)
        self._phase = (self._phase + speed) % 1.0
        triangle = 1.0 - abs(self._phase * 2.0 - 1.0)
        measured = 0.5 - amplitude + triangle * amplitude * 2.0
        return max(0.0, min(1.0, measured)), confidence

    @staticmethod
    def _draw_preview(preview: np.ndarray, position: float, confidence: float) -> None:
        h, w = preview.shape[:2]
        y = round(position * (h - 1))
        cv2.line(preview, (0, y), (w, y), (80, 255, 80), 2)
        cv2.putText(
            preview,
            f"pos {position:.2f} conf {confidence:.2f}",
            (8, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
