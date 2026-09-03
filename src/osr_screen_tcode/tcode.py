from __future__ import annotations

import time
from dataclasses import dataclass


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class TCodeCommand:
    axis: str
    value: int
    interval_ms: int

    def encode(self) -> bytes:
        return f"{self.axis}{self.value:04d}I{self.interval_ms}\n".encode("ascii")


@dataclass(frozen=True)
class MultiTCodeCommand:
    values: dict[str, int]
    interval_ms: int

    def encode(self) -> bytes:
        parts = [f"{axis}{value:04d}I{self.interval_ms}" for axis, value in self.values.items()]
        return (" ".join(parts) + "\n").encode("ascii")


class TCodeMapper:
    def __init__(
        self,
        axis: str = "L0",
        min_value: int = 1500,
        max_value: int = 8500,
        invert: bool = False,
        interval_ms: int = 33,
    ) -> None:
        self.axis = axis.strip().upper() or "L0"
        self.min_value = int(clamp(min_value, 0, 9999))
        self.max_value = int(clamp(max_value, 0, 9999))
        if self.min_value > self.max_value:
            self.min_value, self.max_value = self.max_value, self.min_value
        self.invert = invert
        self.interval_ms = max(1, int(interval_ms))

    def map_position(self, position: float) -> TCodeCommand:
        position = clamp(position, 0.0, 1.0)
        if self.invert:
            position = 1.0 - position
        span = self.max_value - self.min_value
        value = round(self.min_value + span * position)
        return TCodeCommand(self.axis, int(clamp(value, 0, 9999)), self.interval_ms)

    @property
    def center_value(self) -> int:
        return round((self.min_value + self.max_value) / 2)


class SafeTCodeOutput:
    def __init__(
        self,
        mapper: TCodeMapper,
        max_step: int = 260,
        min_activity: float = 0.004,
        idle_mode: str = "Hold",
    ) -> None:
        self.mapper = mapper
        self.max_step = max(1, int(max_step))
        self.min_activity = max(0.0, float(min_activity))
        self.idle_mode = idle_mode
        self._value = mapper.center_value
        self._last_active_at = time.perf_counter()

    def next_command(self, position: float, activity: float) -> TCodeCommand:
        if activity >= self.min_activity:
            target = self.mapper.map_position(position).value
            self._last_active_at = time.perf_counter()
        elif self.idle_mode.lower().startswith("center"):
            target = self.mapper.center_value
        else:
            target = self._value

        delta = target - self._value
        if abs(delta) > self.max_step:
            self._value += self.max_step if delta > 0 else -self.max_step
        else:
            self._value = target
        return TCodeCommand(self.mapper.axis, int(clamp(self._value, 0, 9999)), self.mapper.interval_ms)

    def center_command(self, interval_ms: int | None = None) -> TCodeCommand:
        self._value = self.mapper.center_value
        return TCodeCommand(self.mapper.axis, self._value, interval_ms or self.mapper.interval_ms)


