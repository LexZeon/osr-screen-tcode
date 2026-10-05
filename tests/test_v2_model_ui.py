"""Opt-in model preferences and GUI lifetimes; use the isolated test runner."""
from pathlib import Path
import tempfile
import threading
import tkinter as tk
from tkinter import font, ttk
import unittest
from unittest.mock import patch

from osr_screen_tcode import config
from osr_screen_tcode.config import AppConfig, HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE, STROKE_CYCLE_MODE, normalize_visual_settings
from osr_screen_tcode.ui_layout import display_scale
import test_app_layout as layout_tests


class ModelPreferenceTests(unittest.TestCase):
    def test_default_and_malformed_model_settings_do_not_opt_in(self):
        for extra in ({}, {"v2_vittrack_enabled": "false", "v2_neuflow_enabled": 1,
                           "v2_vittrack_model_path": None, "v2_neuflow_model_path": []}):
            normalize_visual_settings(extra)
            for model in ("vittrack", "neuflow"):
                self.assertIs(extra[f"v2_{model}_enabled"], False)
                self.assertEqual(extra[f"v2_{model}_model_path"], "")

    def test_explicit_options_survive_a_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(config, "APP_DIR", Path(folder)), \
                patch.object(config, "CONFIG_PATH", Path(folder) / "config.json"):
            extra = {"v2_vittrack_enabled": True, "v2_neuflow_enabled": False,
                     "v2_vittrack_model_path": "tracker.onnx", "v2_neuflow_model_path": "flow.onnx"}
            AppConfig(extra=extra).save()
            loaded = AppConfig.load()
            for name, value in extra.items():
                self.assertEqual(loaded.extra[name], value)


