import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig
from osr_screen_tcode.sinks import LogSink


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
    def test_real_hybrid_analysis_keeps_running_with_log_sink_and_stops(self):
        emitted = []
        callback_errors = []
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"), patch("osr_screen_tcode.app.ScreenCapture", SyntheticCapture):
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

            app.after(10, app._begin_realtime_output)
            app.after(1200, stop)
            app.after(1800, app.quit)
            app.mainloop()
            self.assertGreater(len(emitted), 5)
            self.assertFalse(app.worker and app.worker.is_alive())
            self.assertLess(stopped_at[0], 0.2)
            self.assertFalse(callback_errors)
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
