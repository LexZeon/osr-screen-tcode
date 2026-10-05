"""Screen region, video/audio input controls and physical region selection.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
from collections.abc import Callable
import tkinter as tk
from tkinter import messagebox, ttk
from ..capture import ScreenRegion, validate_region
from ..ui_widgets import WideCombobox


class SourcesMixin:
    def _read_screen_region(self) -> ScreenRegion:
        # Read the complete tuple without IntVar's float-to-int truncation.
        try:
            region = ScreenRegion(*(self.getvar(str(variable)) for variable in
                                  (self.x, self.y, self.width, self.height))).normalized()
            if region.width < 16 or region.height < 16:
                raise ValueError
            return region
        except (tk.TclError, ValueError, TypeError) as exc:
            raise ValueError(self._dt("坐标必须是整数，区域宽高至少为 16 像素。",
                "Coordinates must be integers; width and height must be at least 16 pixels.")) from exc

    def _input_geometry_changed(self, *_args) -> None:
        # A capture owns an immutable rectangle. Do not show new settings while
        # continuing to emit output from the old source, including script edits.
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            self.stop()
        try:
            self._screen_region_snapshot = self._read_screen_region()
        except ValueError:
            pass  # A temporary blank/minus sign must not replace a complete ROI.
        self._active_screen_region = None
        self.reset_visual_reference()

    def _refresh_region_controls(self) -> None:
        busy = bool((self.worker and self.worker.is_alive()) or self._video_analysis_active())
        if busy == self._region_busy:
            return
        self._region_busy = busy
        for widget, idle_state in self._input_widgets:
            widget.configure(state="disabled" if busy else idle_state)

    def _validate_start_region(self) -> bool:
        try:
            region = validate_region(self._read_screen_region())
        except (ValueError, OSError, RuntimeError) as exc:
            self.status.set(str(exc))
            messagebox.showerror(self._dt("请重新选择屏幕区域", "Select the screen region again"),
                                 str(exc), parent=self)
            return False
        self._screen_region_snapshot = region
        return True

    def _region_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "屏幕区域", row)
        for label, variable in (("X", self.x), ("Y", self.y), ("宽", self.width), ("高", self.height)):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(parent, textvariable=variable, width=12)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
            self._input_widgets.append((entry, "normal"))
            row += 1
        button = ttk.Button(parent, text="框选区域", command=self.pick_region)
        button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self._input_widgets.append((button, "normal"))
        ttk.Label(parent, text=self._dt("物理像素；左侧／上方副屏坐标可为负数。",
            "Physical pixels; displays left/above may have negative coordinates."),
            wraplength=300, foreground="#555").grid(row=row+1, column=0, columnspan=3, sticky="ew", pady=4)
        return row + 2

    def _source_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "输入来源", row)
        ttk.Label(parent, text="来源").grid(row=row, column=0, sticky="w", pady=2)
        source = WideCombobox(
            parent,
            textvariable=self.source_mode,
            values=("Screen", "Video File", "Audio Only"),
            state="readonly",
            width=12,
        )
        source.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        self._input_widgets.append((source, "readonly"))
        row += 1
        ttk.Label(parent, text="视频").grid(row=row, column=0, sticky="w", pady=2)
        entry = ttk.Entry(parent, textvariable=self.video_path, width=18)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        button = ttk.Button(parent, text="选择", command=self.pick_video)
        button.grid(row=row, column=2, sticky="ew", padx=(4, 0))
        self._input_widgets.extend(((entry, "normal"), (button, "normal")))
        row += 1
        ttk.Button(parent, text="分析视频并保存脚本", command=self.analyze_video_file).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        return row + 1

    def _audio_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "声音监听", row)
        ttk.Label(parent, text="声音分析").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.audio_mode,
            values=("Audio Level", "Dynamic Accent", "Beat Pulse"),
            state="readonly",
            width=14,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="声音设备").grid(row=row, column=0, sticky="w", pady=2)
        self.audio_device_combo = WideCombobox(parent, textvariable=self.audio_device, values=(), width=14)
        self.audio_device_combo.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="刷新", command=self.refresh_audio_devices).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._slider(parent, "声音增益", self.audio_gain, row, 0.2, 8.0)
        row = self._slider(parent, "声音门槛", self.audio_threshold, row, 0.0, 0.35)
        row = self._slider(parent, "声音平滑", self.audio_smoothing, row, 0.0, 0.95)
        ttk.Label(
            parent,
            text="选择 Audio Only 后只监听声音，不读取屏幕画面。",
            wraplength=300,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        return row + 1

    def pick_region(self, on_close: Callable[[bool], None] | None = None) -> None:
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            messagebox.showwarning(self._dt("先停止分析", "Stop analysis first"),
                self._dt("请先停止当前分析，再更改采集区域。", "Stop the current analysis before changing the capture region."), parent=self)
            if on_close:
                on_close(False)
            return
        if self._region_selector is not None and not self._region_selector.closed:
            self._region_selector.window.lift()
            return
        try:
            current = self._read_screen_region()
        except ValueError:
            current = None
        previous_state = self.state()

        def restore():
            if previous_state == "withdrawn":
                return
            self.deiconify()
            if previous_state in ("zoomed", "iconic"):
                self.state(previous_state)
            else:
                self.lift()

        def complete(region):
            self._region_selector = None
            restore()
            if region is not None:
                for variable, value in zip((self.x, self.y, self.width, self.height),
                                           (region.x, region.y, region.width, region.height)):
                    variable.set(value)
                self.status.set(self._dt("已选择物理像素区域", "Physical pixel region selected") +
                    f": X {region.x} · Y {region.y} · {region.width} × {region.height} px")
            if on_close:
                on_close(region is not None)

        # The single in-memory snapshot is taken after hiding our own window.
        self.withdraw()
        self.update_idletasks()
        try:
            self._region_selector = self._create_region_selector(current=current, on_done=complete, translate=self._t)
        except Exception as exc:
            self._region_selector = None
            restore()
            messagebox.showerror(self._dt("无法框选区域", "Could not select a region"), str(exc), parent=self)
            if on_close:
                on_close(False)
