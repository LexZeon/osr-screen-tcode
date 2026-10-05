"""Device discovery, asynchronous connection and failure handling.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import asyncio
import threading
import tkinter as tk
from tkinter import messagebox
from ..audio import list_audio_devices
from ..sinks import BleSink, LogSink, SerialSink, choose_best_serial_port, extract_serial_device, list_serial_port_infos, scan_ble_devices


class ConnectionMixin:
    def refresh_ports(self) -> None:
        infos = list_serial_port_infos()
        ports = [info.display_name for info in infos]
        self.port_combo["values"] = ports
        current_device = extract_serial_device(self.serial_port.get())
        if current_device:
            for item in ports:
                if extract_serial_device(item).upper() == current_device.upper():
                    self.serial_port.set(item)
                    break
        elif ports:
            self.serial_port.set(choose_best_serial_port(infos))

    def refresh_audio_devices(self) -> None:
        devices = list_audio_devices()
        if not hasattr(self, "audio_device_combo"):
            return
        self.audio_device_combo["values"] = devices
        if devices and self.audio_device.get() not in devices:
            self.audio_device.set(devices[0])

    @staticmethod
    def _powershell_ports() -> list[str]:
        return []

    def autodetect_device(self) -> None:
        infos = list_serial_port_infos()
        if not infos:
            self.status.set(self._t("未发现串口设备"))
            return
        selected = choose_best_serial_port(infos)
        self.sink_type.set("Serial COM")
        self.serial_port.set(selected)
        self.status.set(f"{self._t('已选择')}: {selected}")

    def scan_ble(self) -> None:
        self.status.set(self._t("BLE 扫描中..."))

        def worker() -> None:
            try:
                devices = asyncio.run(scan_ble_devices(self.ble_name.get()))
                self.frame_queue.put({"ble_devices": devices})
            except Exception as exc:
                self.frame_queue.put({"error": f"{self._t('BLE 扫描失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()

    def _close_sink_safely(self, sink: object) -> None:
        try:
            sink.close()
        except Exception:
            pass

    def _connection_snapshot(self) -> dict[str, object]:
        kind = self.sink_type.get()
        if kind == "Log only":
            return {"kind": kind}
        return {
            "kind": kind,
            "serial_port": extract_serial_device(self.serial_port.get()),
            "baudrate": self.baudrate.get(),
            "ble_address": self.ble_address.get(),
            "ble_write_uuid": self.ble_write_uuid.get(),
        }

    def _open_sink_from_snapshot(self, snapshot: dict[str, object]) -> object:
        kind = str(snapshot["kind"])
        if kind in ("USB Serial", "Serial COM"):
            return SerialSink(str(snapshot["serial_port"]), int(snapshot["baudrate"]))
        if kind == "BLE UART":
            return BleSink(str(snapshot["ble_address"]), str(snapshot["ble_write_uuid"]))
        if kind == "Log only":
            return LogSink()
        raise ValueError(f"Unsupported output transport: {kind}")

    def _set_connecting(self, active: bool) -> None:
        self._connecting = active
        self.connect_button_text.set(self._t("连接中...") if active else self._t("连接并回中"))
        self._set_device_controls_busy(active or bool(self.worker and self.worker.is_alive()))
        for name in ("connect_button", "monitor_connect_button"):
            button = getattr(self, name, None)
            if button is None:
                continue
            try:
                button.state(["disabled"] if active else ["!disabled"])
            except tk.TclError:
                pass

    def _finish_connection_success(self, item: dict[str, object]) -> None:
        attempt_id = int(item.get("attempt_id", 0))
        sink = item.get("sink")
        if attempt_id != self._connect_attempt_id:
            if sink is not None:
                self._close_sink_safely(sink)
            return
        if sink is None:
            return
        self.sink = sink
        self.connected = True
        self._set_connecting(False)
        kind = str(item.get("kind", self.sink_type.get()))
        self.status.set(f"{self._t('已连接')}: {kind}")
        if kind in ("USB Serial", "Serial COM"):
            self.device_status.set(f"{self._t('设备')}: {self._t('已连接')} {item.get('serial_port', '')}")
        elif kind == "BLE UART":
            self.device_status.set(f"{self._t('设备')}: {self._t('已连接')} BLE {item.get('ble_address', '')}")
        else:
            self.device_status.set(f"{self._t('设备')}: {self._t('日志模式')}")
        self._save_config()
        if bool(item.get("center_after", False)):
            try:
                self.send_center(interval_ms=600)
                self.status.set(self._t("已连接并回中"))
            except Exception as exc:
                self.status.set(f"{self._t('回中失败')}: {exc}")
        if self._start_after_connect and not (self.worker and self.worker.is_alive()):
            self._start_after_connect = False
            self.after(0, self._begin_realtime_output)

    def _finish_connection_error(self, item: dict[str, object]) -> None:
        attempt_id = int(item.get("attempt_id", 0))
        if attempt_id != self._connect_attempt_id:
            return
        self.sink = LogSink()
        self.connected = False
        self._start_after_connect = False
        self._set_connecting(False)
        message = str(item.get("message", self._t("连接失败")))
        self.device_status.set(f"{self._t('设备')}: {self._t('连接失败')}")
        self.status.set(f"{self._t('连接失败')}: {message}")
        messagebox.showerror(self._t("连接失败"), self._dt(
            "未能接入设备。请检查设备连接及串口／蓝牙选择；无设备时请选择 Log only。\n\n具体原因：",
            "Could not connect to the device. Check the connection and selected serial/BLE device; use Log only without hardware.\n\nDetails: ")+message, parent=self)

    def _finish_output_failure(self, item: dict[str, object]) -> None:
        failed_sink = item.get("sink")
        if failed_sink is not self.sink:
            return  # An old worker must not disconnect a replacement connection.
        self.stop()
        self._close_sink_safely(failed_sink)
        self.sink = LogSink()
        self.connected = False
        self._set_connecting(False)
        title = self._dt("设备输出失败", "Device output failed")
        detail = str(item.get("message", ""))
        self.device_status.set(self._dt("设备：连接不可用", "Device: connection unavailable"))
        self.status.set(f"{title}: {detail}")
        messagebox.showerror(title, self._dt(
            "设备输出失败，实时输出已停止。设备可能未接入、连接中断或写入超时。\n\n"
            "请检查后重新连接；无设备时请选择 Log only。\n\n具体原因：",
            "Device output failed; realtime output has stopped. The device may be missing, disconnected or timed out.\n\n"
            "Check and reconnect it; use Log only without hardware.\n\nDetails: ")+detail, parent=self)

    def _connection_watchdog(self, attempt_id: int) -> None:
        if not self._connecting or attempt_id != self._connect_attempt_id:
            return
        self._connect_attempt_id += 1
        self.sink = LogSink()
        self.connected = False
        self._start_after_connect = False
        self._set_connecting(False)
        self.device_status.set(f"{self._t('设备')}: {self._t('连接失败')}")
        self.status.set(self._t("连接超时"))
        messagebox.showerror(self._t("连接超时"), self._dt(
            "未能接入设备。请检查连接后重试；无设备时请选择 Log only。",
            "Could not connect to the device. Check the connection and retry; use Log only without hardware."), parent=self)

    def _start_connection_worker(self, center_after: bool = False) -> None:
        if self._gpu_installing:
            self._start_after_connect = False
            self.status.set(self._dt("请等待 GPU 运行库安装完成。", "Wait for GPU runtime installation to finish."))
            return
        if self._connecting:
            self.status.set(self._t("正在连接，连接成功后请再试一次。"))
            return
        if self.worker and self.worker.is_alive():
            self.status.set(self._dt("请先停止实时输出，再更换连接。", "Stop realtime output before changing connections."))
            return
        try:
            snapshot = self._connection_snapshot()
        except (ValueError, tk.TclError) as exc:
            self._start_after_connect = False
            self.status.set(str(exc))
            return
        kind = str(snapshot["kind"])
        self._connect_attempt_id += 1
        attempt_id = self._connect_attempt_id
        self._close_sink_safely(self.sink)
        self.sink = LogSink()
        self.connected = False
        if kind not in ("USB Serial", "Serial COM", "BLE UART"):
            self.sink.open()
            self.connected = True
            self.status.set(f"{self._t('已连接')}: {kind}")
            self.device_status.set(f"{self._t('设备')}: {self._t('日志模式')}")
            self._save_config()
            if center_after:
                self.send_center(interval_ms=600)
                self.status.set(self._t("已连接并回中"))
            return
        self._set_connecting(True)
        self.status.set(self._t("正在连接，请稍候..."))
        self.device_status.set(f"{self._t('设备')}: {self._t('正在连接，请稍候...')}")

        def worker() -> None:
            sink: object | None = None
            try:
                sink = self._open_sink_from_snapshot(snapshot)
                sink.open()
                payload = dict(snapshot)
                payload.update(
                    {
                        "connection_success": True,
                        "attempt_id": attempt_id,
                        "sink": sink,
                        "kind": kind,
                        "center_after": center_after,
                    }
                )
                self._queue_latest(payload)
            except Exception as exc:
                if sink is not None:
                    self._close_sink_safely(sink)
                self._queue_latest(
                    {
                        "connection_error": True,
                        "attempt_id": attempt_id,
                        "message": str(exc),
                    }
                )

        self._connect_worker = threading.Thread(target=worker, daemon=True)
        self._connect_worker.start()
        self.after(15000, lambda attempt=attempt_id: self._connection_watchdog(attempt))

    def connect_sink(self) -> None:
        self._start_connection_worker(center_after=False)

    def connect_and_center(self) -> None:
        self._start_connection_worker(center_after=True)

    def disconnect_sink(self) -> None:
        if self.worker and self.worker.is_alive():
            self.stop()
        self._connect_attempt_id += 1
        self._start_after_connect = False
        self._set_connecting(False)
        self._close_sink_safely(self.sink)
        self.sink = LogSink()
        self.connected = False
        self.device_status.set(f"{self._t('设备')}: {self._t('未连接')}")
        if not self.worker:
            self.status.set(self._t("未连接"))

    def query_device_axes(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再查询设备轴。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        if not isinstance(self.sink, SerialSink):
            messagebox.showinfo(self._t("暂不支持"), self._t("设备轴查询目前只支持 Serial COM。BLE UART 通常需要通知通道，暂时只做写入。"))
            return

        def worker() -> None:
            try:
                response = self.sink.query(b"D2\n", wait_s=0.8)
                text = response.decode("utf-8", errors="replace").strip()
                if not text:
                    text = self._t("无回复：可继续用六轴轻测，或确认固件是否支持 TCode D2 查询。")
                self._queue_latest({"status_text": f"{self._t('设备轴查询')}: {text}", "command": f"D2 -> {text}"})
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('设备轴查询失败')}: {exc}"})

        threading.Thread(target=worker, daemon=True).start()
