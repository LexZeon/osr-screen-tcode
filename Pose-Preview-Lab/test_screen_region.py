"""Lab selection/capture wiring without creating windows or reading the desktop."""
from collections import deque
import unittest
from unittest.mock import Mock, patch

import numpy as np

from preview import App, MODES, Options, ScreenRegion


class ScreenRegionTests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.root = Mock()
        app.worker = None
        app.region = ScreenRegion(20, 30, 320, 240)
        app.region_selector = None
        app.canvas = Mock()
        app.status = Mock()
        app.measurement_status = Mock()
        app.render_chart = Mock()
        app.reference_generation = 4
        app.history = deque([object()])
        app.last_pair = object()
        app.photo = object()
        return app

    def test_selecting_negative_desktop_region_clears_stale_preview(self):
        app = self.app()
        old_region = app.region
        with patch("preview.ScreenRegionSelector") as selector:
            app.select_region()
        self.assertEqual(selector.call_args.kwargs["current"], old_region)
        selected = ScreenRegion(-1800, -700, 2400, 900)
        selector.call_args.kwargs["on_done"](selected)
        self.assertIs(app.region, selected)
        self.assertIsNone(app.region_selector)
        self.assertIsNone(app.last_pair)
        self.assertIsNone(app.photo)
        self.assertFalse(app.history)
        self.assertEqual(app.reference_generation, 5)
        app.canvas.delete.assert_called_once_with("all")
        app.root.deiconify.assert_called_once()
        self.assertIn("-1800, -700", app.status.set.call_args.args[0])

    def test_cancel_preserves_previous_region_and_preview(self):
        app = self.app()
        region, pair = app.region, app.last_pair
        with patch("preview.ScreenRegionSelector") as selector:
            app.select_region()
        selector.call_args.kwargs["on_done"](None)
        self.assertIs(app.region, region)
        self.assertIs(app.last_pair, pair)
        self.assertEqual(app.reference_generation, 4)
        app.canvas.delete.assert_not_called()
        app.root.deiconify.assert_called_once()

    def test_active_worker_and_open_selector_prevent_duplicate_selection(self):
        app = self.app()
        app.worker = Mock()
        app.worker.is_alive.return_value = True
        with patch("preview.ScreenRegionSelector") as selector, patch("preview.messagebox.showinfo") as info:
            app.select_region()
        selector.assert_not_called()
        info.assert_called_once()
        app.worker = None
        app.region_selector = object()
        with patch("preview.ScreenRegionSelector") as selector:
            app.select_region()
        selector.assert_not_called()

    def test_selector_error_restores_window_without_changing_region(self):
        app = self.app()
        original = app.region
        with patch("preview.ScreenRegionSelector", side_effect=OSError("desktop changed")), \
                patch("preview.messagebox.showerror") as error:
            app.select_region()
        self.assertIs(app.region, original)
        self.assertIsNone(app.region_selector)
        app.root.deiconify.assert_called_once()
        error.assert_called_once()

    def test_worker_uses_exact_signed_region_and_closes_capture(self):
        app = self.app()
        app.current_options = Options()
        app.processing_edge = 640
        app.stop_event = Mock()
        app.stop_event.is_set.side_effect = (False, False, True)
        app.publish = Mock()
        region = ScreenRegion(-1280, -100, 1280, 720)
        with patch("preview.ScreenCapture") as capture, patch("preview.FrameMotion") as motion:
            capture.return_value.grab_bgr.return_value = np.full((720, 1280, 3), 31, np.uint8)
            motion.return_value.update.return_value = (None, ())
            app.run("", None, region, MODES[1])
        capture.assert_called_once_with(region)
        capture.return_value.close.assert_called_once()
        pair, status, _, _ = app.publish.call_args.args[0]
        self.assertNotIn("Error", status)
        self.assertIn("X -1280 Y -100", status)
        self.assertIn("1280x720 px", status)
        self.assertIn("Analysis size / 分析尺寸 640x360", status)
        for frame in pair:
            self.assertEqual(frame.shape, (360, 640, 3))
            np.testing.assert_array_equal(frame[0, 0], (31, 31, 31))

    def prepare_start(self, app, mode=MODES[1]):
        app.mode = Mock()
        app.mode.get.return_value = mode
        app.model = Mock()
        app.model.get.return_value = ""
        app.stop_event = Mock()
        app.options_changed = Mock(side_effect=app.reset_reference)

    def test_new_source_clears_old_preview_before_worker_then_error_cannot_restore_it(self):
        app = self.app()
        self.prepare_start(app)
        events = []
        app.canvas.delete.side_effect = lambda _tag: events.append("clear")
        with patch("preview.threading.Thread") as thread:
            thread.return_value.start.side_effect = lambda: events.append("start")
            app.start("unavailable-video.avi")
        self.assertEqual(events, ["clear", "start"])
        self.assertIsNone(app.last_pair)
        self.assertIsNone(app.photo)
        self.assertFalse(app.history)
        self.assertEqual(app.reference_generation, 5)
        app.options_changed.assert_called_once()
        app.publish = Mock()
        with patch("preview.cv2.VideoCapture") as video:
            video.return_value.isOpened.return_value = False
            app.run("", "unavailable-video.avi", app.region, MODES[1])
        self.assertIsNone(app.last_pair)
        self.assertIsNone(app.publish.call_args.args[0][0])
        self.assertIn("Error", app.publish.call_args.args[0][1])
        video.return_value.release.assert_called_once()

    def test_failed_model_precheck_or_unselected_region_keeps_previous_preview(self):
        app = self.app()
        self.prepare_start(app, mode=MODES[0])
        previous = app.last_pair
        with patch("preview.Path.is_file", return_value=False), patch("preview.messagebox.showerror"), \
                patch("preview.threading.Thread") as thread:
            app.start("video.avi")
        self.assertIs(app.last_pair, previous)
        app.canvas.delete.assert_not_called()
        thread.assert_not_called()
        app.mode.get.return_value = MODES[1]
        app.region = None
        app.select_region = Mock()
        with patch("preview.threading.Thread") as thread:
            app.start(None)
        self.assertIs(app.last_pair, previous)
        app.canvas.delete.assert_not_called()
        app.select_region.assert_called_once()
        thread.assert_not_called()

    def test_video_status_reports_analysis_size_without_screen_coordinates(self):
        app = self.app()
        app.current_options = Options()
        app.processing_edge = 640
        app.stop_event = Mock()
        app.stop_event.is_set.side_effect = (False, False, True)
        app.publish = Mock()
        with patch("preview.cv2.VideoCapture") as video, patch("preview.FrameMotion") as motion:
            video.return_value.isOpened.return_value = True
            video.return_value.get.return_value = 30.
            video.return_value.read.return_value = (True, np.full((720, 1280, 3), 31, np.uint8))
            motion.return_value.update.return_value = (None, ())
            app.run("", "video.avi", app.region, MODES[1])
        status = app.publish.call_args.args[0][1]
        self.assertNotIn("Error", status)
        self.assertNotIn("Screen capture", status)
        self.assertNotIn(" px", status)
        self.assertIn("Analysis size / 分析尺寸 640x360", status)
        video.return_value.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
