"""A shared whole-desktop picker whose selected rectangles are physical pixels.

The overlay covers the virtual desktop, including signed monitor origins. Its
canvas is only a presentation viewport: mouse endpoints come from the physical
cursor, never from a desktop-size/primary-monitor-size DPI estimate.
"""
from __future__ import annotations

import tkinter as tk
import time

from PIL import Image, ImageTk

from .capture import ScreenCapture, ScreenRegion, validate_region
from .screen_geometry import physical_cursor_position, place_physical_window, screen_monitors, flush_desktop_composition


TEXT = {
    "拖拽选择实时读取区域": "Drag to select the realtime screen region",
    "可跨显示器框选；Enter 确认，R 重选，Esc 取消。显示器间空隙为黑色。":
        "Drag across monitors; Enter: use, R: retry, Esc: cancel. Gaps between monitors are black.",
    "当前区域": "Current region",
    "使用此区域": "Use this region",
    "重新选择": "Select again",
    "取消": "Cancel",
    "区域太小，请重新拖拽": "Region too small; drag again",
    "显示器布局已改变，请取消后重新框选。": "Display layout changed; cancel and select again.",
    "选区无效，请在显示器画面内重新框选。": "Invalid region; select an area containing a display.",
    "物理像素": "physical pixels",
    "屏幕": "Display",
    "屏幕快照 · 确认后实时读取": "Screen snapshot · Live capture starts after confirmation",
    "拖拽框选 · 支持跨屏": "Drag a region · Multiple displays supported",
    "Enter 确认   R 重选   Esc 取消": "Enter: use   R: retry   Esc: cancel",
    "选区已就绪": "Region ready",
    "选框内为实际读取范围": "The bright area is the exact capture region",
}


def desktop_bounds(monitors):
    if not monitors:
        raise ValueError("No connected displays / 未找到显示器")
    left, top = min(m['left'] for m in monitors), min(m['top'] for m in monitors)
    right = max(m['left']+m['width'] for m in monitors)
    bottom = max(m['top']+m['height'] for m in monitors)
    return dict(left=left, top=top, width=right-left, height=bottom-top)


def canvas_point(point, bounds, size):
    """Map physical coordinates to this overlay, not to the primary monitor."""
    return ((point[0]-bounds['left'])*size[0]/bounds['width'],
            (point[1]-bounds['top'])*size[1]/bounds['height'])


def region_from_points(first, last, monitors):
    x, y = min(first[0], last[0]), min(first[1], last[1])
    region = ScreenRegion(x, y, abs(last[0]-first[0]), abs(last[1]-first[1]))
    if min(region.width, region.height) < 24:
        raise ValueError("Region too small")
    return validate_region(region, monitors)


def card_geometry(monitor_box, requested_size, preferred, margin=16):
    """Fit a UI card inside one real display, even when content is oversized."""
    left, top, right, bottom = monitor_box
    margin = max(0, min(margin, (right-left)/4, (bottom-top)/4))
    width = max(1, min(requested_size[0], right-left-2*margin))
    height = max(1, min(requested_size[1], bottom-top-2*margin))
    x = max(left+margin, min(preferred[0], right-margin-width))
    y = max(top+margin, min(preferred[1], bottom-margin-height))
    return x, y, width, height


