import unittest
from unittest.mock import Mock, patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig, HYBRID_MODE
from osr_screen_tcode.sinks import SerialSink, BleSink, LogSink, OutputWriteError
from test_realtime_integration import SyntheticCapture


class TransportFailureTests(unittest.TestCase):
    def test_unconnected_transports_reject_commands(self):
        for sink in (SerialSink('test'), BleSink('test', 'test')):
            with self.assertRaises(ConnectionError):
                sink.write(b'L05000I24\n')
        log = LogSink()
        log.write(b'L05000I24\n')
        self.assertEqual(log.last_payload, b'L05000I24\n')

    def test_serial_partial_write_is_a_failure_and_is_not_retried(self):
        sink = SerialSink('test')
        sink._serial = Mock()
        sink._serial.write.return_value = 3
        with self.assertRaisesRegex(OSError, '3/10'):
            sink.write(b'L05000I24\n')
        sink._serial.write.assert_called_once()

    def test_ble_thread_error_is_preserved(self):
        sink = BleSink('test', 'test')
        sink._error = TimeoutError('BLE write timed out')
        with self.assertRaisesRegex(TimeoutError, 'BLE write timed out'):
            sink.write(b'L05000I24\n')


class OutputFailureUiTests(unittest.TestCase):
    def setUp(self):
        patches = [patch.object(AppConfig, 'load', side_effect=lambda: AppConfig(last_sink='Log only', tracker_mode=HYBRID_MODE)),
                   patch.object(AppConfig, 'save')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.app = OsrScreenApp(enforce_age_gate=False, ui_language='zh')
        self.app.withdraw()
        self.addCleanup(self.app.on_close)

    def test_write_failure_stops_and_prompts_once_without_forwarding_failed_command(self):
        class FailingHardware:
            def __init__(self):
                self.writes, self.accepted, self.closed = 0, [], False

            def write(self, payload):
                self.writes += 1
                if self.writes > 2:
                    raise TimeoutError('device write timed out')
                self.accepted.append(payload)

            def close(self):
                self.closed = True

        sink = FailingHardware()
        self.app.sink_type.set('Serial COM')
        self.app.sink, self.app.connected = sink, True
        callbacks = []
        self.app.report_callback_exception = lambda *info: callbacks.append(info)
        with patch('osr_screen_tcode.app.ScreenCapture', SyntheticCapture), \
                patch('osr_screen_tcode.app.messagebox.showerror') as popup, \
                patch.object(self.app.preview_bridge, 'broadcast_tcode') as broadcast:
            def begin():
                self.app._begin_realtime_output()
                self.app.after(1500, self.app.quit)
            self.app.after(10, begin)
            self.app.mainloop()
            self.assertFalse(callbacks)
            self.assertFalse(self.app.worker and self.app.worker.is_alive())
            self.assertFalse(self.app.connected)
            self.assertTrue(self.app.stop_event.is_set())
            self.assertTrue(sink.closed)
            self.assertEqual(sink.writes, 3)
            self.assertEqual(broadcast.call_count, 2)
            self.assertEqual([c.args[0] for c in broadcast.call_args_list],
                             [p.decode().strip() for p in sink.accepted])
            popup.assert_called_once()
            self.assertIn('设备输出失败', popup.call_args.args[0])
            self.assertIn('未接入', popup.call_args.args[1])
            self.assertIn('TimeoutError: device write timed out', popup.call_args.args[1])
            self.assertIn('Log only', popup.call_args.args[1])
            self.assertEqual(self.app.sink_type.get(), 'Serial COM')

    def test_closed_serial_failure_is_queued_for_ui_and_old_failure_cannot_close_new_sink(self):
        failed = SerialSink('test')
        self.app.sink = failed
        with self.assertRaises(OutputWriteError):
            self.app._emit_command('L05000I24')
        item = self.app.control_queue.get_nowait()
        self.assertTrue(item['output_failed'])
        replacement = LogSink()
        self.app.sink, self.app.connected = replacement, True
        with patch('osr_screen_tcode.app.messagebox.showerror') as popup:
            self.app._finish_output_failure(item)
            popup.assert_not_called()
        self.assertIs(self.app.sink, replacement)
        self.assertTrue(self.app.connected)

    def test_english_popup_and_connection_failure_explain_missing_hardware(self):
        self.app.ui_language = 'en'
        failed = SerialSink('test')
        self.app.sink, self.app.connected = failed, True
        with patch('osr_screen_tcode.app.messagebox.showerror') as popup:
            self.app._finish_output_failure({'sink': failed, 'message': 'not connected'})
            self.assertEqual(popup.call_args.args[0], 'Device output failed')
            self.assertIn('missing, disconnected or timed out', popup.call_args.args[1])
            self.app._finish_connection_error({'attempt_id': self.app._connect_attempt_id, 'message': 'port unavailable'})
            self.assertIn('Could not connect', popup.call_args.args[1])
            self.assertIn('port unavailable', popup.call_args.args[1])

    def test_capture_setup_error_is_reported_and_is_not_labeled_device_failure(self):
        with patch.object(self.app, '_normalize_limits', side_effect=ValueError('invalid setup')):
            self.app._run_capture()
        item = self.app.control_queue.get_nowait()
        self.assertEqual(item['error'], 'ValueError: invalid setup')
        self.assertNotIn('output_failed', item)
        self.assertTrue(self.app.control_queue.get_nowait()['capture_stopped'])


if __name__ == '__main__':
    unittest.main()
