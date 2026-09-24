"""Tk display for the main pipeline's paired frames; no capture or device I/O."""
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

from .ui_widgets import WideCombobox
from .visual_pipeline import RESOLUTIONS
from .motion_reference import reference_lines, projected_axes, AXIS_COLORS


class IntegratedPreview(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.history = deque(maxlen=600)
        self.last_frame = None
        self.photo = None
        self.t = app._dt
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        controls = ttk.Frame(self, padding=(6, 4))
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(3, weight=1)
        ttk.Label(controls, text=self.t("分析模式", "Analysis mode")).grid(row=0, column=0, sticky="w")
        self.mode_box = WideCombobox(controls, textvariable=app.tracker_mode, values=app._tracker_choices(), state="readonly")
        self.mode_box.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=(0, 4))
        braking = ttk.Frame(controls)
        braking.grid(row=1, column=0, columnspan=4, sticky="ew")
        braking.columnconfigure(1, weight=1)
        app._endpoint_controls(braking, 0, app.endpoint_slowdown_enabled, app.endpoint_slowdown_pct, compact=True)
        ttk.Label(controls, text=self.t("处理最长边", "Processing max edge")).grid(row=2, column=0, sticky="w")
        self.edge_box = WideCombobox(controls, textvariable=app.visual_processing_edge, values=RESOLUTIONS,
                                     state="readonly", width=7)
        self.edge_box.grid(row=2, column=1, padx=6, sticky="w")
        ttk.Button(controls, text=self.t("重设参考", "Recalibrate"), command=app.reset_visual_reference).grid(row=2, column=2, sticky="w")
        ttk.Button(controls, text=self.t('参考详情', 'Reference details'), command=self.show_reference_details).grid(row=2, column=3, sticky='w', padx=6)
        self.switches = []
        self.v2_pose_switch = ttk.Checkbutton(controls, text=self.t("v2：启用 RTM 2D 旋转辅助", "v2: RTM 2D rotation assist"), variable=app.hybrid_v2_pose_enabled)
        self.v2_pose_switch.grid(row=5, column=0, columnspan=4, sticky="w")
        self.point_l0_controls = app._point_l0_control(controls, 8, app.v2_l0_reference)
        self.pose_auto_l0_switch = app._pose_auto_l0_control(controls, 6, app.pose_auto_l0_enabled)
        self.pose_auto_l0_switch.grid_configure(columnspan=2)
        self.pose_pattern_switch = app._pose_pattern_control(controls, 7, app.pose_pattern_enabled)
        self.pose_pattern_switch.grid_configure(columnspan=4)
        self.pose_fast_v1_switch = app._pose_fast_v1_control(controls, 6, app.pose_fast_v1_enabled)
        self.pose_fast_v1_switch.grid_configure(column=2, columnspan=2)
        for i, (zh, en, variable) in enumerate((
            ("异常过滤", "Reject outliers", app.rtm_pose_reject_enabled),
            ("光流", "Optical flow", app.rtm_pose_flow_enabled),
            ("卡尔曼", "Kalman", app.rtm_pose_kalman_enabled),
            ("仅微抖平滑", "Micro smoothing", app.rtm_pose_micro_smooth_enabled),
        )):
            widget = ttk.Checkbutton(controls, text=self.t(zh, en), variable=variable)
            widget.grid(row=3 + i // 2, column=(i % 2) * 2, columnspan=2, sticky="w", pady=2)
            self.switches.append(widget)
        self.details = tk.StringVar(value=self.t("选择屏幕区域或视频后开始分析", "Select a screen region or video, then start analysis"))
        ttk.Label(self, textvariable=self.details, wraplength=620).grid(row=1, column=0, sticky="ew", padx=6)
        self.headings = tk.StringVar()
        ttk.Label(self, textvariable=self.headings, anchor="center").grid(row=2, column=0, sticky="ew", pady=3)
        self.canvas = tk.Canvas(self, background="#111111", highlightthickness=0, width=640, height=300)
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self.render())
        self.chart = tk.Canvas(self, height=150, background="#171b1d", highlightthickness=0)
        self.chart.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        self.chart.bind("<Configure>", lambda _event: self.render_chart())
        ttk.Label(self, text=self.t(
            "画面尺度不是真实深度。图表为识别观测；输出监视为指令值，不是硬件反馈。",
            "Image scale is not depth. Charts show observations; the output monitor shows commands, not feedback."),
            wraplength=620).grid(row=5, column=0, sticky="ew", padx=6, pady=4)
        self.refresh_mode()

    def refresh_mode(self):
        from .config import HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE, RTM_POSE_2D_MODE
        pose = self.app._pose_model_required()
        visual = pose or self.app._tracker_internal(self.app.tracker_mode.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE)
        if self.app._tracker_internal(self.app.tracker_mode.get()) == RTM_POSE_2D_MODE:
            self.pose_auto_l0_switch.grid()
            self.pose_pattern_switch.grid()
            self.pose_fast_v1_switch.grid()
        else:
            self.pose_auto_l0_switch.grid_remove()
            self.pose_pattern_switch.grid_remove()
            self.pose_fast_v1_switch.grid_remove()
        self.v2_pose_switch.configure(state="normal" if self.app._tracker_internal(self.app.tracker_mode.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE) else "disabled")
        if self.app._tracker_internal(self.app.tracker_mode.get()) in (HYBRID_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            self.v2_pose_switch.grid()
        else:
            self.v2_pose_switch.grid_remove()
        self.edge_box.configure(state="readonly" if visual else "disabled")
        for widget in self.switches:
            widget.configure(state="normal" if pose else "disabled")
            widget.grid() if pose else widget.grid_remove()
        self.headings.set(self.t("原始识别（橙）              处理后（青）", "Raw pose (orange)              Processed pose (cyan)")
                          if pose else self.t("原始画面              当前分析画面", "Original frame              Current analysis"))

    def clear(self):
        self.history.clear()
        self.last_frame = None
        self.canvas.delete("all")
        self.details.set(self.t("建立参考中；有效观测前保持原有输出策略", "Calibrating; existing idle output policy applies until observations are valid")
                         if self.app.worker is not None else self.t("选择屏幕区域或视频后开始分析", "Select a screen region or video, then start analysis"))
        self.render_chart()

    def display(self, frame):
        if frame.generation != self.app._visual_settings.generation:
            return
        self.last_frame = frame
        if frame.reference is not None:
            self.headings.set(self.t("原始画面／识别说明              实际识别参考",
                                    "Original / measurements              Actual reference"))
        sample = frame.observation
        if frame.reset:
            self.history.clear()
        if sample is not None:
            self.history.append(sample)
            while self.history and sample.timestamp - self.history[0].timestamp > 8:
                self.history.popleft()
        h, w = frame.pair[0].shape[:2]
        state = {"ready": self.t("相对参考", "Relative to reference"),
                 "calibrating": self.t("建立参考中", "Calibrating"),
                 "camera_only": self.t("等待局部运动", "Waiting for local motion"),
                 "holding": self.t("短暂丢点，保持参考", "Brief tracking loss; reference held"),
                 "missing": self.t("参考不足（见画面说明）", "Insufficient reference (see image notes)")}.get(sample.state if sample else "", "")
        region = getattr(self.app, "_active_screen_region", None)
        source = (self.t("采集", "Capture") + f" X {region.x} · Y {region.y} · {region.width}×{region.height} px\n"
                  if region is not None else "")
        self.details.set(source + self.t("分析尺寸", "Analysis size") + f" {w}×{h} · {state} · " + self.t(
            f"推理 {frame.inference_ms:.1f} / 处理 {frame.processing_ms:.1f} ms · 帧间隔 {frame.gap_ms:.0f} ms · 重置 {frame.resets} · 视频跳过 {frame.skipped}",
            f"Inference {frame.inference_ms:.1f} / processing {frame.processing_ms:.1f} ms · Gap {frame.gap_ms:.0f} ms · Resets {frame.resets} · Video skips {frame.skipped}"))
        if frame.motion_weights is not None:
            source = self.t("骨架旋转", "Pose rotations") if frame.rotation_source == "pose" else self.t("画面旋转近似", "Image rotation estimates") if frame.rotation_source == "image" else "L0"
            self.details.set(self.details.get() + "\n" + self.t(
                f"3D 运动轴（画面估计）· L0 主轴 / L1、L2 横向轴 · {source}",
                f"3D motion frame (image estimate) · L0 main / L1, L2 transverse · {source}"))
        if frame.l0_source:
            sources = {"waiting": self.t("静止判定中", "Checking for stillness"),
                       "detected": self.t("识别 L0", "Detected L0"),
                       "idle": self.t("无有效轴运动：保持", "No valid axis motion: hold"),
                       "R1": self.t("由 R1 自动生成", "Generated from R1"),
                       "R2": self.t("由 R2 自动生成", "Generated from R2"),
                       "v1": self.t("快速丢点：混合 v1 接续", "Fast Pose loss: Hybrid v1"),
                       "v1_return": self.t("混合 v1 平滑交回", "Returning from Hybrid v1"),
                       "wave": self.t("自动余弦波：1/4～1/2，周期 1 秒", "Auto cosine: quarter–half, 1 s period"),
                       "rhythm": self.t("节奏接续（预测，最多 2 秒）", "Rhythm continuation (predicted, up to 2 s)"),
                       "velocity": self.t("短速度接续（估算，最多 0.3 秒／分析行程 15%）", "Brief velocity continuation (estimated, up to 0.3 s / 15% before gains)"),
                       "weak": self.t("弱跟踪接续（估算，最多 2 秒）", "Weak-tracking continuation (estimated, up to 2 s)")}
            self.details.set(self.details.get()+"\n"+self.t("L0 来源：", "L0 source: ")+sources[frame.l0_source])
        if frame.pattern_gains:
            self.details.set(self.details.get()+"\n"+self.t("小幅往复放大：", "Small stroke gains: ")+
                             " · ".join(f"{axis} ×{gain:.2f}" for axis, gain in frame.pattern_gains))
        if frame.l0_recoveries:
            self.details.set(self.details.get()+" · "+self.t(
                f"L0 端点复位 {frame.l0_recoveries} 次", f"L0 endpoint recenter: {frame.l0_recoveries}"))
        self.render()
        self.render_chart()

    def show_reference_details(self):
        reference = self.last_frame.reference if self.last_frame else None
        text = '\n'.join(reference_lines(reference, self.t)) if reference else self.t('尚无分析参考', 'No analysis reference yet')
        messagebox.showinfo(self.t('参考详情', 'Reference details'), text, parent=self.app)

    def render(self):
        if self.last_frame is None:
            return
        width, height = max(2, self.canvas.winfo_width()), max(2, self.canvas.winfo_height())
        image = Image.new("RGB", (width, height), "#111111")
        for i, frame in enumerate(self.last_frame.pair):
            part = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            part.thumbnail((max(1, width // 2 - 8), height), Image.Resampling.BILINEAR)
            image.paste(part, (i * (width // 2) + (width // 2 - part.width) // 2, (height - part.height) // 2))
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        if self.last_frame.reference is not None:
            lines = reference_lines(self.last_frame.reference, self.t)
            # The left-hand notes leave the actual reference points/region on
            # the right completely visible. Tk supplies readable CJK fonts.
            left, right = 5, width//2-5
            text = self.canvas.create_text(left+7, 8, text="\n".join(lines), anchor="nw",
                width=max(30, right-left-14), fill="#f3f3f3", font=("Segoe UI", 9))
            box = self.canvas.bbox(text)
            if box and box[3] > height-6:
                self.canvas.itemconfigure(text, font=("Segoe UI", 8))
                box = self.canvas.bbox(text)
            if box and box[3] > height-6:
                lines = reference_lines(self.last_frame.reference, self.t, compact=True)
                self.canvas.itemconfigure(text, text='\n'.join(lines))
                box = self.canvas.bbox(text)
            if box:
                background = self.canvas.create_rectangle(left, 3, right, box[3]+5,
                    fill="#171b1d", outline="#56616b")
                self.canvas.tag_lower(background, text)

    def render_axes_key(self, width, height):
        canvas = self.chart
        reference = self.last_frame.reference
        directions = projected_axes(reference.basis)
        if directions is None or width < 400 or height < 125:
            return
        # A fixed oblique view keeps scale-direction and labels legible even
        # when the subject is small. The same frame is drawn on the real ROI.
        left, top = width-182, height-122
        canvas.create_rectangle(left, top, width-5, height-5, fill='#171b1d', outline='#56616b')
        canvas.create_text(left+7, top+12, text=self.t('轴方向 · S 为尺度', 'Axes · S is image scale'),
                                anchor='w', fill='#eeeeee', font=('Segoe UI', 8))
        cx, cy = left+62, top+72
        # Faint reference cube distinguishes an oblique 3D view from three
        # unrelated screen arrows. Its S direction is still only image scale.
        corners = [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
        projected = [(cx+37*(x-.6*z), cy+37*(-y+.4*z)) for x, y, z in corners]
        for i, a in enumerate(corners):
            for j in range(i+1, len(corners)):
                if sum(u != v for u, v in zip(a, corners[j])) == 1:
                    canvas.create_line(*projected[i], *projected[j], fill='#3d4750')
        for i, (direction, bgr) in enumerate(zip(directions, AXIS_COLORS)):
            color = '#%02x%02x%02x' % tuple(reversed(bgr))
            dx, dy = direction*37
            canvas.create_line(cx-dx*.6, cy-dy*.6, cx, cy, fill=color, dash=(2, 3))
            canvas.create_line(cx, cy, cx+dx, cy+dy, fill=color, width=2, arrow='last')
            canvas.create_text(cx-dx*.75, cy-dy*.75, text='−', fill=color, font=('Segoe UI', 8))
            canvas.create_text(left+122, top+36+i*22, text=f'L{i} / R{i}', fill=color, font=('Segoe UI', 9))
        canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill='white', outline='')

    def render_chart(self):
        self.chart.delete("all")
        width = max(2, self.chart.winfo_width())
        full_width = width
        show_basis = (width >= 620 and self.last_frame is not None
                      and self.last_frame.reference is not None and bool(self.last_frame.reference.basis))
        if show_basis:
            # Reserve chart space for the key instead of hiding the tracked
            # region/axis endpoints beneath an opaque image overlay.
            width -= 187
        labels = (self.t("左右 / 画宽 %", "X / width %"), self.t("上下 / 画高 %", "Y / height %"), self.t("画面尺度 %", "Image scale %"))
        end = self.history[-1].timestamp if self.history else 0
        for axis, (label, color) in enumerate(zip(labels, ("#76c6ff", "#e8c16d", "#d5a3ed"))):
            top = axis * 50
            value = self.history[-1].values[axis] if self.history and self.history[-1].values else None
            self.chart.create_text(8, top + 12, text=label, fill=color, anchor="w")
            self.chart.create_text(8, top + 32, text="--" if value is None else f"{value:+.1f}%", fill="white", anchor="w")
            left, right, middle = 155, max(156, width - 42), top + 25
            self.chart.create_line(left, middle, right, middle, fill="#3d4447")
            extent = max(5, max((abs(s.values[axis]) for s in self.history if s.values), default=0))
            self.chart.create_text(width - 4, top + 8, text=f"{extent:.0f}%", fill="#9ca4a7", anchor="ne")
            previous = None
            for sample in self.history:
                if sample.values is None:
                    previous = None
                    continue
                x = left + (sample.timestamp - (end - 8)) / 8 * (right - left)
                y = middle - sample.values[axis] / extent * 18
                if previous is not None and sample.timestamp - previous[2] <= 0.5:
                    self.chart.create_line(previous[0], previous[1], x, y, fill=color, width=2)
                previous = (x, y, sample.timestamp)
        if show_basis:
            self.render_axes_key(full_width, 150)
