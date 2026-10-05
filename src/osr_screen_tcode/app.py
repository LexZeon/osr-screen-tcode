from __future__ import annotations

import asyncio
import argparse
from collections.abc import Callable
from collections import deque
from dataclasses import replace
import ctypes
import os
import queue
import re
import sys
import locale
import threading
import time
import urllib.request
import zipfile
from pathlib import Path


from .screen_geometry import configure_dpi_awareness, physical_cursor_position, place_physical_window, move_physical_window


def _configure_windows_dpi_awareness() -> None:
    configure_dpi_awareness()


_configure_windows_dpi_awareness()

from .gpu_runtime import activate_local_runtime

activate_local_runtime()

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from .analyzer import SIX_AXES, RealtimeAnalyzer
from .audio import AudioAnalyzer, AudioCapture, list_audio_devices
from . import APP_NAME, __version__
from .capture import LatestScreenCapture, ScreenCapture, ScreenRegion, capture_fps, validate_region
from .region_selector import ScreenRegionSelector, TEXT as REGION_TEXT
from .pose_output import rtm_rotation_amplitudes, rtm_l0_amplitude
from .output_curve import OutputCurveFilter
from .config import (
    AppConfig,
    DEFAULT_AXIS_OUTPUT_INVERTS,
    DEFAULT_SIX_AXIS_GAINS,
    DEFAULT_SIX_AXIS_INVERTS,
    DEFAULT_SIX_AXIS_TRAVEL_SCALES,
    RTM_POSE_2D_MODE,
    RTM_POSE_3D_MODE,
    RTM_POSE_MODE,
    HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE, normalize_visual_settings,
)
from .analysis_preferences import AnalysisPreferences, defaults as analysis_defaults, load_profiles
from .integrated_preview import IntegratedPreview
from .preview import PreviewBridge
from .visual_pipeline import LabAnalyzer, VisualFrame, VisualSettings, make_analyzer
from .visual_lab.stabilizer import Options
from .device_controls import DeviceControls
from .gpu_controls import GpuControls
from .ui_widgets import WideCombobox, monitor_workarea
from .ui_layout import ControlSidebar, MainPanes, display_scale
from .recorder import MultiAxisFunscriptRecorder
from .sinks import (
    OutputWriteError,
    BleSink,
    LogSink,
    SerialSink,
    choose_best_serial_port,
    extract_serial_device,
    list_serial_port_infos,
    scan_ble_devices,
)
from .tcode import MultiAxisSafeOutput


from .application.language import LanguageMixin
from .application.state import StateMixin
from .application.settings import SettingsMixin
from .application.analysis_options import AnalysisOptionsMixin
from .application.layout import LayoutMixin
from .application.analysis_controls import AnalysisControlsMixin
from .application.sources import SourcesMixin
from .application.models import ModelsMixin
from .application.model_options import ModelOptionsMixin
from .application.travel_controls import TravelControlsMixin
from .application.device_panel import DevicePanelMixin
from .application.connection import ConnectionMixin
from .application.manual_output import ManualOutputMixin
from .application.presets import PresetsMixin
from .application.realtime import RealtimeMixin
from .application.start_dialog import StartDialogMixin
from .application.output import OutputMixin
from .application.video_export import VideoExportMixin
from .application.monitor import MonitorMixin
from .application.model_sources import RTM_POSE_2D_MODEL_URL, RTM_POSE_2D_MODEL_NAME
from .application.translations import TRACKER_MODE_CHOICES, TRACKER_MODE_EN, UI_TEXT_EN, UI_TEXT_REVERSE_EN
from .application.tooltips import Tooltip, TOOLTIPS, TOOLTIPS_EN


