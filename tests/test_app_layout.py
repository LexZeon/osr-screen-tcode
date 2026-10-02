"""Full control-tree layout checks; run through the isolated test runner."""
from contextlib import ExitStack, contextmanager
import tkinter as tk
from tkinter import font, ttk
import unittest
from unittest.mock import patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig


class AppLayoutTests(unittest.TestCase):
    @contextmanager
    def window(self, language="en", scale=1.0, extra=None):
        with ExitStack() as stack:
            stack.enter_context(patch.object(AppConfig, "load", side_effect=lambda:
                AppConfig(last_sink="Log only", extra=dict(extra or {}))))
            stack.enter_context(patch.object(AppConfig, "save"))
            for method in ("refresh_ports", "refresh_audio_devices", "autodetect_device",
                           "_startup_actions", "_schedule_rtm_pose_gpu_status_refresh"):
                stack.enter_context(patch.object(OsrScreenApp, method))
            original = OsrScreenApp._configure_style
            def scaled_style(app):
                app.tk.call("tk", "scaling", scale * 96 / 72)
                for name in font.names(app):
                    value = font.nametofont(name, root=app)
                    value.configure(size=value.cget("size"))
                original(app)
            stack.enter_context(patch.object(OsrScreenApp, "_configure_style", scaled_style))
            app = OsrScreenApp(enforce_age_gate=False, ui_language=language)
            errors = []
            app.report_callback_exception = lambda *args: errors.append(args)
            try:
                app.update()
                yield app
                self.assertEqual(errors, [])
            finally:
                # Tk keeps pending callback names across successive roots; remove
                # them while the interpreter and settings protection still exist.
                for token in app.tk.splitlist(app.tk.call("after", "info")):
                    app.after_cancel(token)
                app._config_save_after_id = None
                app.on_close()

    def test_bilingual_scaled_controls_have_full_natural_width(self):
        for language in ("en", "zh"):
            for scale in (1, 1.5, 2, 3):
                with self.subTest(language=language, scale=scale), self.window(language, scale) as app:
                    panes = app.main_panes
                    bar = panes.sidebar
                    self.assertGreater(bar.canvas.winfo_width(), 220)
                    self.assertGreaterEqual(bar.content.winfo_width(), bar.content.winfo_reqwidth())
                    self.assertEqual(str(app.preview_tabs.select()), str(app.output_tab))
                    app.output_mode.set("Six Axis")
                    app._update_command_monitor("L04500 R15500 R24500")
                    app._update_command_monitor("L05500 R15000 R25000")
                    if scale <= 2:
                        for canvas in (app.stroke_canvas, app.axis_canvas, app.curve_canvas):
                            for item in canvas.find_all():
                                if canvas.type(item) == "text":
                                    left, top, right, bottom = canvas.bbox(item)
                                    self.assertGreaterEqual(left, 0)
                                    self.assertGreaterEqual(top, 0)
                                    self.assertLessEqual(right, canvas.winfo_width())
                                    self.assertLessEqual(bottom, canvas.winfo_height())
                    app.show_more_settings.set(True)
                    app.show_six_axis_travel_scales.set(True)
                    app.show_six_axis_tuning.set(True)
                    app.update()
                    self.assertGreaterEqual(bar.content.winfo_width(), bar.content.winfo_reqwidth())
                    # The screenshot's last limit numbers and measurement buttons
                    # now live on a complete surface, even if scrolling is needed.
                    def descendants(widget):
                        for child in widget.winfo_children():
                            yield child
                            yield from descendants(child)
                    for widget in descendants(bar.content):
                        if widget.winfo_ismapped() and isinstance(widget, (ttk.Button, ttk.Label)):
                            if isinstance(widget, ttk.Label) and widget.winfo_pixels(widget.cget("wraplength") or 0) > 0:
                                continue
                            self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth(), str(widget))

    def test_narrow_window_preserves_right_edge_and_preview(self):
        with self.window("en", 2) as app:
            app.show_more_settings.set(True)
            app.show_six_axis_travel_scales.set(True)
            app.geometry("800x620")
            app.update()
            panes, bar = app.main_panes, app.main_panes.sidebar
            self.assertTrue(bar.horizontal.winfo_ismapped())
            bar.canvas.xview_moveto(1)
            app.update()
            self.assertAlmostEqual(bar.canvas.xview()[1], 1.0, places=3)
            self.assertLessEqual(panes.preview.winfo_x() + panes.preview.winfo_width(), panes.winfo_width())
            self.assertGreaterEqual(panes.preview.winfo_width(), 220)

    def test_layout_preference_saves_and_factory_reset_removes_it(self):
        with self.window(extra={"sidebar_width_dip": 470}) as app:
            self.assertAlmostEqual(app.main_panes.sash_coord(0)[0], 470, delta=2)
            app.main_panes.preferred_width = 510.25
            app._save_config()
            self.assertEqual(app.config_model.extra["sidebar_width_dip"], 510.25)
            with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
                app.reset_all_settings()
            app.update()
            self.assertIsNone(app.main_panes.preferred_width)
            self.assertNotIn("sidebar_width_dip", app.config_model.extra)
            self.assertEqual(str(app.preview_tabs.select()), str(app.output_tab))

    def test_expansion_and_status_refresh_do_not_move_user_divider(self):
        with self.window("en", 2) as app:
            app.main_panes.sash_place(0, 750, 0)
            app.update()
            before = app.main_panes.sash_coord(0)
            app.show_more_settings.set(True)
            app.show_six_axis_travel_scales.set(True)
            app._refresh_limit_text()
            app.update()
            self.assertEqual(app.main_panes.sash_coord(0), before)


if __name__ == "__main__":
    unittest.main()
