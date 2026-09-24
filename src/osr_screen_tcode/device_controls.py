"""Generic SR6/OSR6 TCode transport UI, without commercial-device adapters."""
from tkinter import ttk


class DeviceControls:
    def _dt(self, zh: str, en: str) -> str:
        return zh if self.ui_language == "zh" else en

    def _refresh_device_controls(self) -> None:
        if hasattr(self, "query_axes_button"):
            if self.sink_type.get() in ("Serial COM", "USB Serial"):
                self.query_axes_button.grid()
            else:
                self.query_axes_button.grid_remove()

    def _set_device_controls_busy(self, busy: bool) -> None:
        widget = getattr(self, "native_output_combo", None)
        if widget is not None:
            widget.configure(state="disabled" if busy else "readonly")

    def _device_selector_controls(self, parent, row: int) -> int:
        ttk.Label(parent, text=self._dt("SR6/OSR6 TCode（机械臂兼容性未验证）",
                                       "SR6/OSR6 TCode (robot arm unverified)"),
                  wraplength=300).grid(row=row, column=0, columnspan=3, sticky="ew", pady=3)
        return row + 1
