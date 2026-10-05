"""Autosave, restoring defaults and saved configuration mapping.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from ..analyzer import SIX_AXES
from ..capture import capture_fps
from ..config import AppConfig, DEFAULT_AXIS_OUTPUT_INVERTS, DEFAULT_SIX_AXIS_GAINS, DEFAULT_SIX_AXIS_INVERTS, DEFAULT_SIX_AXIS_TRAVEL_SCALES, HYBRID_V2_MODE
from ..analysis_preferences import AnalysisPreferences, defaults as analysis_defaults


class SettingsMixin:
    def _install_config_autosave(self) -> None:
        for variable in self._config_variables():
            variable.trace_add("write", lambda *_args: self._schedule_config_save())

    def _schedule_config_save(self) -> None:
        if self._config_autosave_suspended:
            return
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
        self._config_save_after_id = self.after(650, self._autosave_config)

    def _autosave_config(self) -> None:
        self._config_save_after_id = None
        if self._config_autosave_suspended:
            return
        self._save_config()

    def reset_all_settings(self) -> None:
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            messagebox.showwarning(self._t("正在运行"), self._t("请先停止实时输出，再恢复默认设置。"))
            return
        confirmed = messagebox.askyesno(
            self._t("恢复所有默认设置"),
            self._t("确认要恢复所有默认设置吗？") + "\n\n"
            + self._t("这会重置屏幕区域、输出方式、串口/BLE 信息、上下限、倍率、五档预设、六轴参数、声音参数和高级参数。")
            + "\n" + self._t("当前本地保存的设置会被覆盖。"),
        )
        if not confirmed:
            return

        self._config_autosave_suspended = True
        if self._config_save_after_id is not None:
            try:
                self.after_cancel(self._config_save_after_id)
            except tk.TclError:
                pass
            self._config_save_after_id = None
        try:
            self.stop()
            self.disconnect_sink()
            self._cancel_v2_model_downloads()
            if hasattr(self, "preview_button"):
                self.preview_button.configure(text=self._t("显示预览"))

            defaults = AppConfig()
            self.config_model = defaults
            self.x.set(defaults.x)
            self.y.set(defaults.y)
            self.width.set(defaults.width)
            self.height.set(defaults.height)
            self.fps.set(defaults.fps)
            self.output_curve_fitting.set(True)
            self.endpoint_slowdown_enabled.set(True)
            self.endpoint_slowdown_pct.set(10)
            self.source_mode.set("Screen")
            self.video_path.set("")
            self.output_mode.set("L0 Only")
            self.audio_mode.set(defaults.audio_mode)
            self.audio_gain.set(defaults.audio_gain)
            self.audio_threshold.set(defaults.audio_threshold)
            self.audio_smoothing.set(defaults.audio_smoothing)
            self.audio_device.set(defaults.audio_device)
            for axis in SIX_AXES:
                self.axis_min_vars[axis].set(defaults.axis_limits[axis][0])
                self.axis_max_vars[axis].set(defaults.axis_limits[axis][1])
            self.smoothing.set(defaults.smoothing)
            self.enable_smoothing.set(defaults.enable_smoothing)
            self.deadzone.set(defaults.deadzone)
            self.enable_deadzone.set(defaults.enable_deadzone)
            self.enable_l0_jitter_guard.set(True)
            self.l0_guard_strength.set(0.70)
            self.enable_extreme_reset.set(True)
            self.extreme_hold_ms.set(850)
            self.enable_endpoint_guard.set(True)
            self.endpoint_margin_pct.set(10)
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
            self.pose_l0_weight.set(60)
            self.pose_six_axis_weight.set(60)
            self.pose_v2_dance_six_axis.set(False)
            self.pose_v2_l0_analysis.set(False)
            self.pose_v2_six_axis_analysis.set(False)
            self.pose_v2_l0_weight.set(60)
            self.pose_v2_six_axis_weight.set(60)
            self.rtm_pose_3d_enabled.set(False)
            self.rtm_pose_2d_model_path.set("")
            self.rtm_pose_3d_model_path.set("")
            self.rtm_pose_3d_weight.set(100)
            self.rtm_hybrid_l0_enabled.set(False)
            self.pose_auto_l0_enabled.set(True)
            self.pose_pattern_enabled.set(False)
            self.pose_fast_v1_enabled.set(True)
            self.rtm_hybrid_l0_weight.set(30)
            self.rtm_pose_gpu_enabled.set(False)
            self.rtm_pose_gpu_backend.set("cuda")
            self.rtm_pose_flow_enabled.set(False)
            self.rtm_pose_kalman_enabled.set(False)
            self.hybrid_v2_pose_enabled.set(False)
            self.v2_vittrack_enabled.set(False)
            self.v2_neuflow_enabled.set(False)
            self.v2_vittrack_model_path.set("")
            self.v2_neuflow_model_path.set("")
            self.v2_l0_reference.set('fusion')
            self.rtm_pose_reject_enabled.set(False)
            self.rtm_pose_micro_smooth_enabled.set(False)
            self.visual_processing_edge.set(640)
            self.rtm_hybrid_source.set(HYBRID_V2_MODE)
            self._set_tracker_mode(defaults.tracker_mode)
            self.response_curve.set(defaults.response_curve)
            self.motion_gain.set(defaults.motion_gain)
            self.visual_stroke_scale.set(defaults.visual_stroke_scale)
            self.compression_latency.set(0)
            self.l0_travel_scale.set(defaults.global_travel_scale)
            self.global_travel_scale.set(defaults.global_travel_scale)
            self.six_axis_travel_invert.set(False)
            for axis, value in DEFAULT_SIX_AXIS_TRAVEL_SCALES.items():
                self.six_axis_travel_scale_vars[axis].set(value)
            for axis, inverted in DEFAULT_AXIS_OUTPUT_INVERTS.items():
                self.axis_output_invert_vars[axis].set(inverted)
            self.six_axis_intensity.set(65)
            self.six_axis_jitter_reduction.set(55)
            self.six_axis_sensitivity_level.set(5)
            self.show_more_settings.set(False)
            self.show_measurement_limits.set(True)
            self.show_six_axis_tuning.set(False)
            self.show_rtm_pose_3d_settings.set(False)
            self.show_six_axis_travel_scales.set(False)
            for axis, gain in DEFAULT_SIX_AXIS_GAINS.items():
                self.six_axis_gain_vars[axis].set(gain)
            for axis, inverted in DEFAULT_SIX_AXIS_INVERTS.items():
                self.six_axis_invert_vars[axis].set(inverted)
            self.min_activity.set(defaults.min_activity)
            self.enable_activity_gate.set(defaults.enable_activity_gate)
            self.max_step.set(defaults.max_step)
            self.enable_speed_limit.set(defaults.enable_speed_limit)
            self.idle_mode.set(defaults.idle_mode)
            self.invert.set(defaults.invert)
            self.enable_startup_ramp.set(defaults.enable_startup_ramp)
            self.startup_ramp_ms.set(defaults.startup_ramp_ms)
            self.axis.set(defaults.axis)
            self.interval_ms.set(defaults.output_interval_ms)
            self.sink_type.set(defaults.last_sink)
            self.serial_port.set(defaults.serial_port)
            self.baudrate.set(defaults.baudrate)
            self.ble_name.set(defaults.ble_name)
            self.ble_address.set(defaults.ble_address)
            self.ble_service_uuid.set(defaults.ble_service_uuid)
            self.ble_write_uuid.set(defaults.ble_write_uuid)
            self.measure_axis.set("L0")
            self.measure_value.set(5000)
            self.measure_live.set(True)
            self.apply_play_preset(3, announce=False)
            self._last_axis_values = {axis: 5000 for axis in SIX_AXES}
            self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
            self._previous_l0_value = 5000
            self._script_history.clear()
            self.output_value.set("L05000I20")
            self.l0_status.set("L0 5000")
            self.stroke_status.set(f"{self._t('中段')} 50%")
            self.activity.set(f"{self._t('活动')}: 0.000")
            self.record_status.set(self._t("未录制"))
            self.device_status.set(f"{self._t('设备')}: {self._t('未连接')}")
            self._refresh_limit_text()
            self._draw_axis_monitor(self._last_axis_values)
            self._draw_script_curve()
            self._refresh_play_preset_buttons()
            self.config_model.extra["play_preset_initialized_v1"] = True
            self._analysis_preferences = AnalysisPreferences({key: analysis_defaults(key) for key in ("hybrid", "dance")}, defaults.tracker_mode)
            self._analysis_preferences.apply(self._analysis_variables())
            self.preview_tabs.select(self.output_tab)
            self.main_panes.reset_width()
        finally:
            self._config_autosave_suspended = False
        self._save_config()
        self.status.set(self._t("已恢复所有默认设置，并保存到本机"))

    def _save_config(self) -> None:
        self._analysis_preferences.remember(self._analysis_variables())
        self.config_model.extra["analysis_profiles"] = {key: dict(value) for key, value in self._analysis_preferences.profiles.items()}
        cfg = self.config_model
        if self.main_panes.preferred_width is None:
            cfg.extra.pop("sidebar_width_dip", None)
        else:
            cfg.extra["sidebar_width_dip"] = round(self.main_panes.preferred_width, 2)
        try:
            region = self._read_screen_region()
        except ValueError:
            pass  # Keep the last complete rectangle while an entry is unfinished.
        else:
            cfg.x, cfg.y, cfg.width, cfg.height = region.x, region.y, region.width, region.height
        cfg.fps = capture_fps(self.fps.get())
        cfg.extra["output_curve_fitting"] = bool(self.output_curve_fitting.get())
        cfg.extra["endpoint_slowdown_enabled"] = self._endpoint_options[0]
        cfg.extra["endpoint_slowdown_pct"] = round(self._endpoint_options[1]*100)
        cfg.extra["source_mode"] = self.source_mode.get()
        cfg.extra["video_path"] = self.video_path.get()
        cfg.extra["output_mode"] = self.output_mode.get()
        cfg.extra["play_preset_level"] = self.play_preset_level.get()
        cfg.extra["six_axis_intensity"] = self.six_axis_intensity.get()
        cfg.extra["six_axis_jitter_reduction"] = self.six_axis_jitter_reduction.get()
        cfg.extra["six_axis_sensitivity_level"] = self.six_axis_sensitivity_level.get()
        cfg.extra["show_more_settings"] = self.show_more_settings.get()
        cfg.extra["show_measurement_limits"] = self.show_measurement_limits.get()
        cfg.extra["show_six_axis_tuning"] = self.show_six_axis_tuning.get()
        cfg.extra["show_rtm_pose_3d_settings"] = self.show_rtm_pose_3d_settings.get()
        cfg.extra["show_six_axis_travel_scales"] = self.show_six_axis_travel_scales.get()
        cfg.extra["six_axis_travel_scales"] = {
            axis: self.six_axis_travel_scale_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["six_axis_travel_invert"] = self.six_axis_travel_invert.get()
        cfg.extra["axis_output_inverts"] = {
            axis: self.axis_output_invert_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["six_axis_gains"] = {
            axis: self.six_axis_gain_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["six_axis_inverts"] = {
            axis: self.six_axis_invert_vars[axis].get()
            for axis in ("L1", "L2", "R0", "R1", "R2")
        }
        cfg.extra["enable_l0_jitter_guard"] = self.enable_l0_jitter_guard.get()
        cfg.extra["l0_guard_strength"] = self.l0_guard_strength.get()
        cfg.extra["enable_extreme_reset"] = self.enable_extreme_reset.get()
        cfg.extra["extreme_hold_ms"] = self.extreme_hold_ms.get()
        cfg.extra["enable_endpoint_guard"] = self.enable_endpoint_guard.get()
        cfg.extra["endpoint_margin_pct"] = self.endpoint_margin_pct.get()
        cfg.extra["pose_dance_analysis"] = self.pose_l0_analysis.get() or self.pose_six_axis_analysis.get()
        cfg.extra["pose_l0_analysis"] = self.pose_l0_analysis.get()
        cfg.extra["pose_six_axis_analysis"] = self.pose_six_axis_analysis.get()
        cfg.extra["pose_l0_weight"] = self.pose_l0_weight.get()
        cfg.extra["pose_six_axis_weight"] = self.pose_six_axis_weight.get()
        cfg.extra["pose_v2_dance_six_axis"] = self.pose_v2_dance_six_axis.get()
        cfg.extra["pose_v2_l0_analysis"] = self.pose_v2_l0_analysis.get()
        cfg.extra["pose_v2_six_axis_analysis"] = self.pose_v2_six_axis_analysis.get()
        cfg.extra["pose_v2_l0_weight"] = self.pose_v2_l0_weight.get()
        cfg.extra["pose_v2_six_axis_weight"] = self.pose_v2_six_axis_weight.get()
        cfg.extra["rtm_pose_2d_model_path"] = self.rtm_pose_2d_model_path.get()
        for key in ("rtm_pose_3d_enabled", "rtm_pose_3d_model_path", "rtm_pose_3d_weight"):
            cfg.extra.pop(key, None)
        cfg.extra["visual_processing_edge"] = self.visual_processing_edge.get()
        cfg.extra["hybrid_v2_pose_enabled"] = self.hybrid_v2_pose_enabled.get()
        for name, variable in self._v2_model_variables().items():
            cfg.extra[f"v2_{name}"] = variable.get()
        cfg.extra['v2_l0_reference'] = self.v2_l0_reference.get()
        cfg.extra["rtm_pose_reject_enabled"] = self.rtm_pose_reject_enabled.get()
        cfg.extra["rtm_pose_micro_smooth_enabled"] = self.rtm_pose_micro_smooth_enabled.get()
        cfg.extra["rtm_hybrid_source"] = HYBRID_V2_MODE
        cfg.extra["rtm_hybrid_l0_enabled"] = self.rtm_hybrid_l0_enabled.get()
        cfg.extra["pose_auto_l0_enabled"] = self.pose_auto_l0_enabled.get()
        cfg.extra["pose_pattern_enabled"] = self.pose_pattern_enabled.get()
        cfg.extra["pose_fast_v1_enabled"] = self.pose_fast_v1_enabled.get()
        cfg.extra["rtm_hybrid_l0_weight"] = max(1, min(100, int(self.rtm_hybrid_l0_weight.get())))
        cfg.extra["rtm_pose_gpu_enabled"] = self.rtm_pose_gpu_enabled.get()
        cfg.extra["rtm_pose_gpu_backend"] = self.rtm_pose_gpu_backend.get()
        cfg.extra["rtm_pose_flow_enabled"] = self.rtm_pose_flow_enabled.get()
        cfg.extra["rtm_pose_kalman_enabled"] = self.rtm_pose_kalman_enabled.get()
        cfg.extra["l0_travel_scale"] = self.l0_travel_scale.get()
        cfg.extra["compression_latency"] = max(-5, min(5, int(self.compression_latency.get())))
        cfg.extra["measure_axis"] = self.measure_axis.get()
        cfg.extra["measure_value"] = self.measure_value.get()
        cfg.extra["measure_live"] = self.measure_live.get()
        cfg.min_value = self.min_value.get()
        cfg.max_value = self.max_value.get()
        cfg.axis_limits = {
            axis: [self.axis_min_vars[axis].get(), self.axis_max_vars[axis].get()]
            for axis in SIX_AXES
        }
        cfg.smoothing = self.smoothing.get()
        cfg.enable_smoothing = self.enable_smoothing.get()
        cfg.deadzone = self.deadzone.get()
        cfg.enable_deadzone = self.enable_deadzone.get()
        cfg.tracker_mode = self._tracker_internal(self.tracker_mode.get())
        cfg.extra["ui_language"] = self.ui_language
        cfg.response_curve = self.response_curve.get()
        cfg.motion_gain = self.motion_gain.get()
        cfg.visual_stroke_scale = self.visual_stroke_scale.get()
        cfg.global_travel_scale = self.global_travel_scale.get()
        cfg.min_activity = self.min_activity.get()
        cfg.enable_activity_gate = self.enable_activity_gate.get()
        cfg.max_step = self.max_step.get()
        cfg.enable_speed_limit = self.enable_speed_limit.get()
        cfg.idle_mode = self.idle_mode.get()
        cfg.invert = self.invert.get()
        cfg.enable_startup_ramp = self.enable_startup_ramp.get()
        cfg.startup_ramp_ms = self.startup_ramp_ms.get()
        cfg.axis = self.axis.get()
        cfg.output_interval_ms = self.interval_ms.get()
        cfg.serial_port = self.serial_port.get()
        cfg.baudrate = self.baudrate.get()
        cfg.ble_name = self.ble_name.get()
        cfg.ble_address = self.ble_address.get()
        cfg.ble_service_uuid = self.ble_service_uuid.get()
        cfg.ble_write_uuid = self.ble_write_uuid.get()
        cfg.last_sink = self.sink_type.get()
        cfg.audio_mode = self.audio_mode.get()
        cfg.audio_gain = self.audio_gain.get()
        cfg.audio_threshold = self.audio_threshold.get()
        cfg.audio_smoothing = self.audio_smoothing.get()
        cfg.audio_device = self.audio_device.get()
        cfg.save()
