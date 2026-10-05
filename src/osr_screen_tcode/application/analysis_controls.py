"""Analysis, filtering and speed-option control construction.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from ..capture import capture_fps
from ..config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from ..ui_widgets import WideCombobox
from .tooltips import Tooltip


class AnalysisControlsMixin:
    def _capture_fps_changed(self, *_args: object) -> None:
        try:
            self._capture_target_fps = capture_fps(self.fps.get())
        except tk.TclError:
            pass

    def _capture_rate_controls(self, parent: ttk.Frame, row: int, variable: tk.IntVar) -> int:
        label = ttk.Label(parent, text="采集帧率 FPS")
        label.grid(row=row, column=0, sticky="w", pady=2)
        slider = ttk.Scale(parent, from_=1, to=120, variable=variable,
                           command=lambda value: variable.set(capture_fps(value)))
        slider.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=variable, width=4, anchor="e").grid(row=row, column=2, sticky="e")
        hint = self._dt(
            "屏幕模式的目标截图次数，默认 45，最高 120，实时输出时可调。更高帧率增加负载，不会增加视频原始帧数。分析 FPS 是处理循环速度，不等于模型推理 FPS；输入帧龄仅统计进入分析前的等待，不是总延迟。",
            "Target screen captures/second: default 45, maximum 120, adjustable live. Higher rates use more resources, not extra original video frames. Analysis FPS measures the processing loop, not model inference. Input age excludes analysis and output latency.")
        Tooltip(label, hint)
        Tooltip(slider, hint)
        ttk.Label(parent, textvariable=self.capture_rate_text, foreground="#555", wraplength=300).grid(
            row=row + 1, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        return row + 2

    def _output_curve_changed(self, *_args: object) -> None:
        self._output_curve_enabled = bool(self.output_curve_fitting.get())

    def _endpoint_options_changed(self, *_args):
        self._endpoint_options = (bool(self.endpoint_slowdown_enabled.get()),
                                  max(1., min(50., self.endpoint_slowdown_pct.get()))/100.)

    def _endpoint_controls(self, parent, row, enabled, percent, compact=False):
        box = ttk.Frame(parent)
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(2, 5))
        box.columnconfigure(2 if compact else 1, weight=1)
        check = ttk.Checkbutton(box, text=self._dt("接近上下限时减速", "Slow near upper/lower limits"), variable=enabled)
        check.grid(row=0, column=0, columnspan=1 if compact else 3, sticky="w")
        ttk.Label(box, text=self._dt("减速距离", "Braking distance")).grid(row=0 if compact else 1, column=1 if compact else 0, sticky="w", padx=(8 if compact else 0, 0))
        slider = ttk.Scale(box, from_=1, to=50, variable=percent)
        slider.grid(row=0 if compact else 1, column=2 if compact else 1, sticky="ew", padx=4)
        value = ttk.Label(box, width=5, anchor="e")
        value.grid(row=0 if compact else 1, column=3 if compact else 2)
        def refresh(*_args):
            if box.winfo_exists():
                value.configure(text=f"{percent.get():.0f}%")
                slider.state(["!disabled" if enabled.get() else "disabled"])
        callbacks = [(variable, variable.trace_add("write", refresh)) for variable in (enabled, percent)]
        def dispose(event):
            if event.widget == box:
                for variable, callback in callbacks:
                    variable.trace_remove("write", callback)
        box.bind("<Destroy>", dispose, add="+")
        refresh()
        Tooltip(check, self._dt(
            "默认开启，距离 10%：最终输出只延长接近每个轴上下限的到达时间，目标位置不变；导出脚本可能变长。离开限位正常响应，急停和手动回中不受影响。",
            "On by default, distance 10%: final output only extends arrival time near each axis limit; target positions are unchanged. Exported scripts may run longer. Motion away from limits, emergency stop and manual centering are unchanged."))
        return row+1

    def _output_curve_control(self, parent: ttk.Frame, row: int, variable: tk.BooleanVar) -> int:
        check = ttk.Checkbutton(parent, text="输出曲线拟合", variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 5))
        Tooltip(check, self._dt(
            "默认开启：用 One Euro 自适应平滑处理分析输出，慢动作抑抖、快动作减小滞后。Pose 自动 L0 保留已生成的曲线与切换过渡，不再重复平滑。会增加少量跟随延迟，不能保证完全无抖动；急停/手动回中不经过此滤波。",
            "Enabled by default: One Euro adaptive smoothing reduces slow-motion jitter and fast-motion lag. Generated Pose L0 retains its curve and source transition without a second smoothing pass. Adds some lag and cannot remove all jitter; emergency stop/manual centering bypass this filter."))
        return row + 1

    def _pose_auto_l0_control(self, parent, row, variable):
        check = ttk.Checkbutton(parent, text=self._dt("L0 静止／小幅时自动生成", "Generate L0 when still / small"), variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(3, 2))
        Tooltip(check, self._dt(
            "默认开启，仅 Pose：L0 静止约 0.65 秒，或 L0 幅度小而旋转明显更大时，依次用 R1、R2 生成 L0，中点对应 1/3、两端对应 2/3；R1/R2 无变化但其他识别轴仍在运动时，才生成 1/4～1/2、峰到峰 1 秒的余弦波。所有识别轴静止或缺失时保持位置，不启动兜底波。L0 恢复足够幅度后平滑交回识别；只在分析运行中生效。",
            "On by default, Pose only: after about 0.65 s of still L0, or small L0 with clearly larger rotation, use R1 then R2 (midpoint to one-third L0; either end to two-thirds). When R1/R2 are still but another observed axis is moving, generate a quarter-to-half cosine with a 1 s peak-to-peak period. If all observed axes are still/missing, hold without starting a wave. Sufficient L0 motion smoothly takes over again. Runs only during analysis."))
        return check

    def _point_l0_control(self, parent, row, variable, tracker=None):
        from ..point_l0 import POINT_MODES
        tracker = self.tracker_mode if tracker is None else tracker
        box = ttk.Frame(parent)
        box.columnconfigure(1, weight=1)
        box.grid(row=row, column=0, columnspan=4, sticky='ew', pady=(3, 3))
        ttk.Label(box, text=self._dt('v2 L0 参考', 'v2 L0 reference')).grid(row=0, column=0, sticky='w')
        labels = (self._dt('融合参考（默认）', 'Fused reference (default)'),
                  self._dt('三维运动轴', '3D motion axis'),
                  self._dt('往复中心点', 'Stroke center'),
                  self._dt('交互点候选（实验）', 'Interaction candidate (experimental)'))
        shown = tk.StringVar()
        combo = WideCombobox(box, textvariable=shown, values=labels, state='readonly', width=25)
        combo.grid(row=0, column=1, sticky='ew', padx=6)
        combo.bind('<<ComboboxSelected>>', lambda _event: variable.set(POINT_MODES[labels.index(shown.get())]))
        def refresh(*_args):
            value = variable.get()
            shown.set(labels[POINT_MODES.index(value) if value in POINT_MODES else 0])
            if self._tracker_internal(tracker.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
                box.grid()
            else:
                box.grid_remove()
        callbacks = [(v, v.trace_add('write', refresh)) for v in (variable, tracker)]
        def dispose(event):
            if event.widget is box:
                for v, token in callbacks:
                    v.trace_remove('write', token)
        box.bind('<Destroy>', dispose, add='+')
        Tooltip(combo, self._dt(
            '默认融合主轴、往复中心与可靠交互候选。方向确认后远离目标 L0 大、靠近 L0 小；T? 标注目标估计，未确认真实接触。识别不清时仅延续已确认规律，最多 2 秒，最后 0.5 秒减速停住。暂停、切镜头与重设参考停止延续。保留三个单独参考供比较，五档与最终限制仍生效。',
            'Default: align and fuse the motion axis, stroke center and reliable interaction evidence. Once polarity is confirmed, away means larger L0 and toward means smaller L0. T? is an estimated target, not confirmed contact. Unclear tracking continues only a confirmed rhythm for up to 2 s, braking over the final 0.5 s. Pauses, cuts and recalibration stop continuation. Three individual references remain available. Final presets and limits still apply.'))
        refresh()
        return box

    def _pose_pattern_control(self, parent, row, variable):
        check = ttk.Checkbutton(parent, text=self._dt("小幅往复渐放大", "Gradually expand small repeated strokes"), variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(3, 2))
        Tooltip(check, self._dt(
            "默认关闭，仅 Pose 的 L0、R0、R1：各轴单独确认约 3 个节奏稳定的小幅往复后，用约 1 秒渐增至最多 2 倍，围绕该动作中点放大。实际幅度变大、节奏中断或观测丢失时各自平滑退出。L1、L2、R2 及自动生成的 L0 不参与检测或放大；后续行程倍率、限位和减速仍生效。",
            "Off by default, Pose L0/R0/R1 only: each axis independently confirms about 3 steady small cycles, then expands around that motion's midpoint up to 2x over about 1 s. Each releases when real motion grows, rhythm breaks or observations are lost. L1/L2/R2 and generated L0 are excluded. Travel gains, limits and slowdown still apply."))
        return check

    def _pose_fast_v1_control(self, parent, row, variable):
        check = ttk.Checkbutton(parent, text=self._dt("快速丢点时用混合 v1", "Use Hybrid v1 on fast Pose loss"), variable=variable)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(3, 2))
        Tooltip(check, self._dt(
            "默认开启，仅 Pose：开启后 v1 持续分析同批画面；近期有效骨架丢失且 v1 测得明显快速运动时，从当前输出位置接续 L0 的后续变化，不跳到 v1 的累计位置；Pose 恢复后平滑交回。持续运行 v1 会增加处理开销。只接管 L0，不乘 Pose 的 10 倍，其他轴保留原丢失处理。未建立 Pose、静止丢点或切镜头不会仅凭缺失启用；v1 无有效运动时退回原有自动／保持策略。",
            "On by default, Pose only: v1 continuously analyzes the same sampled frames. After recent valid Pose loss with fast v1 motion, L0 continues from the current output using subsequent changes, without jumping to v1's accumulated position. Pose recovery returns smoothly. Continuous v1 adds processing cost. L0 only, without Pose's 10x gain; other axes retain loss handling. Missing Pose alone, startup or a cut does not activate it. Without valid v1 motion, normal auto/hold behavior applies."))
        return check

    def _tracking_controls(self, parent: ttk.Frame, row: int) -> int:
        row = self._section(parent, "高级参数", row)
        ttk.Label(parent, text="输出模式").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.output_mode,
            values=("L0 Only", "Six Axis"),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="分析模式").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.tracker_mode,
            values=self._tracker_choices(),
            state="readonly",
            width=12,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        row = self._endpoint_controls(parent, row, self.endpoint_slowdown_enabled, self.endpoint_slowdown_pct)
        self.sidebar_v2_model_controls = self._v2_model_controls(parent, row, compact=True)
        row += 1
        row = self._capture_rate_controls(parent, row, self.fps)
        row = self._output_curve_control(parent, row, self.output_curve_fitting)
        row = self._entry(parent, "到达时间下限 ms", self.interval_ms, row)
        ttk.Checkbutton(parent, text="启用每帧限速", variable=self.enable_speed_limit).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "限速值", self.max_step, row)
        ttk.Checkbutton(parent, text="启用平滑曲线", variable=self.enable_smoothing).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="平滑").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=0.95, variable=self.smoothing).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Checkbutton(parent, text="启用死区滤波", variable=self.enable_deadzone).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="死区").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=0.12, variable=self.deadzone).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Checkbutton(parent, text="启用 L0 防抽搐", variable=self.enable_l0_jitter_guard).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="L0 防抖").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=1.0, variable=self.l0_guard_strength).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Checkbutton(parent, text="极端位自动复位", variable=self.enable_extreme_reset).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "极端停留 ms", self.extreme_hold_ms, row)
        ttk.Checkbutton(parent, text="端点保护", variable=self.enable_endpoint_guard).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "端点留白 %", self.endpoint_margin_pct, row)
        ttk.Checkbutton(parent, text="启用活动门控", variable=self.enable_activity_gate).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Label(parent, text="活动阈值").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.0, to=0.04, variable=self.min_activity).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(parent, text="增益").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.2, to=4.0, variable=self.motion_gain).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(parent, text="视觉行程").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=0.35, to=1.2, variable=self.visual_stroke_scale).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(parent, text="压缩延迟").grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(parent, from_=-5, to=5, variable=self.compression_latency).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(parent, textvariable=self.compression_latency, width=6, anchor="e").grid(row=row, column=2, sticky="e")
        row += 1
        ttk.Label(parent, text="-5 最准确 / 0 默认 / 5 延迟最低", wraplength=300, foreground="#555").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4)
        )
        row += 1
        ttk.Label(parent, text="响应曲线").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.response_curve,
            values=("Linear", "Soft", "Sharp", "Ease In"),
            state="readonly",
            width=10,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Label(parent, text="空闲").grid(row=row, column=0, sticky="w", pady=2)
        WideCombobox(
            parent,
            textvariable=self.idle_mode,
            values=("Hold", "Center"),
            state="readonly",
            width=10,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Checkbutton(parent, text="启用启动渐入", variable=self.enable_startup_ramp).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        row = self._entry(parent, "渐入 ms", self.startup_ramp_ms, row)
        ttk.Checkbutton(parent, text="反向", variable=self.invert).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1
        ttk.Button(parent, text="一键稳态 L0", command=self.apply_stable_l0_preset, style="Primary.TButton").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(4, 0)
        )
        return row + 1

    def _rtm_pose_3d_controls(self, parent: ttk.Frame, row: int) -> int:
        self.rtm_pose_3d_settings_button = ttk.Button(parent, command=self._toggle_rtm_pose_3d_settings)
        self.rtm_pose_3d_settings_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        row += 1
        box = ttk.LabelFrame(parent, text="RTM Pose 模型", padding=8)
        self.rtm_pose_3d_settings_frame = box
        box.columnconfigure(1, weight=1)
        rtm_hybrid_check = ttk.Checkbutton(box, text="混合分析 L0 权重", variable=self.rtm_hybrid_l0_enabled)
        rtm_hybrid_check.grid(row=0, column=0, sticky="w", pady=2)
        Tooltip(rtm_hybrid_check, self._tooltip_text("混合分析 L0 权重"))
        blend_scale = ttk.Scale(box, from_=1, to=100, variable=self.rtm_hybrid_l0_weight)
        blend_scale.grid(row=0, column=1, sticky="ew", pady=2)
        blend_value = ttk.Label(box, textvariable=self.rtm_hybrid_l0_weight, width=4, anchor="e")
        blend_value.grid(row=0, column=2, sticky="e")
        rtm_model_weight_label = ttk.Label(box, textvariable=self.rtm_model_l0_weight_text, foreground="#555")
        rtm_model_weight_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 5))
        Tooltip(rtm_model_weight_label, self._tooltip_text("当前本模型分析权重"))
        ttk.Label(box, text="RTM Pose 模型").grid(row=2, column=0, sticky="w", pady=2)
        rtm_model_entry = ttk.Entry(box, textvariable=self.rtm_pose_model_path)
        rtm_model_entry.grid(row=2, column=1, sticky="ew", pady=2)
        Tooltip(rtm_model_entry, self._tooltip_text("RTM Pose 模型"))
        ttk.Button(box, text="选择模型", command=self.pick_rtm_pose_3d_model).grid(row=2, column=2, sticky="ew", padx=(4, 0), pady=2)
        ttk.Button(box, textvariable=self.rtm_model_download_button_text, command=self.download_rtm_pose_3d_model).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2)
        )
        ttk.Label(box, textvariable=self.rtm_model_download_status_text, foreground="#555", wraplength=330).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 2)
        )
        ttk.Label(
            box,
            text="来源：OpenMMLab MMPose / rtmlib，需要本地 ONNX 模型。",
            foreground="#555",
            wraplength=330,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 2))
        rtm_gpu_check = ttk.Checkbutton(box, text="RTM GPU 加速", variable=self.rtm_pose_gpu_enabled)
        rtm_gpu_check.grid(row=6, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_gpu_check, self._tooltip_text("RTM GPU 加速"))
        self._gpu_status_controls(box, 7, self.rtm_pose_gpu_enabled, self.rtm_pose_gpu_status_text)
        rtm_flow_check = ttk.Checkbutton(box, text="RTM 光流辅助", variable=self.rtm_pose_flow_enabled)
        rtm_flow_check.grid(row=8, column=0, columnspan=3, sticky="w", pady=(5, 0))
        Tooltip(rtm_flow_check, self._tooltip_text("RTM 光流辅助"))
        rtm_kalman_check = ttk.Checkbutton(box, text="RTM 卡尔曼融合", variable=self.rtm_pose_kalman_enabled)
        rtm_kalman_check.grid(row=9, column=0, columnspan=3, sticky="w", pady=(2, 0))
        Tooltip(rtm_kalman_check, self._tooltip_text("RTM 卡尔曼融合"))
        ttk.Checkbutton(box, text=self._dt("异常过滤", "Reject outliers"), variable=self.rtm_pose_reject_enabled).grid(row=10, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(box, text=self._dt("仅微抖平滑", "Micro smoothing"), variable=self.rtm_pose_micro_smooth_enabled).grid(row=11, column=0, columnspan=3, sticky="w")
        self.rtm_hybrid_source_label = ttk.Label(box, text=self._dt("L0 混合来源：混合分析 v2", "L0 blend source: Hybrid v2"))
        self.rtm_hybrid_source_label.grid(row=12, column=0, columnspan=3, sticky="w")
        self.pose_auto_l0_check = self._pose_auto_l0_control(box, 13, self.pose_auto_l0_enabled)
        self.pose_pattern_check = self._pose_pattern_control(box, 14, self.pose_pattern_enabled)
        self.pose_fast_v1_check = self._pose_fast_v1_control(box, 15, self.pose_fast_v1_enabled)
        self._rtm_blend_widgets = (rtm_hybrid_check, blend_scale, blend_value, rtm_model_weight_label, self.pose_auto_l0_check, self.pose_pattern_check, self.pose_fast_v1_check)
        self._refresh_hybrid_source()
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self._refresh_rtm_pose_3d_settings()
        return row + 1

    def _six_axis_tuning_controls(self, parent: ttk.Frame, row: int) -> int:
        self.six_axis_tuning_button = ttk.Button(parent, command=self._toggle_six_axis_tuning)
        self.six_axis_tuning_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        row += 1
        box = ttk.LabelFrame(parent, text="六轴辅助调节（仅混合分析推荐）", padding=8)
        self.six_axis_tuning_frame = box
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text="总强度").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Scale(box, from_=0, to=180, variable=self.six_axis_intensity).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(box, textvariable=self.six_axis_intensity, width=4, anchor="e").grid(row=0, column=2, sticky="e")
        row_i = 1
        ttk.Label(box, text="六轴降抖").grid(row=row_i, column=0, sticky="w", pady=2)
        ttk.Scale(box, from_=0, to=100, variable=self.six_axis_jitter_reduction).grid(row=row_i, column=1, sticky="ew", pady=2)
        ttk.Label(box, textvariable=self.six_axis_jitter_reduction, width=4, anchor="e").grid(row=row_i, column=2, sticky="e")
        row_i += 1
        ttk.Button(box, text="一键稳六轴", command=self.apply_stable_six_axis_preset, style="Primary.TButton").grid(
            row=row_i, column=0, columnspan=3, sticky="ew", pady=(2, 5)
        )
        row_i += 1
        ttk.Label(box, text="六轴敏感度").grid(row=row_i, column=0, sticky="w", pady=2)
        sensitivity_row = ttk.Frame(box)
        for column in range(5):
            sensitivity_row.columnconfigure(column, weight=1)
        for level in range(1, 11):
            row_pos = 0 if level <= 5 else 1
            col_pos = (level - 1) % 5
            button = ttk.Button(
                sensitivity_row,
                text=str(level),
                width=3,
                command=lambda selected=level: self.apply_six_axis_sensitivity(selected),
            )
            button.grid(row=row_pos, column=col_pos, sticky="ew", padx=(0 if col_pos == 0 else 3, 0), pady=(0 if row_pos == 0 else 3, 0))
            if not hasattr(self, "six_axis_sensitivity_buttons"):
                self.six_axis_sensitivity_buttons = {}
            self.six_axis_sensitivity_buttons[level] = button
        sensitivity_row.grid(row=row_i, column=1, columnspan=2, sticky="ew", pady=(2, 5))
        row_i += 1
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            ttk.Label(box, text=axis, width=4).grid(row=row_i, column=0, sticky="w", pady=1)
            ttk.Scale(box, from_=0, to=200, variable=self.six_axis_gain_vars[axis]).grid(row=row_i, column=1, sticky="ew", padx=(2, 3), pady=1)
            mini = ttk.Frame(box)
            ttk.Label(mini, textvariable=self.six_axis_gain_vars[axis], width=4, anchor="e").grid(row=0, column=0, sticky="e")
            ttk.Checkbutton(mini, text="反", variable=self.six_axis_invert_vars[axis]).grid(row=0, column=1, sticky="e")
            mini.grid(row=row_i, column=2, sticky="e")
            row_i += 1
        ttk.Label(
            box,
            text="这组滑块只推荐用于混合分析（推荐-非舞蹈）；RTM Pose 输出不会接入这里。",
            wraplength=270,
            foreground="#555",
        ).grid(row=row_i, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self._refresh_six_axis_tuning()
        return row + 1
