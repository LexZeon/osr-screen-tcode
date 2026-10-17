"""Exercise a live start modal across event-loop turns, with settings isolated.

Run via tests/run_tests.py, serially with the other GUI tests. No output device,
model inference, model download or GPU installation is started by these tests.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import tkinter as tk
from tkinter import font, ttk
import unittest
from unittest.mock import patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.application.start_dialog import _StartDialogSidebar
from osr_screen_tcode.config import AppConfig
from osr_screen_tcode.screen_geometry import move_physical_window, screen_monitors


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class StartDialogResponsivenessTests(unittest.TestCase):
    @contextmanager
    def window(self, language="en", scale=1.5):
        # Enumerate the current desktop rather than fixing a developer's monitor
        # geometry in the product. Prefer the right-hand secondary display.
        monitors = screen_monitors()
        monitor = max(monitors, key=lambda item: item["left"])
        origin = monitor["left"] + 40, monitor["top"] + 80
        with ExitStack() as stack:
            stack.enter_context(patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only")))
            stack.enter_context(patch.object(AppConfig, "save"))
            stack.enter_context(patch("osr_screen_tcode.v2_model_assets.detect_model",
                                      return_value=("", "Model file is missing.")))
            for method in ("refresh_ports", "refresh_audio_devices", "autodetect_device",
                           "_startup_actions", "_schedule_rtm_pose_gpu_status_refresh"):
                stack.enter_context(patch.object(OsrScreenApp, method))
            original_style = OsrScreenApp._configure_style

            def configure(app):
                app.withdraw()
                app.geometry(f"{origin[0]:+d}{origin[1]:+d}")
                app.tk.call("tk", "scaling", scale * 96 / 72)
                original_style(app)

            stack.enter_context(patch.object(OsrScreenApp, "_configure_style", configure))
            app = OsrScreenApp(enforce_age_gate=False, ui_language=language)
            callback_errors = []
            app.report_callback_exception = lambda *error: callback_errors.append(error)
            try:
                move_physical_window(app, *origin)
                app.deiconify()
                app.update()
                # Windows can set Tk DPI on the real monitor transition.
                app.tk.call("tk", "scaling", scale * 96 / 72)
                for name in font.names(app):
                    value = font.nametofont(name, root=app)
                    value.configure(size=value.cget("size"))
                app.update()
                yield app
                self.assertEqual(callback_errors, [], "Tk callbacks raised an exception")
            finally:
                for token in app.tk.splitlist(app.tk.call("after", "info")):
                    app.after_cancel(token)
                app._config_save_after_id = None
                app.on_close()

    def modal(self, app, prepare, inspect):
        errors, ticks, dialogs = [], [], []

        def close_owned():
            for child in tuple(app.winfo_children()):
                if isinstance(child, tk.Toplevel) and child.winfo_exists():
                    child.destroy()

        def guarded(callback):
            try:
                callback()
            except Exception as exc:
                errors.append(exc)
                close_owned()

        def heartbeat():
            ticks.append(True)
            if dialogs and dialogs[0].winfo_exists():
                app.after(20, heartbeat)

        def enter():
            dialog = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
            dialogs.append(dialog)
            panel = next(w for w in descendants(dialog) if hasattr(w, "model_controls"))
            prepare(dialog, panel)
            app.after(20, heartbeat)
            # In contrast to same-callback invoke/cancel checks, leave Tk free
            # to lay out the changed labels, redraw and service real timers.
            def inspect_when_ticking():
                if len(ticks) < 3:
                    app.after(40, lambda: guarded(inspect_when_ticking))
                else:
                    guarded(lambda: inspect(dialog, panel, ticks))
            app.after(220, lambda: guarded(inspect_when_ticking))

        timeout = app.after(5000, lambda: guarded(lambda: self.fail("Start modal did not finish")))
        app.after(80, lambda: guarded(enter))
        try:
            accepted = app._confirm_realtime_start()
        finally:
            app.after_cancel(timeout)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(ticks), 3, "The event loop did not continue after toggling")
        return accepted

    @staticmethod
    def action(app, dialog, text):
        return next(w for w in descendants(dialog)
                    if isinstance(w, ttk.Button) and w.cget("text") == app._t(text))

    def assert_visible(self, widget, viewport):
        detail = f'{widget}: {widget.winfo_geometry()} inside {viewport}: {viewport.winfo_geometry()}'
        self.assertGreaterEqual(widget.winfo_rootx(), viewport.winfo_rootx() - 1, detail)
        self.assertGreaterEqual(widget.winfo_rooty(), viewport.winfo_rooty() - 1, detail)
        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                             viewport.winfo_rootx() + viewport.winfo_width() + 1, detail)
        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                             viewport.winfo_rooty() + viewport.winfo_height() + 1, detail)

    def test_bilingual_high_dpi_toggles_keep_heartbeat_footer_and_model_controls_reachable(self):
        for language in ("en", "zh"):
            for scale in (1.5, 3):
                with self.subTest(language=language, scale=scale), self.window(language, scale) as app:
                    configurations = []
                    path = Path("missing models") / (("long-model-name-" * 12) + ".onnx")
                    app.v2_vittrack_model_path.set(str(path))
                    app.v2_neuflow_model_path.set(str(path))

                    def prepare(dialog, panel):
                        dialog.geometry("460x400")
                        dialog.bind("<Configure>", lambda event: configurations.append(event), add="+")
                        for model in ("vittrack", "neuflow"):
                            check = panel.model_controls[model][0]
                            # A long existing preference must not obscure the
                            # setup buttons or make geometry resize endlessly.
                            check.invoke()

                    def inspect(dialog, panel, ticks):
                        self.assertGreaterEqual(len(ticks), 3)
                        self.assertLess(len(configurations), 250, "Configure events failed to settle")
                        scroll = next(w for w in descendants(dialog) if isinstance(w, _StartDialogSidebar))
                        self.assertGreaterEqual(scroll.content.winfo_width(), scroll.content.winfo_reqwidth())
                        for button in (self.action(app, dialog, "取消"), self.action(app, dialog, "确认开始")):
                            self.assert_visible(button, dialog)
                        for model in ("vittrack", "neuflow"):
                            check, choose, download, _label = panel.model_controls[model]
                            self.assertTrue(int(app.getvar(str(check.cget("variable")))))
                            for button in (choose, download):
                                # Exercise focus routing without stealing the
                                # keyboard from a concurrently tested old app.
                                button.event_generate('<FocusIn>')
                                app.update()
                                self.assert_visible(button, scroll.canvas)
                        combo = next(w for w in descendants(dialog) if isinstance(w, ttk.Combobox))
                        combo.event_generate('<FocusIn>')
                        app.update()
                        before = combo.get()
                        scroll.canvas.yview_moveto(0)
                        combo.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
                        app.update()
                        self.assertEqual(combo.get(), before)
                        self.assertGreater(scroll.canvas.yview()[0], 0)
                        self.action(app, dialog, "取消").invoke()

                    self.assertFalse(self.modal(app, prepare, inspect))
                    self.assertFalse(app.v2_vittrack_enabled.get())
                    self.assertFalse(app.v2_neuflow_enabled.get())

    def test_confirmation_applies_both_staged_switches_after_event_loop_turns(self):
        with self.window() as app:
            def prepare(_dialog, panel):
                for model in ("vittrack", "neuflow"):
                    panel.model_controls[model][0].invoke()

            def inspect(dialog, _panel, _ticks):
                self.assertFalse(app.v2_vittrack_enabled.get())
                self.assertFalse(app.v2_neuflow_enabled.get())
                self.action(app, dialog, "确认开始").invoke()

            self.assertTrue(self.modal(app, prepare, inspect))
            self.assertTrue(app.v2_vittrack_enabled.get())
            self.assertTrue(app.v2_neuflow_enabled.get())

    def test_focus_before_resize_reveals_after_horizontal_layout_without_manual_snapback(self):
        with self.window() as app:
            dialog = tk.Toplevel(app)
            dialog.geometry("900x360")
            monitors = screen_monitors()
            monitor = max(monitors, key=lambda item: item["left"])
            move_physical_window(dialog, monitor["left"] + 80, monitor["top"] + 200)
            scroll = _StartDialogSidebar(dialog)
            scroll.pack(fill="both", expand=True)
            ttk.Frame(scroll.content, width=700, height=700).grid(row=0, column=0)
            button = ttk.Button(scroll.content, text="Reach me")
            button.grid(row=1, column=0, sticky="w")
            try:
                app.update()
                self.assertFalse(scroll.horizontal.winfo_ismapped())
                dialog.geometry("420x360")
                # A single focus event deliberately precedes pending resize
                # and scrollbar geometry; do not retry focus until it passes.
                button.event_generate("<FocusIn>")
                app.update()
                self.assertTrue(scroll.horizontal.winfo_ismapped())
                self.assert_visible(button, scroll.canvas)

                previous = scroll.canvas.yview()[0]
                button.event_generate("<MouseWheel>", delta=120, x=5, y=5)
                app.update()
                self.assertIsNone(scroll._focus_target)
                self.assertLess(scroll.canvas.yview()[0], previous)

                button.event_generate("<FocusIn>")
                app.update()
                self.assert_visible(button, scroll.canvas)
                app.tk.call(scroll.vertical.cget("command"), "moveto", 0)
                app.update()
                self.assertIsNone(scroll._focus_target)
                self.assertEqual(scroll.canvas.yview()[0], 0)

                # Footer/outside controls must not pull the viewport back to
                # the formerly focused in-body button during later layouts.
                button.event_generate("<FocusIn>")
                dialog.event_generate("<FocusIn>")
                self.assertIsNone(scroll._focus_target)
                self.assertIsNone(scroll._focus_after)

                button.event_generate("<FocusIn>")
                scroll._layout()
                pending = (scroll._focus_after, scroll._layout_after)
                self.assertTrue(all(pending))
                scroll.destroy()
                remaining = app.tk.splitlist(app.tk.call("after", "info"))
                for token in pending:
                    self.assertNotIn(token, remaining)
                app.update()
            finally:
                dialog.destroy()

    def test_gpu_modal_owns_parent_confirmation_and_cancel_keys(self):
        with self.window() as app:
            def prepare(dialog, panel):
                panel.model_controls["neuflow"][0].invoke()
                gpu_button = getattr(panel, "gpu_button", None)
                if gpu_button is None:
                    gpu_button = next(w for w in panel.winfo_children()
                                      if isinstance(w, ttk.Button) and "GPU" in w.cget("text"))
                gpu_button.invoke()
                self.assertIs(app.grab_current(), app._v2_gpu_dialog)

            def inspect(dialog, _panel, _ticks):
                gpu = app._v2_gpu_dialog
                self.assertIs(app.grab_current(), gpu)
                self.action(app, dialog, "确认开始").invoke()
                self.action(app, dialog, "取消").invoke()
                dialog.event_generate("<Return>")
                dialog.event_generate("<Escape>")
                app.update()
                self.assertTrue(dialog.winfo_exists())
                self.assertTrue(gpu.winfo_exists())
                self.assertFalse(app.v2_neuflow_enabled.get())
                close = next(w for w in descendants(gpu) if isinstance(w, ttk.Button)
                             and w.cget("text") == app._dt("关闭", "Close"))
                close.invoke()
                self.assertIs(app.grab_current(), dialog)
                self.action(app, dialog, "取消").invoke()

            self.assertFalse(self.modal(app, prepare, inspect))
            self.assertFalse(app.v2_neuflow_enabled.get())
