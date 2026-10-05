"""Realtime-start confirmation and its original geometry lifecycle.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
from ..screen_geometry import move_physical_window
import tkinter as tk
from tkinter import messagebox, ttk
from ..analyzer import SIX_AXES
from ..capture import capture_fps
from ..config import HYBRID_V2_MODE
from ..analysis_preferences import AnalysisPreferences
from ..ui_widgets import WideCombobox, monitor_workarea
from .translations import TRACKER_MODE_CHOICES
from .tooltips import Tooltip


class StartDialogMixin:
    def _restore_start_geometry_once(self) -> None:
        geometry = self._startup_window_geometry
        if geometry:
            self.geometry(geometry)

    def _release_start_geometry(self) -> None:
        self._startup_window_geometry = None

    def _confirm_realtime_start(self) -> bool:
        dialog = tk.Toplevel(self)
        dialog.title(self._t("开始实时输出前确认"))
        dialog.transient(self)
        dialog.resizable(True, True)
        dialog.grab_set()

        mode = tk.StringVar(value=self.output_mode.get() if self.output_mode.get() in ("L0 Only", "Six Axis") else "L0 Only")
        current_tracker = self._tracker_internal(self.tracker_mode.get())
        if current_tracker not in TRACKER_MODE_CHOICES:
            current_tracker = HYBRID_V2_MODE
        tracker = tk.StringVar(value=self._tracker_display(current_tracker))
        pose_l0 = tk.BooleanVar(value=self.pose_l0_analysis.get())
        pose_six = tk.BooleanVar(value=self.pose_six_axis_analysis.get())
        pose_l0_weight = tk.IntVar(value=self.pose_l0_weight.get())
        pose_six_weight = tk.IntVar(value=self.pose_six_axis_weight.get())
        pose_v2 = tk.BooleanVar(value=self.pose_v2_dance_six_axis.get())
        pose_v2_l0 = tk.BooleanVar(value=self.pose_v2_l0_analysis.get())
        pose_v2_six = tk.BooleanVar(value=self.pose_v2_six_axis_analysis.get())
        pose_v2_l0_weight = tk.IntVar(value=self.pose_v2_l0_weight.get())
        pose_v2_six_weight = tk.IntVar(value=self.pose_v2_six_axis_weight.get())
        rtm_pose_3d = tk.BooleanVar(value=self._rtm_pose_mode_active(current_tracker))
        rtm_pose_2d_model = tk.StringVar(value=self.rtm_pose_2d_model_path.get())
        rtm_pose_3d_model = tk.StringVar(value=self.rtm_pose_3d_model_path.get())
        rtm_popup_model_path = tk.StringVar()
        rtm_pose_3d_weight = tk.IntVar(value=self.rtm_pose_3d_weight.get())
        rtm_hybrid_l0_enabled = tk.BooleanVar(value=self.rtm_hybrid_l0_enabled.get())
        pose_auto_l0_enabled = tk.BooleanVar(value=self.pose_auto_l0_enabled.get())
        pose_pattern_enabled = tk.BooleanVar(value=self.pose_pattern_enabled.get())
        pose_fast_v1_enabled = tk.BooleanVar(value=self.pose_fast_v1_enabled.get())
        rtm_hybrid_l0_weight = tk.IntVar(value=self.rtm_hybrid_l0_weight.get())
        rtm_pose_gpu_enabled = tk.BooleanVar(value=self.rtm_pose_gpu_enabled.get())
        rtm_pose_gpu_status_text = tk.StringVar()
        rtm_pose_flow_enabled = tk.BooleanVar(value=self.rtm_pose_flow_enabled.get())
        rtm_pose_kalman_enabled = tk.BooleanVar(value=self.rtm_pose_kalman_enabled.get())
        rtm_pose_reject_enabled = tk.BooleanVar(value=self.rtm_pose_reject_enabled.get())
        rtm_pose_micro_smooth_enabled = tk.BooleanVar(value=self.rtm_pose_micro_smooth_enabled.get())
        rtm_hybrid_source = tk.StringVar(value=HYBRID_V2_MODE)
        hybrid_v2_pose = tk.BooleanVar(value=self.hybrid_v2_pose_enabled.get())
        v2_l0_reference = tk.StringVar(value=self.v2_l0_reference.get())
        v2_model_variables = {name: type(variable)(value=variable.get())
                              for name, variable in self._v2_model_variables().items()}
        compression_latency = tk.IntVar(value=self.compression_latency.get())
        capture_rate = tk.IntVar(value=self._capture_target_fps)
        curve_fitting = tk.BooleanVar(value=self.output_curve_fitting.get())
        endpoint_enabled = tk.BooleanVar(value=self.endpoint_slowdown_enabled.get())
        endpoint_percent = tk.DoubleVar(value=self.endpoint_slowdown_pct.get())
        self._analysis_preferences.remember(self._analysis_variables())
        popup_preferences = AnalysisPreferences(self._analysis_preferences.profiles, current_tracker)
        popup_variables = {
            "pose_auto_l0_enabled": pose_auto_l0_enabled,
            "pose_pattern_enabled": pose_pattern_enabled,
            "pose_fast_v1_enabled": pose_fast_v1_enabled,
            "fps": capture_rate, "output_curve_fitting": curve_fitting, "compression_latency": compression_latency,
            "rtm_pose_gpu_enabled": rtm_pose_gpu_enabled, "rtm_hybrid_l0_enabled": rtm_hybrid_l0_enabled,
            "rtm_hybrid_l0_weight": rtm_hybrid_l0_weight, "rtm_pose_flow_enabled": rtm_pose_flow_enabled,
            "rtm_pose_kalman_enabled": rtm_pose_kalman_enabled, "rtm_pose_reject_enabled": rtm_pose_reject_enabled,
            "rtm_pose_micro_smooth_enabled": rtm_pose_micro_smooth_enabled,
        }
        pose_l0_base_text = tk.StringVar()
        pose_six_base_text = tk.StringVar()
        pose_v2_l0_base_text = tk.StringVar()
        pose_v2_six_base_text = tk.StringVar()
        rtm_pose_3d_base_text = tk.StringVar()
        rtm_popup_model_l0_text = tk.StringVar()
        result = {"ok": False}
        pose_popup_syncing = False
        rtm_popup_path_syncing = False

        def active_popup_rtm_model_var() -> tk.StringVar:
            return rtm_pose_2d_model

        def refresh_popup_rtm_model_path(*_args: object) -> None:
            nonlocal rtm_popup_path_syncing
            rtm_popup_path_syncing = True
            try:
                rtm_popup_model_path.set(active_popup_rtm_model_var().get())
            finally:
                rtm_popup_path_syncing = False

        def store_popup_rtm_model_path(*_args: object) -> None:
            if rtm_popup_path_syncing:
                return
            active_popup_rtm_model_var().set(rtm_popup_model_path.get())

        def refresh_pose_base_texts(*_args: object) -> None:
            pose_l0_base_text.set(self._pose_base_weight_label(pose_l0.get(), pose_l0_weight.get(), "基础分析 L0 权重"))
            pose_six_base_text.set(self._pose_base_weight_label(pose_six.get(), pose_six_weight.get(), "基础分析六轴权重"))
            pose_v2_l0_base_text.set(self._pose_base_weight_label(pose_v2_l0.get(), pose_v2_l0_weight.get(), "基础分析 v2 L0 权重"))
            pose_v2_six_base_text.set(self._pose_base_weight_label(pose_v2_six.get(), pose_v2_six_weight.get(), "基础分析 v2 六轴权重"))
            rtm_pose_3d_base_text.set(self._pose_base_weight_label(rtm_pose_3d.get(), rtm_pose_3d_weight.get(), "基础分析 RTM 权重"))
            model_weight = 100
            if rtm_hybrid_l0_enabled.get():
                model_weight = max(0, 100 - self._clamped_percent(rtm_hybrid_l0_weight.get(), 30))
            rtm_popup_model_l0_text.set(f"{self._t('当前本模型分析权重')}: {model_weight}%")

        def refresh_popup_gpu_status(*_args: object) -> None:
            self._schedule_rtm_pose_gpu_status_refresh()

        def sync_popup_pose_mode(source: str) -> None:
            nonlocal pose_popup_syncing
            if pose_popup_syncing:
                return
            pose_popup_syncing = True
            try:
                if source == "v2_mode":
                    if pose_v2.get():
                        pose_l0.set(False)
                        pose_six.set(False)
                        if not pose_v2_l0.get() and not pose_v2_six.get():
                            pose_v2_six.set(True)
                    else:
                        pose_v2_l0.set(False)
                        pose_v2_six.set(False)
                elif source == "v2_bias":
                    if pose_v2_l0.get() or pose_v2_six.get():
                        pose_v2.set(True)
                        pose_l0.set(False)
                        pose_six.set(False)
                elif source == "v1" and (pose_l0.get() or pose_six.get()):
                    pose_v2.set(False)
                    pose_v2_l0.set(False)
                    pose_v2_six.set(False)
            finally:
                pose_popup_syncing = False
            refresh_pose_base_texts()

        pose_l0.trace_add("write", lambda *_args: sync_popup_pose_mode("v1"))
        pose_six.trace_add("write", lambda *_args: sync_popup_pose_mode("v1"))
        pose_v2.trace_add("write", lambda *_args: sync_popup_pose_mode("v2_mode"))
        pose_v2_l0.trace_add("write", lambda *_args: sync_popup_pose_mode("v2_bias"))
        pose_v2_six.trace_add("write", lambda *_args: sync_popup_pose_mode("v2_bias"))
        for variable in (
            pose_l0,
            pose_six,
            pose_l0_weight,
            pose_six_weight,
            pose_v2,
            pose_v2_l0,
            pose_v2_six,
            pose_v2_l0_weight,
            pose_v2_six_weight,
            rtm_pose_3d,
            rtm_pose_3d_weight,
            rtm_hybrid_l0_enabled,
            rtm_hybrid_l0_weight,
        ):
            variable.trace_add("write", refresh_pose_base_texts)
        rtm_pose_gpu_enabled.trace_add("write", refresh_popup_gpu_status)
        rtm_popup_model_path.trace_add("write", store_popup_rtm_model_path)
        refresh_pose_base_texts()
        refresh_popup_gpu_status()
        refresh_popup_rtm_model_path()

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        scroll = tk.Canvas(dialog, highlightthickness=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=scroll.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        scroll.configure(yscrollcommand=scrollbar.set)
        body = ttk.Frame(scroll, padding=14)
        body_window = scroll.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(body_window, width=event.width))
        dialog.bind("<MouseWheel>", lambda event: scroll.yview_scroll(-int(event.delta / 120), "units"))
        body.columnconfigure(0, weight=1)

        ttk.Label(body, text="开始实时输出前确认", font=("", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="请先确认上下限已经调好。六轴模式会同时控制 L0/L1/L2/R0/R1/R2，建议先用较窄范围和低档测试。",
            wraplength=360,
            foreground="#555",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        region_text = tk.StringVar()

        def refresh_region_text() -> None:
            try:
                region = self._read_screen_region()
                region_text.set(f"{self._t('屏幕区域')}: X {region.x}  Y {region.y}  {region.width} × {region.height} px")
            except ValueError:
                region_text.set(self._dt("区域输入尚未完成，请重新框选。", "Region entry is incomplete; select a region again."))

        def choose_region() -> None:
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.withdraw()

            def restore(_accepted: bool) -> None:
                if not dialog.winfo_exists():
                    return
                refresh_region_text()
                dialog.deiconify()
                dialog.lift()
                dialog.focus_force()
                dialog.grab_set()

            self.pick_region(on_close=restore)

        region_box = ttk.LabelFrame(body, text="屏幕区域", padding=8)
        region_box.grid(row=2, column=0, sticky="ew")
        region_box.columnconfigure(0, weight=1)
        refresh_region_text()
        ttk.Label(region_box, textvariable=region_text, foreground="#333").grid(row=0, column=0, sticky="w")
        ttk.Button(region_box, text="框选屏幕区域", command=choose_region).grid(row=0, column=1, sticky="e", padx=(8, 0))

        choices = ttk.LabelFrame(body, text="输出模式", padding=8)
        choices.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Radiobutton(choices, text="L0 Only：只上下", variable=mode, value="L0 Only").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Radiobutton(choices, text="Six Axis：六轴", variable=mode, value="Six Axis").grid(row=1, column=0, sticky="w", pady=2)

        analysis = ttk.LabelFrame(body, text="分析", padding=8)
        analysis.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        analysis.columnconfigure(1, weight=1)
        WideCombobox(
            analysis,
            textvariable=tracker,
            values=self._tracker_choices(),
            state="readonly",
            width=28,
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        fps_frame = ttk.Frame(analysis)
        fps_frame.columnconfigure(1, weight=1)
        fps_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        next_row = self._endpoint_controls(fps_frame, 0, endpoint_enabled, endpoint_percent)
        next_row = self._capture_rate_controls(fps_frame, next_row, capture_rate)
        self._output_curve_control(fps_frame, next_row, curve_fitting)
        rtm_popup_frame = ttk.Frame(analysis)
        rtm_popup_frame.columnconfigure(1, weight=1)
        rtm_popup_hybrid_check = ttk.Checkbutton(rtm_popup_frame, text="混合分析 L0 权重", variable=rtm_hybrid_l0_enabled)
        rtm_popup_hybrid_check.grid(row=0, column=0, sticky="w", pady=2)
        Tooltip(rtm_popup_hybrid_check, self._tooltip_text("混合分析 L0 权重"))
        popup_blend_scale = ttk.Scale(rtm_popup_frame, from_=1, to=100, variable=rtm_hybrid_l0_weight)
        popup_blend_scale.grid(row=0, column=1, sticky="ew", pady=2)
        popup_blend_value = ttk.Label(rtm_popup_frame, textvariable=rtm_hybrid_l0_weight, width=4, anchor="e")
        popup_blend_value.grid(row=0, column=2, sticky="e")
        rtm_popup_model_label = ttk.Label(rtm_popup_frame, textvariable=rtm_popup_model_l0_text, foreground="#555")
        rtm_popup_model_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 5))
        Tooltip(rtm_popup_model_label, self._tooltip_text("当前本模型分析权重"))
        ttk.Label(rtm_popup_frame, text="RTM Pose 模型").grid(row=2, column=0, sticky="w", pady=2)
        rtm_popup_entry = ttk.Entry(rtm_popup_frame, textvariable=rtm_popup_model_path)
        rtm_popup_entry.grid(row=2, column=1, sticky="ew", pady=2)
        Tooltip(rtm_popup_entry, self._tooltip_text("RTM Pose 模型"))
        ttk.Button(
            rtm_popup_frame,
            text="选择模型",
            command=lambda: self._choose_rtm_pose_3d_model_for_var(rtm_popup_model_path, self._tracker_internal(tracker.get())),
        ).grid(
            row=2, column=2, sticky="ew", padx=(4, 0), pady=2
        )
        ttk.Button(
            rtm_popup_frame,
            textvariable=self.rtm_model_download_button_text,
            command=lambda: self.download_rtm_pose_3d_model(rtm_popup_model_path, self._tracker_internal(tracker.get())),
        ).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2)
        )
        ttk.Label(rtm_popup_frame, textvariable=self.rtm_model_download_status_text, foreground="#555", wraplength=360).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(0, 2)
        )
        ttk.Label(
            rtm_popup_frame,
            text="来源：OpenMMLab MMPose / rtmlib，需要本地 ONNX 模型。",
            wraplength=360,
            foreground="#555",
        ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        rtm_popup_gpu_check = ttk.Checkbutton(rtm_popup_frame, text="RTM GPU 加速", variable=rtm_pose_gpu_enabled)
        rtm_popup_gpu_check.grid(row=6, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_popup_gpu_check, self._tooltip_text("RTM GPU 加速"))
        self._gpu_status_controls(rtm_popup_frame, 7, rtm_pose_gpu_enabled, rtm_pose_gpu_status_text)
        rtm_popup_flow_check = ttk.Checkbutton(rtm_popup_frame, text="RTM 光流辅助", variable=rtm_pose_flow_enabled)
        rtm_popup_flow_check.grid(row=8, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_popup_flow_check, self._tooltip_text("RTM 光流辅助"))
        rtm_popup_kalman_check = ttk.Checkbutton(rtm_popup_frame, text="RTM 卡尔曼融合", variable=rtm_pose_kalman_enabled)
        rtm_popup_kalman_check.grid(row=9, column=0, columnspan=3, sticky="w", pady=(2, 0))
        Tooltip(rtm_popup_kalman_check, self._tooltip_text("RTM 卡尔曼融合"))

        ttk.Checkbutton(rtm_popup_frame, text=self._dt("异常过滤", "Reject outliers"), variable=rtm_pose_reject_enabled).grid(row=10, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(rtm_popup_frame, text=self._dt("仅微抖平滑", "Micro smoothing"), variable=rtm_pose_micro_smooth_enabled).grid(row=11, column=0, columnspan=3, sticky="w")
        popup_source_label = ttk.Label(rtm_popup_frame, text=self._dt("L0 混合来源：混合分析 v2", "L0 blend source: Hybrid v2"))
        popup_source_label.grid(row=12, column=0, columnspan=3, sticky="w")
        popup_auto_l0 = self._pose_auto_l0_control(rtm_popup_frame, 13, pose_auto_l0_enabled)
        popup_pattern = self._pose_pattern_control(rtm_popup_frame, 14, pose_pattern_enabled)
        popup_fast_v1 = self._pose_fast_v1_control(rtm_popup_frame, 15, pose_fast_v1_enabled)
        popup_assist = ttk.Checkbutton(analysis, text=self._dt("v2：启用 RTM 2D 旋转辅助", "v2: RTM 2D rotation assist"), variable=hybrid_v2_pose)
        popup_assist.grid(row=5, column=0, columnspan=3, sticky="w")
        self._point_l0_control(analysis, 6, v2_l0_reference, tracker)
        self._v2_model_controls(analysis, 7, tracker, v2_model_variables, gpu_enabled=rtm_pose_gpu_enabled)

        def refresh_rtm_popup_settings(*_args: object) -> None:
            popup_preferences.switch(self._tracker_internal(tracker.get()), popup_variables)
            self._analysis_visibility(self._tracker_internal(tracker.get()), rtm_hybrid_l0_enabled.get(),
                popup_source_label, popup_assist, (rtm_popup_hybrid_check, popup_blend_scale, popup_blend_value, rtm_popup_model_label, popup_auto_l0, popup_pattern, popup_fast_v1))
            rtm_pose_3d.set(self._rtm_pose_mode_active(tracker.get()))
            refresh_pose_base_texts()
            if self._pose_model_required(tracker.get(), mode.get(), hybrid_v2_pose.get()):
                refresh_popup_rtm_model_path()
                rtm_popup_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            else:
                rtm_popup_frame.grid_remove()

        rtm_hybrid_l0_enabled.trace_add("write", refresh_rtm_popup_settings)
        mode.trace_add("write", refresh_rtm_popup_settings)
        hybrid_v2_pose.trace_add("write", refresh_rtm_popup_settings)
        tracker.trace_add("write", refresh_rtm_popup_settings)
        refresh_rtm_popup_settings()

        ttk.Label(analysis, text="压缩延迟").grid(row=3, column=0, sticky="w", pady=(8, 2))
        ttk.Scale(analysis, from_=-5, to=5, variable=compression_latency).grid(row=3, column=1, sticky="ew", pady=(8, 2))
        ttk.Label(analysis, textvariable=compression_latency, width=4, anchor="e").grid(row=3, column=2, sticky="e", pady=(8, 2))
        ttk.Label(analysis, text="-5 最准确 / 0 默认 / 5 延迟最低", wraplength=360, foreground="#555").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(0, 2)
        )

        limits_text = tk.StringVar()

        def refresh_limits() -> None:
            if mode.get() == "Six Axis":
                parts = [
                    f"{axis} {self.axis_min_vars[axis].get()}..{self.axis_max_vars[axis].get()}"
                    for axis in SIX_AXES
                ]
                limits_text.set(f"{self._t('当前范围')}: " + " / ".join(parts))
            else:
                limits_text.set(f"{self._t('当前范围')}: L0 {self.min_value.get()}..{self.max_value.get()}")

        mode.trace_add("write", lambda *_args: refresh_limits())
        refresh_limits()
        ttk.Label(body, textvariable=limits_text, wraplength=420, foreground="#333").grid(row=5, column=0, sticky="ew", pady=(10, 0))

        buttons = ttk.Frame(dialog, padding=14)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)

        def cancel() -> None:
            dialog.destroy()

        def confirm() -> None:
            if self._gpu_installing or (self._gpu_restart_required and rtm_pose_gpu_enabled.get()):
                messagebox.showwarning(self._dt("GPU 运行库", "GPU Runtime"), self._dt(
                    "请等待安装结束后重启软件；或关闭 GPU 使用 CPU。", "Wait for installation and restart the app, or disable GPU to use CPU."), parent=dialog)
                return
            self.output_mode.set(mode.get())
            self.tracker_mode.set(tracker.get())
            rtm_mode_selected = self._rtm_pose_mode_active(tracker.get())
            self.pose_l0_analysis.set(False)
            self.pose_six_axis_analysis.set(False)
            self.pose_l0_weight.set(pose_l0_weight.get())
            self.pose_six_axis_weight.set(pose_six_weight.get())
            self.pose_v2_dance_six_axis.set(pose_v2.get())
            self.pose_v2_l0_analysis.set(pose_v2_l0.get())
            self.pose_v2_six_axis_analysis.set(pose_v2_six.get())
            self.pose_v2_l0_weight.set(pose_v2_l0_weight.get())
            self.pose_v2_six_axis_weight.set(pose_v2_six_weight.get())
            self.pose_v2_dance_six_axis.set(False)
            self.pose_v2_l0_analysis.set(False)
            self.pose_v2_six_axis_analysis.set(False)
            self.rtm_pose_3d_enabled.set(self._rtm_pose_3d_mode_active(tracker.get()))
            self.rtm_pose_2d_model_path.set(rtm_pose_2d_model.get())
            self.rtm_pose_3d_model_path.set(rtm_pose_3d_model.get())
            self._refresh_active_rtm_pose_model_path()
            self.rtm_pose_3d_weight.set(100 if rtm_mode_selected else 0)
            self.rtm_hybrid_l0_enabled.set(rtm_hybrid_l0_enabled.get())
            self.pose_auto_l0_enabled.set(pose_auto_l0_enabled.get())
            self.pose_pattern_enabled.set(pose_pattern_enabled.get())
            self.pose_fast_v1_enabled.set(pose_fast_v1_enabled.get())
            self.rtm_hybrid_l0_weight.set(max(1, min(100, int(rtm_hybrid_l0_weight.get()))))
            self.rtm_pose_gpu_enabled.set(rtm_pose_gpu_enabled.get())
            self.rtm_pose_flow_enabled.set(rtm_pose_flow_enabled.get())
            self.rtm_pose_kalman_enabled.set(rtm_pose_kalman_enabled.get())
            self.rtm_pose_reject_enabled.set(rtm_pose_reject_enabled.get())
            self.rtm_pose_micro_smooth_enabled.set(rtm_pose_micro_smooth_enabled.get())
            self.rtm_hybrid_source.set(rtm_hybrid_source.get())
            self.hybrid_v2_pose_enabled.set(hybrid_v2_pose.get())
            self.v2_l0_reference.set(v2_l0_reference.get())
            for name, variable in v2_model_variables.items():
                self._v2_model_variables()[name].set(variable.get())
            self.compression_latency.set(max(-5, min(5, int(compression_latency.get()))))
            self.fps.set(capture_fps(capture_rate.get()))
            self.output_curve_fitting.set(curve_fitting.get())
            self.endpoint_slowdown_enabled.set(endpoint_enabled.get())
            self.endpoint_slowdown_pct.set(endpoint_percent.get())
            popup_preferences.remember(popup_variables)
            self._analysis_preferences = popup_preferences
            result["ok"] = True
            dialog.destroy()

        ttk.Button(buttons, text="取消", command=cancel).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="确认开始", command=confirm, style="Primary.TButton").grid(row=0, column=1, sticky="ew", padx=(6, 0))

        dialog.bind("<Escape>", lambda _event: cancel())
        dialog.bind("<Return>", lambda _event: confirm())
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self._install_tooltips(dialog)
        self._localize_widget_tree(dialog)
        dialog.update_idletasks()
        left, top, right, bottom = monitor_workarea(self)
        width = min(max(560, body.winfo_reqwidth() + 24), right - left - 40)
        height = min(body.winfo_reqheight() + buttons.winfo_reqheight(), bottom - top - 80)
        x = max(left, min(self.winfo_rootx() + (self.winfo_width() - width) // 2, right - width))
        y = max(top, min(self.winfo_rooty() + (self.winfo_height() - height) // 2, bottom - height - 40))
        dialog.geometry(f"{width}x{height}")
        dialog.update_idletasks()
        move_physical_window(dialog, x, y)
        self.wait_window(dialog)
        return bool(result["ok"])
