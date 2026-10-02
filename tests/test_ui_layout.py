"""Real Tk geometry checks; no application settings or device access.

Run through tests/run_tests.py with the other GUI checks, not concurrently.
"""
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from osr_screen_tcode.ui_layout import ControlSidebar, MainPanes


class TkLayoutTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.geometry("360x300+50+50")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.callback_errors = []
        self.root.report_callback_exception = lambda *error: self.callback_errors.append(error)

    def tearDown(self):
        try:
            for identifier in self.root.tk.splitlist(self.root.tk.call("after", "info")):
                self.root.after_cancel(identifier)
        finally:
            self.root.destroy()
        self.assertEqual(self.callback_errors, [], "Tk callbacks raised an exception")

    def settle(self):
        self.root.deiconify()
        self.root.update()

    def sidebar(self):
        sidebar = ControlSidebar(self.root)
        sidebar.grid(row=0, column=0, sticky="nsew")
        return sidebar

    def assert_visible(self, widget, canvas):
        self.assertGreaterEqual(widget.winfo_rootx(), canvas.winfo_rootx() - 1)
        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                             canvas.winfo_rootx() + canvas.winfo_width() + 1)
        self.assertGreaterEqual(widget.winfo_rooty(), canvas.winfo_rooty() - 1)
        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                             canvas.winfo_rooty() + canvas.winfo_height() + 1)


class SidebarLayoutTests(TkLayoutTestCase):
    def test_same_height_text_growth_and_shrink_update_overflow_without_window_resize(self):
        sidebar = self.sidebar()
        label = ttk.Label(sidebar.content, text="Short")
        label.grid(row=0, column=0, columnspan=3, sticky="w")
        self.settle()
        initial_height = label.winfo_height()
        initial_viewport = sidebar.canvas.winfo_width()
        self.assertEqual(sidebar.horizontal.winfo_manager(), "")

        label.configure(text="A much longer single-line control description " * 4)
        self.root.update()
        self.assertEqual(label.winfo_height(), initial_height)
        self.assertEqual(sidebar.canvas.winfo_width(), initial_viewport)
        self.assertEqual(sidebar.horizontal.winfo_manager(), "grid")
        self.assertGreaterEqual(sidebar.surface.winfo_width(), label.winfo_reqwidth())
        sidebar.canvas.xview_moveto(1)
        self.root.update()
        self.assertLessEqual(label.winfo_rootx() + label.winfo_width(),
                             sidebar.canvas.winfo_rootx() + sidebar.canvas.winfo_width())

        label.configure(text="Short again")
        self.root.update()
        self.assertEqual(label.winfo_height(), initial_height)
        self.assertEqual(sidebar.horizontal.winfo_manager(), "")
        self.assertEqual(sidebar.canvas.xview(), (0.0, 1.0))
        self.assertLessEqual(abs(sidebar.surface.winfo_width() - sidebar.canvas.winfo_width()), 1)

    def test_narrow_pane_rightmost_control_is_reachable_by_scroll_and_focus(self):
        sidebar = self.sidebar()
        ttk.Frame(sidebar.content, width=850, height=1).grid(row=0, column=0, columnspan=3)
        ttk.Frame(sidebar.content, width=1, height=600).grid(row=1, column=0)
        entry = ttk.Entry(sidebar.content, width=10)
        entry.grid(row=2, column=2, sticky="e")
        self.settle()
        self.assertGreater(entry.winfo_rootx(),
                           sidebar.canvas.winfo_rootx() + sidebar.canvas.winfo_width())
        sidebar.canvas.xview_moveto(1)
        sidebar.canvas.yview_moveto(1)
        self.root.update()
        self.assert_visible(entry, sidebar.canvas)

        sidebar.canvas.xview_moveto(0)
        sidebar.canvas.yview_moveto(0)
        entry.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), entry)
        self.assert_visible(entry, sidebar.canvas)

    def test_wheel_over_combobox_scrolls_both_directions_without_changing_selection(self):
        sidebar = self.sidebar()
        combo = ttk.Combobox(sidebar.content, values=("First", "Second", "Third"),
                             state="readonly", width=12)
        combo.current(1)
        combo.grid(row=0, column=0, sticky="w")
        ttk.Frame(sidebar.content, width=850, height=800).grid(row=1, column=0, columnspan=3)
        self.settle()
        before_y = sidebar.canvas.yview()[0]
        combo.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
        self.root.update()
        self.assertEqual(combo.current(), 1)
        self.assertGreater(sidebar.canvas.yview()[0], before_y)

        sidebar.canvas.yview_moveto(0)
        before_x = sidebar.canvas.xview()[0]
        combo.event_generate("<Shift-MouseWheel>", delta=-120, x=5, y=5)
        self.root.update()
        self.assertEqual(combo.current(), 1)
        self.assertGreater(sidebar.canvas.xview()[0], before_x)

    def test_sidebar_wheel_does_not_intercept_a_separate_dropdown_window(self):
        sidebar = self.sidebar()
        self.settle()
        popup = tk.Toplevel(sidebar)
        combo = ttk.Combobox(popup, values=("First", "Second", "Third"), state="readonly")
        combo.current(1)
        combo.pack()
        self.root.update()
        before = sidebar.canvas.yview()
        combo.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
        self.root.update()
        self.assertEqual(combo.current(), 2)
        self.assertEqual(sidebar.canvas.yview(), before)
        popup.destroy()


