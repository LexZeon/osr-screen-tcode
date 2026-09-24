"""Physical desktop coordinates shared by screen selection and capture.

Windows desktop positions are signed pixels, not Tk's display-size ratios.
This module deliberately imports neither Tk nor the application and changes no
third-party implementation. Call configure_dpi_awareness before creating UI.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import sys
import time


def _library(name):
    return ctypes.WinDLL(name, use_last_error=True)


def _function(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


def _thread_awareness(user32):
    try:
        get_context = _function(user32, "GetThreadDpiAwarenessContext", [], ctypes.c_void_p)
        get_awareness = _function(user32, "GetAwarenessFromDpiAwarenessContext", [ctypes.c_void_p], ctypes.c_int)
        return get_awareness(get_context())
    except (AttributeError, OSError):
        return None


def _process_awareness():
    try:
        shcore = _library("shcore")
        query = _function(shcore, "GetProcessDpiAwareness", [wintypes.HANDLE, ctypes.POINTER(ctypes.c_int)], ctypes.c_long)
        value = ctypes.c_int()
        if query(None, ctypes.byref(value)) == 0:
            return value.value
    except (AttributeError, OSError):
        pass
    return None


def _set_physical_thread(user32):
    try:
        setter = _function(user32, "SetThreadDpiAwarenessContext", [ctypes.c_void_p], ctypes.c_void_p)
    except AttributeError:
        return None, None
    for context in (-4, -3):  # Per Monitor V2, then Windows 10's original PM mode.
        previous = setter(context)
        if previous:
            return setter, previous
    return None, None


def configure_dpi_awareness() -> bool:
    """Set physical DPI coordinates before creating any UI.

    An embedding host may already have locked the process setting. In that case
    Windows 10 permits a per-monitor context on this GUI thread; capture threads
    use physical_dpi_context separately. No DLL is loaded on non-Windows hosts.
    """
    if not sys.platform.startswith("win"):
        return False
    user32 = _library("user32")
    try:
        setter = _function(user32, "SetProcessDpiAwarenessContext", [ctypes.c_void_p], wintypes.BOOL)
        if setter(-4):
            return True
    except AttributeError:
        pass
    try:
        shcore = _library("shcore")
        setter = _function(shcore, "SetProcessDpiAwareness", [ctypes.c_int], ctypes.c_long)
        if setter(2) == 0:  # HRESULT, not a BOOL. A denied call is not success.
            return True
    except (AttributeError, OSError):
        pass
    awareness = _thread_awareness(user32)
    if awareness == 2 or (awareness is None and _process_awareness() == 2):
        return True
    setter, previous = _set_physical_thread(user32)
    if previous:
        return True  # Keep this GUI thread physical for the life of its windows.
    try:
        setter = _function(user32, "SetProcessDPIAware", [], wintypes.BOOL)
        if setter():
            # Vista/7 have one system DPI, so system-aware is the best supported
            # physical-coordinate mode. Newer Windows must use per-monitor mode.
            return _process_awareness() is None and not hasattr(user32, "SetThreadDpiAwarenessContext")
    except AttributeError:
        pass
    return False


def flush_desktop_composition() -> bool:
    """Let a just-hidden window leave the one-off region-picker snapshot.

    DwmFlush waits for queued presentation, not for the whole desktop session
    or every hide animation to finish. Allow one 250 ms settling interval,
    then flush again before taking the snapshot. The interval starts before
    the first flush, so its own wait is not added to the settling allowance.

    This is only for opening the picker, never for realtime capture. It pumps
    no Tk events and changes no animation settings. Unusual slow transitions
    and remote compositors may still need user verification; a successful
    HRESULT is not a guarantee that other applications finished rendering.
    False means DWM synchronization was unavailable, not a capture failure.
    https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmflush
    """
    if not sys.platform.startswith("win"):
        return False
    started = time.monotonic()
    flush = None
    try:
        flush = _function(_library("dwmapi"), "DwmFlush", [], ctypes.c_long)
        flush()
    except (AttributeError, OSError):
        flush = None
    remaining = .250 - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)
    if flush is not None:
        try:
            return flush() == 0  # HRESULT success is S_OK, not a truthy BOOL.
        except (AttributeError, OSError):
            pass
    return False


@contextmanager
def physical_dpi_context():
    """Temporarily use physical screen coordinates, restoring this thread only."""
    if not sys.platform.startswith("win"):
        yield
        return
    user32 = _library("user32")
    setter, previous = _set_physical_thread(user32)
    if previous:
        try:
            yield
        finally:
            if not setter(previous):
                raise OSError("Could not restore the screen thread DPI context")
        return
    awareness = _thread_awareness(user32)
    if awareness is None:
        awareness = _process_awareness()
        if awareness is None:
            try:
                query = _function(user32, "IsProcessDPIAware", [], wintypes.BOOL)
                if query():
                    awareness = 2  # Pre-8.1 systems have no per-monitor scaling.
            except AttributeError:
                pass
    if awareness != 2:
        raise RuntimeError("Physical screen coordinates unavailable; restart the application / 无法获取屏幕物理坐标，请重启程序")
    yield


def screen_monitors() -> list[dict[str, int]]:
    """Return only real display rectangles, in physical virtual-desktop pixels."""
    if not sys.platform.startswith("win"):
        import mss
        with mss.mss() as capture:
            return [{key: int(monitor[key]) for key in ("left", "top", "width", "height")}
                    for monitor in capture.monitors[1:]]
    with physical_dpi_context():
        user32 = _library("user32")
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                          ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        monitors = []

        @callback_type
        def receive(_monitor, _dc, rectangle, _data):
            rect = rectangle.contents
            if rect.right > rect.left and rect.bottom > rect.top:
                monitors.append(dict(left=int(rect.left), top=int(rect.top),
                                     width=int(rect.right - rect.left), height=int(rect.bottom - rect.top)))
            return True

        enumerate_monitors = _function(user32, "EnumDisplayMonitors",
                                       [wintypes.HDC, ctypes.POINTER(wintypes.RECT), callback_type, wintypes.LPARAM], wintypes.BOOL)
        if not enumerate_monitors(None, None, receive, 0) or not monitors:
            raise OSError("No available screen / 未找到可用屏幕")
        return monitors


def desktop_bounds(monitors) -> dict[str, int]:
    """Union bounds retain negative origins; gaps are not additional displays."""
    if not monitors:
        raise ValueError("No available screen / 未找到可用屏幕")
    left = min(int(monitor["left"]) for monitor in monitors)
    top = min(int(monitor["top"]) for monitor in monitors)
    right = max(int(monitor["left"]) + int(monitor["width"]) for monitor in monitors)
    bottom = max(int(monitor["top"]) + int(monitor["height"]) for monitor in monitors)
    return dict(left=left, top=top, width=right - left, height=bottom - top)


def virtual_screen_bounds() -> dict[str, int]:
    return desktop_bounds(screen_monitors())


def physical_cursor_position() -> tuple[int, int]:
    if not sys.platform.startswith("win"):
        raise RuntimeError("Native physical cursor queries require Windows")
    user32 = _library("user32")
    with physical_dpi_context():
        # GetPhysicalCursorPos is independent of the calling thread's DPI mode.
        name = "GetPhysicalCursorPos" if hasattr(user32, "GetPhysicalCursorPos") else "GetCursorPos"
        query = _function(user32, name, [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL)
        point = wintypes.POINT()
        if not query(ctypes.byref(point)):
            raise OSError("Could not query the screen cursor position")
        return int(point.x), int(point.y)


def place_physical_window(window, bounds_dict) -> None:
    """Place an undecorated Tk toplevel at an absolute physical rectangle.

    Tk interprets negative geometry offsets relative to a screen edge. Win32 does
    not, so use the actual top-level HWND after Tk has created its native wrapper.
    The caller owns overrideredirect/topmost flags and focus policy.
    """
    left, top, width, height = (int(bounds_dict[key]) for key in ("left", "top", "width", "height"))
    if width <= 0 or height <= 0:
        raise ValueError("Screen window dimensions must be positive")
    window.update_idletasks()
    if not sys.platform.startswith("win"):
        window.geometry(f"{width}x{height}{left:+d}{top:+d}")
        return
    user32 = _library("user32")
    with physical_dpi_context():
        ancestor = _function(user32, "GetAncestor", [wintypes.HWND, wintypes.UINT], wintypes.HWND)
        hwnd = ancestor(window.winfo_id(), 2)  # GA_ROOT: Tk's native wrapper.
        if not hwnd:
            raise OSError("Could not locate the screen selection window")
        place = _function(user32, "SetWindowPos",
                          [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL)
        if not place(hwnd, None, left, top, width, height, 0x0004 | 0x0010 | 0x0040):
            raise OSError("Could not place the screen selection window")
    window.update_idletasks()


def move_physical_window(window, x: int, y: int) -> None:
    """Move a Tk toplevel's outer frame without changing size or activation.

    This also handles decorated dialogs: positions belong to the actual native
    wrapper, so negative desktop coordinates are not Tk screen-edge offsets.
    Visibility, focus and stacking remain controlled by the caller.
    """
    x, y = int(x), int(y)
    window.update_idletasks()
    if not sys.platform.startswith("win"):
        window.geometry(f"{x:+d}{y:+d}")
        return
    user32 = _library("user32")
    with physical_dpi_context():
        ancestor = _function(user32, "GetAncestor", [wintypes.HWND, wintypes.UINT], wintypes.HWND)
        hwnd = ancestor(window.winfo_id(), 2)  # GA_ROOT: includes decorated wrappers.
        if not hwnd:
            raise OSError("Could not locate the application window")
        move = _function(user32, "SetWindowPos",
                         [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                          ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL)
        # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE. No SHOWWINDOW flag: a
        # hidden dialog stays hidden until its owner explicitly presents it.
        if not move(hwnd, None, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010):
            raise OSError("Could not move the application window")
    window.update_idletasks()
