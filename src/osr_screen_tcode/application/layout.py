"""Main window layout, shared widgets, disclosure groups and preview visibility.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import font as tkfont, ttk
from .. import APP_NAME, __version__
from ..integrated_preview import IntegratedPreview
from ..ui_layout import MainPanes
from .translations import UI_TEXT_REVERSE_EN
from .tooltips import TOOLTIPS, TOOLTIPS_EN, Tooltip


class LayoutMixin:
    def _build_ui(self) -> None:
        self._configure_style()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(12, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        product_label = ttk.Label(header, text=f"{APP_NAME}  v{__version__}", wraplength=900)
        product_label.grid(row=0, column=0, sticky="ew")
        header.bind("<Configure>", lambda event: product_label.configure(wraplength=max(240, event.width - 24)))
        ttk.Label(header, text=self._dt("合作与侵权联系：aivnailedeng@gmail.com", "Cooperation / copyright: aivnailedeng@gmail.com")).grid(row=1, column=0, sticky="w")
        ttk.Label(header, text=self._dt("机械臂模拟测试；实际硬件映射尚未验证。",
                                       "Robot-arm simulation test; physical hardware mapping is unverified.")).grid(row=2, column=0, sticky="w")

        self.main_panes = MainPanes(self, self.config_model.extra.get("sidebar_width_dip"),
                                    on_width_changed=self._schedule_config_save)
        self.main_panes.grid(row=1, column=0, sticky="nsew")
        sidebar = self.main_panes.sidebar.content
        layout_hint = ttk.Label(sidebar, text=self._dt("控制区 · 拖动右侧分隔栏 ↔", "Controls · drag divider ↔"), foreground="#555")
        layout_hint.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        Tooltip(layout_hint, self._dt(
            "拖动分隔栏调整控制区宽度；栏宽自动保存。较窄时可用底部横向滚动条或 Shift＋滚轮。恢复默认设置会重置栏宽。",
            "Drag the divider to resize controls; width is saved. In a narrow pane, use the bottom scrollbar or Shift+wheel. Reset defaults also resets the width."))
        preview = self.main_panes.preview
        preview.rowconfigure(0, weight=1)
        preview.columnconfigure(0, weight=1)
        self.preview_tabs = ttk.Notebook(preview)
        self.preview_tabs.grid(row=0, column=0, sticky="nsew")
        self.analysis_tab = ttk.Frame(self.preview_tabs)
        self.analysis_tab.columnconfigure(0, weight=1)
        self.analysis_tab.rowconfigure(0, weight=1)
        self.output_tab = ttk.Frame(self.preview_tabs)
        self.output_tab.columnconfigure(0, weight=1)
        self.preview_tabs.add(self.analysis_tab, text=self._dt("分析预览", "Analysis Preview"))
        self.preview_tabs.add(self.output_tab, text=self._dt("输出监视", "Output Monitor"))
        self.preview_tabs.select(self.output_tab)

        monitor = ttk.Frame(self.output_tab, padding=10)
        monitor.grid(row=0, column=0, sticky="ew")
        monitor.columnconfigure(0, weight=0)
        monitor.columnconfigure(1, weight=1)
        monitor.columnconfigure(2, weight=0)
        preset_bar = ttk.Frame(monitor)
        preset_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        preset_bar.columnconfigure(6, weight=1)
        ttk.Label(preset_bar, text="五档预设", font=("", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.preset_buttons: dict[int, ttk.Button] = {}
        for level in range(1, 6):
            button = ttk.Button(preset_bar, text=str(level), width=4, command=lambda selected=level: self.apply_play_preset(selected))
            button.grid(row=0, column=level, sticky="w", padx=(0, 4))
            self.preset_buttons[level] = button
        ttk.Label(preset_bar, text="仅调整最终输出幅度", foreground="#555").grid(row=0, column=6, sticky="w", padx=(4, 0))

        ui_scale = self.main_panes.scale
        label_font = tkfont.nametofont("TkDefaultFont", root=self)
        stroke_width = max(round(72 * ui_scale), max(label_font.measure(self._t(text)) for text in ("上限方向", "下限方向")) + 12)
        self.stroke_canvas = tk.Canvas(monitor, width=stroke_width, height=round(176 * ui_scale), highlightthickness=0, background="#f4f4f4")
        self.stroke_canvas.grid(row=1, column=0, rowspan=4, sticky="nsw", padx=(0, 12))
        ttk.Label(monitor, textvariable=self.l0_status, font=("", 30, "bold")).grid(row=1, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.stroke_status, font=("", 15, "bold"), foreground="#0b6b3a").grid(row=2, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.range_status, font=("", 12)).grid(row=3, column=1, sticky="w")
        ttk.Label(monitor, textvariable=self.activity, font=("", 12)).grid(row=4, column=1, sticky="w")
        ttk.Button(monitor, text="急停回中", command=self.estop, style="Danger.TButton").grid(row=1, column=2, sticky="ew")
        ttk.Button(monitor, text="全行程", command=self.apply_full_preset, style="Primary.TButton").grid(row=2, column=2, sticky="ew", pady=4)
        self.monitor_connect_button = ttk.Button(monitor, textvariable=self.connect_button_text, command=self.connect_and_center)
        self.monitor_connect_button.grid(row=3, column=2, sticky="ew")
        self.axis_canvas = tk.Canvas(monitor, width=520, height=round(136 * ui_scale), highlightthickness=0, background="#f8f8f8")
        self.axis_canvas.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.axis_canvas.bind("<Configure>", lambda _event: self._draw_axis_monitor(self._last_axis_values))
        self.curve_canvas = tk.Canvas(monitor, width=520, height=round(150 * ui_scale), highlightthickness=0, background="#101418")
        self.curve_canvas.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.curve_canvas.bind("<Configure>", lambda _event: self._draw_script_curve())

        self.integrated_preview = IntegratedPreview(self.analysis_tab, self)
        self.integrated_preview.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas = self.integrated_preview.canvas
        stats = ttk.Frame(preview)
        stats.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        stats.columnconfigure((0, 1, 2), weight=1)
        ttk.Label(stats, textvariable=self.device_status).grid(row=0, column=0, sticky="w")
        ttk.Label(stats, textvariable=self.output_value, anchor="center").grid(row=0, column=1, sticky="ew")
        ttk.Label(stats, textvariable=self.record_status, anchor="e").grid(row=0, column=2, sticky="e")
        ttk.Label(preview, textvariable=self.status, foreground="#555").grid(row=3, column=0, sticky="ew", pady=(4, 0))

        row = 1
        row = self._connection_controls(sidebar, row)
        row = self._quick_controls(sidebar, row)
        row = self._axis_limit_controls(sidebar, row)
        row = self._more_settings_controls(sidebar, row)
        ttk.Label(
            sidebar,
            text="实时输出由下限/上限滑块决定。想要更大更快，点全行程。",
            wraplength=300,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._refresh_limit_text()
        self._refresh_play_preset_buttons()
        self._refresh_six_axis_sensitivity_buttons()
        self._draw_stroke_monitor(5000)
        self._draw_axis_monitor(self._last_axis_values)
        self._draw_script_curve()
        self._install_tooltips(self)
        self._localize_widget_tree(self)
        self.main_panes.fit_initial_window()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Primary.TButton", font=("", 10, "bold"))
        style.configure("Danger.TButton", font=("", 10, "bold"))
        style.configure("PresetActive.TButton", font=("", 10, "bold"))

    def _section(self, parent: ttk.Frame, title: str, row: int) -> int:
        ttk.Label(parent, text=title, font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0 if row == 0 else 14, 6)
        )
        return row + 1

    def _entry(self, parent: ttk.Frame, label: str, var: tk.Variable, row: int, width: int = 8) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        return row + 1

    def _slider(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.Variable,
        row: int,
        from_: float,
        to: float,
        value_text: tk.StringVar | None = None,
    ) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=from_, to=to, variable=var, command=lambda _value: self._refresh_limit_text()).grid(
            row=row, column=1, sticky="ew", pady=2
        )
        if value_text is not None:
            ttk.Label(parent, textvariable=value_text, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        else:
            ttk.Label(parent, textvariable=var, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        return row + 1

    def _more_settings_controls(self, parent: ttk.Frame, row: int) -> int:
        self.more_settings_button = ttk.Button(parent, command=self._toggle_more_settings)
        self.more_settings_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        row += 1
        self.more_settings_frame = ttk.Frame(parent)
        self.more_settings_frame.columnconfigure(1, weight=1)
        inner_row = 0
        inner_row = self._manual_test_controls(self.more_settings_frame, inner_row)
        inner_row = self._preset_controls(self.more_settings_frame, inner_row)
        inner_row = self._source_controls(self.more_settings_frame, inner_row)
        inner_row = self._audio_controls(self.more_settings_frame, inner_row)
        inner_row = self._region_controls(self.more_settings_frame, inner_row)
        inner_row = self._tracking_controls(self.more_settings_frame, inner_row)
        self._refresh_more_settings()
        return row + 1

    def _toggle_more_settings(self) -> None:
        self.show_more_settings.set(not self.show_more_settings.get())
        self._refresh_more_settings()

    def _refresh_more_settings(self) -> None:
        if not hasattr(self, "more_settings_button") or not hasattr(self, "more_settings_frame"):
            return
        expanded = self.show_more_settings.get()
        self.more_settings_button.configure(text=self._t("收起更多设置" if expanded else "展开更多设置"))
        if expanded:
            self.more_settings_frame.grid(row=int(self.more_settings_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew")
            self._refresh_ble_settings()
            self._refresh_measurement_limits()
            self._refresh_six_axis_tuning()
            self._refresh_rtm_pose_3d_settings()
        else:
            self.more_settings_frame.grid_remove()

    def _toggle_measurement_limits(self) -> None:
        self.show_measurement_limits.set(not self.show_measurement_limits.get())
        self._refresh_measurement_limits()

    def _refresh_measurement_limits(self) -> None:
        if not hasattr(self, "measurement_limits_button") or not hasattr(self, "measurement_limits_frame"):
            return
        expanded = self.show_measurement_limits.get()
        self.measurement_limits_button.configure(text=self._t("收起测量模式和轴上下限" if expanded else "展开测量模式和轴上下限"))
        if expanded:
            self.measurement_limits_frame.grid(row=int(self.measurement_limits_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew")
        else:
            self.measurement_limits_frame.grid_remove()

    def _toggle_six_axis_tuning(self) -> None:
        self.show_six_axis_tuning.set(not self.show_six_axis_tuning.get())
        self._refresh_six_axis_tuning()

    def _refresh_six_axis_tuning(self) -> None:
        if not hasattr(self, "six_axis_tuning_button") or not hasattr(self, "six_axis_tuning_frame"):
            return
        expanded = self.show_six_axis_tuning.get()
        self.six_axis_tuning_button.configure(text=self._t("收起六轴辅助调节（仅混合分析）" if expanded else "展开六轴辅助调节（仅混合分析）"))
        if expanded:
            self.six_axis_tuning_frame.grid(row=int(self.six_axis_tuning_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        else:
            self.six_axis_tuning_frame.grid_remove()

    def _toggle_rtm_pose_3d_settings(self) -> None:
        self.show_rtm_pose_3d_settings.set(not self.show_rtm_pose_3d_settings.get())
        self._refresh_rtm_pose_3d_settings()

    def _refresh_rtm_pose_3d_settings(self) -> None:
        if not hasattr(self, "rtm_pose_3d_settings_button") or not hasattr(self, "rtm_pose_3d_settings_frame"):
            return
        if not self._pose_model_required():
            self.rtm_pose_3d_settings_button.grid_remove()
            self.rtm_pose_3d_settings_frame.grid_remove()
            return
        self.rtm_pose_3d_settings_button.grid()
        expanded = self.show_rtm_pose_3d_settings.get()
        self.rtm_pose_3d_settings_button.configure(text=self._t("收起 RTM Pose 模型设置" if expanded else "展开 RTM Pose 模型设置"))
        if expanded:
            self.rtm_pose_3d_settings_frame.grid(row=int(self.rtm_pose_3d_settings_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        else:
            self.rtm_pose_3d_settings_frame.grid_remove()

    def _toggle_six_axis_travel_scales(self) -> None:
        self.show_six_axis_travel_scales.set(not self.show_six_axis_travel_scales.get())
        self._refresh_six_axis_travel_scales()

    def _refresh_six_axis_travel_scales(self) -> None:
        if not hasattr(self, "six_axis_travel_button") or not hasattr(self, "six_axis_travel_frame"):
            return
        expanded = self.show_six_axis_travel_scales.get()
        self.six_axis_travel_button.configure(text=self._t("收起六轴单轴行程倍率" if expanded else "展开六轴单轴行程倍率"))
        if expanded:
            self.six_axis_travel_frame.grid(row=int(self.six_axis_travel_button.grid_info()["row"]) + 1, column=0, columnspan=3, sticky="ew")
        else:
            self.six_axis_travel_frame.grid_remove()

    def _refresh_ble_settings(self) -> None:
        if not hasattr(self, "ble_settings_frame"):
            return
        if self.sink_type.get() == "BLE UART":
            self.ble_settings_frame.grid()
        else:
            self.ble_settings_frame.grid_remove()
        if hasattr(self, "serial_settings_frame"):
            if self.sink_type.get() in ("Serial COM", "USB Serial"):
                self.serial_settings_frame.grid()
            else:
                self.serial_settings_frame.grid_remove()

    def _on_native_output_changed(self, *_args) -> None:
        if not hasattr(self, "native_connection_frame"):
            return
        if self.connected or self._connecting:
            self.stop()
            self.disconnect_sink()
        self._refresh_ble_settings()
        self._refresh_device_controls()

    def _install_tooltips(self, widget: tk.Widget) -> None:
        try:
            text = str(widget.cget("text")).strip()
        except tk.TclError:
            text = ""
        tooltip_key = UI_TEXT_REVERSE_EN.get(text, text)
        tooltip_text = self._tooltip_text(tooltip_key)
        if tooltip_text:
            Tooltip(widget, tooltip_text)
        for child in widget.winfo_children():
            self._install_tooltips(child)

    def _tooltip_text(self, key: str) -> str:
        return (TOOLTIPS_EN if self.ui_language == "en" else TOOLTIPS).get(key, "")

    def _localize_widget_tree(self, widget: tk.Widget) -> None:
        if self.ui_language != "en":
            return
        try:
            text = str(widget.cget("text"))
            translated = self._t(text)
            if translated != text:
                widget.configure(text=translated)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._localize_widget_tree(child)

    def _quick_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "实时输出", row)
        row = self._slider(parent, "下限", self.min_value, row, 0, 9999)
        row = self._slider(parent, "上限", self.max_value, row, 0, 9999)
        ttk.Label(parent, text="速度").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=100, to=9999, variable=self.max_step).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=self.max_step, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        row += 1
        ttk.Button(parent, text="恢复所有默认设置", command=self.reset_all_settings).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        self.start_button = ttk.Button(parent, textvariable=self.start_button_text, command=self.start)
        self.start_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        row += 1
        self.preview_button = ttk.Button(parent, text="显示预览", command=self.toggle_preview)
        self.preview_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        row += 1
        ttk.Button(parent, text="停止", command=self.stop).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        row += 1
        ttk.Button(parent, text="急停回中", command=self.estop, style="Danger.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="开始录制", command=self.start_recording).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(parent, text="保存脚本", command=self.save_recording).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(8, 0))
        row += 1
        row = self._travel_slider(parent, "L0 总行程倍率", self.l0_travel_scale, self.l0_travel_slider, self.l0_travel_text, row, self.invert)
        row = self._travel_slider(
            parent,
            "六轴总行程倍率",
            self.global_travel_scale,
            self.global_travel_slider,
            self.global_travel_text,
            row,
            self.six_axis_travel_invert,
        )
        self.six_axis_travel_button = ttk.Button(parent, command=self._toggle_six_axis_travel_scales)
        self.six_axis_travel_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        row += 1
        self.six_axis_travel_frame = ttk.Frame(parent)
        self.six_axis_travel_frame.columnconfigure(1, weight=1)
        inner_row = 0
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            inner_row = self._travel_slider(
                self.six_axis_travel_frame,
                f"{axis} 行程倍率",
                self.six_axis_travel_scale_vars[axis],
                self.six_axis_travel_slider_vars[axis],
                self.six_axis_travel_text_vars[axis],
                inner_row,
                self.axis_output_invert_vars[axis],
            )
        self.six_axis_travel_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        self._refresh_six_axis_travel_scales()
        row += 1
        return row + 1

    def toggle_preview(self) -> None:
        try:
            self.preview_bridge.set_device_context("SR6/OSR6", False, self.ui_language)
            self.preview_bridge.start()
            self.preview_bridge.open_window()
            self.status.set(self._dt("3D 模拟器已打开，显示最终输出指令", "3D simulator opened; showing final output commands"))
        except Exception as exc:
            self.status.set(self._dt("无法打开 3D 模拟器：", "Cannot open 3D simulator: ") + str(exc))
