from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import math
import threading
import time

import mss
import numpy as np

from .screen_geometry import desktop_bounds, physical_dpi_context, screen_monitors, virtual_screen_bounds


def _pixel(value) -> int:
    try:
        pixel = int(value)
        if isinstance(value, bool) or pixel != float(value):
            raise ValueError
        return pixel
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Screen coordinates must be integer pixels / 屏幕坐标必须为整数像素") from exc


@dataclass(frozen=True)
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int

    def normalized(self) -> "ScreenRegion":
        return ScreenRegion(*(_pixel(value) for value in (self.x, self.y, self.width, self.height)))

    def to_mss(self) -> dict[str, int]:
        region = self.normalized()
        return {
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        }


def validate_region(region: ScreenRegion, monitors=None) -> ScreenRegion:
    """Validate without shifting, resizing, or removing negative coordinates."""
    region = region.normalized()
    if region.width < 16 or region.height < 16:
        raise ValueError("Screen region must be at least 16 x 16 pixels / 屏幕区域至少为 16 x 16 像素")
    monitors = screen_monitors() if monitors is None else list(monitors)
    bounds = desktop_bounds(monitors)
    right, bottom = region.x + region.width, region.y + region.height
    if (region.x < bounds["left"] or region.y < bounds["top"]
            or right > bounds["left"] + bounds["width"] or bottom > bounds["top"] + bounds["height"]):
        raise ValueError("Screen region is outside the current desktop; select it again / 屏幕区域超出当前桌面，请重新框选")
    if not any(region.x < monitor["left"] + monitor["width"] and right > monitor["left"]
               and region.y < monitor["top"] + monitor["height"] and bottom > monitor["top"] for monitor in monitors):
        raise ValueError("Screen region contains no display pixels; select it again / 屏幕区域位于显示器空隙，请重新框选")
    return region


def _topology(monitors):
    return tuple(sorted((monitor["left"], monitor["top"], monitor["width"], monitor["height"]) for monitor in monitors))


class ScreenCapture:
    def __init__(self, region: ScreenRegion) -> None:
        self._sct = None
        self._dpi = physical_dpi_context()
        self._dpi.__enter__()
        self._closed = False
        try:
            monitors = screen_monitors()
            self.region = validate_region(region, monitors)
            self._topology = _topology(monitors)
            self._next_topology_check = time.perf_counter() + 0.5
            self._gap_mask = self._desktop_gap_mask(monitors)
            self._sct = mss.mss()
        except BaseException:
            self.close()
            raise

    def _desktop_gap_mask(self, monitors):
        region = self.region
        # The common one-display region needs no mask or extra per-frame copy.
        if any(region.x >= monitor["left"] and region.y >= monitor["top"]
               and region.x + region.width <= monitor["left"] + monitor["width"]
               and region.y + region.height <= monitor["top"] + monitor["height"] for monitor in monitors):
            return None
        gaps = np.ones((region.height, region.width), dtype=bool)
        for monitor in monitors:
            left = max(0, monitor["left"] - region.x)
            top = max(0, monitor["top"] - region.y)
            right = min(region.width, monitor["left"] + monitor["width"] - region.x)
            bottom = min(region.height, monitor["top"] + monitor["height"] - region.y)
            if right > left and bottom > top:
                gaps[top:bottom, left:right] = False
        return gaps if gaps.any() else None

    def grab_bgr(self) -> np.ndarray:
        if self._closed:
            raise RuntimeError("Screen capture is closed")
        now = time.perf_counter()
        if now >= self._next_topology_check:
            if _topology(screen_monitors()) != self._topology:
                raise RuntimeError("Display layout or resolution changed; select the screen region again / 显示器布局或分辨率已改变，请重新框选")
            self._next_topology_check = now + 0.5
        raw = self._sct.grab(self.region.to_mss())
        frame = np.asarray(raw)
        if frame.ndim != 3 or frame.shape[:2] != (self.region.height, self.region.width) or frame.shape[2] < 3:
            raise RuntimeError("Captured image dimensions do not match the selected region / 采集图像尺寸与框选区域不符")
        result = frame[:, :, :3]
        if self._gap_mask is not None:
            result = result.copy()
            result[self._gap_mask] = 0
        return result

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._sct is not None:
                self._sct.close()
        finally:
            self._dpi.__exit__(None, None, None)

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def capture_fps(value: object) -> int:
    try:
        number = float(value)
        return max(1, min(120, round(number))) if math.isfinite(number) else 45
    except (TypeError, ValueError, OverflowError):
        return 45


@dataclass(frozen=True)
class CapturedFrame:
    sequence: int
    bgr: np.ndarray
    captured_at: float
    fps: float


class LatestScreenCapture:
    """Thread-owned MSS capture with one replaceable frame, never a frame backlog.

    fps_provider must read ordinary Python state, not a GUI variable.
    """

    def __init__(self, region: ScreenRegion, fps_provider, capture_factory=ScreenCapture) -> None:
        self.region = region
        self.fps_provider = fps_provider
        self.capture_factory = capture_factory
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._latest: CapturedFrame | None = None
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="screen-capture", daemon=True)

    def __enter__(self) -> "LatestScreenCapture":
        self._thread.start()
        return self

    def _run(self) -> None:
        recent = deque()
        sequence = 0
        try:
            # MSS uses thread-local native resources; create and close on this thread.
            with self.capture_factory(self.region) as capture:
                while not self._stop.is_set():
                    started = time.perf_counter()
                    frame = np.array(capture.grab_bgr(), copy=True, order="C")
                    now = time.perf_counter()
                    recent.append(now)
                    while len(recent) > 2 and recent[0] < now - 1.0:
                        recent.popleft()
                    fps = (len(recent) - 1) / (now - recent[0]) if len(recent) > 1 else 0.0
                    sequence += 1
                    with self._condition:
                        self._latest = CapturedFrame(sequence, frame, started, fps)
                        self._condition.notify_all()
                    while not self._stop.is_set():
                        remaining = 1.0 / capture_fps(self.fps_provider()) - (time.perf_counter() - started)
                        if remaining <= 0:
                            break
                        self._stop.wait(min(0.05, remaining))
        except Exception as exc:
            with self._condition:
                self._error = exc
        finally:
            self._stop.set()
            with self._condition:
                self._condition.notify_all()

    def next_frame(self, after_sequence: int, timeout: float = 0.1) -> CapturedFrame | None:
        with self._condition:
            self._condition.wait_for(
                lambda: self._stop.is_set() or self._error is not None
                or (self._latest is not None and self._latest.sequence > after_sequence), timeout=timeout)
            if self._error is not None:
                raise RuntimeError(f"Screen capture failed: {self._error}") from self._error
            if self._stop.is_set():
                return None
            return self._latest if self._latest is not None and self._latest.sequence > after_sequence else None

    def close(self) -> None:
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        self._thread.join(timeout=1.0)

    def __exit__(self, *_: object) -> None:
        self.close()
