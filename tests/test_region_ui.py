"""Region changes must agree with capture, saved settings and paired previews.

Run through tests/run_tests.py for full path isolation. Every window below is
closed while configuration writes, startup actions and device scans are mocked.
No test opens a native selection overlay or connects to hardware.
"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

import numpy as np

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.capture import ScreenRegion
from osr_screen_tcode.config import AppConfig, HYBRID_MODE
from osr_screen_tcode.region_selector import canvas_point, desktop_bounds, region_from_points


MONITORS = [
    dict(left=0, top=0, width=2560, height=1440),
    dict(left=-1600, top=0, width=1600, height=900),
    dict(left=0, top=-900, width=1600, height=900),
]


def rectangle(config):
    return config.x, config.y, config.width, config.height


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


class RegionProjectionTests(unittest.TestCase):
    def test_signed_desktop_canvas_uses_virtual_origin_and_both_dimensions(self):
        bounds = desktop_bounds(MONITORS)
        self.assertEqual(bounds, dict(left=-1600, top=-900, width=4160, height=2340))
        self.assertEqual(canvas_point((-1600, -900), bounds, (1040, 585)), (0, 0))
        self.assertEqual(canvas_point((0, 0), bounds, (1040, 585)), (400, 225))
        self.assertEqual(canvas_point((2560, 1440), bounds, (1040, 585)), (1040, 585))

    def test_reverse_drag_preserves_negative_origin_and_cross_screen_pixels(self):
        expected = ScreenRegion(-100, 100, 200, 400)
        self.assertEqual(region_from_points((100, 500), (-100, 100), MONITORS), expected)
        self.assertEqual(region_from_points((-100, 100), (100, 500), MONITORS), expected)
        self.assertEqual(region_from_points((200, -800), (400, -500), MONITORS),
                         ScreenRegion(200, -800, 200, 300))

    def test_gap_only_outside_desktop_and_tiny_drags_are_rejected(self):
        for first, last in (((-1500, -800), (-1400, -700)),
                            ((2500, 1300), (2700, 1500)),
                            ((0, 0), (23, 100))):
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                region_from_points(first, last, MONITORS)


class RegionUiTests(unittest.TestCase):
    @contextmanager
    def app_window(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(AppConfig, 'load', side_effect=lambda: AppConfig(last_sink='Log only')))
            stack.enter_context(patch.object(AppConfig, 'save'))
            stack.enter_context(patch('osr_screen_tcode.capture.screen_monitors', return_value=MONITORS))
            stack.enter_context(patch('osr_screen_tcode.gpu_controls.runtime_needs_restart', return_value=False))
            for method in ('refresh_ports', 'refresh_audio_devices', 'autodetect_device',
                           '_startup_actions', '_schedule_rtm_pose_gpu_status_refresh'):
                stack.enter_context(patch.object(OsrScreenApp, method))
            app = OsrScreenApp(enforce_age_gate=False, ui_language='zh')
            app.withdraw()
            try:
                app.update_idletasks()
                yield app
            finally:
                # Keep all protection active through save/stop/destroy, including
                # assertion failures inside a test with a synthetic worker.
                app.worker = None
                app._video_worker = None
                app.on_close()

    @staticmethod
    def set_region(app, values):
        for variable, value in zip((app.x, app.y, app.width, app.height), values):
            variable.set(value)

    def test_signed_region_saves_exactly_and_round_trips_through_validation(self):
        with self.app_window() as app:
            values = (-1400, 100, 640, 480)
            self.set_region(app, values)
            self.assertEqual(app._read_screen_region(), ScreenRegion(*values))
            app._save_config()
            self.assertEqual(rectangle(app.config_model), values)

    def test_invalid_edits_preserve_whole_saved_rectangle_and_other_settings(self):
        with self.app_window() as app:
            original = (-1000, 100, 300, 300)
            self.set_region(app, original)
            app._save_config()
            invalid = ((-900, '-', 350, 350), ('', 200, 350, 350),
                       (-900, 200, 0, 350), (-900, 200, 350, -1))
            for index, values in enumerate(invalid):
                with self.subTest(values=values):
                    self.set_region(app, values)
                    app.fps.set(80 + index)
                    app._save_config()
                    self.assertEqual(rectangle(app.config_model), original)
                    self.assertEqual(app.config_model.fps, 80 + index)
                    with self.assertRaises((ValueError, tk.TclError)):
                        app._read_screen_region()

    def test_region_edit_clears_preview_and_rejects_queued_previous_frame(self):
        from osr_screen_tcode.visual_pipeline import VisualFrame
        with self.app_window() as app:
            old = VisualFrame((np.zeros((80, 120, 3), np.uint8),) * 2,
                              None, False, app._visual_settings.generation)
            app.integrated_preview.display(old)
            self.assertIs(app.integrated_preview.last_frame, old)
            app.x.set(200)
            self.assertGreater(app._visual_settings.generation, old.generation)
            self.assertIsNone(app.integrated_preview.last_frame)
            app.integrated_preview.display(old)
            self.assertIsNone(app.integrated_preview.last_frame)

    def test_invalid_region_never_reaches_device_connection_or_capture_start(self):
        with self.app_window() as app:
            self.set_region(app, (-900, 100, 0, 300))
            with patch.object(app, '_confirm_realtime_start', return_value=True), \
                    patch.object(app, '_ensure_rtm_pose_model_ready', return_value=True), \
                    patch.object(app, 'connect_sink') as connect, \
                    patch.object(app, '_begin_realtime_output') as begin, \
                    patch('osr_screen_tcode.app.messagebox.showerror'), \
                    patch('osr_screen_tcode.app.messagebox.showwarning'):
                app.start()
                connect.assert_not_called()
                begin.assert_not_called()
                self.assertIsNone(app.worker)

    def test_picker_accept_cancel_and_duplicate_open(self):
        with self.app_window() as app, patch('osr_screen_tcode.app.ScreenRegionSelector') as picker:
            selector = picker.return_value
            selector.closed = False
            selector.window.winfo_exists.return_value = True
            before = tuple(v.get() for v in (app.x, app.y, app.width, app.height))
            old_generation = app._visual_settings.generation
            app.pick_region()
            app.pick_region()
            picker.assert_called_once()
            selector.closed = True
            picker.call_args.kwargs['on_done'](None)
            self.assertEqual(tuple(v.get() for v in (app.x, app.y, app.width, app.height)), before)
            self.assertEqual(app._visual_settings.generation, old_generation)

            picker.reset_mock()
            selector.closed = False
            app.pick_region()
            chosen = ScreenRegion(-1300, 200, 500, 400)
            selector.closed = True
            picker.call_args.kwargs['on_done'](chosen)
            self.assertEqual(app._read_screen_region(), chosen)
            self.assertGreater(app._visual_settings.generation, old_generation)
            self.assertIsNone(app.integrated_preview.last_frame)
            app._save_config()
            self.assertEqual(rectangle(app.config_model), (-1300, 200, 500, 400))

    def test_running_capture_locks_region_and_source_controls_and_rejects_picker(self):
        with self.app_window() as app, patch('osr_screen_tcode.app.ScreenRegionSelector') as picker, \
                patch('osr_screen_tcode.app.messagebox.showwarning'):
            variables = {str(v) for v in (app.x, app.y, app.width, app.height, app.source_mode)}
            controls = [w for w in widgets(app) if isinstance(w, (ttk.Entry, ttk.Combobox))
                        and str(w.cget('textvariable')) in variables]
            self.assertEqual(len(controls), 5)
            app.worker = SimpleNamespace(is_alive=lambda: True)
            app._refresh_region_controls()
            self.assertTrue(all('disabled' in w.state() for w in controls))
            app.pick_region()
            picker.assert_not_called()
            app.worker = None
            app._refresh_region_controls()
            self.assertTrue(all('disabled' not in w.state() for w in controls))

    def test_programmatic_region_change_during_capture_stops_old_region(self):
        with self.app_window() as app:
            app.worker = SimpleNamespace(is_alive=lambda: True)
            before = app._visual_settings.generation
            with patch.object(app, 'stop') as stop:
                app.x.set(250)
                stop.assert_called()
            self.assertGreater(app._visual_settings.generation, before)

    def test_capture_uses_validated_snapshot_without_reading_tk_coordinates(self):
        with self.app_window() as app:
            snapshot = ScreenRegion(-900, 100, 400, 300)
            app._screen_region_snapshot = snapshot
            app.stop_event.clear()
            capture = Mock()
            capture.__enter__ = Mock(return_value=capture)
            capture.__exit__ = Mock(return_value=False)

            def stop_after_wait(_sequence):
                app.stop_event.set()
                return None

            capture.next_frame.side_effect = stop_after_wait
            with ExitStack() as stack:
                factory = stack.enter_context(patch('osr_screen_tcode.app.LatestScreenCapture', return_value=capture))
                for variable in (app.x, app.y, app.width, app.height):
                    stack.enter_context(patch.object(variable, 'get', side_effect=AssertionError('Worker read Tk coordinates')))
                app._run_screen(Mock(), Mock(), 1 / 45, 0)
                self.assertEqual(factory.call_args.args[0], snapshot)

    def test_compression_preserves_aspect_and_does_not_enlarge_short_edges(self):
        with self.app_window() as app:
            app.compression_latency.set(5)
            for height, width in ((16, 1000), (1000, 16), (64, 1000), (1000, 64), (180, 320)):
                with self.subTest(height=height, width=width):
                    frame = np.zeros((height, width, 3), np.uint8)
                    result = app._prepare_analysis_frame(frame)
                    rh, rw = result.shape[:2]
                    self.assertLessEqual(rh, height)
                    self.assertLessEqual(rw, width)
                    self.assertLessEqual(abs(rw * height - rh * width), max(width, height))
                    if min(height, width) <= 64:
                        self.assertEqual((rh, rw), (height, width))
                    else:
                        self.assertEqual((rh, rw), (108, 192))

    def test_live_v1_compression_change_resets_old_frame_before_processing(self):
        from osr_screen_tcode.analyzer import RealtimeAnalyzer
        with self.app_window() as app:
            app._set_tracker_mode(HYBRID_MODE)
            app.compression_latency.set(0)
            analyzer = RealtimeAnalyzer(tracker_mode=HYBRID_MODE)
            frame = np.zeros((180, 320, 3), np.uint8)
            app.stop_event.clear()
            output = Mock()
            with patch.object(app, '_refresh_live_output_mapping'), \
                    patch.object(app, '_emit_command', return_value='L05000I24'), \
                    patch.object(app, '_queue_latest'):
                app._process_frame(analyzer, output, frame, 0, timestamp=0)
                self.assertEqual(analyzer._prev_gray.shape, (180, 320))
                generation = app._visual_settings.generation
                app.compression_latency.set(5)
                self.assertGreater(app._visual_settings.generation, generation)
                app._process_frame(analyzer, output, frame, 0, timestamp=1 / 30)
                self.assertEqual(analyzer._prev_gray.shape, (108, 192))
                self.assertEqual(output.next_command.call_count, 2)
                self.assertFalse(app.stop_event.is_set())

    def test_reset_defaults_replaces_region_and_invalidates_old_preview(self):
        with self.app_window() as app:
            self.set_region(app, (-1300, 100, 500, 400))
            generation = app._visual_settings.generation
            with patch('osr_screen_tcode.app.messagebox.askyesno', return_value=True):
                app.reset_all_settings()
            defaults = AppConfig()
            self.assertEqual(rectangle(app.config_model), rectangle(defaults))
            self.assertEqual(app._read_screen_region(), ScreenRegion(*rectangle(defaults)))
            self.assertGreater(app._visual_settings.generation, generation)
            self.assertIsNone(app.integrated_preview.last_frame)


if __name__ == '__main__':
    unittest.main()
