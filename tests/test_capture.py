import threading
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import contextmanager, nullcontext

import numpy as np

from osr_screen_tcode.capture import LatestScreenCapture, ScreenCapture, ScreenRegion, capture_fps, validate_region


class ReusedBufferCapture:
    def __init__(self, region):
        self.owner = threading.get_ident()
        self.buffer = np.zeros((16, 16, 3), np.uint8)
        self.count = 0
        self.closed = False

    def __enter__(self):
        return self

    def grab_bgr(self):
        assert threading.get_ident() == self.owner
        self.count += 1
        self.buffer.fill(self.count % 255)
        return self.buffer

    def __exit__(self, *_):
        assert threading.get_ident() == self.owner
        self.closed = True


class CaptureTests(unittest.TestCase):
    def test_negative_coordinates_remain_identical_through_capture_arguments(self):
        displays = [dict(left=-1920, top=0, width=1920, height=1080),
                    dict(left=0, top=-1440, width=2560, height=1440),
                    dict(left=0, top=0, width=1920, height=1080)]
        for region in (ScreenRegion(-1800, 100, 640, 480), ScreenRegion(100, -1300, 640, 480), ScreenRegion(-100, -100, 200, 200)):
            with self.subTest(region=region):
                self.assertEqual(validate_region(region, displays), region)
                self.assertEqual(region.to_mss(), dict(left=region.x, top=region.y, width=region.width, height=region.height))

    def test_invalid_and_missing_screen_regions_are_rejected_without_clamping(self):
        displays = [dict(left=-100, top=0, width=100, height=100), dict(left=100, top=0, width=100, height=100)]
        for region in (ScreenRegion(5, 5, 20, 20), ScreenRegion(-101, 0, 20, 20), ScreenRegion(190, 0, 20, 20),
                       ScreenRegion(-90, -1, 20, 20), ScreenRegion(-90, 90, 20, 20), ScreenRegion(-90, 0, 15, 20),
                       ScreenRegion(-90, 0, 20, -20), ScreenRegion(float('nan'), 0, 20, 20), ScreenRegion(-90.5, 0, 20, 20)):
            with self.subTest(region=region), self.assertRaises(ValueError):
                validate_region(region, displays)
        with self.assertRaises(ValueError):
            validate_region(ScreenRegion(0, 0, 16, 16), [])

    def test_capture_masks_only_desktop_gaps_and_owns_dpi_until_close(self):
        displays = [dict(left=-100, top=0, width=100, height=100), dict(left=100, top=0, width=100, height=100)]
        events = []

        @contextmanager
        def context():
            events.append("dpi enter")
            try:
                yield
            finally:
                events.append("dpi exit")

        class FakeMss:
            def grab(self, bounds):
                events.append(bounds)
                return np.full((bounds['height'], bounds['width'], 4), (5, 70, 190, 255), dtype=np.uint8)

            def close(self):
                events.append("mss close")

        with patch('osr_screen_tcode.capture.screen_monitors', return_value=displays), patch('osr_screen_tcode.capture.physical_dpi_context', context), patch('osr_screen_tcode.capture.mss.mss', return_value=FakeMss()):
            with ScreenCapture(ScreenRegion(-50, 10, 200, 50)) as capture:
                frame = capture.grab_bgr()
                self.assertEqual(frame.shape, (50, 200, 3))
                self.assertTrue(np.all(frame[:, :50] == (5, 70, 190)))
                self.assertTrue(np.all(frame[:, 50:150] == 0))
                self.assertTrue(np.all(frame[:, 150:] == (5, 70, 190)))
                self.assertNotIn("dpi exit", events)
            capture.close()  # cleanup is idempotent
        self.assertEqual(events, ["dpi enter", dict(left=-50, top=10, width=200, height=50), "mss close", "dpi exit"])

    def test_capture_rechecks_topology_without_recreating_capture(self):
        displays = [dict(left=0, top=0, width=1920, height=1080)]
        changed = [dict(left=0, top=0, width=1280, height=720)]
        fake = type('FakeMss', (), {'close': lambda self: None, 'grab': lambda self, bounds: np.zeros((16, 16, 4), dtype=np.uint8)})()
        with patch('osr_screen_tcode.capture.screen_monitors', side_effect=[displays, displays, changed]) as monitors, patch('osr_screen_tcode.capture.physical_dpi_context', nullcontext), patch('osr_screen_tcode.capture.mss.mss', return_value=fake) as factory, patch('osr_screen_tcode.capture.time.perf_counter', side_effect=[0, 0.1, 0.5, 1.0]):
            with ScreenCapture(ScreenRegion(0, 0, 16, 16)) as capture:
                capture.grab_bgr()
                self.assertEqual(monitors.call_count, 1)
                capture.grab_bgr()
                with self.assertRaisesRegex(RuntimeError, "layout or resolution changed"):
                    capture.grab_bgr()
            self.assertEqual(factory.call_count, 1)
            self.assertEqual(monitors.call_count, 3)

    def test_capture_dimension_mismatch_is_not_resized_into_a_false_preview(self):
        fake = type('FakeMss', (), {'close': lambda self: None, 'grab': lambda self, bounds: np.zeros((16, 24, 4), dtype=np.uint8)})()
        with patch('osr_screen_tcode.capture.screen_monitors', return_value=[dict(left=0, top=0, width=1920, height=1080)]), patch('osr_screen_tcode.capture.physical_dpi_context', nullcontext), patch('osr_screen_tcode.capture.mss.mss', return_value=fake):
            with ScreenCapture(ScreenRegion(0, 0, 16, 16)) as capture:
                with self.assertRaisesRegex(RuntimeError, "dimensions do not match"):
                    capture.grab_bgr()

    def test_constructor_failure_restores_dpi_without_opening_mss(self):
        events = []

        @contextmanager
        def context():
            events.append("enter")
            try:
                yield
            finally:
                events.append("exit")

        with patch('osr_screen_tcode.capture.physical_dpi_context', context), patch('osr_screen_tcode.capture.screen_monitors', return_value=[dict(left=0, top=0, width=1920, height=1080)]), patch('osr_screen_tcode.capture.mss.mss') as factory:
            with self.assertRaises(ValueError):
                ScreenCapture(ScreenRegion(-100, 0, 50, 50))
            factory.assert_not_called()
        self.assertEqual(events, ['enter', 'exit'])

    def test_saved_negative_screen_coordinates_survive_load(self):
        from osr_screen_tcode import config
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(dict(x=-1700, y=-900, width=640, height=480)), encoding='utf-8')
            with patch.object(config, 'CONFIG_PATH', path):
                saved = config.AppConfig.load()
            self.assertEqual((saved.x, saved.y, saved.width, saved.height), (-1700, -900, 640, 480))

    def test_latest_frame_skips_backlog_and_owns_its_pixels(self):
        instances = []
        def factory(region):
            value = ReusedBufferCapture(region)
            instances.append(value)
            return value
        with LatestScreenCapture(ScreenRegion(0, 0, 16, 16), lambda: 120, factory) as capture:
            first = capture.next_frame(0, timeout=1)
            self.assertIsNotNone(first)
            original = first.bgr.copy()
            time.sleep(0.12)
            latest = capture.next_frame(first.sequence)
            input_age = time.perf_counter() - latest.captured_at
            self.assertGreater(latest.sequence, first.sequence + 2)
            np.testing.assert_array_equal(first.bgr, original)
            self.assertGreater(latest.fps, 10)
            self.assertLess(input_age, 0.12)
        self.assertTrue(instances[0].closed)
        self.assertFalse(capture._thread.is_alive())

    def test_live_rate_increase_and_interruptible_low_rate_stop(self):
        rate = [5]
        with LatestScreenCapture(ScreenRegion(0, 0, 16, 16), lambda: rate[0], ReusedBufferCapture) as capture:
            first = capture.next_frame(0, timeout=1)
            rate[0] = 120
            time.sleep(0.4)
            latest = capture.next_frame(first.sequence)
            self.assertGreater(latest.sequence - first.sequence, 8)
        with LatestScreenCapture(ScreenRegion(0, 0, 16, 16), lambda: 1, ReusedBufferCapture) as capture:
            capture.next_frame(0, timeout=1)
            started = time.perf_counter()
        self.assertLess(time.perf_counter() - started, 0.2)

    def test_capture_error_reaches_consumer_instead_of_hanging(self):
        def broken(region):
            raise OSError("synthetic capture failure")
        with LatestScreenCapture(ScreenRegion(0, 0, 16, 16), lambda: 45, broken) as capture:
            with self.assertRaisesRegex(RuntimeError, "synthetic capture failure"):
                capture.next_frame(0, timeout=1)

    def test_invalid_rates_are_bounded(self):
        for value, expected in ((0, 1), (999, 120), (59.8, 60), (None, 45), (float("nan"), 45)):
            self.assertEqual(capture_fps(value), expected)

    def test_saved_rate_clamping_and_default_curve_migration(self):
        from osr_screen_tcode import config
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for value, expected in ((999, 120), (-2, 1), ("invalid", 45)):
                path.write_text(json.dumps({"fps": value}), encoding="utf-8")
                with patch.object(config, "CONFIG_PATH", path):
                    cfg = config.AppConfig.load()
                self.assertEqual(cfg.fps, expected)
                self.assertTrue(cfg.extra["output_curve_fitting"])
            path.write_text(json.dumps({"fps": 75, "extra": {"output_curve_fitting": False}}), encoding="utf-8")
            with patch.object(config, "CONFIG_PATH", path):
                self.assertFalse(config.AppConfig.load().extra["output_curve_fitting"])
