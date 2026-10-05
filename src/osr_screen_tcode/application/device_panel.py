"""Device connection, manual test and per-axis limit control construction.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
from tkinter import ttk
from ..analyzer import SIX_AXES
from ..ui_widgets import WideCombobox


class DevicePanelMixin:
    def _manual_test_controls(self, parent: ttk.Frame, row: int) -> int:
        ttk.Button(parent, text="居中", command=self.send_center).grid(row=row, column=0, sticky="ew")
        ttk.Button(parent, text="中等测试", command=self.send_small_test).grid(row=row, column=1, columnspan=2, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Button(parent, text="上下全幅测试", command=self.send_full_l0_test).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1
        ttk.Button(parent, text="SR6/OSR6 六轴轻测", command=self.send_six_axis_test).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 8)
        )
        return row + 1

    def _preset_controls(self, parent: ttk.Frame, row: int) -> int:
        ttk.Button(parent, text="安全预设", command=self.apply_safe_preset).grid(row=row, column=0, sticky="ew")
        ttk.Button(parent, text="标准预设", command=self.apply_normal_preset).grid(row=row, column=1, sticky="ew", padx=(4, 0))
        ttk.Button(parent, text="全行程", command=self.apply_full_preset).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Button(parent, text="混合分析灵敏", command=self.apply_hybrid_analysis_preset, style="Primary.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 12)
        )
        return row + 1

    def _connection_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "连接设备", row)
        ttk.Label(parent, textvariable=self.device_status, foreground="#0b6b3a").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4)
        )
        row += 1
        row = self._device_selector_controls(parent, row)
        connection_parent, connection_row = parent, row + 1
        self.native_connection_frame = ttk.Frame(parent)
        self.native_connection_frame.columnconfigure(1, weight=1)
        self.native_connection_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        parent, row = self.native_connection_frame, 0
        ttk.Label(parent, text="输出").grid(row=row, column=0, sticky="w", pady=2)
        self.native_output_combo = WideCombobox(
            parent,
            textvariable=self.sink_type,
            values=("Log only", "Serial COM", "BLE UART"),
            state="readonly",
            width=14,
        )
        self.native_output_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        self.serial_settings_frame = ttk.Frame(parent)
        self.serial_settings_frame.columnconfigure(1, weight=1)
        self.serial_settings_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        parent, row = self.serial_settings_frame, 0
        ttk.Label(parent, text="串口").grid(row=row, column=0, sticky="w", pady=2)
        self.port_combo = WideCombobox(parent, textvariable=self.serial_port, values=(), width=14)
        self.port_combo.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="刷新", command=self.refresh_ports).grid(row=row, column=2, sticky="ew", padx=(4, 0))
        row += 1
        row = self._entry(parent, "波特率", self.baudrate, row)
        ttk.Button(parent, text="自动检测 SR6/OSR6", command=self.autodetect_device).grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        row += 1

        self.ble_settings_frame = ttk.Frame(self.native_connection_frame)
        self.ble_settings_frame.columnconfigure(1, weight=1)
        ble_row = 0
        ttk.Label(self.ble_settings_frame, text="BLE 名称").grid(row=ble_row, column=0, sticky="w", pady=2)
        ttk.Entry(self.ble_settings_frame, textvariable=self.ble_name).grid(row=ble_row, column=1, sticky="ew", pady=2)
        ttk.Button(self.ble_settings_frame, text="扫描", command=self.scan_ble).grid(row=ble_row, column=2, sticky="ew", padx=(4, 0))
        ble_row += 1
        ttk.Label(self.ble_settings_frame, text="BLE 地址").grid(row=ble_row, column=0, sticky="w", pady=2)
        ttk.Entry(self.ble_settings_frame, textvariable=self.ble_address, width=18).grid(row=ble_row, column=1, columnspan=2, sticky="ew", pady=2)
        ble_row += 1
        ttk.Label(self.ble_settings_frame, text="写入 UUID").grid(row=ble_row, column=0, sticky="w", pady=2)
        ttk.Entry(self.ble_settings_frame, textvariable=self.ble_write_uuid, width=18).grid(row=ble_row, column=1, columnspan=2, sticky="ew", pady=2)
        self.ble_settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        parent = connection_parent
        row = connection_row
        self.connect_button = ttk.Button(parent, textvariable=self.connect_button_text, command=self.connect_and_center, style="Primary.TButton")
        self.connect_button.grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )
        ttk.Button(parent, text="断开", command=self.disconnect_sink).grid(row=row, column=2, sticky="ew", padx=(4, 0), pady=(4, 0))
        row += 1
        self.query_axes_button = ttk.Button(parent, text="查询设备轴", command=self.query_device_axes)
        self.query_axes_button.grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        self._refresh_ble_settings()
        self._refresh_device_controls()
        return row + 1

    def _axis_limit_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "六轴独立上下限", row)
        self.measurement_limits_button = ttk.Button(parent, command=self._toggle_measurement_limits)
        self.measurement_limits_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        row += 1
        self.measurement_limits_frame = ttk.Frame(parent)
        self.measurement_limits_frame.columnconfigure(1, weight=1)
        inner_row = 0
        inner_row = self._measurement_controls(self.measurement_limits_frame, inner_row)
        ttk.Label(self.measurement_limits_frame, text="轴").grid(row=inner_row, column=0, sticky="w")
        ttk.Label(self.measurement_limits_frame, text="下限").grid(row=inner_row, column=1, sticky="w")
        ttk.Label(self.measurement_limits_frame, text="上限").grid(row=inner_row, column=2, sticky="w")
        inner_row += 1
        for axis in SIX_AXES:
            line = ttk.Frame(self.measurement_limits_frame)
            line.columnconfigure(1, weight=1)
            line.columnconfigure(3, weight=1)
            ttk.Label(line, text=axis, width=4).grid(row=0, column=0, sticky="w")
            ttk.Scale(
                line,
                from_=0,
                to=9999,
                variable=self.axis_min_vars[axis],
                command=lambda _value, axis_name=axis: self._normalize_axis_limit(axis_name),
            ).grid(row=0, column=1, sticky="ew", padx=(2, 3))
            ttk.Label(line, textvariable=self.axis_min_vars[axis], width=5, anchor="e").grid(row=0, column=2, sticky="e")
            ttk.Scale(
                line,
                from_=0,
                to=9999,
                variable=self.axis_max_vars[axis],
                command=lambda _value, axis_name=axis: self._normalize_axis_limit(axis_name),
            ).grid(row=0, column=3, sticky="ew", padx=(8, 3))
            ttk.Label(line, textvariable=self.axis_max_vars[axis], width=5, anchor="e").grid(row=0, column=4, sticky="e")
            line.grid(row=inner_row, column=0, columnspan=3, sticky="ew", pady=1)
            inner_row += 1
        ttk.Label(
            self.measurement_limits_frame,
            text="实时输出与测试会按每个轴自己的范围映射。滑块交叉时会自动整理。",
            wraplength=300,
            foreground="#555",
        ).grid(row=inner_row, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.measurement_limits_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        self._refresh_measurement_limits()
        row += 1
        row = self._six_axis_tuning_controls(parent, row)
        row = self._rtm_pose_3d_controls(parent, row)
        return row

    def _measurement_controls(self, parent: ttk.Frame, row: int) -> int:
        box = ttk.LabelFrame(parent, text="测量模式", padding=8)
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="轴").grid(row=0, column=0, sticky="w", pady=2)
        axis_combo = WideCombobox(
            box,
            textvariable=self.measure_axis,
            values=SIX_AXES,
            state="readonly",
            width=6,
        )
        axis_combo.grid(row=0, column=1, sticky="ew", pady=2)
        axis_combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_measure_value_from_axis())
        ttk.Checkbutton(box, text="滑动即发送", variable=self.measure_live).grid(row=0, column=2, sticky="e", padx=(6, 0))
        ttk.Label(box, text="位置").grid(row=1, column=0, sticky="w", pady=2)
        measure_scale = ttk.Scale(
            box,
            from_=0,
            to=9999,
            variable=self.measure_value,
            command=lambda _value: self._on_measure_slider(),
        )
        measure_scale.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(box, textvariable=self.measure_value, width=5, anchor="e").grid(row=1, column=2, sticky="e")
        ttk.Button(box, text="发送当前位置", command=self.send_measure_position).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        button_row = ttk.Frame(box)
        button_row.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(button_row, text="保存为下限", command=lambda: self.save_measure_limit("low")).grid(row=0, column=0, sticky="ew")
        ttk.Button(button_row, text="当前轴回中", command=lambda: self.send_measure_position(5000)).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(button_row, text="保存为上限", command=lambda: self.save_measure_limit("high")).grid(row=0, column=2, sticky="ew")
        button_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(
            box,
            text="用于找机械安全范围：先低档、慢慢滑，确认位置后保存上下限。",
            wraplength=270,
            foreground="#555",
        ).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(6, 8))
        return row + 1
