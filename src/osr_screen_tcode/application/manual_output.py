"""Command transmission, centering, measurement and manual device tests.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import threading
import time
import tkinter as tk
from tkinter import messagebox
from ..analyzer import SIX_AXES
from ..sinks import OutputWriteError
from ..tcode import MultiAxisSafeOutput


class ManualOutputMixin:
    def _emit_command(self, command: object) -> str:
        if isinstance(command, str):
            text = command.strip()
            payload = (text + "\n").encode("ascii")
        else:
            payload = command.encode()
            text = payload.decode("ascii").strip()
        sink = self.sink
        if getattr(self._output_context, "sink", sink) is not sink:
            return text
        if threading.current_thread() is self.worker and self.stop_event.is_set():
            return text
        try:
            sink.write(payload)
        except Exception as exc:
            self._queue_latest({"output_failed": True, "sink": sink,
                                "message": f"{type(exc).__name__}: {exc}"})
            raise OutputWriteError(f"{type(exc).__name__}: {exc}") from exc
        self.preview_bridge.broadcast_tcode(text)
        return text

    def send_center(self, interval_ms: int | None = None) -> None:
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        output = self._new_output(interval_ms or 500)
        command = output.center_command(interval_ms or 500)
        self.output_value.set(self._emit_command(command))
        self._update_command_monitor(self.output_value.get())

    def _on_measure_slider(self) -> None:
        if not self.measure_live.get():
            return
        if not self.connected:
            self.status.set(self._t("测量模式: 请先连接设备"))
            return
        now = time.perf_counter()
        if now - self._last_measure_sent < 0.045:
            return
        self._last_measure_sent = now
        self.send_measure_position()

    def _sync_measure_value_from_axis(self) -> None:
        axis = self.measure_axis.get() if self.measure_axis.get() in SIX_AXES else "L0"
        self.measure_value.set(max(0, min(9999, int(self._last_axis_values.get(axis, 5000)))))

    def send_measure_position(self, value: int | None = None) -> None:
        if self.worker and self.worker.is_alive():
            self.status.set(self._t("请先停止实时输出，再使用测量模式"))
            return
        if value is not None:
            self.measure_value.set(max(0, min(9999, int(value))))
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        axis = self.measure_axis.get() if self.measure_axis.get() in SIX_AXES else "L0"
        try:
            position = max(0, min(9999, int(float(self.measure_value.get()))))
        except (tk.TclError, ValueError):
            position = 5000
            self.measure_value.set(position)
        interval = max(80, min(900, int(self.interval_ms.get()) if self.interval_ms.get() else 250))
        command = f"{axis}{position:04d}I{interval}"
        try:
            self._emit_command(command)
        except Exception as exc:
            self.status.set(f"{self._t('测量发送失败')}: {exc}")
            return
        self.output_value.set(command)
        self._update_command_monitor(command)
        self.status.set(f"{self._t('测量模式')}: {axis} -> {position:04d}")

    def save_measure_limit(self, which: str) -> None:
        axis = self.measure_axis.get() if self.measure_axis.get() in SIX_AXES else "L0"
        try:
            value = max(0, min(9999, int(float(self.measure_value.get()))))
        except (tk.TclError, ValueError):
            return
        low_var = self.axis_min_vars[axis]
        high_var = self.axis_max_vars[axis]
        if which == "low":
            low_var.set(value)
        else:
            high_var.set(value)
        self._normalize_axis_limit(axis)
        self._refresh_limit_text()
        self._draw_axis_monitor(self._last_axis_values)
        label = self._t("下限" if which == "low" else "上限")
        self.status.set(f"{self._t('已保存')} {axis} {label}: {value:04d}")

    def send_small_test(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再做中等测试。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        axes = self._active_axes()
        output = MultiAxisSafeOutput(
            axes,
            self.min_value.get(),
            self.max_value.get(),
            self.invert.get(),
            480,
            999,
            0.0,
            "Hold",
            axis_limits=self._axis_limits(axes),
            position_scale=self.global_travel_scale.get(),
            axis_position_scales=self._axis_position_scales(),
            axis_position_inverts=self._axis_position_inverts(),
            enable_endpoint_guard=self.enable_endpoint_guard.get(),
            endpoint_margin=self.endpoint_margin_pct.get() / 100.0,
        )
        for pos in (0.5, 0.0, 1.0, 0.0, 1.0, 0.5):
            positions = {axis: 0.5 for axis in axes}
            positions["L0"] = pos
            command = output.next_command(positions, 1.0)
            self.output_value.set(self._emit_command(command))
            self._update_command_monitor(self.output_value.get())
            self.update_idletasks()
            time.sleep(0.32)
        self.status.set(self._t("中等测试完成"))

    def send_full_l0_test(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再做上下全幅测试。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        axes = self._active_axes()
        axis_limits = self._axis_limits(axes)
        invert_l0 = self.invert.get()
        axis_position_inverts = self._axis_position_inverts()
        min_value = self.min_value.get()
        max_value = self.max_value.get()

        def worker() -> None:
            self._output_context.sink = test_sink
            output = MultiAxisSafeOutput(
                axes,
                min_value,
                max_value,
                invert_l0,
                900,
                9999,
                0.0,
                "Hold",
                axis_limits=axis_limits,
                axis_position_inverts=axis_position_inverts,
                enable_endpoint_guard=False,
            )
            center = {axis: 0.5 for axis in axes}
            try:
                for pos in (0.5, 0.0, 1.0, 0.0, 1.0, 0.5):
                    positions = center.copy()
                    positions["L0"] = pos
                    command = output.next_command(positions, 1.0)
                    command_text = self._emit_command(command)
                    self._queue_latest(
                        {
                            "command": command_text,
                            "status_text": self._t("上下全幅测试中"),
                        }
                    )
                    time.sleep(0.95)
                center_command = output.center_command(900)
                center_text = self._emit_command(center_command)
                self._queue_latest(
                    {
                        "command": center_text,
                        "status_text": self._t("上下全幅测试完成，已回中"),
                    }
                )
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('上下全幅测试失败')}: {exc}"})

        test_sink = self.sink
        threading.Thread(target=worker, daemon=True).start()

    def send_six_axis_test(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再做六轴轻测。"))
            return
        if not self.connected:
            self.connect_sink()
            if not self.connected:
                return
        self._normalize_limits()
        axes = SIX_AXES.copy()
        axis_limits = self._axis_limits(axes)
        axis_position_scales = self._axis_position_scales()
        axis_position_inverts = self._axis_position_inverts()
        global_position_scale = self.global_travel_scale.get()
        invert_l0 = self.invert.get()
        endpoint_guard = self.enable_endpoint_guard.get()
        endpoint_margin = self.endpoint_margin_pct.get() / 100.0
        min_value = self.min_value.get()
        max_value = self.max_value.get()

        def worker() -> None:
            self._output_context.sink = test_sink
            output = MultiAxisSafeOutput(
                axes,
                min_value,
                max_value,
                invert_l0,
                320,
                999,
                0.0,
                "Hold",
                axis_limits=axis_limits,
                position_scale=global_position_scale,
                axis_position_scales=axis_position_scales,
                axis_position_inverts=axis_position_inverts,
                enable_endpoint_guard=endpoint_guard,
                endpoint_margin=endpoint_margin,
            )
            center = {axis: 0.5 for axis in axes}
            try:
                command = output.next_command(center, 1.0)
                self._queue_latest({"command": self._emit_command(command), "status_text": self._t("SR6/OSR6 六轴轻测中")})
                time.sleep(0.35)
                for axis in axes:
                    for value in (0.35, 0.65, 0.5):
                        positions = center.copy()
                        positions[axis] = value
                        command = output.next_command(positions, 1.0)
                        self._queue_latest({"command": self._emit_command(command)})
                        time.sleep(0.35)
                center_command = output.center_command(600)
                self._queue_latest({"command": self._emit_command(center_command)})
                self._queue_latest({"status_text": self._t("SR6/OSR6 六轴轻测完成，已回中")})
            except Exception as exc:
                self._queue_latest({"error": f"{self._t('六轴轻测失败')}: {exc}"})

        test_sink = self.sink
        threading.Thread(target=worker, daemon=True).start()
