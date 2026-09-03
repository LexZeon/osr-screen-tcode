from __future__ import annotations

from dataclasses import dataclass
import sys

import mss
import numpy as np


def _keep_mss_from_changing_process_dpi() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        from mss.windows.gdi import MSSImplGdi
    except Exception:
        return
    MSSImplGdi._set_dpi_awareness = lambda self: None  # type: ignore[method-assign]


_keep_mss_from_changing_process_dpi()


@dataclass(frozen=True)
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int

    def normalized(self) -> "ScreenRegion":
        return ScreenRegion(
            max(0, self.x),
            max(0, self.y),
            max(16, self.width),
            max(16, self.height),
        )

    def to_mss(self) -> dict[str, int]:
        region = self.normalized()
        return {
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        }


class ScreenCapture:
    def __init__(self, region: ScreenRegion) -> None:
        self.region = region.normalized()
        self._sct = mss.mss()

    def grab_bgr(self) -> np.ndarray:
        raw = self._sct.grab(self.region.to_mss())
        frame = np.asarray(raw)
        return frame[:, :, :3]

    def close(self) -> None:
        self._sct.close()

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
