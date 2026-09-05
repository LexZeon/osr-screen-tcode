import json
from pathlib import Path
import tempfile
import threading
import unittest
import tkinter as tk
from unittest.mock import patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode import APP_NAME, __version__
from osr_screen_tcode.config import AppConfig
from osr_screen_tcode.device_backends import DEVICE_FAMILIES, IntifaceDevice
from osr_screen_tcode.preview import PreviewBridge
from test_device_backends import device_message


class DeviceUiTests(unittest.TestCase):
    def test_directml_controls_and_preferences_without_nvidia(self):
        with patch.object(self.app, "_start_gpu_task"):
            self.app.rtm_pose_gpu_backend.set("directml")
            self.app._gpu_result = {"nvidia": False, "cuda": False, "reason": "dml_missing"}
            self.app.rtm_pose_gpu_enabled.set(True)
            view = self.app._gpu_views[0]
            self.assertIn("DirectML", view[2].get())
            self.assertEqual(view[3].winfo_manager(), "grid")
            self.assertIn("DirectML", view[3].cget("text"))
            self.app._save_config()
            self.assertEqual(self.app.config_model.extra["rtm_pose_gpu_backend"], "directml")
            self.app._finish_gpu_event({"gpu_event": "checked", "backend": "directml",
                "result": {"ready": True, "nvidia": False, "cuda": False, "backend": "directml"}})
            self.assertIn("验证通过", view[2].get())
            self.assertEqual(view[3].winfo_manager(), "")

    def test_gpu_download_progress_shared_in_both_languages(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "cpu_ort", "ort_version": "1.29.0"}
        self.app.rtm_pose_gpu_enabled.set(True)
        self.assertIn("CPU 版", self.app._gpu_views[0][2].get())
        popup = tk.Toplevel(self.app)
        self.addCleanup(popup.destroy)
        enabled, status = tk.BooleanVar(value=True), tk.StringVar()
        self.app._gpu_status_controls(popup, 0, enabled, status)
        self.app._gpu_installing = True
        data = {"stage": "downloading", "component": "nvidia-cudnn-cu12", "downloaded": 25 * 1024 ** 2,
                "total": 100 * 1024 ** 2, "index": 2, "count": 8}
        for language in ("zh", "en"):
            self.app.ui_language = language
            self.app._finish_gpu_event({"gpu_event": "stage", "stage": "downloading", "progress": data})
            self.assertIn("25.0%", status.get())
            self.assertIn("2/8  nvidia-cudnn-cu12", status.get())
            self.assertEqual(status.get(), self.app._gpu_views[0][2].get())
            self.assertEqual(float(self.app._gpu_views[0][5].cget("value")), 25)
            self.assertEqual(str(self.app._gpu_views[0][3].cget("state")), "disabled")
        self.app._finish_gpu_event({"gpu_event": "stage", "stage": "installing"})
        self.assertIn("Extracting", status.get())
        self.assertNotIn("100%", status.get())
        self.app._finish_gpu_event({"gpu_event": "failed", "error": "download_verification_failed"})
        self.assertIn("verification failed", status.get())
        self.assertEqual(self.app._gpu_views[0][5].winfo_manager(), "")

    def test_gpu_recheck_invalidates_cache_and_runs_in_background(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "cpu_ort"}
        self.app.rtm_pose_gpu_enabled.set(True)
        with patch.object(self.app, "_start_gpu_task") as start:
            self.app._recheck_gpu()
            self.assertIsNone(self.app._gpu_result)
            self.assertTrue(self.app._gpu_check_running)
            start.assert_called_once()
            self.app._recheck_gpu()
            start.assert_called_once()

    def test_closing_waits_for_gpu_task_cancellation(self):
        stopped = threading.Event()
        def work():
            self.app._gpu_cancel.wait(2)
            stopped.set()
        self.app._start_gpu_task(work, "gpu-cancel-test")
        self.app._cancel_gpu_tasks()
        self.assertTrue(stopped.is_set())
        self.assertTrue(all(not thread.is_alive() for thread in self.app._gpu_threads))
    def test_gpu_install_button_main_and_popup_share_state(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "runtime"}
        self.app.rtm_pose_gpu_enabled.set(True)
        view = self.app._gpu_views[0]
        self.assertEqual(view[3].winfo_manager(), "grid")
        self.assertIn("NVIDIA", view[2].get())
        popup = tk.Toplevel(self.app)
        enabled, status = tk.BooleanVar(value=True), tk.StringVar()
        self.app._gpu_status_controls(popup, 0, enabled, status)
        self.app._finish_gpu_event({"gpu_event": "installed"})
        self.assertIn("Start.cmd", status.get())
        self.assertIn("Start.cmd", view[2].get())
        self.app._begin_realtime_output()
        self.assertIsNone(self.app.worker)
        popup.destroy()
        self.app._refresh_gpu_views()
        self.assertEqual(len(self.app._gpu_views), 1)

    def test_gpu_install_requires_confirmation_and_never_runs_on_toggle(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "runtime"}
        with patch("osr_screen_tcode.gpu_controls.install_runtime") as install, patch("osr_screen_tcode.gpu_controls.messagebox.askyesno", return_value=False):
            self.app.rtm_pose_gpu_enabled.set(True)
            install.assert_not_called()
            self.app._install_gpu_runtime()
            install.assert_not_called()
            self.assertFalse(self.app._gpu_installing)

    def test_gpu_cpu_and_failed_install_states(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "runtime"}
        self.app.rtm_pose_gpu_enabled.set(True)
        self.app._gpu_installing = True
        self.app._finish_gpu_event({"gpu_event": "stage", "stage": "verifying"})
        view = self.app._gpu_views[0]
        self.assertEqual(str(view[3].cget("state")), "disabled")
        self.assertIn("验证", view[2].get())
        self.app._finish_gpu_event({"gpu_event": "failed"})
        self.assertIn("失败", view[2].get())
        self.assertFalse(self.app._gpu_restart_required)
        self.app.rtm_pose_gpu_enabled.set(False)
        self.assertEqual(view[3].winfo_manager(), "")
    def setUp(self):
        self.restart_patch = patch("osr_screen_tcode.gpu_controls.runtime_needs_restart", return_value=False)
        self.restart_patch.start()
        self.addCleanup(self.restart_patch.stop)
        self.save_patch = patch.object(AppConfig, "save")
        self.save_patch.start()
        self.addCleanup(self.save_patch.stop)
        self.load_patch = patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only"))
        self.load_patch.start()
        self.addCleanup(self.load_patch.stop)
        self.app = OsrScreenApp(enforce_age_gate=False, ui_language="zh")
        self.app.withdraw()
        self.app.update()
        self.addCleanup(self.app.on_close)

    def choose_device(self):
        self.app.device_family.set(DEVICE_FAMILIES["handy"])
        self.app._finish_device_scan({"device_scan": self.app._device_scan_generation,
                                     "devices": [IntifaceDevice.from_message(device_message(name="The Handy"))]})
        self.app.external_device.set(next(iter(self.app._external_devices)))
        self.app._on_external_device_selected()

    def test_version_header_and_contact_are_visible_text(self):
        def texts(widget):
            values = []
            if "text" in widget.keys():
                values.append(str(widget.cget("text")))
            for child in widget.winfo_children():
                values.extend(texts(child))
            return values
        labels = texts(self.app)
        self.assertEqual(self.app.title(), f"{APP_NAME} v{__version__}")
        self.assertTrue(any("合作与侵权" in t and "aivnailedeng@gmail.com" in t for t in labels))
        self.assertTrue(any(APP_NAME in t and __version__ in t for t in labels))

    def test_log_only_hides_all_serial_controls_and_ignores_invalid_baudrate(self):
        self.assertEqual(self.app.serial_settings_frame.winfo_manager(), "")
        self.assertEqual(self.app.ble_settings_frame.winfo_manager(), "")
        self.assertEqual(self.app.query_axes_button.winfo_manager(), "")
        self.app.baudrate.set("invalid")
        self.assertEqual(self.app._connection_snapshot(), {"kind": "Log only"})
        self.app.baudrate.set(115200)
        self.app.sink_type.set("Serial COM")
        self.assertEqual(self.app.serial_settings_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.query_axes_button.winfo_manager(), "grid")
        self.app.sink_type.set("BLE UART")
        self.assertEqual(self.app.serial_settings_frame.winfo_manager(), "")
        self.assertEqual(self.app.ble_settings_frame.winfo_manager(), "grid")

    def test_switch_to_log_disconnects_existing_hardware_connection(self):
        self.app.sink_type.set("Serial COM")
        self.app.connected = True
        with patch.object(self.app, "disconnect_sink", wraps=self.app.disconnect_sink) as disconnect:
            self.app.sink_type.set("Log only")
            disconnect.assert_called_once()
        self.assertFalse(self.app.connected)

    def test_custom_second_empty_by_default_and_duplicate_rejected(self):
        values = self.app.device_family_combo.cget("values")
        self.assertEqual(values[1], "自定义（Intiface）")
        self.app.device_family.set(values[1])
        device = IntifaceDevice.from_message(device_message(messages={
            "LinearCmd": [{"ActuatorType": "Linear"}],
            "ScalarCmd": [{"ActuatorType": "Vibrate"}]}))
        self.app._finish_device_scan({"device_scan": self.app._device_scan_generation, "devices": [device]})
        self.app.external_device.set(next(iter(self.app._external_devices)))
        self.app._on_external_device_selected()
        self.assertEqual(self.app.custom_mapping_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.external_single_mapping_frame.winfo_manager(), "")
        with self.assertRaises(ValueError):
            self.app._external_snapshot()
        labels = list(self.app._external_features)
        self.app.custom_bindings["L0"].set(labels[0])
        self.app.custom_bindings["R0"].set(labels[1])
        self.assertEqual(self.app.output_mode.get(), "Six Axis")
        snapshot = self.app._external_snapshot()
        self.assertEqual(snapshot["bindings"], {"L0": device.features[0].key, "R0": device.features[1].key})
        sink = self.app._open_sink_from_snapshot(snapshot)
        self.assertEqual(sink.axes, ("L0", "R0"))
        self.app._save_device_config()
        self.app._clear_external_selection()
        self.app._finish_device_scan({"device_scan": self.app._device_scan_generation, "devices": [device]})
        self.app.external_device.set(next(iter(self.app._external_devices)))
        self.app._on_external_device_selected()
        self.assertEqual(self.app._custom_binding_keys(), snapshot["bindings"])
        self.app.custom_bindings["L1"].set(labels[0])
        with self.assertRaisesRegex(ValueError, "不能绑定"):
            self.app._external_snapshot()
        self.app._reset_device_config()
        self.assertFalse(self.app.config_model.custom_bindings)
        self.assertEqual(self.app.config_model.custom_binding_signature, "")

    def test_custom_profile_never_restored_to_a_different_device(self):
        self.app.config_model.custom_bindings = {"L0": "LinearCmd:0:Linear"}
        self.app.config_model.custom_binding_signature = "different-device"
        self.app.device_family.set(self.app._device_family_labels["custom"])
        device = IntifaceDevice.from_message(device_message())
        self.app._finish_device_scan({"device_scan": self.app._device_scan_generation, "devices": [device]})
        self.app.external_device.set(next(iter(self.app._external_devices)))
        self.app._on_external_device_selected()
        self.assertFalse(self.app._custom_binding_keys())

    def test_measurement_open_on_first_use_and_reset(self):
        self.assertTrue(self.app.show_measurement_limits.get())
        self.assertEqual(self.app.measurement_limits_frame.winfo_manager(), "grid")
        self.app.show_measurement_limits.set(False)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True), patch("osr_screen_tcode.app.messagebox.showinfo"):
            self.app.reset_all_settings()
        self.assertTrue(self.app.show_measurement_limits.get())
        self.assertEqual(self.app.measurement_limits_frame.winfo_manager(), "grid")

    def test_native_and_external_connection_paths(self):
        self.assertEqual(self.app._connection_snapshot()["kind"], "Log only")
        self.choose_device()
        snapshot = self.app._connection_snapshot()
        self.assertEqual(snapshot["kind"], "Intiface")
        self.assertEqual(snapshot["axis"], "L0")
        self.assertEqual(snapshot["limit"], 0.2)
        self.assertFalse(self.app.connected)
        self.assertEqual(self.app.native_connection_frame.winfo_manager(), "")
        self.assertEqual(self.app.external_device_frame.winfo_manager(), "grid")
        self.assertIn("与实际设备不同", self.app.preview_shape_hint.cget("text"))

    def test_pending_autoblow_cannot_start_output(self):
        self.app.device_family.set(DEVICE_FAMILIES["autoblow"])
        self.app._start_after_connect = True
        self.app.connect_sink()
        self.assertFalse(self.app.connected)
        self.assertFalse(self.app._connecting)
        self.assertFalse(self.app._start_after_connect)
        self.assertIn("未启用输出", self.app.status.get())

    def test_rescan_invalidates_selected_device_and_late_result(self):
        self.choose_device()
        generation = self.app._device_scan_generation
        self.app.intiface_url.set("ws://127.0.0.1:12346")
        self.app._finish_device_scan({"device_scan": generation, "devices": [IntifaceDevice.from_message(device_message())]})
        self.assertFalse(self.app._external_devices)
        with self.assertRaises(ValueError):
            self.app._external_snapshot()

    def test_settings_reset_and_axis_mode(self):
        self.choose_device()
        self.app.external_axis.set("R0")
        self.assertEqual(self.app.output_mode.get(), "Six Axis")
        self.app.external_limit.set(37)
        self.app._save_config()
        self.assertEqual(self.app.config_model.device_family, "handy")
        self.assertEqual(self.app.config_model.external_limit, 37)
        self.assertEqual(self.app.config_model.external_axis, "R0")
        self.app._reset_device_config()
        self.assertEqual(self.app.external_limit.get(), 20)
        self.assertEqual(self.app.external_axis.get(), "L0")
        self.assertFalse(self.app._external_devices)

    def test_critical_events_not_dropped_by_preview_frames(self):
        self.app._queue_latest({"device_scan": 999, "devices": []})
        for _ in range(30):
            self.app._queue_latest({"activity": 0.1})
        self.assertEqual(self.app.control_queue.get_nowait()["device_scan"], 999)

    def test_cancel_connect_on_stop(self):
        self.app._start_after_connect = True
        self.app.stop()
        self.assertFalse(self.app._start_after_connect)

    def test_late_worker_completion_releases_controls(self):
        finished = threading.Thread(target=lambda: None)
        finished.start()
        finished.join()
        self.app.worker = finished
        self.app._set_device_controls_busy(True)
        self.app._poll_worker()
        self.assertIsNone(self.app.worker)
        self.assertEqual(str(self.app.device_family_combo.cget("state")), "readonly")