class MultiAxisSafeOutput:
    def __init__(
        self,
        axes: list[str],
        min_value: int = 1500,
        max_value: int = 8500,
        invert_l0: bool = False,
        interval_ms: int = 33,
        max_step: int = 260,
        min_activity: float = 0.004,
        idle_mode: str = "Hold",
        axis_limits: dict[str, tuple[int, int]] | None = None,
        startup_ramp_ms: int = 0,
        position_scale: float = 1.0,
        axis_position_scales: dict[str, float] | None = None,
        enable_extreme_reset: bool = True,
        extreme_hold_ms: int = 900,
        extreme_margin: float = 0.06,
        enable_endpoint_guard: bool = True,
        endpoint_margin: float = 0.10,
    ) -> None:
        self.axes = axes
        self.min_value = int(clamp(min_value, 0, 9999))
        self.max_value = int(clamp(max_value, 0, 9999))
        if self.min_value > self.max_value:
            self.min_value, self.max_value = self.max_value, self.min_value
        self.axis_limits = {
            axis: self._normalize_limit(axis_limits.get(axis, (self.min_value, self.max_value)) if axis_limits else (self.min_value, self.max_value))
            for axis in axes
        }
        self.invert_l0 = invert_l0
        self.interval_ms = max(1, int(interval_ms))
        self.max_step = max(1, int(max_step))
        self.min_activity = max(0.0, float(min_activity))
        self.idle_mode = idle_mode
        self.startup_ramp_ms = max(0, int(startup_ramp_ms))
        self.position_scale = clamp(float(position_scale), 0.0, 3.0)
        self.axis_position_scales = {
            axis: clamp(float(scale), 0.0, 3.0)
            for axis, scale in (axis_position_scales or {}).items()
        }
        self.enable_extreme_reset = bool(enable_extreme_reset)
        self.extreme_hold_ms = max(150, int(extreme_hold_ms))
        self.extreme_margin = clamp(float(extreme_margin), 0.01, 0.18)
        self.enable_endpoint_guard = bool(enable_endpoint_guard)
        self.endpoint_margin = clamp(float(endpoint_margin), 0.0, 0.25)
        self._started_at = time.perf_counter()
        self._values = {axis: self._center_for(axis) for axis in axes}
        self._extreme_since: dict[str, float | None] = {axis: None for axis in axes}
        self._extreme_side: dict[str, int] = {axis: 0 for axis in axes}

    @property
    def center_value(self) -> int:
        return round((self.min_value + self.max_value) / 2)

    def next_command(self, positions: dict[str, float], activity: float) -> MultiTCodeCommand:
        values: dict[str, int] = {}
        now = time.perf_counter()
        for axis in self.axes:
            if activity < self.min_activity:
                target = self._center_for(axis) if self.idle_mode.lower().startswith("center") else self._values[axis]
            else:
                target = self._map_axis(axis, positions.get(axis, 0.5))
            target = self._release_stuck_extreme(axis, target, activity, now)
            if self.startup_ramp_ms > 0:
                elapsed = (now - self._started_at) * 1000.0
                ramp = min(1.0, elapsed / self.startup_ramp_ms)
                target = self._center_for(axis) + (target - self._center_for(axis)) * ramp
            current = self._values[axis]
            delta = target - current
            if abs(delta) > self.max_step:
                current += self.max_step if delta > 0 else -self.max_step
            else:
                current = target
            self._values[axis] = int(clamp(current, 0, 9999))
            values[axis] = self._values[axis]
        return MultiTCodeCommand(values, self.interval_ms)

    def center_command(self, interval_ms: int | None = None) -> MultiTCodeCommand:
        for axis in self.axes:
            self._values[axis] = self._center_for(axis)
            self._extreme_since[axis] = None
            self._extreme_side[axis] = 0
        return MultiTCodeCommand(dict(self._values), interval_ms or self.interval_ms)

    def _map_axis(self, axis: str, position: float) -> int:
        position = clamp(position, 0.0, 1.0)
        scale = self.axis_position_scales.get(axis, self.position_scale)
        position = clamp(0.5 + (position - 0.5) * scale, 0.0, 1.0)
        if axis == "L0" and self.invert_l0:
            position = 1.0 - position
        if self.enable_endpoint_guard and axis == "L0":
            margin = self.endpoint_margin
            position = margin + (1.0 - margin * 2.0) * position
        low, high = self.axis_limits.get(axis, (self.min_value, self.max_value))
        span = high - low
        return int(clamp(round(low + span * position), 0, 9999))

    def _release_stuck_extreme(self, axis: str, target: float, activity: float, now: float) -> float:
        if not self.enable_extreme_reset:
            return target
        low, high = self.axis_limits.get(axis, (self.min_value, self.max_value))
        span = max(1, high - low)
        margin = max(50, round(span * self.extreme_margin))
        current = self._values[axis]
        near_low = current <= low + margin and target <= low + margin
        near_high = current >= high - margin and target >= high - margin
        side = -1 if near_low else 1 if near_high else 0
        if side == 0:
            self._extreme_since[axis] = None
            self._extreme_side[axis] = 0
            return target
        if self._extreme_side.get(axis) != side or self._extreme_since.get(axis) is None:
            self._extreme_side[axis] = side
            self._extreme_since[axis] = now
            return target

        held_ms = (now - (self._extreme_since[axis] or now)) * 1000.0
        if held_ms < self.extreme_hold_ms:
            return target

        center = self._center_for(axis)
        if activity < self.min_activity:
            return center

        if held_ms >= self.extreme_hold_ms * 2.5:
            release = 0.62 if axis == "L0" else 0.50
            return center + (target - center) * release
        return target

    @staticmethod
    def _normalize_limit(limit: tuple[int, int]) -> tuple[int, int]:
        low = int(clamp(limit[0], 0, 9999))
        high = int(clamp(limit[1], 0, 9999))
        if low > high:
            low, high = high, low
        return low, high

    def _center_for(self, axis: str) -> int:
        low, high = self.axis_limits.get(axis, (self.min_value, self.max_value))
        return round((low + high) / 2)
