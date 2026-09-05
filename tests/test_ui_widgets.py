import tkinter as tk
from tkinter import font
import unittest
from unittest.mock import patch

from osr_screen_tcode.ui_widgets import WideCombobox, popup_horizontal_bounds


class DropdownTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("420x200+50+50")
        self.addCleanup(self.root.destroy)

    def post(self, combo):
        self.root.update()
        self.root.tk.call("ttk::combobox::Post", str(combo))
        self.root.update()
        return str(self.root.tk.call("ttk::combobox::PopdownWindow", str(combo)))

    def test_narrow_input_opens_full_width_without_resizing_input(self):
        name = "System Output - High Definition Audio Device (Loopback)"
        combo = WideCombobox(self.root, values=[name, "Default"], width=2)
        combo.pack()
        self.root.update()
        before = combo.winfo_width()
        popup = self.post(combo)
        popup_font = font.Font(root=self.root, font=self.root.tk.call(popup + ".f.l", "cget", "-font"))
        self.assertGreater(int(self.root.tk.call("winfo", "width", popup)), popup_font.measure(name))
        self.assertEqual(before, combo.winfo_width())
        self.assertEqual(self.root.tk.call("winfo", "manager", popup + ".f.horizontal"), "")

    def test_oversized_option_scrolls_inside_monitor(self):
        combo = WideCombobox(self.root, values=["Long device " * 100], width=2)
        combo.pack()
        with patch("osr_screen_tcode.ui_widgets.monitor_workarea", return_value=(0, 0, 420, 400)):
            popup = self.post(combo)
        self.assertEqual(int(self.root.tk.call("winfo", "width", popup)), 420)
        self.assertEqual(self.root.tk.call("winfo", "manager", popup + ".f.horizontal"), "grid")
        self.root.tk.call(popup + ".f.l", "xview", "moveto", 1)
        self.assertGreater(float(self.root.tk.call(popup + ".f.l", "xview")[0]), 0)

    def test_dynamic_options_large_font_and_native_keyboard_selection(self):
        combo = WideCombobox(self.root, width=2, state="readonly", postcommand=lambda: combo.configure(values=["Refreshed", "Long option " * 6]))
        combo.pack()
        popup = str(self.root.tk.call("ttk::combobox::PopdownWindow", str(combo)))
        self.root.tk.call(popup + ".f.l", "configure", "-font", ("Segoe UI", 20))
        self.post(combo)
        self.root.tk.call("event", "generate", popup + ".f.l", "<KeyPress-Down>")
        self.root.tk.call("event", "generate", popup + ".f.l", "<KeyPress-Return>")
        self.root.update()
        self.assertEqual(combo.current(), 1)

    def test_right_edge_and_negative_monitor_coordinates(self):
        self.assertEqual(popup_horizontal_bounds(1800, 600, 0, 1920), (1320, 600))
        self.assertEqual(popup_horizontal_bounds(-200, 600, -1920, 0), (-600, 600))
        self.assertEqual(popup_horizontal_bounds(-1900, 3000, -1920, 0), (-1920, 1920))