class ConfigTests(unittest.TestCase):
    def test_custom_profile_and_user_collapsed_state_persist(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp) / "config.json"):
            cfg = AppConfig(custom_bindings={"R0": "RotateCmd:0:Rotate"}, custom_binding_signature="signature",
                            extra={"show_measurement_limits": False})
            cfg.save()
            loaded = AppConfig.load()
            self.assertEqual(loaded.custom_bindings, cfg.custom_bindings)
            self.assertEqual(loaded.custom_binding_signature, "signature")
            self.assertFalse(loaded.extra["show_measurement_limits"])
    def test_round_trip_without_persisting_session_device_indexes(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp) / "config.json"):
            cfg = AppConfig(device_family="kiiroo", external_limit=28, external_axis="L2")
            cfg.save()
            loaded = AppConfig.load()
            self.assertEqual((loaded.device_family, loaded.external_limit, loaded.external_axis), ("kiiroo", 28, "L2"))
            saved = json.loads((Path(temp) / "config.json").read_text())
            self.assertNotIn("DeviceIndex", saved)

    def test_invalid_saved_values_clamped(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp) / "config.json"):
            cfg = AppConfig(external_limit=1000, external_axis="X9")
            cfg.save()
            loaded = AppConfig.load()
            self.assertEqual((loaded.external_limit, loaded.external_axis), (100, "L0"))


class PreviewTests(unittest.TestCase):
    def test_shape_notice_and_safe_name_in_generated_preview(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.preview.APP_DIR", Path(temp)), patch("webbrowser.open"):
            preview = PreviewBridge()
            preview.url = "ws://127.0.0.1:1234/test"
            preview.set_device_context("The Handy </script>", True, "en")
            html = preview.open_window().read_text(encoding="utf-8")
            self.assertIn("Preview shape differs from the actual device", html)
            self.assertTrue(__version__ in html)
            self.assertTrue(APP_NAME in html)
            self.assertNotIn("__OSR_PREVIEW_CONTEXT__", html)
            self.assertNotIn("The Handy </script>", html)
            self.assertIn("ws://127.0.0.1:1234/test", html)


if __name__ == "__main__":
    unittest.main()