class MainPaneLayoutTests(TkLayoutTestCase):
    def setUp(self):
        super().setUp()
        self.root.geometry("1200x700+50+50")
        self.move_patch = patch("osr_screen_tcode.ui_layout.move_physical_window")
        self.move_window = self.move_patch.start()
        self.addCleanup(self.move_patch.stop)

    def panes(self, **options):
        panes = MainPanes(self.root, **options)
        panes.grid(row=0, column=0, sticky="nsew")
        ttk.Label(panes.sidebar.content, text="Controls").grid(row=0, column=0)
        return panes

    def drag_to(self, panes, position):
        start = panes.sash_coord(0)[0]
        pointer = start + max(1, int(panes.cget("sashwidth")) // 2)
        panes.event_generate("<ButtonPress-1>", x=pointer, y=40)
        panes.event_generate("<B1-Motion>", x=position + pointer - start, y=40)
        panes.event_generate("<ButtonRelease-1>", x=position + pointer - start, y=40)
        self.root.update()

    def test_minimum_width_drag_at_200_percent_saves_and_restores(self):
        self.root.tk.call("tk", "scaling", 192 / 72)
        changed = Mock()
        panes = self.panes(on_width_changed=changed)
        self.settle()
        # Move away from the minimum before checking a real native sash drag.
        self.drag_to(panes, 450)
        changed.reset_mock()
        self.drag_to(panes, 50)
        actual = panes.sash_coord(0)[0]
        saved = panes.preferred_width
        changed.assert_called_once_with()
        self.assertGreaterEqual(actual, 220)
        self.assertLess(saved, 160, "This reproduces the rejected high-DPI saved-width range")
        self.assertAlmostEqual(saved * panes.scale, actual, delta=1)
        panes.destroy()

        restored = self.panes(saved_width=saved)
        restored.fit_initial_window()
        self.root.update()
        self.assertAlmostEqual(restored.preferred_width, saved)
        self.assertAlmostEqual(restored.sash_coord(0)[0], actual, delta=1)

    def test_user_width_survives_resize_and_expanded_content_then_reset_fits(self):
        changed = Mock()
        panes = self.panes(on_width_changed=changed)
        label = ttk.Label(panes.sidebar.content, text="Short")
        label.grid(row=1, column=0, columnspan=3, sticky="w")
        self.settle()
        self.drag_to(panes, 400)
        chosen = panes.sash_coord(0)[0]
        saved = panes.preferred_width
        changed.reset_mock()

        self.root.geometry("1450x750+50+50")
        self.root.update()
        self.assertEqual(panes.sash_coord(0)[0], chosen)
        label.configure(text="Expanded controls need more horizontal space " * 4)
        self.root.update()
        self.assertEqual(panes.sash_coord(0)[0], chosen)
        self.assertEqual(panes.sidebar.horizontal.winfo_manager(), "grid")
        self.root.geometry("900x600+50+50")
        self.root.update()
        self.assertEqual(panes.sash_coord(0)[0], chosen)
        self.assertEqual(panes.preferred_width, saved)
        changed.assert_not_called()

        label.configure(text="Short")
        panes.reset_width()
        self.root.update()
        self.assertIsNone(panes.preferred_width)
        self.assertEqual(panes.sidebar.horizontal.winfo_manager(), "")

    def test_scaled_initial_fit_uses_final_mapped_size_and_monitor_bounds(self):
        self.root.tk.call("tk", "scaling", 192 / 72)
        self.root.geometry("640x420+50+50")
        panes = self.panes()
        ttk.Frame(panes.sidebar.content, width=700, height=40).grid(row=1, column=0, columnspan=3)
        with patch("osr_screen_tcode.ui_layout.monitor_workarea", return_value=(0, 0, 1800, 1100)):
            panes.fit_initial_window()
            self.settle()
        # Windows can adjust non-client margins during a mixed-DPI monitor
        # transition. The client must fit inside the cap, not equal it exactly.
        self.assertGreater(self.root.winfo_width(), 1700)
        self.assertLessEqual(self.root.winfo_width(), 1768)
        self.assertLessEqual(self.root.winfo_height(), 1020)
        self.assertGreater(panes.sash_coord(0)[0], 640)
        self.assertGreaterEqual(panes.sidebar.canvas.winfo_width(), panes.sidebar.content.winfo_reqwidth())
        self.assertEqual(panes.sidebar.horizontal.winfo_manager(), "")
        self.move_window.assert_called()
        root, x, y = self.move_window.call_args.args
        self.assertIs(root, self.root)
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + root.winfo_width(), 1800)
        self.assertLessEqual(y + root.winfo_height(), 1100)
