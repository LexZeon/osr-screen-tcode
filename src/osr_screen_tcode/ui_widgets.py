"""Shared native widgets. Dropdowns size their popup independently of the sidebar."""
from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import font, ttk


def monitor_workarea(widget) -> tuple[int, int, int, int]:
    fallback = (0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())
    if os.name != "nt":
        return fallback
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
        monitor = user32.MonitorFromWindow(widget.winfo_id(), 2)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    except (OSError, AttributeError):
        pass
    return fallback


def popup_horizontal_bounds(x: int, wanted: int, left: int, right: int) -> tuple[int, int]:
    width = min(max(1, wanted), max(1, right - left))
    return max(left, min(x, right - width)), width


class WideCombobox(ttk.Combobox):
    """Keep native selection/keyboard behavior, but fit each popup to its options."""

    def __init__(self, master=None, **kwargs):
        self._before_post = kwargs.pop("postcommand", None)
        super().__init__(master, **kwargs)
        self._popup_style = f"Wide{id(self)}.{self.cget('style') or 'TCombobox'}"
        self.configure(style=self._popup_style, postcommand=self._prepare_popup)

    def _prepare_popup(self):
        if self._before_post:
            if callable(self._before_post):
                self._before_post()
            else:
                self.tk.eval(self._before_post)
        popdown = self.tk.call("ttk::combobox::PopdownWindow", str(self))
        listbox = f"{popdown}.f.l"
        popup_font = font.Font(root=self, font=self.tk.call(listbox, "cget", "-font"))
        values = self.cget("values")
        widest = max((popup_font.measure(str(value)) for value in values), default=0)
        padding = popup_font.measure("00") + 24
        wanted = max(self.winfo_width(), widest + padding)
        left, _top, right, _bottom = monitor_workarea(self)
        x, width = popup_horizontal_bounds(self.winfo_rootx(), wanted, left, right)
        ttk.Style(self).configure(self._popup_style,
            postoffset=(x - self.winfo_rootx(), 0, width - self.winfo_width(), 0))
        # Extremely long names cannot fit on one monitor; keep every character reachable.
        scroll = f"{popdown}.f.horizontal"
        if not self.tk.getboolean(self.tk.call("winfo", "exists", scroll)):
            self.tk.call("ttk::scrollbar", scroll, "-orient", "horizontal", "-command", (listbox, "xview"))
            self.tk.call(listbox, "configure", "-xscrollcommand", (scroll, "set"))
        if wanted > width:
            self.tk.call("grid", scroll, "-row", 1, "-column", 0, "-columnspan", 2, "-sticky", "ew")
        else:
            self.tk.call("grid", "remove", scroll)
        self.tk.call(listbox, "xview", "moveto", 0)
