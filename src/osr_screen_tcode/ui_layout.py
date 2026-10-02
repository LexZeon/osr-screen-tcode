"""Resizable main panes with an unclipped, keyboard-reachable control surface."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from .ui_widgets import monitor_workarea
from .screen_geometry import move_physical_window


def display_scale(widget) -> float:
    # Tk distances use physical pixels here; font sizes use points.
    return max(0.5, float(widget.winfo_fpixels("1i")) / 96.0)


class ControlSidebar(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, width=340, height=1, highlightthickness=0)
        self.vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set,
                              yscrollincrement=1, xscrollincrement=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.horizontal.grid_remove()
        # Let geometry propagation measure the natural width, including later
        # text/font changes that don't change the height of the content.
        self.surface = ttk.Frame(self.canvas)
        self.content = ttk.Frame(self.surface, padding=12)
        self.content.grid(row=0, column=0, sticky="ew")
        self.surface.columnconfigure(0, weight=1)
        self.window = self.canvas.create_window((0, 0), window=self.surface, anchor="nw")
        self.content.columnconfigure(1, weight=1)
        self.surface.bind("<Configure>", self._layout)
        # Canvas unmaps an item that shrinks entirely outside the scrolled view,
        # delaying its physical Configure until it becomes visible again.
        self.surface.bind("<Unmap>", self._layout)
        self.canvas.bind("<Configure>", self._layout)
        # A pane-specific tag precedes native combobox/scale wheel handlers.
        # A toplevel binding alone runs too late and could change a setting.
        root = self.winfo_toplevel()
        self._wheel_tag = f"ControlSidebarWheel{id(self)}"
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>"):
            self.bind_class(self._wheel_tag, sequence, self._wheel)
        self._bindings = [(event, root.bind(event, callback, add="+")) for event, callback in
                          (("<Map>", self._track_widget), ("<FocusIn>", self._focus))]
        self.bind("<Destroy>", self._dispose, add="+")

    def _contains(self, widget):
        return (isinstance(widget, tk.Misc) and widget.winfo_toplevel() is self.winfo_toplevel()
                and (widget is self or str(widget).startswith(str(self) + ".")))

    def _track_widget(self, event):
        widget = event.widget
        if self._contains(widget) and self._wheel_tag not in widget.bindtags():
            widget.bindtags((self._wheel_tag, *widget.bindtags()))

    def _layout(self, _event=None):
        viewport = max(1, self.canvas.winfo_width())
        self.surface.columnconfigure(0, minsize=viewport)
        width = max(viewport, self.surface.winfo_reqwidth())
        self.canvas.configure(scrollregion=(0, 0, width, self.surface.winfo_reqheight()))
        if width > viewport:
            self.horizontal.grid()
        else:
            self.horizontal.grid_remove()
            self.canvas.xview_moveto(0)

    def _wheel(self, event):
        if not self._contains(event.widget) or not event.delta:
            return None
        amount = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        view = self.canvas.xview_scroll if event.state & 1 else self.canvas.yview_scroll
        view(amount * max(24, round(24 * display_scale(self))), "units")
        return "break"

    def _focus(self, event):
        widget = event.widget
        if not self._contains(widget) or widget in (self, self.canvas, self.vertical, self.horizontal):
            return
        # Tab navigation must reveal controls outside either edge of the viewport.
        for coordinate, size, total, origin, visible, move in (
            (widget.winfo_rootx() - self.content.winfo_rootx(), widget.winfo_width(),
             self.content.winfo_width(), self.canvas.canvasx(0), self.canvas.winfo_width(), self.canvas.xview_moveto),
            (widget.winfo_rooty() - self.content.winfo_rooty(), widget.winfo_height(),
             self.content.winfo_height(), self.canvas.canvasy(0), self.canvas.winfo_height(), self.canvas.yview_moveto),
        ):
            if coordinate < origin or coordinate + size > origin + visible:
                offset = coordinate if size >= visible or coordinate < origin else coordinate + size - visible
                move(max(0, offset) / max(1, total))

    def _dispose(self, event):
        if event.widget is self:
            root = self.winfo_toplevel()
            for sequence, token in self._bindings:
                root.unbind(sequence, token)
            for sequence in ("<MouseWheel>", "<Shift-MouseWheel>"):
                self.unbind_class(self._wheel_tag, sequence)


class MainPanes(tk.PanedWindow):
    def __init__(self, master, saved_width=None, on_width_changed=None):
        self.scale = display_scale(master)
        super().__init__(master, orient="horizontal", borderwidth=0,
                         sashwidth=max(8, round(8 * self.scale)), sashrelief="raised",
                         showhandle=True, opaqueresize=True)
        self.sidebar = ControlSidebar(self)
        self.preview = ttk.Frame(self, padding=(0, 12, 12, 12))
        self.add(self.sidebar, minsize=220, stretch="never")
        self.add(self.preview, minsize=220, stretch="always")
        self.preferred_width = self._valid_width(saved_width)
        self._on_width_changed = on_width_changed
        self._drag_start = None
        self._initial_fit = False
        self._fit_callback = None
        self.bind("<Configure>", self._mapped_size, add="+")
        self.bind("<Destroy>", self._dispose, add="+")
        self.bind("<ButtonPress-1>", self._begin_drag, add="+")
        self.bind("<ButtonRelease-1>", self._end_drag, add="+")

    @staticmethod
    def _valid_width(value):
        try:
            width = float(value)
            return width if math.isfinite(width) and 1 <= width <= 10000 else None
        except (TypeError, ValueError):
            return None

    def fit_initial_window(self):
        root = self.winfo_toplevel()
        root.update_idletasks()
        left, top, right, bottom = monitor_workarea(root)
        available_w, available_h = max(1, right - left - 32), max(1, bottom - top - 80)
        wanted = self.sidebar.content.winfo_reqwidth() + self.sidebar.vertical.winfo_reqwidth()
        width = min(available_w, max(round(1040 * self.scale), wanted + round(560 * self.scale)))
        height = min(available_h, round(700 * self.scale))
        root.minsize(min(640, available_w), min(420, available_h))
        self._initial_fit = True
        root.geometry(f"{width}x{height}")
        # When a caller fits an already mapped window at the same size there may
        # be no new Configure event. Defer until geometry requests have settled.
        root.update_idletasks()
        if self._initial_fit and self.winfo_width() > 1 and self._fit_callback is None:
            self._fit_callback = self.after_idle(self._finish_initial_fit)

    def _mapped_size(self, event):
        if self._initial_fit and event.width > 1 and self._fit_callback is None:
            self._fit_callback = self.after_idle(self._finish_initial_fit)

    def _finish_initial_fit(self):
        self._initial_fit = False
        self._fit_callback = None
        self.reset_width(keep_saved=True)
        root = self.winfo_toplevel()
        left, top, right, bottom = monitor_workarea(root)
        # Keep title bar and bottom scrollbar on the launching monitor.
        x = max(left + 8, min(root.winfo_rootx(), right - root.winfo_width() - 8))
        y = max(top + 40, min(root.winfo_rooty(), bottom - root.winfo_height() - 8))
        move_physical_window(root, x, y)

    def _dispose(self, event):
        if event.widget is self and self._fit_callback is not None:
            self.after_cancel(self._fit_callback)

    def reset_width(self, keep_saved=False):
        if not keep_saved:
            self.preferred_width = None
        self.update_idletasks()
        if self.winfo_width() <= 1:
            return  # The initial mapped-size callback will finish the layout.
        wanted = (round(self.preferred_width * self.scale) if self.preferred_width is not None else
                  self.sidebar.content.winfo_reqwidth() + self.sidebar.vertical.winfo_reqwidth())
        # Leave room for the preview on smaller displays; overflow stays reachable.
        reserve = (220 + int(self.cget("sashwidth")) if self.preferred_width is not None
                   else max(280, round(400 * self.scale)))
        width = max(220, min(wanted, self.winfo_width() - reserve))
        self.sash_place(0, width, 0)
        self.sidebar.canvas.xview_moveto(0)

    def _begin_drag(self, event):
        self._drag_start = self.sash_coord(0)[0] if self.identify(event.x, event.y) else None

    def _end_drag(self, _event):
        if self._drag_start is None:
            return
        current = self.sash_coord(0)[0]
        previous, self._drag_start = self._drag_start, None
        if current != previous:
            self.preferred_width = current / self.scale
            if self._on_width_changed:
                self._on_width_changed()
