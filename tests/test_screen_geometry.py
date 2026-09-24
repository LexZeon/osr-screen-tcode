import ctypes
from ctypes import wintypes
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from osr_screen_tcode import screen_geometry as geometry


class NativeFunction:
    def __init__(self, implementation):
        self.implementation = implementation
        self.calls = []

    def __call__(self, *arguments):
        self.calls.append(arguments)
        return self.implementation(*arguments)


def native(result):
    return NativeFunction(lambda *arguments: result)


class GeometryTests(unittest.TestCase):
    def test_union_retains_left_and_above_displays_without_scaling(self):
        layouts = (
            ([dict(left=0, top=0, width=1920, height=1080), dict(left=1920, top=0, width=3840, height=2160)],
             dict(left=0, top=0, width=5760, height=2160)),
            ([dict(left=0, top=0, width=1920, height=1080), dict(left=-2560, top=-1440, width=2560, height=1440)],
             dict(left=-2560, top=-1440, width=4480, height=2520)),
        )
        for monitors, expected in layouts:
            with self.subTest(monitors=monitors), patch.object(geometry, "screen_monitors", return_value=monitors):
                self.assertEqual(geometry.virtual_screen_bounds(), expected)

    def test_dpi_process_prefers_v2_and_checks_boolean_result(self):
        user = SimpleNamespace(SetProcessDpiAwarenessContext=native(True))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user):
            self.assertTrue(geometry.configure_dpi_awareness())
        self.assertEqual(user.SetProcessDpiAwarenessContext.calls, [(-4,)])

    def test_denied_process_hresult_falls_back_to_physical_gui_thread(self):
        user = SimpleNamespace(SetProcessDpiAwarenessContext=native(False),
                               GetThreadDpiAwarenessContext=native(-2),
                               GetAwarenessFromDpiAwarenessContext=native(1),
                               SetThreadDpiAwarenessContext=native(-2))
        core = SimpleNamespace(SetProcessDpiAwareness=native(-2147024891))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", side_effect=lambda name: user if name == "user32" else core):
            self.assertTrue(geometry.configure_dpi_awareness())
        self.assertEqual(core.SetProcessDpiAwareness.calls, [(2,)])
        self.assertEqual(user.SetThreadDpiAwarenessContext.calls, [(-4,)])

    def test_old_process_api_uses_zero_hresult_as_success(self):
        user = SimpleNamespace()
        core = SimpleNamespace(SetProcessDpiAwareness=native(0))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", side_effect=lambda name: user if name == "user32" else core):
            self.assertTrue(geometry.configure_dpi_awareness())

    def test_already_per_monitor_windows_81_does_not_require_thread_api(self):
        def query(_process, pointer):
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int)).contents.value = 2
            return 0
        user = SimpleNamespace()
        core = SimpleNamespace(SetProcessDpiAwareness=native(-2147024891), GetProcessDpiAwareness=NativeFunction(query))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", side_effect=lambda name: user if name == "user32" else core):
            self.assertTrue(geometry.configure_dpi_awareness())
            with geometry.physical_dpi_context():
                pass

    def test_physical_context_restores_previous_thread_even_on_failure(self):
        switch = NativeFunction(lambda context: -2 if context == -4 else -4)
        user = SimpleNamespace(SetThreadDpiAwarenessContext=switch)
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user):
            with self.assertRaisesRegex(ValueError, "synthetic"), geometry.physical_dpi_context():
                raise ValueError("synthetic")
        self.assertEqual(switch.calls, [(-4,), (-2,)])

    def test_physical_context_rejects_unavailable_dpi_instead_of_guessing(self):
        user = SimpleNamespace(SetThreadDpiAwarenessContext=native(None),
                               GetThreadDpiAwarenessContext=native(-2),
                               GetAwarenessFromDpiAwarenessContext=native(1))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user):
            with self.assertRaisesRegex(RuntimeError, "Physical screen coordinates"):
                with geometry.physical_dpi_context():
                    self.fail("A logical coordinate context must not capture")

    def test_cursor_keeps_physical_negative_coordinates(self):
        def read(point):
            value = ctypes.cast(point, ctypes.POINTER(wintypes.POINT)).contents
            value.x, value.y = -2300, -1000
            return True
        user = SimpleNamespace(SetThreadDpiAwarenessContext=native(-4), GetPhysicalCursorPos=NativeFunction(read))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user):
            self.assertEqual(geometry.physical_cursor_position(), (-2300, -1000))

    def test_window_placement_is_absolute_and_uses_native_wrapper(self):
        user = SimpleNamespace(SetThreadDpiAwarenessContext=native(-4), GetAncestor=native(0x123456789), SetWindowPos=native(True))
        window = SimpleNamespace(update_idletasks=native(None), winfo_id=native(123))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user):
            geometry.place_physical_window(window, dict(left=-2560, top=-1440, width=4480, height=2520))
        self.assertEqual(user.GetAncestor.calls, [(123, 2)])
        self.assertEqual(user.SetWindowPos.calls[0][:6], (0x123456789, None, -2560, -1440, 4480, 2520))
        self.assertEqual(len(window.update_idletasks.calls), 2)

    def test_dialog_move_preserves_size_stacking_focus_and_visibility(self):
        user = SimpleNamespace(SetThreadDpiAwarenessContext=native(-4),
                               GetAncestor=native(0x123456789), SetWindowPos=native(True))
        window = SimpleNamespace(update_idletasks=native(None), winfo_id=native(123), geometry=native(None))
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user):
            geometry.move_physical_window(window, -2100, -750)
        self.assertEqual(user.GetAncestor.calls, [(123, 2)])
        self.assertEqual(user.SetWindowPos.calls, [(0x123456789, None, -2100, -750, 0, 0, 0x0015)])
        self.assertEqual(window.geometry.calls, [])
        self.assertEqual(len(window.update_idletasks.calls), 2)

    def test_dialog_move_reports_native_wrapper_or_position_failure(self):
        for handle, moved in ((0, True), (0x123456789, False)):
            user = SimpleNamespace(SetThreadDpiAwarenessContext=native(-4),
                                   GetAncestor=native(handle), SetWindowPos=native(moved))
            window = SimpleNamespace(update_idletasks=native(None), winfo_id=native(123))
            with self.subTest(handle=handle), patch.object(geometry.sys, "platform", "win32"), \
                    patch.object(geometry, "_library", return_value=user), self.assertRaises(OSError):
                geometry.move_physical_window(window, -1600, 100)
            self.assertEqual(len(user.SetWindowPos.calls), 1 if handle else 0)

    def test_non_windows_move_keeps_size_out_of_geometry_request(self):
        window = SimpleNamespace(update_idletasks=native(None), geometry=native(None))
        with patch.object(geometry.sys, "platform", "linux"), patch.object(geometry, "_library") as library:
            geometry.move_physical_window(window, -300, 200)
            library.assert_not_called()
        self.assertEqual(window.geometry.calls, [("-300+200",)])

    def test_monitor_enumeration_uses_signed_physical_rectangles(self):
        def enumerate_monitors(_dc, _clip, receive, data):
            for coordinates in ((-2560, -1440, 0, 0), (0, 0, 1920, 1080)):
                rectangle = wintypes.RECT(*coordinates)
                receive(None, None, ctypes.pointer(rectangle), data)
            return True
        user = SimpleNamespace(SetThreadDpiAwarenessContext=native(-4), EnumDisplayMonitors=NativeFunction(enumerate_monitors))
        # CFUNCTYPE also permits this pure native-boundary test on non-Windows CI.
        with patch.object(geometry.sys, "platform", "win32"), patch.object(geometry, "_library", return_value=user), patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True):
            self.assertEqual(geometry.screen_monitors(), [dict(left=-2560, top=-1440, width=2560, height=1440),
                                                          dict(left=0, top=0, width=1920, height=1080)])

    def test_non_windows_configuration_does_not_load_windows_dll(self):
        with patch.object(geometry.sys, "platform", "linux"), patch.object(geometry, "_library") as library:
            self.assertFalse(geometry.configure_dpi_awareness())
            with geometry.physical_dpi_context():
                pass
            library.assert_not_called()


if __name__ == "__main__":
    unittest.main()
