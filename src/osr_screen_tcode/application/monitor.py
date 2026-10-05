"""Final command, travel status, axis and recent-script chart rendering.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import re
import time
import tkinter as tk
from ..analyzer import SIX_AXES


class MonitorMixin:
    def _update_command_monitor(self, command: str) -> None:
        values = self._parse_axis_values(command)
        if not values:
            return
        self._last_axis_values.update(values)
        now = time.perf_counter()
        self._script_history.append((now, dict(self._last_axis_values)))
        l0 = values.get("L0")
        if l0 is not None:
            self.l0_status.set(f"L0 {l0:04d}")
            self._update_stroke_status(l0)
            self._draw_stroke_monitor(l0)
            self._previous_l0_value = l0
        self._draw_axis_monitor(self._last_axis_values)
        self._draw_script_curve()

    @staticmethod
    def _parse_l0_value(command: str) -> int | None:
        match = re.search(r"L0(\d{4})", command)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _parse_axis_values(command: str) -> dict[str, int]:
        return {
            axis: int(value)
            for axis, value in re.findall(r"([LR][0-2])(\d{4})", command)
        }

    def _update_stroke_status(self, value: int) -> None:
        try:
            low = max(0, min(9999, int(float(self.min_value.get()))))
            high = max(0, min(9999, int(float(self.max_value.get()))))
        except (tk.TclError, ValueError):
            low, high = 0, 9999
        if low > high:
            low, high = high, low
        span = max(1, high - low)
        ratio = max(0.0, min(1.0, (value - low) / span))
        delta = value - self._previous_l0_value
        if delta <= -22:
            label = self._t("向下限移动")
        elif delta >= 22:
            label = self._t("向上限移动")
        elif ratio <= 0.22:
            label = self._t("下限端点")
        elif ratio >= 0.78:
            label = self._t("上限端点")
        else:
            label = self._t("中段")
        self.stroke_status.set(f"{label}  {ratio * 100:.0f}%")

    def _draw_stroke_monitor(self, value: int) -> None:
        if not hasattr(self, "stroke_canvas"):
            return
        canvas = self.stroke_canvas
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        scale = self.main_panes.scale
        pad = round(24 * scale)
        try:
            low = max(0, min(9999, int(float(self.min_value.get()))))
            high = max(0, min(9999, int(float(self.max_value.get()))))
        except (tk.TclError, ValueError):
            low, high = 0, 9999
        if low > high:
            low, high = high, low

        def y_for(v: int) -> float:
            return height - pad - (v / 9999) * (height - 2 * pad)

        x = width // 2
        canvas.create_rectangle(x - 8, pad, x + 8, height - pad, fill="#e7e7e7", outline="#c5c5c5")
        canvas.create_rectangle(x - 14, y_for(high), x + 14, y_for(low), fill="#bfe7cc", outline="#58a873")
        y = y_for(max(0, min(9999, value)))
        canvas.create_oval(x - 19, y - 8, x + 19, y + 8, fill="#176f3f", outline="")
        canvas.create_text(x, pad - 2, text=self._t("上限方向"), anchor="s", fill="#555")
        canvas.create_text(x, height - pad + 2, text=self._t("下限方向"), anchor="n", fill="#555")

    def _draw_axis_monitor(self, values: dict[str, int]) -> None:
        if not hasattr(self, "axis_canvas"):
            return
        canvas = self.axis_canvas
        canvas.delete("all")
        width = max(360, canvas.winfo_width() or int(canvas["width"]))
        height = int(canvas["height"])
        scale = self.main_panes.scale
        left = round(42 * scale)
        right = width - round(52 * scale)
        row_h = height / 6.0
        active_axes = set(self._active_axes())
        for index, axis in enumerate(SIX_AXES):
            y = int(row_h * index + row_h * 0.5)
            value = max(0, min(9999, int(values.get(axis, 5000))))
            try:
                low = max(0, min(9999, int(float(self.axis_min_vars[axis].get()))))
                high = max(0, min(9999, int(float(self.axis_max_vars[axis].get()))))
            except (tk.TclError, ValueError):
                low, high = 0, 9999
            if low > high:
                low, high = high, low

            def x_for(v: int) -> float:
                return left + (v / 9999) * max(1, right - left)

            muted = axis not in active_axes
            track = "#eeeeee" if muted else "#e3e7ea"
            range_fill = "#d8ecdf" if axis == "L0" else "#dfe8f7"
            marker = "#176f3f" if axis == "L0" else "#335f9f"
            text_fill = "#9a9a9a" if muted else "#222222"
            canvas.create_text(10, y, text=axis, anchor="w", fill=text_fill, font=("", 9, "bold"))
            canvas.create_rectangle(left, y - 4, right, y + 4, fill=track, outline="")
            canvas.create_rectangle(x_for(low), y - 5, x_for(high), y + 5, fill=range_fill, outline="")
            x = x_for(value)
            canvas.create_rectangle(x - 3, y - 9, x + 3, y + 9, fill=marker if not muted else "#bdbdbd", outline="")
            canvas.create_text(width - 8, y, text=f"{value:04d}", anchor="e", fill=text_fill, font=("", 9))

    def _draw_script_curve(self) -> None:
        if not hasattr(self, "curve_canvas"):
            return
        canvas = self.curve_canvas
        canvas.delete("all")
        width = max(360, canvas.winfo_width() or int(canvas["width"]))
        height = int(canvas["height"])
        scale = self.main_panes.scale
        pad_l = round(46 * scale)
        pad_r = round(12 * scale)
        pad_t = round(34 * scale)
        pad_b = round(22 * scale)
        plot_w = max(1, width - pad_l - pad_r)
        plot_h = max(1, height - pad_t - pad_b)
        canvas.create_rectangle(0, 0, width, height, fill="#101418", outline="")
        canvas.create_text(10, 8, text=self._t("脚本曲线"), anchor="nw", fill="#e9eef2", font=("", 10, "bold"))
        canvas.create_text(width - 10, 8, text=self._t("最近12秒 / 实际输出"), anchor="ne", fill="#95a1aa", font=("", 9))
        for label, value in (("9999", 9999), ("5000", 5000), ("0000", 0)):
            y = pad_t + (1.0 - value / 9999.0) * plot_h
            canvas.create_line(pad_l, y, width - pad_r, y, fill="#27313a", dash=(3, 5) if value != 5000 else ())
            canvas.create_text(pad_l - 8, y, text=label, anchor="e", fill="#8c98a3", font=("", 8))
        canvas.create_rectangle(pad_l, pad_t, width - pad_r, height - pad_b, outline="#2e3942")
        if len(self._script_history) < 2:
            canvas.create_text(
                pad_l + plot_w / 2,
                pad_t + plot_h / 2,
                text=self._t("开始输出后显示曲线"),
                fill="#7f8c96",
                font=("", 11),
            )
            return
        latest = self._script_history[-1][0]
        window_s = 12.0
        points = [(ts, values) for ts, values in self._script_history if latest - ts <= window_s]
        if len(points) < 2:
            return

        def x_for(ts: float) -> float:
            age = max(0.0, min(window_s, latest - ts))
            return pad_l + plot_w * (1.0 - age / window_s)

        def y_for(value: int) -> float:
            return pad_t + (1.0 - max(0, min(9999, value)) / 9999.0) * plot_h

        colors = {
            "L0": "#46d184",
            "L1": "#67a6ff",
            "L2": "#ffcc66",
            "R0": "#ff7f7f",
            "R1": "#b58cff",
            "R2": "#69d2e7",
        }
        active_axes = self._active_axes()
        for axis in active_axes:
            coords: list[float] = []
            for ts, values in points:
                coords.extend((x_for(ts), y_for(int(values.get(axis, 5000)))))
            if len(coords) >= 4:
                canvas.create_line(*coords, fill=colors.get(axis, "#ffffff"), width=3 if axis == "L0" else 2, smooth=True)
        legend_x = pad_l
        for axis in active_axes:
            color = colors.get(axis, "#ffffff")
            canvas.create_rectangle(legend_x, height - 15 * scale, legend_x + 10 * scale, height - 5 * scale, fill=color, outline="")
            canvas.create_text(legend_x + 14 * scale, height - 11 * scale, text=axis, anchor="w", fill="#d8e0e6", font=("", 8, "bold"))
            legend_x += 44 * scale
