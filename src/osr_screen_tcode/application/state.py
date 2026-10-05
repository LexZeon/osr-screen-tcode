"""Tk variables and the existing saved-setting variable registry.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
from collections import deque
import tkinter as tk
from ..analyzer import SIX_AXES
from ..capture import ScreenRegion, capture_fps
from ..config import DEFAULT_AXIS_OUTPUT_INVERTS, DEFAULT_SIX_AXIS_GAINS, DEFAULT_SIX_AXIS_INVERTS, DEFAULT_SIX_AXIS_TRAVEL_SCALES, RTM_POSE_2D_MODE, RTM_POSE_3D_MODE, normalize_visual_settings
from ..analysis_preferences import AnalysisPreferences, load_profiles


class StateMixin:
    def _build_vars(self) -> None:
        cfg = self.config_model
        self.x = tk.IntVar(value=cfg.x)
        self.y = tk.IntVar(value=cfg.y)
        self.width = tk.IntVar(value=cfg.width)
        self.height = tk.IntVar(value=cfg.height)
        self._screen_region_snapshot = ScreenRegion(cfg.x, cfg.y, cfg.width, cfg.height)
        self._live_source_mode = cfg.extra.get("source_mode", "Screen")
        self.fps = tk.IntVar(value=cfg.fps)
        self._capture_target_fps = capture_fps(cfg.fps)
        self.fps.trace_add("write", self._capture_fps_changed)
        self.capture_rate_text = tk.StringVar(value="")
        self.output_curve_fitting = tk.BooleanVar(value=bool(cfg.extra.get("output_curve_fitting", True)))
        self.endpoint_slowdown_enabled = tk.BooleanVar(value=bool(cfg.extra.get("endpoint_slowdown_enabled", True)))
        self.endpoint_slowdown_pct = tk.DoubleVar(value=float(cfg.extra.get("endpoint_slowdown_pct", 10)))
        self._endpoint_options_changed()
        self.endpoint_slowdown_enabled.trace_add("write", self._endpoint_options_changed)
        self.endpoint_slowdown_pct.trace_add("write", self._endpoint_options_changed)
        self._output_curve_enabled = self.output_curve_fitting.get()
        self.output_curve_fitting.trace_add("write", self._output_curve_changed)
        self.source_mode = tk.StringVar(value=cfg.extra.get("source_mode", "Screen"))
        self.video_path = tk.StringVar(value=cfg.extra.get("video_path", ""))
        self.output_mode = tk.StringVar(value=cfg.extra.get("output_mode", "L0 Only"))
        self.audio_mode = tk.StringVar(value=cfg.audio_mode)
        self.audio_gain = tk.DoubleVar(value=cfg.audio_gain)
        self.audio_threshold = tk.DoubleVar(value=cfg.audio_threshold)
        self.audio_smoothing = tk.DoubleVar(value=cfg.audio_smoothing)
        self.audio_device = tk.StringVar(value=cfg.audio_device)
        stored_limits = cfg.axis_limits if isinstance(cfg.axis_limits, dict) else {}
        self.axis_min_vars: dict[str, tk.IntVar] = {}
        self.axis_max_vars: dict[str, tk.IntVar] = {}
        for axis in SIX_AXES:
            raw_limit = stored_limits.get(axis)
            if not isinstance(raw_limit, (list, tuple)) or len(raw_limit) < 2:
                raw_limit = (cfg.min_value, cfg.max_value)
            try:
                low, high = int(float(raw_limit[0])), int(float(raw_limit[1]))
            except (TypeError, ValueError):
                low, high = cfg.min_value, cfg.max_value
            self.axis_min_vars[axis] = tk.IntVar(value=max(0, min(9999, low)))
            self.axis_max_vars[axis] = tk.IntVar(value=max(0, min(9999, high)))
        # Keep the compact L0 controls as aliases for backwards-compatible presets/configs.
        self.min_value = self.axis_min_vars["L0"]
        self.max_value = self.axis_max_vars["L0"]
        self.smoothing = tk.DoubleVar(value=cfg.smoothing)
        self.enable_smoothing = tk.BooleanVar(value=cfg.enable_smoothing)
        self.deadzone = tk.DoubleVar(value=cfg.deadzone)
        self.enable_deadzone = tk.BooleanVar(value=cfg.enable_deadzone)
        self.enable_l0_jitter_guard = tk.BooleanVar(value=bool(cfg.extra.get("enable_l0_jitter_guard", True)))
        self.l0_guard_strength = tk.DoubleVar(value=float(cfg.extra.get("l0_guard_strength", 0.70)))
        self.enable_extreme_reset = tk.BooleanVar(value=bool(cfg.extra.get("enable_extreme_reset", True)))
        self.extreme_hold_ms = tk.IntVar(value=int(cfg.extra.get("extreme_hold_ms", 850)))
        self.enable_endpoint_guard = tk.BooleanVar(value=bool(cfg.extra.get("enable_endpoint_guard", True)))
        self.endpoint_margin_pct = tk.IntVar(value=int(cfg.extra.get("endpoint_margin_pct", 10)))
        legacy_pose = bool(cfg.extra.get("pose_dance_analysis", False))
        self.pose_l0_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_l0_analysis", legacy_pose)))
        self.pose_six_axis_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_six_axis_analysis", legacy_pose)))
        self.pose_l0_weight = tk.IntVar(value=int(cfg.extra.get("pose_l0_weight", 60)))
        self.pose_six_axis_weight = tk.IntVar(value=int(cfg.extra.get("pose_six_axis_weight", 60)))
        self.pose_v2_dance_six_axis = tk.BooleanVar(value=bool(cfg.extra.get("pose_v2_dance_six_axis", False)))
        self.pose_v2_l0_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_v2_l0_analysis", False)))
        self.pose_v2_six_axis_analysis = tk.BooleanVar(value=bool(cfg.extra.get("pose_v2_six_axis_analysis", self.pose_v2_dance_six_axis.get())))
        self.pose_v2_l0_weight = tk.IntVar(value=int(cfg.extra.get("pose_v2_l0_weight", 60)))
        self.pose_v2_six_axis_weight = tk.IntVar(value=int(cfg.extra.get("pose_v2_six_axis_weight", 60)))
        if self.pose_v2_dance_six_axis.get() and (self.pose_v2_l0_analysis.get() or self.pose_v2_six_axis_analysis.get()):
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
        elif self.pose_l0_analysis.get() or self.pose_six_axis_analysis.get():
            self.pose_v2_dance_six_axis.set(False)
            self.pose_v2_l0_analysis.set(False)
            self.pose_v2_six_axis_analysis.set(False)
        self.pose_l0_base_weight_text = tk.StringVar()
        self.pose_six_axis_base_weight_text = tk.StringVar()
        self.pose_v2_l0_base_weight_text = tk.StringVar()
        self.pose_v2_six_axis_base_weight_text = tk.StringVar()
        self._pose_mode_syncing = False
        initial_tracker_mode = self._normalize_tracker_mode(cfg.tracker_mode)
        if bool(cfg.extra.get("rtm_pose_3d_enabled", False)):
            initial_tracker_mode = RTM_POSE_2D_MODE
        initial_rtm_pose_mode = initial_tracker_mode in (RTM_POSE_2D_MODE,)
        self.rtm_pose_3d_enabled = tk.BooleanVar(value=initial_tracker_mode == RTM_POSE_3D_MODE)
        self.rtm_pose_2d_model_path = tk.StringVar(value=str(cfg.extra.get("rtm_pose_2d_model_path", "")))
        self.rtm_pose_3d_model_path = tk.StringVar(value="")
        self.rtm_pose_3d_weight = tk.IntVar(value=100 if initial_rtm_pose_mode else 0)
        self.rtm_hybrid_l0_enabled = tk.BooleanVar(value=bool(cfg.extra.get("rtm_hybrid_l0_enabled", False)))
        self.pose_auto_l0_enabled = tk.BooleanVar(value=bool(cfg.extra.get("pose_auto_l0_enabled", True)))
        self.pose_pattern_enabled = tk.BooleanVar(value=bool(cfg.extra.get("pose_pattern_enabled", False)))
        self.pose_fast_v1_enabled = tk.BooleanVar(value=bool(cfg.extra.get("pose_fast_v1_enabled", True)))
        self.rtm_hybrid_l0_weight = tk.IntVar(value=max(1, min(100, int(cfg.extra.get("rtm_hybrid_l0_weight", 30)))))
        self.rtm_model_l0_weight_text = tk.StringVar()
        self.rtm_pose_3d_base_weight_text = tk.StringVar()
        self.rtm_model_download_button_text = tk.StringVar(value=self._t("下载/自动检测模型"))
        self.rtm_model_download_status_text = tk.StringVar(value="")
        self.rtm_pose_gpu_enabled = tk.BooleanVar(value=bool(cfg.extra.get("rtm_pose_gpu_enabled", False)))
        self.rtm_pose_gpu_backend = tk.StringVar(value=cfg.extra.get("rtm_pose_gpu_backend", "cuda"))
        self.rtm_pose_gpu_status_text = tk.StringVar()
        self._build_gpu_state()
        self._analysis_preferences = AnalysisPreferences(load_profiles(cfg.extra, initial_tracker_mode, cfg.fps), initial_tracker_mode)
        normalize_visual_settings(cfg.extra)
        self.rtm_pose_flow_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_flow_enabled"])
        self.rtm_pose_kalman_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_kalman_enabled"])
        self.hybrid_v2_pose_enabled = tk.BooleanVar(value=cfg.extra["hybrid_v2_pose_enabled"])
        self.v2_vittrack_enabled = tk.BooleanVar(value=cfg.extra["v2_vittrack_enabled"])
        self.v2_neuflow_enabled = tk.BooleanVar(value=cfg.extra["v2_neuflow_enabled"])
        self.v2_vittrack_model_path = tk.StringVar(value=cfg.extra["v2_vittrack_model_path"])
        self.v2_neuflow_model_path = tk.StringVar(value=cfg.extra["v2_neuflow_model_path"])
        self._v2_model_options = {}
        self._v2_model_revision = tk.IntVar(value=0)
        self._v2_model_notices = {}
        self._v2_model_downloads = {}
        self._v2_model_download_token = 0
        self.v2_l0_reference = tk.StringVar(value=cfg.extra['v2_l0_reference'])
        self.rtm_pose_reject_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_reject_enabled"])
        self.rtm_pose_micro_smooth_enabled = tk.BooleanVar(value=cfg.extra["rtm_pose_micro_smooth_enabled"])
        self.visual_processing_edge = tk.IntVar(value=cfg.extra["visual_processing_edge"])
        self.rtm_hybrid_source = tk.StringVar(value=cfg.extra["rtm_hybrid_source"])
        self._rtm_pose_3d_downloading = False
        self._rtm_pose_3d_download_target: tk.StringVar | None = None
        self._rtm_pose_3d_download_mode: str | None = None
        self._rtm_pose_model_path_syncing = False
        self._rtm_pose_model_validation_cache: dict[tuple[str, str, int, int], tuple[bool, str]] = {}
        self.tracker_mode = tk.StringVar(value=self._tracker_display(initial_tracker_mode))
        self.rtm_pose_model_path = tk.StringVar()
        self.response_curve = tk.StringVar(value=cfg.response_curve)
        self.motion_gain = tk.DoubleVar(value=cfg.motion_gain)
        self.visual_stroke_scale = tk.DoubleVar(value=cfg.visual_stroke_scale)
        self.compression_latency = tk.IntVar(value=max(-5, min(5, int(cfg.extra.get("compression_latency", 0)))))
        self.l0_travel_scale = tk.DoubleVar(value=float(cfg.extra.get("l0_travel_scale", cfg.global_travel_scale)))
        self.global_travel_scale = tk.DoubleVar(value=cfg.global_travel_scale)
        self._travel_slider_syncing = False
        self.l0_travel_slider = tk.DoubleVar(value=self._travel_scale_to_slider(self.l0_travel_scale.get()))
        self.global_travel_slider = tk.DoubleVar(value=self._travel_scale_to_slider(self.global_travel_scale.get()))
        self.l0_travel_text = tk.StringVar(value=self._format_travel_scale(self.l0_travel_scale.get()))
        self.global_travel_text = tk.StringVar(value=self._format_travel_scale(self.global_travel_scale.get()))
        self.six_axis_travel_invert = tk.BooleanVar(value=bool(cfg.extra.get("six_axis_travel_invert", False)))
        stored_travel_scales = cfg.extra.get("six_axis_travel_scales", {})
        stored_output_inverts = cfg.extra.get("axis_output_inverts", {})
        if not isinstance(stored_travel_scales, dict):
            stored_travel_scales = {}
        if not isinstance(stored_output_inverts, dict):
            stored_output_inverts = {}
        self.six_axis_travel_scale_vars: dict[str, tk.DoubleVar] = {}
        self.six_axis_travel_slider_vars: dict[str, tk.DoubleVar] = {}
        self.six_axis_travel_text_vars: dict[str, tk.StringVar] = {}
        self.axis_output_invert_vars: dict[str, tk.BooleanVar] = {}
        for axis, default_scale in DEFAULT_SIX_AXIS_TRAVEL_SCALES.items():
            scale = max(0.0, min(3.0, float(stored_travel_scales.get(axis, default_scale))))
            self.six_axis_travel_scale_vars[axis] = tk.DoubleVar(value=scale)
            self.six_axis_travel_slider_vars[axis] = tk.DoubleVar(value=self._travel_scale_to_slider(scale))
            self.six_axis_travel_text_vars[axis] = tk.StringVar(value=self._format_travel_scale(scale))
            self.axis_output_invert_vars[axis] = tk.BooleanVar(
                value=bool(stored_output_inverts.get(axis, DEFAULT_AXIS_OUTPUT_INVERTS.get(axis, False)))
            )
        self.play_preset_level = tk.IntVar(value=int(cfg.extra.get("play_preset_level", 3)))
        self.six_axis_intensity = tk.IntVar(value=int(cfg.extra.get("six_axis_intensity", 65)))
        self.six_axis_jitter_reduction = tk.IntVar(value=int(cfg.extra.get("six_axis_jitter_reduction", 55)))
        self.six_axis_sensitivity_level = tk.IntVar(value=int(cfg.extra.get("six_axis_sensitivity_level", 5)))
        self.start_button_text = tk.StringVar(value=self._t("开始实时输出"))
        self.show_more_settings = tk.BooleanVar(value=bool(cfg.extra.get("show_more_settings", False)))
        self.show_measurement_limits = tk.BooleanVar(value=bool(cfg.extra.get("show_measurement_limits", True)))
        self.show_six_axis_tuning = tk.BooleanVar(value=bool(cfg.extra.get("show_six_axis_tuning", False)))
        self.show_rtm_pose_3d_settings = tk.BooleanVar(value=bool(cfg.extra.get("show_rtm_pose_3d_settings", False)))
        self.show_six_axis_travel_scales = tk.BooleanVar(value=bool(cfg.extra.get("show_six_axis_travel_scales", False)))
        stored_gains = cfg.extra.get("six_axis_gains", {})
        stored_inverts = cfg.extra.get("six_axis_inverts", {})
        self.six_axis_gain_vars: dict[str, tk.IntVar] = {}
        self.six_axis_invert_vars: dict[str, tk.BooleanVar] = {}
        for axis in SIX_AXES:
            if axis == "L0":
                continue
            gain = stored_gains.get(axis, DEFAULT_SIX_AXIS_GAINS.get(axis, 60)) if isinstance(stored_gains, dict) else DEFAULT_SIX_AXIS_GAINS.get(axis, 60)
            inverted = stored_inverts.get(axis, DEFAULT_SIX_AXIS_INVERTS.get(axis, False)) if isinstance(stored_inverts, dict) else DEFAULT_SIX_AXIS_INVERTS.get(axis, False)
            self.six_axis_gain_vars[axis] = tk.IntVar(value=max(0, min(200, int(float(gain)))))
            self.six_axis_invert_vars[axis] = tk.BooleanVar(value=bool(inverted))
        self.min_activity = tk.DoubleVar(value=cfg.min_activity)
        self.enable_activity_gate = tk.BooleanVar(value=cfg.enable_activity_gate)
        self.max_step = tk.IntVar(value=cfg.max_step)
        self.enable_speed_limit = tk.BooleanVar(value=cfg.enable_speed_limit)
        self.idle_mode = tk.StringVar(value=cfg.idle_mode)
        self.invert = tk.BooleanVar(value=cfg.invert)
        self.enable_startup_ramp = tk.BooleanVar(value=cfg.enable_startup_ramp)
        self.startup_ramp_ms = tk.IntVar(value=cfg.startup_ramp_ms)
        self.axis = tk.StringVar(value=cfg.axis)
        self.interval_ms = tk.IntVar(value=cfg.output_interval_ms)
        self.sink_type = tk.StringVar(value=cfg.last_sink)
        self.serial_port = tk.StringVar(value=cfg.serial_port)
        self.baudrate = tk.IntVar(value=cfg.baudrate)
        self.ble_name = tk.StringVar(value=cfg.ble_name)
        self.ble_address = tk.StringVar(value=cfg.ble_address)
        self.ble_service_uuid = tk.StringVar(value=cfg.ble_service_uuid)
        self.ble_write_uuid = tk.StringVar(value=cfg.ble_write_uuid)
        self.status = tk.StringVar(value=self._t("未连接"))
        self.device_status = tk.StringVar(value=f"{self._t('设备')}: {self._t('未连接')}")
        self.connect_button_text = tk.StringVar(value=self._t("连接并回中"))
        self.output_value = tk.StringVar(value="L05000I20")
        self.l0_status = tk.StringVar(value="L0 5000")
        self.stroke_status = tk.StringVar(value=f"{self._t('中段')} 50%")
        self.range_status = tk.StringVar(value=f"L0 {self._t('下限')} 0 / {self._t('上限')} 9999")
        measure_axis = cfg.extra.get("measure_axis", "L0")
        if measure_axis not in SIX_AXES:
            measure_axis = "L0"
        try:
            measure_value = max(0, min(9999, int(float(cfg.extra.get("measure_value", 5000)))))
        except (TypeError, ValueError):
            measure_value = 5000
        self.measure_axis = tk.StringVar(value=measure_axis)
        self.measure_value = tk.IntVar(value=measure_value)
        self.measure_live = tk.BooleanVar(value=bool(cfg.extra.get("measure_live", True)))
        self.activity = tk.StringVar(value=f"{self._t('活动')}: 0.000")
        self.record_status = tk.StringVar(value=self._t("未录制"))
        self._last_axis_values = {axis: 5000 for axis in SIX_AXES}
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._previous_l0_value = 5000
        self._script_history: deque[tuple[float, dict[str, int]]] = deque(maxlen=900)
        self._last_measure_sent = 0.0
        self._live_output_mapping_dirty = True
        self._analysis_preferences.apply(self._analysis_variables())
        self.min_value.trace_add("write", lambda *_args: self._refresh_limit_text())
        self.max_value.trace_add("write", lambda *_args: self._refresh_limit_text())
        self.l0_travel_scale.trace_add("write", lambda *_args: self._sync_travel_slider(self.l0_travel_scale, self.l0_travel_slider, self.l0_travel_text))
        self.global_travel_scale.trace_add("write", lambda *_args: self._sync_travel_slider(self.global_travel_scale, self.global_travel_slider, self.global_travel_text))
        for axis in self.six_axis_travel_scale_vars:
            self.six_axis_travel_scale_vars[axis].trace_add(
                "write",
                lambda *_args, axis_name=axis: self._sync_travel_slider(
                    self.six_axis_travel_scale_vars[axis_name],
                    self.six_axis_travel_slider_vars[axis_name],
                    self.six_axis_travel_text_vars[axis_name],
                ),
            )
        self.show_more_settings.trace_add("write", lambda *_args: self._refresh_more_settings())
        self.show_measurement_limits.trace_add("write", lambda *_args: self._refresh_measurement_limits())
        self.show_six_axis_tuning.trace_add("write", lambda *_args: self._refresh_six_axis_tuning())
        self.show_rtm_pose_3d_settings.trace_add("write", lambda *_args: self._refresh_rtm_pose_3d_settings())
        self.show_six_axis_travel_scales.trace_add("write", lambda *_args: self._refresh_six_axis_travel_scales())
        self.rtm_hybrid_l0_enabled.trace_add("write", self._refresh_hybrid_source)
        self.rtm_pose_gpu_enabled.trace_add("write", lambda *_args: self._schedule_rtm_pose_gpu_status_refresh())
        self.rtm_pose_gpu_backend.trace_add("write", lambda *_args: self._on_gpu_backend_changed())
        self.tracker_mode.trace_add("write", lambda *_args: self._on_tracker_mode_changed())
        self.hybrid_v2_pose_enabled.trace_add("write", lambda *_args: self._on_tracker_mode_changed())
        self.output_mode.trace_add("write", lambda *_args: self._on_tracker_mode_changed())
        self.rtm_pose_model_path.trace_add("write", lambda *_args: self._store_active_rtm_pose_model_path())
        self.sink_type.trace_add("write", self._on_native_output_changed)
        self.pose_l0_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v1"))
        self.pose_six_axis_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v1"))
        self.pose_v2_dance_six_axis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v2_mode"))
        self.pose_v2_l0_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v2_bias"))
        self.pose_v2_six_axis_analysis.trace_add("write", lambda *_args: self._sync_pose_mode_selection("v2_bias"))
        for variable in (
            self.pose_l0_analysis,
            self.pose_six_axis_analysis,
            self.pose_l0_weight,
            self.pose_six_axis_weight,
            self.pose_v2_dance_six_axis,
            self.pose_v2_l0_analysis,
            self.pose_v2_six_axis_analysis,
            self.pose_v2_l0_weight,
            self.pose_v2_six_axis_weight,
            self.rtm_pose_3d_enabled,
            self.rtm_pose_3d_weight,
            self.rtm_hybrid_l0_enabled,
            self.rtm_hybrid_l0_weight,
        ):
            variable.trace_add("write", lambda *_args: self._refresh_pose_base_weight_texts())
        self._refresh_pose_base_weight_texts()
        self._schedule_rtm_pose_gpu_status_refresh()
        for axis in SIX_AXES:
            self.axis_min_vars[axis].trace_add("write", lambda *_args, axis_name=axis: self._refresh_axis_limit_text(axis_name))
            self.axis_max_vars[axis].trace_add("write", lambda *_args, axis_name=axis: self._refresh_axis_limit_text(axis_name))
        live_mapping_vars: list[tk.Variable] = [
            self.endpoint_slowdown_enabled, self.endpoint_slowdown_pct,
            self.output_mode,
            self.min_value,
            self.max_value,
            self.max_step,
            self.enable_speed_limit,
            self.invert,
            self.l0_travel_scale,
            self.global_travel_scale,
            self.six_axis_travel_invert,
        ]
        live_mapping_vars.extend(self.axis_min_vars.values())
        live_mapping_vars.extend(self.axis_max_vars.values())
        live_mapping_vars.extend(self.six_axis_travel_scale_vars.values())
        live_mapping_vars.extend(self.axis_output_invert_vars.values())
        for variable in live_mapping_vars:
            variable.trace_add("write", lambda *_args: self._mark_live_output_mapping_dirty())
        self._refresh_active_rtm_pose_model_path()
        for variable in (self.rtm_pose_reject_enabled, self.rtm_pose_micro_smooth_enabled,
                         self.rtm_pose_flow_enabled, self.rtm_pose_kalman_enabled, self.visual_processing_edge):
            variable.trace_add("write", self._visual_options_changed)
        self._visual_options_changed()
        self.pose_auto_l0_enabled.trace_add("write", self._pose_auto_l0_changed)
        self.pose_pattern_enabled.trace_add("write", self._pose_auto_l0_changed)
        self.pose_fast_v1_enabled.trace_add("write", self._pose_auto_l0_changed)
        self.v2_l0_reference.trace_add('write', self._pose_auto_l0_changed)
        for variable in (*self._v2_model_variables().values(), self.tracker_mode,
                         self.rtm_pose_gpu_enabled, self.rtm_pose_gpu_backend):
            variable.trace_add("write", self._v2_model_options_changed)
        self._v2_model_options_changed()
        self.compression_latency.trace_add("write", self._visual_options_changed)
        for variable in (self.x, self.y, self.width, self.height, self.source_mode, self.video_path):
            variable.trace_add("write", self._input_geometry_changed)

    def _config_variables(self) -> list[tk.Variable]:
        variables: list[tk.Variable] = [
            *self._v2_model_variables().values(),
            self.v2_l0_reference,
            self.pose_auto_l0_enabled,
            self.pose_pattern_enabled,
            self.pose_fast_v1_enabled,
            self.endpoint_slowdown_enabled, self.endpoint_slowdown_pct,
            self.hybrid_v2_pose_enabled, self.visual_processing_edge, self.rtm_pose_reject_enabled,
            self.rtm_pose_micro_smooth_enabled, self.rtm_hybrid_source,
            self.x,
            self.y,
            self.width,
            self.height,
            self.fps,
            self.output_curve_fitting,
            self.source_mode,
            self.video_path,
            self.output_mode,
            self.audio_mode,
            self.audio_gain,
            self.audio_threshold,
            self.audio_smoothing,
            self.audio_device,
            self.smoothing,
            self.enable_smoothing,
            self.deadzone,
            self.enable_deadzone,
            self.enable_l0_jitter_guard,
            self.l0_guard_strength,
            self.enable_extreme_reset,
            self.extreme_hold_ms,
            self.enable_endpoint_guard,
            self.endpoint_margin_pct,
            self.pose_l0_analysis,
            self.pose_six_axis_analysis,
            self.pose_l0_weight,
            self.pose_six_axis_weight,
            self.pose_v2_dance_six_axis,
            self.pose_v2_l0_analysis,
            self.pose_v2_six_axis_analysis,
            self.pose_v2_l0_weight,
            self.pose_v2_six_axis_weight,
            self.rtm_pose_3d_enabled,
            self.rtm_pose_2d_model_path,
            self.rtm_pose_3d_model_path,
            self.rtm_pose_3d_weight,
            self.rtm_hybrid_l0_enabled,
            self.rtm_hybrid_l0_weight,
            self.rtm_pose_gpu_enabled,
            self.rtm_pose_gpu_backend,
            self.rtm_pose_flow_enabled,
            self.rtm_pose_kalman_enabled,
            self.tracker_mode,
            self.response_curve,
            self.motion_gain,
            self.visual_stroke_scale,
            self.compression_latency,
            self.l0_travel_scale,
            self.global_travel_scale,
            self.six_axis_travel_invert,
            self.play_preset_level,
            self.six_axis_intensity,
            self.six_axis_jitter_reduction,
            self.six_axis_sensitivity_level,
            self.show_more_settings,
            self.show_measurement_limits,
            self.show_six_axis_tuning,
            self.show_rtm_pose_3d_settings,
            self.show_six_axis_travel_scales,
            self.min_activity,
            self.enable_activity_gate,
            self.max_step,
            self.enable_speed_limit,
            self.idle_mode,
            self.invert,
            self.enable_startup_ramp,
            self.startup_ramp_ms,
            self.axis,
            self.interval_ms,
            self.sink_type,
            self.serial_port,
            self.baudrate,
            self.ble_name,
            self.ble_address,
            self.ble_service_uuid,
            self.ble_write_uuid,
            self.measure_axis,
            self.measure_value,
            self.measure_live,
        ]
        variables.extend(self.axis_min_vars.values())
        variables.extend(self.axis_max_vars.values())
        variables.extend(self.six_axis_travel_scale_vars.values())
        variables.extend(self.axis_output_invert_vars.values())
        variables.extend(self.six_axis_gain_vars.values())
        variables.extend(self.six_axis_invert_vars.values())
        return variables
