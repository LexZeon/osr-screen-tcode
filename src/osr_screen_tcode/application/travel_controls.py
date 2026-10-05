"""Existing travel scale slider and entry synchronization.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from .tooltips import Tooltip


class TravelControlsMixin:
    def _travel_slider(
        self,
        parent: ttk.Frame,
        label: str,
        value_var: tk.DoubleVar,
        slider_var: tk.DoubleVar,
        text_var: tk.StringVar,
        row: int,
        invert_var: tk.BooleanVar | None = None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(
            parent,
            from_=0.0,
            to=100.0,
            variable=slider_var,
            command=lambda value, target=value_var, text=text_var: self._on_travel_slider(value, target, text),
        ).grid(row=row, column=1, sticky="ew", pady=2)
        value_box = ttk.Frame(parent)
        value_box.grid(row=row, column=2, sticky="e")
        entry = ttk.Entry(value_box, textvariable=text_var, width=7, justify="right")
        entry.grid(row=0, column=0, sticky="e")
        entry.bind("<Return>", lambda _event, target=value_var, slider=slider_var, text=text_var: self._on_travel_entry(target, slider, text))
        entry.bind("<FocusOut>", lambda _event, target=value_var, slider=slider_var, text=text_var: self._on_travel_entry(target, slider, text))
        Tooltip(entry, self._tooltip_text(label))
        if invert_var is not None:
            check = ttk.Checkbutton(value_box, text=self._t("反转"), variable=invert_var)
            check.grid(row=0, column=1, sticky="e", padx=(4, 0))
            Tooltip(check, self._tooltip_text("反转"))
        return row + 1

    @staticmethod
    def _travel_slider_to_scale(position: float) -> float:
        position = max(0.0, min(100.0, float(position)))
        if position <= 60.0:
            return position / 60.0
        if position <= 85.0:
            return 1.0 + (position - 60.0) / 25.0 * 0.5
        if position <= 95.0:
            return 1.5 + (position - 85.0) / 10.0 * 0.25
        return 1.75 + (position - 95.0) / 5.0 * 1.25

    @staticmethod
    def _travel_scale_to_slider(scale: float) -> float:
        scale = max(0.0, min(3.0, float(scale)))
        if scale <= 1.0:
            return scale * 60.0
        if scale <= 1.5:
            return 60.0 + (scale - 1.0) / 0.5 * 25.0
        if scale <= 1.75:
            return 85.0 + (scale - 1.5) / 0.25 * 10.0
        return 95.0 + (scale - 1.75) / 1.25 * 5.0

    @staticmethod
    def _format_travel_scale(scale: float) -> str:
        return f"{max(0.0, min(3.0, float(scale))):.2f}x"

    def _on_travel_slider(self, value: str | float, target: tk.DoubleVar, text: tk.StringVar) -> None:
        if self._travel_slider_syncing:
            return
        scale = self._travel_slider_to_scale(float(value))
        target.set(round(scale, 3))
        text.set(self._format_travel_scale(scale))
        self._refresh_limit_text()

    def _on_travel_entry(self, target: tk.DoubleVar, slider: tk.DoubleVar, text: tk.StringVar) -> None:
        if self._travel_slider_syncing:
            return
        raw = text.get().strip().lower().replace("x", "")
        try:
            scale = max(0.0, min(3.0, float(raw)))
        except (tk.TclError, ValueError):
            scale = max(0.0, min(3.0, float(target.get())))
        self._travel_slider_syncing = True
        try:
            target.set(round(scale, 3))
            slider.set(self._travel_scale_to_slider(scale))
            text.set(self._format_travel_scale(scale))
        finally:
            self._travel_slider_syncing = False
        self._refresh_limit_text()

    def _sync_travel_slider(self, value_var: tk.DoubleVar, slider_var: tk.DoubleVar, text_var: tk.StringVar) -> None:
        if self._travel_slider_syncing:
            return
        self._travel_slider_syncing = True
        try:
            scale = max(0.0, min(3.0, float(value_var.get())))
            slider_var.set(self._travel_scale_to_slider(scale))
            text_var.set(self._format_travel_scale(scale))
        finally:
            self._travel_slider_syncing = False
