from __future__ import annotations

import json
import time
from pathlib import Path


class FunscriptRecorder:
    def __init__(self) -> None:
        self._start = 0.0
        self._actions: list[dict[str, int]] = []
        self._last_pos: int | None = None

    @property
    def is_recording(self) -> bool:
        return self._start > 0.0

    @property
    def action_count(self) -> int:
        return len(self._actions)

    def start(self) -> None:
        self._start = time.perf_counter()
        self._actions.clear()
        self._last_pos = None

    def stop(self) -> None:
        self._start = 0.0
        self._last_pos = None

    def add(self, position: float) -> None:
        if not self.is_recording:
            return
        pos = max(0, min(100, round(position * 100)))
        if self._last_pos is not None and abs(pos - self._last_pos) < 2:
            return
        at = round((time.perf_counter() - self._start) * 1000)
        self._actions.append({"at": at, "pos": pos})
        self._last_pos = pos

    def save(self, path: Path) -> None:
        data = {
            "version": "1.0",
            "inverted": False,
            "range": 100,
            "actions": self._actions,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class MultiAxisFunscriptRecorder:
    SUFFIXES = {
        "L0": "",
        "L1": ".surge",
        "L2": ".sway",
        "R0": ".twist",
        "R1": ".roll",
        "R2": ".pitch",
    }

    def __init__(self) -> None:
        self._start = 0.0
        self._actions: dict[str, list[dict[str, int]]] = {}
        self._last_pos: dict[str, int] = {}

    @property
    def is_recording(self) -> bool:
        return self._start > 0.0

    @property
    def action_count(self) -> int:
        return sum(len(actions) for actions in self._actions.values())

    def start(self) -> None:
        self._start = time.perf_counter()
        self._actions.clear()
        self._last_pos.clear()

    def stop(self) -> None:
        self._start = 0.0
        self._last_pos.clear()

    def add(self, positions: dict[str, float]) -> None:
        if not self.is_recording:
            return
        at = round((time.perf_counter() - self._start) * 1000)
        self.add_at(positions, at)

    def add_at(self, positions: dict[str, float], at: int) -> None:
        if not self.is_recording:
            return
        for axis, position in positions.items():
            pos = max(0, min(100, round(position * 100)))
            if axis in self._last_pos and abs(pos - self._last_pos[axis]) < 2:
                continue
            self._actions.setdefault(axis, []).append({"at": at, "pos": pos})
            self._last_pos[axis] = pos

    def save(self, path: Path) -> list[Path]:
        written: list[Path] = []
        stem = path.name
        if stem.endswith(".funscript"):
            stem = stem[: -len(".funscript")]
        for axis, actions in self._actions.items():
            suffix = self.SUFFIXES.get(axis, f".{axis.lower()}")
            axis_path = path.with_name(f"{stem}{suffix}.funscript")
            data = {
                "version": "1.0",
                "inverted": False,
                "range": 100,
                "metadata": {"axis": axis},
                "actions": actions,
            }
            axis_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            written.append(axis_path)
        return written