class ModelUiTests(unittest.TestCase):
    window = layout_tests.AppLayoutTests.window

    def test_switches_are_default_off_and_only_visible_for_v2_family(self):
        for language in ("en", "zh"):
            with self.subTest(language=language), self.window(language) as app:
                panel = app.integrated_preview.v2_model_controls
                sidebar = app.sidebar_v2_model_controls
                self.assertFalse(app.v2_vittrack_enabled.get())
                self.assertFalse(app.v2_neuflow_enabled.get())
                for mode, visible in ((HYBRID_V2_MODE, True), (STROKE_CYCLE_MODE, True),
                                      (HYBRID_MODE, False), (RTM_POSE_2D_MODE, False)):
                    app.tracker_mode.set(app._tracker_display(mode))
                    self.assertEqual(panel.winfo_manager() == "grid", visible)
                    self.assertEqual(sidebar.winfo_manager() == "grid", visible)
                texts = [row[0].cget("text") for row in panel.model_controls.values()]
                self.assertIn("ViTTrack", texts[0])
                self.assertIn("NeuFlow", texts[1])
                for controls in (panel, sidebar):
                    body = getattr(controls, "model_body", controls)
                    hint = next(w.cget("text") for w in body.winfo_children()
                                if isinstance(w, ttk.Label) and "NeuFlow" in w.cget("text"))
                    self.assertIn("NVIDIA CUDA", hint)
                    self.assertIn("DirectML", hint)
                    self.assertIn("不支持" if language == "zh" else "unsupported", hint)

    def test_narrow_high_dpi_analysis_model_controls_remain_reachable(self):
        for language in ("en", "zh"):
            for scale in (2, 3):
                with self.subTest(language=language, scale=scale), self.window(language, scale) as app:
                    app.geometry("1000x820")
                    app.preview_tabs.select(app.analysis_tab)
                    app.main_panes.sash_place(0, 600, 0)
                    app.update()
                    # A real monitor move can update Tk's DPI after startup;
                    # apply the test scale once the window is on its display.
                    app.tk.call("tk", "scaling", scale * 96 / 72)
                    for name in font.names(app):
                        value = font.nametofont(name, root=app)
                        value.configure(size=value.cget("size"))
                    app.update()
                    panel = app.integrated_preview.v2_model_controls
                    scroll = panel.model_scroll
                    self.assertFalse(scroll.winfo_ismapped())
                    self.assertTrue(panel.model_header.winfo_ismapped())
                    self.assertLessEqual(panel.winfo_height(), panel.model_header.winfo_height() + 2)
                    panel.model_header.invoke()
                    app.update()
                    self.assertTrue(scroll.winfo_ismapped())
                    self.assertLessEqual(scroll.winfo_height(), round(140 * display_scale(panel)))
                    self.assertLessEqual(scroll.winfo_height(), max(48, round(app.integrated_preview.winfo_height() * .22)))
                    self.assertGreaterEqual(scroll.content.winfo_width(), scroll.content.winfo_reqwidth())
                    self.assertLessEqual(scroll.winfo_rootx() + scroll.winfo_width(),
                                         app.integrated_preview.winfo_rootx() + app.integrated_preview.winfo_width())
                    self.assertLessEqual(scroll.winfo_rooty() + scroll.winfo_height(),
                                         app.integrated_preview.winfo_rooty() + app.integrated_preview.winfo_height())
                    if scroll.content.winfo_reqwidth() > scroll.canvas.winfo_width():
                        self.assertTrue(scroll.horizontal.winfo_ismapped())
                    # Normal focus events must expose both distant button
                    # columns and later rows without shrinking their text.
                    app.focus_force()
                    for button in (panel.model_controls["vittrack"][2], panel.model_controls["neuflow"][2]):
                        button.focus_set()
                        app.update()
                        self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                        self.assertGreaterEqual(button.winfo_rootx(), scroll.canvas.winfo_rootx())
                        self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                             scroll.canvas.winfo_rootx() + scroll.canvas.winfo_width())
                        self.assertGreaterEqual(button.winfo_rooty(), scroll.canvas.winfo_rooty())
                        self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                             scroll.canvas.winfo_rooty() + scroll.canvas.winfo_height())
                    panel.model_header.invoke()
                    app.update()
                    self.assertFalse(scroll.winfo_ismapped())

    def test_mode_gate_preserves_preferences_and_applies_independent_snapshot(self):
        with self.window() as app:
            app.v2_vittrack_enabled.set(True)
            app.v2_neuflow_enabled.set(True)
            snapshot = dict(app._v2_model_options)
            app.tracker_mode.set(app._tracker_display(RTM_POSE_2D_MODE))
            self.assertTrue(app.v2_vittrack_enabled.get())
            self.assertFalse(app._v2_model_options["vittrack_enabled"])
            self.assertFalse(app._v2_model_options["neuflow_enabled"])
            self.assertTrue(snapshot["vittrack_enabled"])
            app.tracker_mode.set(app._tracker_display(HYBRID_V2_MODE))
            self.assertTrue(app._v2_model_options["vittrack_enabled"])
            app._save_config()
            self.assertTrue(app.config_model.extra["v2_vittrack_enabled"])

    def test_active_analysis_stops_when_model_options_change(self):
        with self.window() as app, patch.object(app, "_video_analysis_active", return_value=True), \
                patch.object(app, "stop") as stop:
            app.v2_vittrack_model_path.set("prepared-while-off.onnx")
            stop.assert_not_called()
            app.v2_vittrack_enabled.set(True)
            stop.assert_called_once()
            self.assertIn("restart", app.status.get())

    def test_gpu_preferences_are_snapshotted_and_stop_only_active_neuflow(self):
        with self.window() as app:
            app.rtm_pose_gpu_enabled.set(False)
            with patch.object(app, "_video_analysis_active", return_value=True), patch.object(app, "stop") as stop:
                app.rtm_pose_gpu_enabled.set(True)
                stop.assert_not_called()
            self.assertTrue(app._v2_model_options["gpu_enabled"])
            app.v2_neuflow_enabled.set(True)
            with patch.object(app, "_video_analysis_active", return_value=True), patch.object(app, "stop") as stop:
                app.rtm_pose_gpu_enabled.set(False)
                stop.assert_called_once()
            self.assertFalse(app._v2_model_options["gpu_enabled"])

    def test_gpu_setup_is_available_without_pose_and_does_not_enable_models(self):
        with self.window() as app:
            app._show_v2_gpu_settings(app.integrated_preview.v2_model_controls)
            dialog = app._v2_gpu_dialog
            self.assertTrue(dialog.winfo_exists())
            self.assertIs(app.grab_current(), dialog)
            self.assertFalse(app.hybrid_v2_pose_enabled.get())
            self.assertFalse(app.v2_neuflow_enabled.get())
            self.assertFalse(app.v2_vittrack_enabled.get())
            self.assertTrue(app._gpu_views[-1][0].winfo_exists())
            hint = next(w.cget("text") for w in dialog.winfo_children()[0].winfo_children()
                        if isinstance(w, ttk.Label) and "NeuFlow" in w.cget("text"))
            self.assertIn("NVIDIA CUDA only", hint)
            self.assertIn("DirectML remains available for RTM Pose", hint)
            dialog.destroy()

    def test_reset_cancels_pending_download_and_restores_both_options(self):
        with self.window() as app:
            app.v2_vittrack_enabled.set(True)
            app.v2_neuflow_enabled.set(True)
            app.v2_vittrack_model_path.set("tracker.onnx")
            cancelled = threading.Event()
            app._v2_model_downloads["vittrack"] = {"cancel": cancelled}
            with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
                app.reset_all_settings()
            self.assertTrue(cancelled.is_set())
            self.assertEqual(app._v2_model_downloads, {})
            self.assertFalse(app.v2_vittrack_enabled.get())
            self.assertFalse(app.v2_neuflow_enabled.get())
            self.assertEqual(app.v2_vittrack_model_path.get(), "")
            self.assertEqual(app.v2_neuflow_model_path.get(), "")

    def test_popup_cancel_and_confirm_keep_model_preferences_consistent(self):
        with self.window() as app:
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            for confirm in (False, True):
                errors = []
                def act():
                    try:
                        dialog = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
                        panel = next(w for w in descendants(dialog) if hasattr(w, "model_controls"))
                        hint = next(w.cget("text") for w in panel.winfo_children()
                                    if isinstance(w, ttk.Label) and "NeuFlow" in w.cget("text"))
                        self.assertIn("NVIDIA CUDA", hint)
                        self.assertIn("DirectML is unsupported", hint)
                        panel.model_controls["vittrack"][0].invoke()
                        action = app._t("确认开始" if confirm else "取消")
                        next(w for w in descendants(dialog) if isinstance(w, ttk.Button) and w.cget("text") == action).invoke()
                    except Exception as exc:
                        errors.append(exc)
                        for child in app.winfo_children():
                            if isinstance(child, tk.Toplevel):
                                child.destroy()
                app.after(25, act)
                self.assertEqual(app._confirm_realtime_start(), confirm)
                self.assertEqual(errors, [])
                self.assertEqual(app.v2_vittrack_enabled.get(), confirm)

    def test_model_completion_is_durable_and_cannot_overwrite_later_choice(self):
        with self.window() as app:
            model, owner = "vittrack", app.integrated_preview.v2_model_controls
            app._v2_model_downloads[model] = {"token": 7, "cancel": threading.Event(),
                "owner": owner, "variable": app.v2_vittrack_model_path, "original": ""}
            app.v2_vittrack_model_path.set("later-choice.onnx")
            event = {"model": model, "token": 7, "kind": "done", "path": "download.onnx"}
            app._queue_latest({"v2_model_event": event})
            for index in range(8):
                app._queue_latest({"activity": index})
            self.assertEqual(app.control_queue.get_nowait(), {"v2_model_event": event})
            app._finish_v2_model_event(event)
            self.assertEqual(app.v2_vittrack_model_path.get(), "later-choice.onnx")
            app._finish_v2_model_event(event)  # Duplicate/stale completion is ignored.
            self.assertEqual(app._v2_model_downloads, {})


if __name__ == "__main__":
    unittest.main()