class OsrScreenApp(
    LanguageMixin,
    StateMixin,
    SettingsMixin,
    AnalysisOptionsMixin,
    LayoutMixin,
    AnalysisControlsMixin,
    SourcesMixin,
    ModelsMixin,
    ModelOptionsMixin,
    TravelControlsMixin,
    DevicePanelMixin,
    ConnectionMixin,
    ManualOutputMixin,
    PresetsMixin,
    RealtimeMixin,
    StartDialogMixin,
    OutputMixin,
    VideoExportMixin,
    MonitorMixin,
    DeviceControls,
    GpuControls,
    tk.Tk,
):
    def __init__(
        self,
        auto_connect: bool = False,
        center_on_connect: bool = False,
        enforce_age_gate: bool = True,
        ui_language: str = "auto",
    ) -> None:
        super().__init__()
        self.ui_language = "en"
        self.title(f"{APP_NAME} v{__version__}")
        self.geometry("1040x700")
        self.minsize(960, 620)
        if enforce_age_gate and not os.environ.get("OSR_SCREEN_TCODE_SKIP_AGE_GATE"):
            self._confirm_adult_use_or_exit()

        self.config_model = AppConfig.load()
        self.ui_language = self._choose_ui_language(ui_language)
        self.config_model.extra["ui_language"] = self.ui_language
        self.frame_queue: queue.Queue[dict[str, object]] = queue.Queue(maxsize=3)
        self.control_queue: queue.SimpleQueue[dict[str, object]] = queue.SimpleQueue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._region_selector = None
        self._input_widgets = []
        self._region_busy = None
        self._active_screen_region = None
        self._video_worker: threading.Thread | None = None
        self._video_cancel = threading.Event()
        self.sink = LogSink()
        self.preview_bridge = PreviewBridge()
        self._output_context = threading.local()
        self.connected = False
        self._connecting = False
        self._connect_worker: threading.Thread | None = None
        self._connect_attempt_id = 0
        self._start_after_connect = False
        self.auto_connect = auto_connect
        self.center_on_connect = center_on_connect
        self._config_save_after_id: str | None = None
        self._config_autosave_suspended = False
        self.preview_image: ImageTk.PhotoImage | None = None
        self.preview_canvas_image: int | None = None
        self._visual_generation = 0
        self.recorder = MultiAxisFunscriptRecorder()
        self._startup_window_geometry: str | None = None

        self._build_vars()
        self._build_ui()
        self._install_config_autosave()
        if not self.config_model.extra.get("play_preset_initialized_v1"):
            self.apply_play_preset(3, announce=False)
            self.config_model.extra["play_preset_initialized_v1"] = True
        self.refresh_ports()
        self.refresh_audio_devices()
        if self.config_model.serial_port:
            self.serial_port.set(self.config_model.serial_port)
            self.refresh_ports()
        elif self.config_model.last_sink in ("Serial COM", "USB Serial"):
            self.autodetect_device()
        self.after(50, self._poll_worker)
        self.after(400, self._startup_actions)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _rtm_pose_model_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "models"

    def _running_analysis_label(self) -> str:
        mode = self._tracker_display(self._tracker_internal(self.tracker_mode.get()))
        if self.ui_language == "en":
            return f"Running: {mode}"
        return f"正在以：{mode}：分析"

    def _refresh_start_button_text(self) -> None:
        if self.worker and self.worker.is_alive():
            self.start_button_text.set(self._running_analysis_label())
        else:
            self.start_button_text.set(self._t("开始实时输出"))

    def _startup_actions(self) -> None:
        if not self.auto_connect:
            return
        self.sink_type.set("Serial COM")
        if not self.serial_port.get():
            self.autodetect_device()
        self._start_connection_worker(center_after=self.center_on_connect)

    def _queue_latest(self, item: dict[str, object]) -> None:
        if any(key in item for key in ("connection_success", "connection_error", "output_failed", "device_scan", "gpu_event", "v2_model_event", "capture_stopped", "export_done", "error")):
            self.control_queue.put(item)
            return
        try:
            if self.frame_queue.full():
                self.frame_queue.get_nowait()
            self.frame_queue.put_nowait(item)
        except queue.Full:
            pass

    def _poll_worker(self) -> None:
        self._refresh_region_controls()
        latest_preview = None
        latest_visual = None
        if self.worker is not None and not self.worker.is_alive():
            self.worker = None
            self._set_device_controls_busy(self._connecting)
            self._refresh_start_button_text()
        try:
            while True:
                try:
                    item = self.control_queue.get_nowait()
                except queue.Empty:
                    item = self.frame_queue.get_nowait()
                if "gpu_event" in item:
                    self._finish_gpu_event(item)
                if "v2_model_event" in item:
                    self._finish_v2_model_event(item["v2_model_event"])
                if "connection_success" in item:
                    self._finish_connection_success(item)
                if "connection_error" in item:
                    self._finish_connection_error(item)
                if "output_failed" in item:
                    self._finish_output_failure(item)
                if "error" in item:
                    self.status.set(str(item["error"]))
                if "status_text" in item:
                    self.status.set(str(item["status_text"]))
                if "preview" in item:
                    latest_preview = item["preview"]
                if "visual_frame" in item:
                    latest_visual = item["visual_frame"]
                if item.get("capture_stats") is not None and not self.stop_event.is_set():
                    sampled, analyzed, age_ms = item["capture_stats"]
                    self.capture_rate_text.set(self._dt(
                        f"采集 {sampled:.0f} / 分析 {analyzed:.0f} FPS · 输入帧龄 {age_ms:.0f} ms",
                        f"Capture {sampled:.0f} / Analysis {analyzed:.0f} FPS · Input age {age_ms:.0f} ms"))
                if "command" in item:
                    command = str(item["command"])
                    self.output_value.set(command)
                    self._update_command_monitor(command)
                if "activity" in item:
                    self.activity.set(f"{self._t('活动')}: {float(item['activity']):.3f}")
                if "audio_level" in item:
                    self.activity.set(f"{self._t('声音')}: {float(item['audio_level']):.3f}")
                if "record_count" in item and self.recorder.is_recording:
                    self.record_status.set(f"{self._t('录制中')}: {item['record_count']} {self._t('点')}")
                if "rtm_model_path" in item:
                    model_path = str(item["rtm_model_path"])
                    self.rtm_pose_2d_model_path.set(model_path)
                    if self._rtm_pose_3d_download_target is not None:
                        self._rtm_pose_3d_download_target.set(model_path)
                    self._refresh_active_rtm_pose_model_path()
                if "rtm_download_status" in item:
                    self.rtm_model_download_status_text.set(str(item["rtm_download_status"]))
                if "rtm_download_done" in item:
                    self._rtm_pose_3d_downloading = False
                    self._rtm_pose_3d_download_target = None
                    self._rtm_pose_3d_download_mode = None
                    self.rtm_model_download_button_text.set(self._t("下载/自动检测模型"))
                if "capture_stopped" in item:
                    if self.worker and not self.worker.is_alive():
                        self.worker = None
                        self._set_device_controls_busy(False)
                    self._refresh_start_button_text()
                if "ble_devices" in item:
                    devices = item["ble_devices"]
                    if devices:
                        name, address = devices[0]
                        self.ble_name.set(name)
                        self.ble_address.set(address)
                        self.status.set(f"{self._t('找到 BLE')}: {name}")
                    else:
                        self.status.set(self._t("未找到 BLE 设备"))
        except queue.Empty:
            pass
        if latest_visual is not None:
            self.integrated_preview.display(latest_visual)
        elif latest_preview is not None:
            self._update_preview(latest_preview)
        self.after(16 if self.worker is not None else 50, self._poll_worker)

    def _update_preview(self, frame_bgr: object) -> None:
        self.integrated_preview.display(VisualFrame((frame_bgr, frame_bgr), None, False, self._visual_settings.generation))

    def _redraw_preview_image(self) -> None:
        self.integrated_preview.render()

    def on_close(self) -> None:
        self._cancel_v2_model_downloads()
        self._cancel_gpu_tasks()
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
            self._config_save_after_id = None
        self._save_config()
        self.stop()
        self.disconnect_sink()
        self.preview_bridge.stop()
        self.destroy()

    def _create_analyzer(self, **kwargs):
        """Keep the established analyzer factory import available to callers."""
        return make_analyzer(**kwargs)

    def _create_screen_capture(self, region, target_fps):
        """Keep the established capture factories at the application boundary."""
        return LatestScreenCapture(region, target_fps, capture_factory=ScreenCapture)

    def _create_region_selector(self, **kwargs):
        """Keep physical region selection at the application boundary."""
        return ScreenRegionSelector(self, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(prog="osr6-realtime", description=f"{APP_NAME} GUI")
    parser.add_argument("--auto-connect", action="store_true", help="Connect to the selected serial device at startup")
    parser.add_argument("--center", action="store_true", help="Send center command after auto-connect")
    parser.add_argument("--language", choices=("auto", "zh", "cn", "en"), default="auto", help="Interface language override")
    parser.add_argument("--smoke", action="store_true", help="Check UI startup with temporary Log-only settings")
    args = parser.parse_args()
    if args.smoke:
        from unittest.mock import patch
        with patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"):
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en" if args.language == "auto" else args.language)
            errors = []
            app.report_callback_exception = lambda *details: errors.append(details)
            app.after(1500, app.on_close)
            app.mainloop()
            if errors:
                raise RuntimeError(f"UI callback failed: {errors}")
    else:
        app = OsrScreenApp(auto_connect=args.auto_connect, center_on_connect=args.center, ui_language=args.language)
        app.mainloop()
