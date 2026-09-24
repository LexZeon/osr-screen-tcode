"""One-off picker synchronization: no native windows, screenshots or sleeps."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from osr_screen_tcode import screen_geometry as geometry
from osr_screen_tcode import region_selector


class NativeFlush:
    def __init__(self, events, outcomes=(0, 0)):
        self.events = events
        self.outcomes = iter(outcomes)

    def __call__(self):
        self.events.append("flush")
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class DesktopCompositionTests(unittest.TestCase):
    def test_flush_waits_once_then_commits_before_snapshot(self):
        events = []
        flush = NativeFlush(events)
        with patch.object(geometry.sys, "platform", "win32"), \
                patch.object(geometry, "_library", return_value=SimpleNamespace(DwmFlush=flush)), \
                patch.object(geometry.time, "monotonic", side_effect=(10., 10.04)), \
                patch.object(geometry.time, "sleep", side_effect=lambda seconds: events.append(("sleep", seconds))):
            self.assertTrue(geometry.flush_desktop_composition())
        self.assertEqual(events[0], "flush")
        self.assertEqual(events[1][0], "sleep")
        self.assertAlmostEqual(events[1][1], .21)
        self.assertEqual(events[2], "flush")
        self.assertEqual(len(events), 3)
        self.assertEqual(flush.argtypes, [])
        self.assertIs(flush.restype, geometry.ctypes.c_long)

    def test_slow_first_commit_does_not_add_another_quarter_second(self):
        events = []
        with patch.object(geometry.sys, "platform", "win32"), \
                patch.object(geometry, "_library", return_value=SimpleNamespace(DwmFlush=NativeFlush(events))), \
                patch.object(geometry.time, "monotonic", side_effect=(10., 10.31)), \
                patch.object(geometry.time, "sleep") as sleep:
            self.assertTrue(geometry.flush_desktop_composition())
        sleep.assert_not_called()
        self.assertEqual(events, ["flush", "flush"])

    def test_missing_dwm_keeps_settle_without_preventing_capture(self):
        for failure in (OSError("DWM unavailable"), AttributeError("DwmFlush absent")):
            with self.subTest(error=type(failure).__name__), \
                    patch.object(geometry.sys, "platform", "win32"), \
                    patch.object(geometry, "_library", side_effect=failure), \
                    patch.object(geometry.time, "monotonic", side_effect=(10., 10.)), \
                    patch.object(geometry.time, "sleep") as sleep:
                self.assertFalse(geometry.flush_desktop_composition())
                sleep.assert_called_once_with(.25)

    def test_final_hresult_or_api_error_is_not_reported_as_success(self):
        for result in (-2147467259, OSError("compositor stopped")):
            events = []
            with self.subTest(result=repr(result)), patch.object(geometry.sys, "platform", "win32"), \
                    patch.object(geometry, "_library", return_value=SimpleNamespace(DwmFlush=NativeFlush(events, (0, result)))), \
                    patch.object(geometry.time, "monotonic", side_effect=(10., 10.)), \
                    patch.object(geometry.time, "sleep"):
                self.assertFalse(geometry.flush_desktop_composition())
            self.assertEqual(events, ["flush", "flush"])

    def test_non_windows_has_no_delay_or_native_calls(self):
        with patch.object(geometry.sys, "platform", "linux"), \
                patch.object(geometry, "_library") as library, \
                patch.object(geometry.time, "sleep") as sleep:
            self.assertFalse(geometry.flush_desktop_composition())
        library.assert_not_called()
        sleep.assert_not_called()

    def test_picker_settles_before_constructing_snapshot_capture(self):
        events = []

        def begin_capture(_region):
            events.append("capture")
            raise OSError("synthetic stop before creating any native window")

        monitors = [dict(left=-1920, top=0, width=3840, height=1080)]
        with patch.object(region_selector, "screen_monitors", return_value=monitors), \
                patch.object(region_selector, "flush_desktop_composition", side_effect=lambda: events.append("settle")), \
                patch.object(region_selector, "ScreenCapture", side_effect=begin_capture), \
                patch.object(region_selector.tk, "Toplevel") as window:
            with self.assertRaisesRegex(OSError, "synthetic stop"):
                region_selector.ScreenRegionSelector(Mock(), on_done=Mock())
        self.assertEqual(events, ["settle", "capture"])
        window.assert_not_called()


if __name__ == "__main__":
    unittest.main()
