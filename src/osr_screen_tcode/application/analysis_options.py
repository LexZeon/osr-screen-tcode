"""Analysis-mode visibility, selected profiles and option callbacks.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
from dataclasses import replace
import tkinter as tk
from ..config import RTM_POSE_2D_MODE, HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE
from ..analysis_preferences import defaults as analysis_defaults
from ..visual_pipeline import VisualSettings
from ..visual_lab.stabilizer import Options


class AnalysisOptionsMixin:
    def _on_tracker_mode_changed(self) -> None:
        is_rtm = self._rtm_pose_mode_active()
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            self.stop()
        self._analysis_preferences.switch(self._tracker_internal(self.tracker_mode.get()), self._analysis_variables())
        if hasattr(self, "integrated_preview"):
            self.reset_visual_reference()
            self.integrated_preview.refresh_mode()
        self.rtm_pose_3d_enabled.set(self._rtm_pose_3d_mode_active())
        self.rtm_pose_3d_weight.set(100 if is_rtm else 0)
        self._refresh_active_rtm_pose_model_path()
        self._refresh_pose_base_weight_texts()
        self._refresh_rtm_pose_3d_settings()
        self._refresh_hybrid_source()

    def _analysis_variables(self):
        return {name: getattr(self, name) for name in analysis_defaults("dance")}

    @staticmethod
    def _analysis_visibility(mode, blend_enabled, source_label, assist=None, blend_widgets=()):
        dance = mode == RTM_POSE_2D_MODE
        for widget in blend_widgets:
            widget.grid() if dance else widget.grid_remove()
        source_label.grid() if dance and blend_enabled else source_label.grid_remove()
        if assist is not None:
            assist.grid() if mode in (HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE) else assist.grid_remove()
            assist.configure(state="normal" if mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE) else "disabled")

    def _refresh_hybrid_source(self, *_args):
        if hasattr(self, "rtm_hybrid_source_label"):
            self._analysis_visibility(self._tracker_internal(self.tracker_mode.get()), self.rtm_hybrid_l0_enabled.get(),
                self.rtm_hybrid_source_label, blend_widgets=self._rtm_blend_widgets)

    @staticmethod
    def _normalize_tracker_mode(value: str) -> str:
        aliases = {
            "混合分析（内测）": HYBRID_MODE,
            "Hybrid Analysis (Internal Test)": HYBRID_MODE,
            "Hybrid Analysis (Recommended - Large Planar Motion)": HYBRID_MODE,
            "混合分析（推荐）": HYBRID_MODE,
            "Hybrid Analysis (Recommended)": HYBRID_MODE,
            "Hybrid Analysis (Recommended - Non-Dance)": HYBRID_MODE,
            "RTM Pose": RTM_POSE_2D_MODE,
            "RTM Pose（推荐-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose 2D": RTM_POSE_2D_MODE,
            "RTM Pose 2D（推荐-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose 2D (Recommended - Dance)": RTM_POSE_2D_MODE,
            "RTM Pose 3D": RTM_POSE_2D_MODE,
            "RTM Pose 3D（推荐-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose 3D（高延迟-舞蹈）": RTM_POSE_2D_MODE,
            "RTM Pose (Recommended - Dance)": RTM_POSE_2D_MODE,
            "RTM Pose 3D (Higher Latency - Dance)": RTM_POSE_2D_MODE,
        }
        aliases.update({"混合分析（推荐-非舞蹈）": HYBRID_MODE, "混合分析 v2（画面运动 v2，仅 L0）": HYBRID_V2_MODE, "Hybrid Analysis v2 (Image Motion v2, L0 only)": HYBRID_V2_MODE, "混合分析v2": HYBRID_V2_MODE, "混合分析 v2": HYBRID_V2_MODE,
                        "Hybrid Analysis v2": HYBRID_V2_MODE})
        return aliases.get(value, value)

    def _pose_auto_l0_changed(self, *_args):
        self._visual_settings = replace(self._visual_settings, pose_auto_l0=self.pose_auto_l0_enabled.get(),
                                        pose_pattern=self.pose_pattern_enabled.get(),
                                        pose_fast_v1=self.pose_fast_v1_enabled.get(),
                                        v2_l0_reference=self.v2_l0_reference.get())

    def _visual_options_changed(self, *_args):
        self._visual_generation += 1
        self._visual_settings = VisualSettings(int(self.visual_processing_edge.get()),
            Options(self.rtm_pose_reject_enabled.get(), self.rtm_pose_flow_enabled.get(),
                    self.rtm_pose_kalman_enabled.get(), self.rtm_pose_micro_smooth_enabled.get()),
            self._visual_generation, pose_auto_l0=self.pose_auto_l0_enabled.get(),
            pose_pattern=self.pose_pattern_enabled.get(), pose_fast_v1=self.pose_fast_v1_enabled.get(),
            v2_l0_reference=self.v2_l0_reference.get())
        if hasattr(self, "integrated_preview"):
            self.integrated_preview.clear()

    def reset_visual_reference(self):
        self._visual_options_changed()

    def _clamped_percent(self, value: object, default: int = 0) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (tk.TclError, TypeError, ValueError):
            return default

    def _pose_base_weight_label(self, enabled: bool, pose_weight: object, label_key: str) -> str:
        pose_value = self._clamped_percent(pose_weight)
        base_value = 100 - pose_value if enabled else 100
        return f"{self._t(label_key)}: {base_value}%"

    def _sync_pose_mode_selection(self, source: str) -> None:
        if self._pose_mode_syncing:
            return
        self._pose_mode_syncing = True
        try:
            if source == "v2_mode":
                if self.pose_v2_dance_six_axis.get():
                    self.pose_l0_analysis.set(False)
                    self.pose_six_axis_analysis.set(False)
                    if not self.pose_v2_l0_analysis.get() and not self.pose_v2_six_axis_analysis.get():
                        self.pose_v2_six_axis_analysis.set(True)
                else:
                    self.pose_v2_l0_analysis.set(False)
                    self.pose_v2_six_axis_analysis.set(False)
            elif source == "v2_bias":
                if self.pose_v2_l0_analysis.get() or self.pose_v2_six_axis_analysis.get():
                    self.pose_v2_dance_six_axis.set(True)
                    self.pose_l0_analysis.set(False)
                    self.pose_six_axis_analysis.set(False)
            elif source == "v1" and (self.pose_l0_analysis.get() or self.pose_six_axis_analysis.get()):
                self.pose_v2_dance_six_axis.set(False)
                self.pose_v2_l0_analysis.set(False)
                self.pose_v2_six_axis_analysis.set(False)
        finally:
            self._pose_mode_syncing = False
        self._refresh_pose_base_weight_texts()

    def _refresh_pose_base_weight_texts(self) -> None:
        if hasattr(self, "pose_l0_base_weight_text"):
            self.pose_l0_base_weight_text.set(
                self._pose_base_weight_label(self.pose_l0_analysis.get(), self.pose_l0_weight.get(), "基础分析 L0 权重")
            )
        if hasattr(self, "pose_six_axis_base_weight_text"):
            self.pose_six_axis_base_weight_text.set(
                self._pose_base_weight_label(
                    self.pose_six_axis_analysis.get(),
                    self.pose_six_axis_weight.get(),
                    "基础分析六轴权重",
                )
            )
        if hasattr(self, "pose_v2_l0_base_weight_text"):
            self.pose_v2_l0_base_weight_text.set(
                self._pose_base_weight_label(self.pose_v2_l0_analysis.get(), self.pose_v2_l0_weight.get(), "基础分析 v2 L0 权重")
            )
        if hasattr(self, "pose_v2_six_axis_base_weight_text"):
            self.pose_v2_six_axis_base_weight_text.set(
                self._pose_base_weight_label(
                    self.pose_v2_six_axis_analysis.get(),
                    self.pose_v2_six_axis_weight.get(),
                    "基础分析 v2 六轴权重",
                )
            )
        if hasattr(self, "rtm_pose_3d_base_weight_text"):
            self.rtm_pose_3d_base_weight_text.set(
                self._pose_base_weight_label(self._rtm_pose_mode_active(), self.rtm_pose_3d_weight.get(), "基础分析 RTM 权重")
            )
        if hasattr(self, "rtm_model_l0_weight_text"):
            model_weight = 100
            if self.rtm_hybrid_l0_enabled.get():
                model_weight = max(0, 100 - self._clamped_percent(self.rtm_hybrid_l0_weight.get(), 30))
            self.rtm_model_l0_weight_text.set(f"{self._t('当前本模型分析权重')}: {model_weight}%")
