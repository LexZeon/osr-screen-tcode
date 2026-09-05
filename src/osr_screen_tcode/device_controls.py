"""Main-window controls for the experimental multi-device output backend."""
from __future__ import annotations

import asyncio
import json
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from .config import AXES
from .ui_widgets import WideCombobox

from .device_backends import (
    DEFAULT_INTIFACE_URL, DEVICE_FAMILIES, NATIVE_FAMILIES,
    IntifaceSink, discover_devices,
)


class DeviceControls:
    def _dt(self, zh: str, en: str) -> str:
        return zh if self.ui_language == "zh" else en

    def _build_device_vars(self) -> None:
        cfg = self.config_model
        family = cfg.device_family if cfg.device_family in DEVICE_FAMILIES else "tcode"
        self._device_family_labels = {**DEVICE_FAMILIES, "custom": self._dt("自定义（Intiface）", "Custom (Intiface)")}
        self.device_family = tk.StringVar(value=self._device_family_labels[family])
        self.intiface_url = tk.StringVar(value=cfg.intiface_url)
        # Device indexes are session-local and are deliberately not restored from disk.
        self.external_device = tk.StringVar()
        self.external_feature = tk.StringVar()
        self.external_axis = tk.StringVar(value=cfg.external_axis)
        self.external_limit = tk.DoubleVar(value=cfg.external_limit)
        self.external_limit_text = tk.StringVar()
        self.external_status = tk.StringVar()
        self.custom_bindings = {axis: tk.StringVar(value=self._unbound_label()) for axis in AXES}
        self._updating_custom_bindings = False
        self._external_devices = {}
        self._external_features = {}
        self._device_scan_generation = 0
        self._device_scanning = False
        self.device_family.trace_add("write", self._on_device_family_changed)
        self.intiface_url.trace_add("write", self._on_external_server_changed)
        for variable in (self.external_feature, self.external_axis, self.external_limit):
            variable.trace_add("write", self._on_external_mapping_changed)
        for variable in self.custom_bindings.values():
            variable.trace_add("write", self._on_custom_mapping_changed)
        self.external_limit.trace_add("write", lambda *_: self.external_limit_text.set(f"{self.external_limit.get():.0f}%"))
        self.external_limit_text.set(f"{cfg.external_limit:.0f}%")

    def _family_id(self) -> str:
        return next((key for key, label in self._device_family_labels.items() if label == self.device_family.get()), "tcode")

    def _unbound_label(self) -> str:
        return self._dt("不绑定", "Unbound")

    def _device_config_variables(self) -> list[tk.Variable]:
        return [self.device_family, self.intiface_url, self.external_axis, self.external_limit, *self.custom_bindings.values()]

    def _save_device_config(self) -> None:
        cfg = self.config_model
        cfg.device_family = self._family_id()
        cfg.intiface_url = self.intiface_url.get().strip()
        cfg.external_axis = self.external_axis.get()
        cfg.external_limit = max(0, min(100, float(self.external_limit.get())))
        device = self._external_devices.get(self.external_device.get())
        if cfg.device_family == "custom" and device and not self._updating_custom_bindings:
            cfg.custom_binding_signature = self._custom_signature(device)
            cfg.custom_bindings = self._custom_binding_keys()

    def _reset_device_config(self) -> None:
        self.config_model.custom_bindings = {}
        self.config_model.custom_binding_signature = ""
        self.device_family.set(DEVICE_FAMILIES["tcode"])
        self.intiface_url.set(DEFAULT_INTIFACE_URL)
        self.external_axis.set("L0")
        self.external_limit.set(20)
        self._clear_external_selection()

    def _device_selector_controls(self, parent, row: int) -> int:
        ttk.Label(parent, text=self._dt("设备类型", "Device type")).grid(row=row, column=0, sticky="w")
        self.device_family_combo = WideCombobox(parent, textvariable=self.device_family,
                                               values=list(self._device_family_labels.values()), state="readonly", width=20)
        self.device_family_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        return row + 1

    def _external_device_controls(self, parent, row: int) -> int:
        frame = self.external_device_frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=3)
        ttk.Label(frame, text="Intiface").grid(row=0, column=0, sticky="w")
        self.intiface_entry = ttk.Entry(frame, textvariable=self.intiface_url, width=18)
        self.intiface_entry.grid(row=0, column=1, columnspan=2, sticky="ew")
        self.device_scan_button = ttk.Button(frame, text=self._dt("扫描/刷新设备", "Scan / Refresh Devices"), command=self._scan_external_devices)
        self.device_scan_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(frame, text=self._dt("下载 Intiface", "Get Intiface"), command=lambda: webbrowser.open("https://intiface.com/")).grid(row=1, column=2, sticky="ew", padx=(4, 0))
        ttk.Label(frame, text=self._dt("选择设备", "Select device")).grid(row=2, column=0, sticky="w")
        self.external_device_combo = WideCombobox(frame, textvariable=self.external_device, state="readonly", width=18)
        self.external_device_combo.grid(row=2, column=1, columnspan=2, sticky="ew", pady=3)
        self.external_device_combo.bind("<<ComboboxSelected>>", self._on_external_device_selected)
        single = self.external_single_mapping_frame = ttk.Frame(frame)
        single.columnconfigure(1, weight=1)
        single.grid(row=3, column=0, columnspan=3, sticky="ew")
        ttk.Label(single, text=self._dt("控制功能", "Device function")).grid(row=0, column=0, sticky="w")
        self.external_feature_combo = WideCombobox(single, textvariable=self.external_feature, state="readonly", width=18)
        self.external_feature_combo.grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(single, text=self._dt("跟随轴", "Follow axis")).grid(row=1, column=0, sticky="w")
        self.external_axis_combo = WideCombobox(single, textvariable=self.external_axis, state="readonly",
                                               values=("L0", "L1", "L2", "R0", "R1", "R2"), width=6)
        self.external_axis_combo.grid(row=1, column=1, sticky="ew", pady=3)
        custom = self.custom_mapping_frame = ttk.Frame(frame)
        custom.columnconfigure(1, weight=1)
        custom.grid(row=4, column=0, columnspan=3, sticky="ew")
        ttk.Label(custom, text=self._dt("自定义交互绑定", "Custom Interaction Bindings")).grid(row=0, column=0, columnspan=2, sticky="w")
        self.custom_binding_combos = {}
        for row_index, axis in enumerate(AXES, 1):
            ttk.Label(custom, text=axis, width=4).grid(row=row_index, column=0, sticky="w")
            combo = WideCombobox(custom, textvariable=self.custom_bindings[axis], state="readonly", width=18,
                                 values=(self._unbound_label(),))
            combo.grid(row=row_index, column=1, sticky="ew", pady=2)
            self.custom_binding_combos[axis] = combo
        ttk.Label(frame, text=self._dt("速度/强度上限", "Speed / Level Cap")).grid(row=5, column=0, sticky="w")
        self.external_limit_slider = ttk.Scale(frame, from_=0, to=100, variable=self.external_limit)
        self.external_limit_slider.grid(row=5, column=1, sticky="ew", pady=3)
        ttk.Label(frame, textvariable=self.external_limit_text, width=5, anchor="e").grid(row=5, column=2, sticky="e")
        self.external_mapping_hint = ttk.Label(frame, wraplength=300, foreground="#555")
        self.external_mapping_hint.grid(row=6, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(frame, textvariable=self.external_status, wraplength=300, foreground="#975000").grid(row=7, column=0, columnspan=3, sticky="ew", pady=3)
        self.external_pending_label = ttk.Label(parent,
            text=self._dt("Autoblow：已核对官方云端 API；实时限频和停止行为仍需验证，本测试暂不发送设备指令。",
                          "Autoblow: official cloud API reviewed. Rate limits and stopping require further validation; device output is not enabled in this test."),
            wraplength=300, foreground="#975000")
        self.external_pending_label.grid(row=row + 1, column=0, columnspan=3, sticky="ew", pady=3)
        self.ossm_hint = ttk.Label(parent,
            text=self._dt("OSSM 仅适用于支持 TCode 的固件。原厂固件不保证支持。", "OSSM requires TCode-capable firmware; stock firmware is not guaranteed to work."),
            wraplength=300, foreground="#975000")
        self.ossm_hint.grid(row=row + 2, column=0, columnspan=3, sticky="ew", pady=3)
        self.preview_shape_hint = ttk.Label(parent, wraplength=300, foreground="#555")
        self.preview_shape_hint.grid(row=row + 3, column=0, columnspan=3, sticky="ew", pady=3)
        self._refresh_device_controls()
        return row + 4

    def _clear_external_selection(self) -> None:
        self._device_scan_generation += 1
        self._device_scanning = False
        self._external_devices.clear()
        self._external_features.clear()
        self.external_device.set("")
        self.external_feature.set("")
        self._set_custom_binding_values({})
        if hasattr(self, "external_device_combo"):
            self.external_device_combo.configure(values=())
            self.external_feature_combo.configure(values=())
            for combo in self.custom_binding_combos.values():
                combo.configure(values=(self._unbound_label(),))

    def _custom_signature(self, device) -> str:
        return json.dumps({"url": self.intiface_url.get().strip(), "identity": device.identity,
                           "features": [(f.key, f.description) for f in device.features]}, sort_keys=True)

    def _custom_binding_keys(self) -> dict[str, str]:
        return {axis: self._external_features[var.get()].key for axis, var in self.custom_bindings.items()
                if var.get() in self._external_features}

    def _set_custom_binding_values(self, saved: dict[str, str]) -> None:
        self._updating_custom_bindings = True
        try:
            labels = {feature.key: label for label, feature in self._external_features.items()}
            for axis, variable in self.custom_bindings.items():
                variable.set(labels.get(saved.get(axis), self._unbound_label()))
        finally:
            self._updating_custom_bindings = False

    def _on_custom_mapping_changed(self, *_args) -> None:
        if self._updating_custom_bindings or self._family_id() != "custom":
            return
        if isinstance(self.sink, IntifaceSink) or self._connecting:
            self.stop()
            self.disconnect_sink()
        if any(axis != "L0" for axis in self._custom_binding_keys()):
            self.output_mode.set("Six Axis")

    def _on_device_family_changed(self, *_args) -> None:
        if not hasattr(self, "native_connection_frame"):
            return
        self.stop()
        self.disconnect_sink()
        self._clear_external_selection()
        self._refresh_device_controls()

    def _on_external_server_changed(self, *_args) -> None:
        if not hasattr(self, "external_device_frame"):
            return
        if isinstance(self.sink, IntifaceSink) or self._connecting:
            self.stop()
            self.disconnect_sink()
        self._clear_external_selection()
        self._refresh_device_controls()

    def _refresh_device_controls(self) -> None:
        if not hasattr(self, "external_device_frame"):
            return
        family = self._family_id()
        if hasattr(self, "query_axes_button"):
            self.query_axes_button.grid() if family in NATIVE_FAMILIES and self.sink_type.get() in ("Serial COM", "USB Serial") else self.query_axes_button.grid_remove()
        for widget, visible in ((self.native_connection_frame, family in NATIVE_FAMILIES),
                                (self.external_device_frame, family not in NATIVE_FAMILIES and family != "autoblow"),
                                (self.external_pending_label, family == "autoblow"),
                                (self.ossm_hint, family == "ossm")):
            widget.grid() if visible else widget.grid_remove()
        self.custom_mapping_frame.grid() if family == "custom" else self.custom_mapping_frame.grid_remove()
        self.external_single_mapping_frame.grid_remove() if family == "custom" else self.external_single_mapping_frame.grid()
        self.external_mapping_hint.configure(text=self._dt(
            "每轴可绑定一个设备功能；同一功能不能重复绑定。位置跟随轴位置，振动/旋转强度跟随轴运动速度。",
            "Bind each axis to one device function, without duplicates. Position follows axis position; vibration/rotation level follows motion speed.") if family == "custom" else self._dt(
            "先在 Intiface 中启动服务，再扫描并选择设备。每次只控制所选功能。位置跟随轴位置，振动/旋转强度跟随轴运动速度。",
            "Start Intiface, then scan and select a device. Only the selected function is driven. Position follows axis position; vibration/rotation level follows motion speed."))
        if not self._external_devices and not self._device_scanning:
            self.external_status.set(self._dt("测试适配，尚未经真机验证；兼容型号以 Intiface 扫描结果为准。", "Experimental, not hardware-tested. Compatibility depends on the devices detected by Intiface."))
        self._set_device_controls_busy(self._connecting or bool(self.worker and self.worker.is_alive()))
        if hasattr(self, "connect_button_text") and not self._connecting:
            self.connect_button_text.set(self._t("连接并回中") if family in NATIVE_FAMILIES else self._dt("连接设备", "Connect Device"))
        self.preview_shape_hint.configure(text=self._dt("预览：SR6 参考模型，不代表设备的精确外形。", "Preview: SR6 reference model, not the exact device geometry.") if family == "tcode" else
            self._dt("预览形状与实际设备不同；预览展示映射前的受限轴指令。", "Preview shape differs from the actual device; it shows limited axes before device mapping."))
        self._refresh_preview_device_context()

    def _on_external_mapping_changed(self, *_args) -> None:
        if isinstance(self.sink, IntifaceSink) or self._connecting:
            self.stop()
            self.disconnect_sink()
        if self._family_id() != "custom" and hasattr(self, "output_mode") and self.external_axis.get() != "L0":
            self.output_mode.set("Six Axis")

    def _set_device_controls_busy(self, busy: bool) -> None:
        if not hasattr(self, "device_family_combo"):
            return
        for name in ("device_family_combo", "native_output_combo", "external_device_combo", "external_feature_combo", "external_axis_combo"):
            widget = getattr(self, name, None)
            if widget:
                widget.configure(state="disabled" if busy else "readonly")
        for widget in getattr(self, "custom_binding_combos", {}).values():
            widget.configure(state="disabled" if busy else "readonly")
        for name in ("intiface_entry", "external_limit_slider", "device_scan_button"):
            widget = getattr(self, name, None)
            if widget:
                widget.configure(state="disabled" if busy or self._device_scanning else "normal")

    def _scan_external_devices(self) -> None:
        if self._device_scanning or self._connecting or (self.worker and self.worker.is_alive()):
            return
        if self.connected:
            self.disconnect_sink()
        self._clear_external_selection()
        self._device_scanning = True
        generation = self._device_scan_generation
        url = self.intiface_url.get()
        self._set_device_controls_busy(False)
        self.external_status.set(self._dt("正在检测 Intiface 并扫描设备...", "Checking Intiface and scanning devices..."))

        def work():
            try:
                devices = asyncio.run(discover_devices(url))
                self._queue_latest({"device_scan": generation, "devices": devices})
            except Exception:
                self._queue_latest({"device_scan": generation, "device_scan_error": True})
        threading.Thread(target=work, name="device-discovery", daemon=True).start()

    def _finish_device_scan(self, item: dict) -> None:
        if item["device_scan"] != self._device_scan_generation:
            return
        self._device_scanning = False
        self._set_device_controls_busy(False)
        if item.get("device_scan_error"):
            self.external_status.set(self._dt("扫描失败。请启动 Intiface 服务，检查地址，并关闭占用设备的其他控制软件。", "Scan failed. Start the Intiface server, check the address and close other device-control clients."))
            return
        self._external_devices = {f"{d.display_name or d.name} [#{d.index}]": d for d in item["devices"]}
        self.external_device_combo.configure(values=list(self._external_devices))
        self.external_status.set(self._dt("请选择设备及功能，再点击连接。未发送运动指令。", "Select a device and function, then connect. No motion commands have been sent.") if self._external_devices else
            self._dt("未发现设备。请检查蓝牙、设备电源和 Intiface 的设备支持列表。", "No devices found. Check Bluetooth, power and Intiface's supported-device list."))

    def _on_external_device_selected(self, _event=None) -> None:
        if self.connected or self._connecting:
            self.stop()
            self.disconnect_sink()
        self._updating_custom_bindings = True
        device = self._external_devices.get(self.external_device.get())
        names = {"Linear": self._dt("位置", "Position"), "Position": self._dt("位置", "Position"),
                 "Vibrate": self._dt("振动", "Vibration"), "Rotate": self._dt("旋转", "Rotation"),
                 "Oscillate": self._dt("往复速度", "Oscillation speed"), "Constrict": self._dt("收缩", "Contraction"),
                 "Inflate": self._dt("充气", "Inflation")}
        self._external_features = {f"{index + 1}. {names.get(f.actuator, f.actuator)} {f.description}".strip(): f for index, f in enumerate(device.features)} if device else {}
        self.external_feature_combo.configure(values=list(self._external_features))
        self.external_feature.set(next(iter(self._external_features), ""))
        for combo in self.custom_binding_combos.values():
            combo.configure(values=(self._unbound_label(), *self._external_features))
        saved = self.config_model.custom_bindings if device and self._custom_signature(device) == self.config_model.custom_binding_signature else {}
        self._set_custom_binding_values(saved if self._family_id() == "custom" else {})
        self._on_custom_mapping_changed()
        self.external_status.set(self._dt("一次只控制所选功能；其他电机不会自动映射。", "Only the selected function is controlled; other motors are not automatically mapped.") if self._external_features else
            self._dt("该设备没有本版本支持的输出功能。", "This device has no output features supported by this version."))
        if self._family_id() == "custom" and self._external_features:
            self.external_status.set(self._dt("已恢复匹配设备的绑定，请核对后连接。" if saved else "请为需要的轴选择交互功能；不绑定的轴不控制硬件。",
                "Matching bindings restored; review before connecting." if saved else "Select a function for each required axis. Unbound axes do not drive hardware."))
        self._refresh_preview_device_context()

    def _external_snapshot(self) -> dict:
        family = self._family_id()
        if family == "autoblow":
            raise ValueError(self._dt("Autoblow 仍待适配，本测试未启用输出。", "Autoblow output is not enabled in this test."))
        device = self._external_devices.get(self.external_device.get())
        if family == "custom":
            bindings = self._custom_binding_keys()
            if device is None or not bindings:
                raise ValueError(self._dt("请先扫描并选择设备，至少绑定一个轴。", "Scan, select a device and bind at least one axis."))
            if any(var.get() != self._unbound_label() and var.get() not in self._external_features for var in self.custom_bindings.values()):
                raise ValueError(self._dt("设备功能已变化，请重新绑定。", "Device functions changed; bind again."))
            if len(set(bindings.values())) != len(bindings):
                raise ValueError(self._dt("同一个设备功能不能绑定多个轴。", "A device function cannot be bound to multiple axes."))
            return {"kind": "Intiface", "url": self.intiface_url.get(), "device": device,
                    "bindings": bindings, "limit": self.external_limit.get() / 100}
        feature = self._external_features.get(self.external_feature.get())
        if device is None or feature is None:
            raise ValueError(self._dt("请先扫描并选择设备及控制功能。", "Scan and select a device and function first."))
        axis = self.external_axis.get()
        return {"kind": "Intiface", "url": self.intiface_url.get(), "device": device,
                "feature": feature.key, "axis": axis, "limit": self.external_limit.get() / 100}

    def _refresh_preview_device_context(self) -> None:
        if not hasattr(self, "preview_bridge"):
            return
        family = self._family_id()
        device = self._external_devices.get(self.external_device.get())
        label = device.display_name or device.name if device else self._device_family_labels[family]
        self.preview_bridge.set_device_context(label, family != "tcode", self.ui_language)