class ScreenRegionSelector:
    def __init__(self, master, *, current=None, on_done, translate=None):
        self.master, self.on_done = master, on_done
        self.t = translate or (lambda key: key+" / "+TEXT.get(key, key))
        self.monitors = screen_monitors()
        self.bounds = desktop_bounds(self.monitors)
        self.current, self.start, self.region = current, None, None
        self.closed, self.panel, self.panel_item = False, None, None
        self.window = self.canvas = None
        self._snapshot = self._background_photo = self._selection_photo = None
        self._background_size = None
        self._reveal_after = None
        self._pending_reveal = None
        self._last_reveal = 0.0
        self._reveal_item = None
        self._last_end = None
        self._accent = "#52e7ba"
        try:
            # Capture before mapping the overlay. This stays in memory and cannot
            # include the overlay itself; ordinary live capture resumes on close.
            # Withdrawing the parent can precede its compositor hide animation.
            # Settle only this one-off screenshot, never every live input frame.
            flush_desktop_composition()
            with ScreenCapture(ScreenRegion(self.bounds['left'], self.bounds['top'],
                                            self.bounds['width'], self.bounds['height'])) as capture:
                frame = capture.grab_bgr()
                self._snapshot = Image.fromarray(frame[:, :, ::-1])
            del frame
            self.window = tk.Toplevel(master)
            self.window.title("Screen Region / 屏幕区域")
            self.window.withdraw()
            self.window.overrideredirect(True)
            self.window.configure(background="#07111b", cursor="crosshair")
            self.window.attributes("-topmost", True)
            self.window.maxsize(self.bounds['width'], self.bounds['height'])
            self.canvas = tk.Canvas(self.window, background="#07111b", highlightthickness=0, borderwidth=0)
            self.canvas.pack(fill="both", expand=True)
            self.window.deiconify()
            place_physical_window(self.window, self.bounds)
            self.window.update_idletasks()
            self.window.grab_set()
        except Exception:
            try:
                if self.window is not None:
                    self.window.destroy()
            except tk.TclError:
                pass
            finally:
                self._snapshot = self._background_photo = self._selection_photo = None
            raise
        try:
            self.canvas.bind("<ButtonPress-1>", self.down)
            self.canvas.bind("<B1-Motion>", self.move)
            self.canvas.bind("<ButtonRelease-1>", self.up)
            self.canvas.bind("<Configure>", lambda _event: self.redraw(self._last_end))
            for key, command in (("<Escape>", lambda _event: self.finish(None)),
                                 ("<Return>", self.confirm), ("<r>", self.reset), ("<R>", self.reset)):
                self.window.bind(key, command)
            self.window.protocol("WM_DELETE_WINDOW", lambda: self.finish(None))
            self.window.focus_force()
            self.redraw()
        except Exception:
            self.closed = True
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            finally:
                self._snapshot = self._background_photo = self._selection_photo = None
            raise

    def _local(self, point):
        return canvas_point(point, self.bounds, (max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())))

    def _rect(self, region, **kwargs):
        first = self._local((region.x, region.y))
        last = self._local((region.x+region.width, region.y+region.height))
        return self.canvas.create_rectangle(*first, *last, **kwargs)

    def _active_monitor(self):
        point = physical_cursor_position()
        return next((m for m in self.monitors if m['left'] <= point[0] < m['left']+m['width']
                     and m['top'] <= point[1] < m['top']+m['height']), self.monitors[0])

    def _label(self, region):
        return f"X {region.x}   Y {region.y}   {region.width} × {region.height}  {self.t('物理像素')}"

    def _round_rectangle(self, x1, y1, x2, y2, radius=14, **kwargs):
        radius = min(radius, max(1, (x2-x1)/2), max(1, (y2-y1)/2))
        return self.canvas.create_polygon(
            x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
            x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
            x1, y2, x1, y2-radius, x1, y1+radius, x1, y1,
            smooth=True, splinesteps=18, **kwargs)

    def _draw_background(self):
        size = (max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))
        if self._background_size == size:
            return
        self._background_size = size
        background = self._snapshot.point([round(value*.29) for value in range(256)]*3)
        if background.size != size:
            background = background.resize(size, Image.Resampling.BILINEAR)
        self._background_photo = ImageTk.PhotoImage(background, master=self.window)
        self.canvas.delete("snapshot")
        self.canvas.create_image(0, 0, image=self._background_photo, anchor="nw", tags="snapshot")
        self.canvas.tag_lower("snapshot")

    def _queue_reveal(self, region, *, immediate=False):
        self._pending_reveal = region
        if immediate or time.perf_counter()-self._last_reveal >= .04:
            if self._reveal_after is not None:
                self.window.after_cancel(self._reveal_after)
                self._reveal_after = None
            self._paint_reveal()
        elif self._reveal_after is None:
            self._reveal_after = self.window.after(40, self._paint_reveal)

    def _paint_reveal(self):
        self._reveal_after = None
        if self.closed:
            return
        region = self._pending_reveal
        self.canvas.delete("reveal")
        self._selection_photo = None
        if region is None or region.width < 1 or region.height < 1:
            return
        left = max(0, region.x-self.bounds['left'])
        top = max(0, region.y-self.bounds['top'])
        right = min(self.bounds['width'], region.x+region.width-self.bounds['left'])
        bottom = min(self.bounds['height'], region.y+region.height-self.bounds['top'])
        if right <= left or bottom <= top:
            return
        image = self._snapshot.crop((left, top, right, bottom))
        first = self._local((left+self.bounds['left'], top+self.bounds['top']))
        last = self._local((right+self.bounds['left'], bottom+self.bounds['top']))
        size = (max(1, round(last[0]-first[0])), max(1, round(last[1]-first[1])))
        if image.size != size:
            image = image.resize(size, Image.Resampling.BILINEAR)
        self._selection_photo = ImageTk.PhotoImage(image, master=self.window)
        self._reveal_item = self.canvas.create_image(*first, image=self._selection_photo, anchor="nw", tags="reveal")
        self.canvas.tag_lower("reveal", "drawing")
        self._last_reveal = time.perf_counter()

    def _monitor_box(self, monitor):
        first = self._local((monitor['left'], monitor['top']))
        last = self._local((monitor['left']+monitor['width'], monitor['top']+monitor['height']))
        return *first, *last

    def _text_card(self, monitor, rows, preferred, *, width=660, fill="#102031", outline="#345d65"):
        box = self._monitor_box(monitor)
        _, _, available_width, available_height = card_geometry(box, (width, box[3]-box[1]), preferred)
        padding = min(16, available_width/8, available_height/8)
        cursor_y, items = 0, []
        for text, color, size, weight in rows:
            item = self.canvas.create_text(0, cursor_y, text=text, width=max(1, available_width-2*padding),
                                           anchor="nw", fill=color, font=("Segoe UI", size, weight), tags="drawing")
            bounds = self.canvas.bbox(item)
            if bounds and bounds[3] > available_height-2*padding:
                self.canvas.delete(item)
                break  # Optional lower rows never push the card off this display.
            items.append(item)
            cursor_y = bounds[3]+8 if bounds else cursor_y+24
        x, y, width, height = card_geometry(box, (available_width, cursor_y+2*padding-8), preferred)
        for item in items:
            self.canvas.move(item, x+padding, y+padding)
        background = self._round_rectangle(x, y, x+width, y+height, fill=fill, outline=outline, tags="drawing")
        if items:
            self.canvas.tag_lower(background, items[0])
        return x, y, width, height

    def _draw_monitors(self):
        for number, monitor in enumerate(self.monitors, 1):
            left, top, right, bottom = self._monitor_box(monitor)
            self.canvas.create_rectangle(left+2, top+2, right-2, bottom-2, outline="#496071", width=1, tags="drawing")
            text = f"{self.t('屏幕')} {number}   ·   {monitor['width']} × {monitor['height']}"
            item = self.canvas.create_text(0, 0, text=text, width=max(1, right-left-64), anchor="nw", fill="#e1ecf3", font=("Segoe UI", 10), tags="drawing")
            box = self.canvas.bbox(item)
            if box:
                x, y, width, height = card_geometry((left, top, right, bottom), (box[2]-box[0]+24, box[3]-box[1]+18), (left+18, bottom-60))
                self.canvas.move(item, x+12-box[0], y+9-box[1])
                card = self._round_rectangle(x, y, x+width, y+height,
                                             fill="#122130", outline="#345168", tags="drawing")
                self.canvas.tag_lower(card, item)

    def redraw(self, end=None):
        if self.closed:
            return
        self._draw_background()
        self.canvas.delete("drawing")
        self._draw_monitors()
        if self.current is not None and self.current.width > 0 and self.current.height > 0:
            self._rect(self.current, outline="#88a9d2", width=1, dash=(6, 5), tags="drawing")
        shown = self.region
        if self.start is not None and end is not None:
            shown = ScreenRegion(min(self.start[0], end[0]), min(self.start[1], end[1]),
                                 abs(end[0]-self.start[0]), abs(end[1]-self.start[1]))
        if shown is not None:
            self._rect(shown, outline="#102d29", width=6, tags="drawing")
            self._rect(shown, outline=self._accent, width=2, tags="drawing")
            a, b = self._local((shown.x, shown.y)), self._local((shown.x+shown.width, shown.y+shown.height))
            corner = max(0, min(24, (b[0]-a[0])/3, (b[1]-a[1])/3))
            for x, y, dx, dy in ((a[0], a[1], 1, 1), (b[0], a[1], -1, 1),
                                  (a[0], b[1], 1, -1), (b[0], b[1], -1, -1)):
                self.canvas.create_line(x+dx*corner, y, x, y, x, y+dy*corner,
                                        fill="#d1fff0", width=3, tags="drawing")
            cx, cy = (a[0]+b[0])/2, (a[1]+b[1])/2
            self.canvas.create_line(cx-8, cy, cx+8, cy, fill=self._accent, tags="drawing")
            self.canvas.create_line(cx, cy-8, cx, cy+8, fill=self._accent, tags="drawing")
        # Help follows the monitor being used, including a negative-origin or
        # portrait monitor. It does not disappear into a virtual-desktop gap.
        monitor = self._active_monitor()
        x, y, right, bottom = self._monitor_box(monitor)
        compact = right-x < 500 or bottom-y < 400
        rows = [(self.t("拖拽框选 · 支持跨屏"), "#effcf7", 11 if compact else 15, "bold"),
                (self.t("Enter 确认   R 重选   Esc 取消"), "#76dabe", 9 if compact else 10, "normal"),
                (self.t("屏幕快照 · 确认后实时读取"), "#b9ccd9", 9 if compact else 10, "normal")]
        detail = shown or self.current
        if detail is not None:
            heading = f"{detail.width} × {detail.height}"
            if shown is None:
                heading = self.t("当前区域")+"  "+heading
            rows += [(heading, self._accent, 12 if compact else 16, "bold"),
                     (f"X {detail.x}    Y {detail.y}   ·   {self.t('物理像素')}", "#b9ccd9", 9 if compact else 10, "normal")]
        self._help_bounds = self._text_card(monitor, rows, (x+24, y+24))
        self._queue_reveal(shown, immediate=self.start is None)

    def _clear_panel(self):
        if self.panel_item is not None:
            self.canvas.delete(self.panel_item)
        if self.panel is not None:
            self.panel.destroy()
        self.panel = self.panel_item = None

    def _error(self, key):
        self._clear_panel()
        self.redraw()
        monitor = self._active_monitor()
        left, top, right, bottom = self._monitor_box(monitor)
        self._text_card(monitor, [(self.t(key), "#ffd0c6", 9 if bottom-top < 400 else 11, "bold")],
                        (left+24, top+300), width=660, fill="#44232b", outline="#a65866")

    def down(self, _event=None):
        self._clear_panel()
        self.region = None
        self.start = physical_cursor_position()
        self._last_end = self.start
        self.redraw(self.start)

    def move(self, _event=None):
        if self.start is not None:
            self._last_end = physical_cursor_position()
            self.redraw(self._last_end)

    def up(self, _event=None):
        first, self.start = self.start, None
        if first is None:
            return
        last = physical_cursor_position()
        self._last_end = None
        try:
            self.region = region_from_points(first, last, self.monitors)
        except ValueError:
            key = "区域太小，请重新拖拽" if min(abs(last[0]-first[0]), abs(last[1]-first[1])) < 24 else "选区无效，请在显示器画面内重新框选。"
            self._error(key)
            return
        self.redraw()
        monitor = self._active_monitor()
        monitor_box = self._monitor_box(monitor)
        left, top, right, bottom = monitor_box
        _, _, available_width, available_height = card_geometry(monitor_box, (right-left, bottom-top), (left, top))
        compact = available_height < 350 or available_width < 500
        padding = 8 if compact else 20
        content_width = max(1, available_width-2*padding-4)
        self.panel = tk.Frame(self.window, background="#102031", padx=padding, pady=8 if compact else 16, highlightthickness=1, highlightbackground="#3c746e")
        tk.Label(self.panel, text=self.t("选区已就绪"), background="#102031", foreground=self._accent,
                 anchor="w", wraplength=content_width, font=("Segoe UI", 9 if compact else 12, "bold")).pack(fill="x")
        tk.Label(self.panel, text=self._label(self.region), background="#102031", foreground="#f2faf7",
                 anchor="w", wraplength=content_width, font=("Segoe UI", 9 if compact else 11)).pack(fill="x", pady=(4 if compact else 7, 3))
        if not compact:
            tk.Label(self.panel, text=self.t("选框内为实际读取范围"), background="#102031", foreground="#aebfce",
                     anchor="w", wraplength=content_width, font=("Segoe UI", 10)).pack(fill="x", pady=(0, 14))
        buttons = tk.Frame(self.panel, background="#102031")
        buttons.pack(fill="x")
        button_widgets = []
        for index, (key, command) in enumerate((("使用此区域", self.confirm), ("重新选择", self.reset), ("取消", lambda: self.finish(None)))):
            primary = index == 0
            button = tk.Button(buttons, text=self.t(key), command=command, background=self._accent if primary else "#24364a",
                      foreground="#08231c" if primary else "#e1ebf3", activebackground="#83f5d0" if primary else "#36516a",
                      activeforeground="#08231c" if primary else "white", relief="flat", borderwidth=0,
                      padx=10 if compact else 15, pady=4 if compact else 9, cursor="hand2", wraplength=max(1, content_width-24),
                      font=("Segoe UI", 9 if compact else 10, "bold" if primary else "normal"),
                      highlightthickness=1, highlightbackground="#397c6d" if primary else "#3d5267",
                      highlightcolor="#d1fff0")
            button_widgets.append(button)
        self.panel.update_idletasks()
        vertical = available_width < 500 or sum(button.winfo_reqwidth() for button in button_widgets)+20 > content_width
        for index, button in enumerate(button_widgets):
            button.pack(side="top" if vertical else "left", fill="x" if vertical else "none",
                        padx=0 if vertical else ((0, 10) if index < 2 else 0),
                        pady=(0, 4) if vertical and index < 2 else 0)
        self.panel.update_idletasks()
        px, py = self._local(last)
        px, py, width, height = card_geometry(monitor_box, (self.panel.winfo_reqwidth(), self.panel.winfo_reqheight()), (px, py+20))
        self.panel_item = self.canvas.create_window(px, py, width=width, height=height, window=self.panel, anchor="nw")

    def reset(self, _event=None):
        self._clear_panel()
        self.start = self.region = None
        self._last_end = None
        self.redraw()

    def confirm(self, _event=None):
        if self.region is None or self.closed:
            return
        topology = lambda monitors: sorted((m['left'], m['top'], m['width'], m['height']) for m in monitors)
        try:
            changed = topology(screen_monitors()) != topology(self.monitors)
        except (OSError, RuntimeError, ValueError):
            changed = True
        if changed:
            self._error("显示器布局已改变，请取消后重新框选。")
            return
        self.finish(validate_region(self.region, self.monitors))

    def finish(self, region):
        if self.closed:
            return
        self.closed = True
        if self._reveal_after is not None:
            try:
                self.window.after_cancel(self._reveal_after)
            except tk.TclError:
                pass
            self._reveal_after = None
        self._pending_reveal = None
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        finally:
            self._snapshot = self._background_photo = self._selection_photo = None
            self.panel = self.panel_item = None
        # Release the native overlay before restoring the start dialog or
        # permitting any subsequent capture, so it cannot enter the first frame.
        self.master.after_idle(lambda: self.on_done(region))
