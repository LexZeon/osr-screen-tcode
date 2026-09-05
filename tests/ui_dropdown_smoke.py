"""Visible native popup check with simulated long audio device names."""
import tkinter as tk
from tkinter import ttk
from osr_screen_tcode.ui_widgets import WideCombobox

root = tk.Tk()
root.title("UI Check - Wide Audio Dropdown")
root.geometry("340x200+400+250")
ttk.Label(root, text="Audio Device").grid(row=0, column=0, padx=8, pady=12)
combo = WideCombobox(root, width=2, values=[
    "System Output - High Definition Audio Device (Loopback)",
    "Default Input - Communications Microphone",
    "18: External USB Audio Interface - Stereo Mix (Loopback)",
])
combo.grid(row=0, column=1)
combo.current(0)
ttk.Button(root, text="Refresh").grid(row=0, column=2, padx=4)
root.after(800, lambda: root.tk.call("ttk::combobox::Post", str(combo)))
root.after(45000, root.destroy)
root.mainloop()
