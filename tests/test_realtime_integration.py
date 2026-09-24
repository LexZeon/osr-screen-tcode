import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig
from osr_screen_tcode.sinks import LogSink
from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE
from test_visual_pipeline import FakePose


class SyntheticCapture:
    def __init__(self, _region):
        self.frame = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def grab_bgr(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        y = 30 + (self.frame % 20) * 6
        cv2.rectangle(frame, (70, y), (210, y + 70), (190, 210, 180), -1)
        self.frame += 1
        return frame


class RealtimeIntegrationTests(unittest.TestCase):
    def test_integrated_modes_produce_main_preview_and_log_tcode_and_stop(self):
        class TextureCapture(SyntheticCapture):
            def __init__(self, region):
                super().__init__(region)
                self.texture = np.random.default_rng(9).integers(0, 256, (400, 400, 3), np.uint8)

            def grab_bgr(self):
                self.frame += 1
                return cv2.warpAffine(self.texture, np.float32([[1, 0, 0], [0, 1, -(self.frame % 50)]]), (400, 400))

        for mode, assisted in ((HYBRID_V2_MODE, False), (HYBRID_V2_MODE, True), (RTM_POSE_2D_MODE, False)):
            with self.subTest(mode=mode), patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only", tracker_mode=mode)), patch.object(AppConfig, "save"), patch("osr_screen_tcode.app.ScreenCapture", TextureCapture), patch("osr_screen_tcode.analyzer.OptionalRtmPose2dBackend", side_effect=lambda *a, **kw: FakePose()):
                app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
                app.withdraw()
                app.output_mode.set("Six Axis")
                app._set_tracker_mode(mode)
                app.hybrid_v2_pose_enabled.set(assisted)
                app.fps.set(60)
                errors, emitted = [], []
                app.report_callback_exception = lambda *args: errors.append(args)
                original = app._queue_latest
                def observe(item):
                    if "error" in item:
                        errors.append(item["error"])
                    if "command" in item:
                        emitted.append(item["command"])
                    return original(item)
                app._queue_latest = observe
                app.connect_sink()
                app.after(10, app._begin_realtime_output)
                app.after(1400, app.stop)
                app.after(1900, app.quit)
                app.mainloop()
                try:
                    self.assertFalse(errors, errors)
                    self.assertFalse(app.worker and app.worker.is_alive())
                    self.assertGreater(len(emitted), 5)
                    shown = app.integrated_preview.last_frame
                    self.assertIsNotNone(shown)
                    self.assertEqual(shown.pose, mode == RTM_POSE_2D_MODE or assisted)
                    self.assertEqual(shown.pair[0].shape, shown.pair[1].shape)
                    axes = set(app._parse_axis_values(emitted[-1]))
                    self.assertEqual(axes, {"L0", "L1", "L2", "R0", "R1", "R2"})
                finally:
                    app.on_close()

    def test_real_hybrid_analysis_keeps_running_with_log_sink_and_stops(self):
        emitted = []
        callback_errors = []
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only", tracker_mode=HYBRID_MODE)), patch.object(AppConfig, "save"), patch("osr_screen_tcode.app.ScreenCapture", SyntheticCapture):
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            app.report_callback_exception = lambda *args: callback_errors.append(args)
            app.connect_sink()
            self.assertIsInstance(app.sink, LogSink)
            original_write = app.sink.write

            def collect(payload):
                emitted.append(payload)
                original_write(payload)
            app.sink.write = collect
            stopped_at = []

            def stop():
                started = time.monotonic()
                app.stop()
                stopped_at.append(time.monotonic() - started)

            def begin():
                app._begin_realtime_output()
                # Count live time after startup, not during initial Tk layout.
                app.after(400, lambda: app.fps.set(120))
                app.after(700, lambda: app.output_curve_fitting.set(False))
                app.after(1200, stop)
                app.after(1800, app.quit)
            app.after(10, begin)
            try:
                app.mainloop()
                self.assertGreater(len(emitted), 5)
                self.assertFalse(app.worker and app.worker.is_alive())
                self.assertLess(stopped_at[0], 0.2)
                self.assertFalse(callback_errors)
                self.assertEqual(app._capture_target_fps, 120)
                self.assertFalse(app._output_curve_enabled)
            finally:
                # Close while AppConfig.save is still mocked, including on a
                # failed assertion; cleanup must not write test preferences.
                app.on_close()

    def test_old_worker_cannot_write_to_new_connection(self):
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"):
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            app._output_context.sink = app.sink
            app.sink = LogSink()
            app._emit_command("L09999I20")
            self.assertEqual(app.sink.last_payload, b"")
            app.on_close()


if __name__ == "__main__":
    unittest.main()
