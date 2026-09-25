"""CPU-only, standalone pose comparison viewer. No hardware imports or output."""
import argparse
from collections import deque
import json
from pathlib import Path
import queue
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
# Reuse only source-local desktop geometry/capture helpers, not the main app,
# its settings, analysis, device modules, or any separately installed copy.
SOURCE = str(HERE.parent / "src")
if not getattr(sys, "frozen", False) and SOURCE not in sys.path:
    sys.path.insert(0, SOURCE)
from osr_screen_tcode.screen_geometry import configure_dpi_awareness

configure_dpi_awareness()

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from stabilizer import EDGES, Options, Stabilizer
from observations import ImageObservations
from frame_motion import FrameMotion
from osr_screen_tcode.capture import ScreenCapture, ScreenRegion
from osr_screen_tcode.region_selector import ScreenRegionSelector
from osr_screen_tcode.preview_lab_launcher import preview_lab_paths

SETTINGS_PATH, MODEL_DIR = preview_lab_paths(Path(__file__).resolve())

VERSION = "0.2.2-test"
MODES = ("RTM 骨架 / RTM Pose 2D", "画面运动 / Image Motion", "画面运动 v2 / Image Motion v2")
RESOLUTIONS = (320, 480, 640, 960, 1280)


def resize_for_processing(frame, longest_edge):
    height, width = frame.shape[:2]
    ratio = min(1, longest_edge / max(height, width))
    if ratio < 1:
        # A very wide multi-monitor strip may have a sub-pixel short edge.
        # Preserve the complete frame and retain at least one pixel per edge.
        size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    return frame


def draw(frame, points, color, rejected=None):
    result = frame.copy()
    good = np.isfinite(points).all(axis=1)
    for a, b in EDGES:
        if good[a] and good[b]:
            cv2.line(result, tuple(points[a].astype(int)), tuple(points[b].astype(int)), color, 2, cv2.LINE_AA)
    for i in np.flatnonzero(good):
        c = (0, 0, 255) if rejected is not None and rejected[i] else color
        cv2.circle(result, tuple(points[i].astype(int)), 4, c, -1, cv2.LINE_AA)
    return result


class App:
    def __init__(self, root):
        self.root = root
        root.title(f"Pose Preview Lab {VERSION} | 骨架预览测试（无设备输出）")
        root.geometry("1120x800")
        root.minsize(700, 680)
        self.stop_event = threading.Event()
        self.worker = None
        self.events = queue.Queue(maxsize=2)
        self.region: ScreenRegion | None = None
        self.region_selector = None
        self.reference_generation = 0
        self.history = deque(maxlen=600)
        saved = {}
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            pass
        models = sorted(MODEL_DIR.glob("rtmpose-*_simcc*.onnx"))
        self.model = tk.StringVar(value=saved.get("model", str(models[0]) if models else ""))
        self.mode = tk.StringVar(value=saved.get("mode") if saved.get("mode") in MODES else MODES[0])
        self.processing_edge = saved.get("resolution", 640)
        if self.processing_edge not in RESOLUTIONS:
            self.processing_edge = 640
        self.resolution = tk.StringVar(value=str(self.processing_edge))
        # Earlier defaults were too aggressive in the user's preview comparison.
        # Migrate once to raw; subsequent explicit choices remain local/persistent.
        self.options = [tk.BooleanVar(value=saved.get(key, False) if str(saved.get("version", "")).startswith("0.2.") else False)
                        for key in ("reject", "flow", "kalman", "smooth")]
        controls = ttk.Frame(root, padding=8)
        controls.pack(fill="x")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="RTM Pose 2D ONNX").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.model).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(controls, text="选择模型 / Model", command=self.choose_model).grid(row=0, column=2)
        switches = ttk.Frame(controls)
        switches.grid(row=1, column=0, columnspan=3, sticky="w", pady=6)
        self.switch_widgets = []
        for i, label in enumerate(("异常过滤 / Reject", "光流 / Flow", "卡尔曼 / Kalman", "仅微抖平滑 / Micro smoothing")):
            widget = ttk.Checkbutton(switches, text=label, variable=self.options[i], command=self.options_changed)
            widget.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18))
            self.switch_widgets.append(widget)
        actions = ttk.Frame(controls)
        actions.grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Button(actions, text="框选屏幕 / Region", command=self.select_region).pack(side="left")
        ttk.Button(actions, text="开始屏幕预览 / Screen", command=lambda: self.start(None)).pack(side="left", padx=5)
        ttk.Button(actions, text="打开视频 / Video", command=self.choose_video).pack(side="left")
        ttk.Button(actions, text="停止 / Stop", command=self.stop_event.set).pack(side="left", padx=5)
        reference = ttk.Frame(controls)
        reference.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(reference, text="重设参考 / Recalibrate", command=self.reset_reference).pack(side="left")
        self.measurement_status = tk.StringVar(value="等待人物 / Waiting for person")
        ttk.Label(reference, textvariable=self.measurement_status).pack(side="left", padx=8)
        ttk.Label(controls, text="预览模式 / Preview mode").grid(row=4, column=0, sticky="w", pady=5)
        mode_box = ttk.Combobox(controls, textvariable=self.mode, values=MODES, state="readonly")
        mode_box.grid(row=4, column=1, columnspan=2, sticky="ew", padx=6)
        mode_box.bind("<<ComboboxSelected>>", self.mode_changed)
        ttk.Label(controls, text="处理最长边 / Max edge (px)").grid(row=5, column=0, sticky="w")
        resolution_box = ttk.Combobox(controls, textvariable=self.resolution, values=RESOLUTIONS, state="readonly", width=8)
        resolution_box.grid(row=5, column=1, sticky="w", padx=6)
        resolution_box.bind("<<ComboboxSelected>>", self.resolution_changed)
        self.status = tk.StringVar(value="Ready / 就绪 · CPU · RTM Pose 2D · Preview only / 仅预览")
        ttk.Label(root, textvariable=self.status, wraplength=680).pack(fill="x", padx=8, pady=4)
        headings = ttk.Frame(root)
        headings.pack(fill="x")
        self.heading_vars = [tk.StringVar(), tk.StringVar()]
        for variable in self.heading_vars:
            ttk.Label(headings, textvariable=variable, anchor="center").pack(side="left", fill="x", expand=True)
        self.update_headings()
        self.canvas = tk.Canvas(root, bg="#111111", highlightthickness=0)
        ttk.Label(root, text="来源 / Source: OpenMMLab MMPose / rtmlib · 光流预测最多保留 0.25s / prediction expires after 0.25s", wraplength=680).pack(side="bottom", pady=4)
        ttk.Label(root, text="画面尺度 ≠ 真实深度；运镜/变焦也会改变数值 / Image scale is not depth; camera motion also affects values.", wraplength=680).pack(side="bottom", padx=8)
        self.chart = tk.Canvas(root, height=152, background="#171b1d", highlightthickness=0)
        self.chart.pack(side="bottom", fill="x", padx=8, pady=4)
        self.chart.bind("<Configure>", lambda event: self.render_chart())
        self.canvas.pack(fill="both", expand=True, padx=8, pady=4)
        self.last_pair = None
        self.photo = None
        self.canvas.bind("<Configure>", lambda event: self.render())
        self.current_options = Options(*(v.get() for v in self.options))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(16, self.poll)

    def options_changed(self):
        self.current_options = Options(*(v.get() for v in self.options))
        self.reset_reference()

    def resolution_changed(self, event=None):
        self.processing_edge = int(self.resolution.get())
        self.reset_reference()

    def update_headings(self):
        labels = (("原始识别 / Raw (orange)", "当前开关结果 / Selected processing (cyan)") if self.mode.get() == MODES[0]
                  else ("原始画面 / Original", "画面特征运动 / Tracked features"))
        for variable, text in zip(self.heading_vars, labels):
            variable.set(text)
        for widget in self.switch_widgets:
            widget.configure(state="normal" if self.mode.get() == MODES[0] else "disabled")

    def mode_changed(self, event=None):
        self.stop_event.set()
        self.reset_reference()
        self.update_headings()
        self.status.set("模式已选择，请重新开始 / Mode selected; restart preview")

    def reset_reference(self):
        self.reference_generation += 1
        self.history.clear()
        self.measurement_status.set("建立参考中 / Calibrating")
        self.render_chart()

    def choose_model(self):
        path = filedialog.askopenfilename(filetypes=[("ONNX", "*.onnx")])
        if path:
            self.model.set(path)

    def select_region(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Region", "请先停止预览 / Stop preview first")
            return
        if self.region_selector is not None:
            return
        self.root.withdraw()
        self.root.update_idletasks()

        def done(region):
            self.region_selector = None
            self.root.deiconify()
            if region is not None:
                self.region = region
                self.last_pair = None
                self.photo = None
                self.canvas.delete("all")
                self.reset_reference()
                self.status.set(f"Region / 区域: {region.x}, {region.y} · {region.width} x {region.height} px")

        try:
            self.region_selector = ScreenRegionSelector(self.root, current=self.region, on_done=done)
        except Exception as exc:
            self.root.deiconify()
            messagebox.showerror("Region / 区域", f"无法选择屏幕区域 / Cannot select screen region: {exc}")

    def choose_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.avi *.mkv *.mov *.webm")])
        if path:
            self.start(path)

    def start(self, video):
        if self.worker and self.worker.is_alive():
            return
        mode = self.mode.get()
        if mode == MODES[0] and not Path(self.model.get()).is_file():
            messagebox.showerror("Model", "请选择 RTM Pose 2D ONNX 模型 / Select an RTM Pose 2D ONNX model")
            return
        if video is None and self.region is None:
            self.select_region()
            return
        self.stop_event.clear()
        self.last_pair = None
        self.photo = None
        self.canvas.delete("all")
        self.options_changed()
        self.status.set("Loading / 加载中…")
        self.worker = threading.Thread(target=self.run, args=(self.model.get(), video, self.region, mode), daemon=True)
        self.worker.start()

    def publish(self, value):
        try:
            self.events.put_nowait(value)
        except queue.Full:
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            self.events.put_nowait(value)

    def run(self, model_path, video, region, mode):
        cap = None
        screen = None
        try:
            model = None
            if mode == MODES[0]:
                from rtmlib import RTMPose
                model = RTMPose(model_path, model_input_size=(192, 256), backend="onnxruntime", device="cpu")
                shape = model.session.get_inputs()[0].shape
                if list(shape[-2:]) != [256, 192]:
                    raise ValueError("Requires 256x192 RTM Pose 2D model / 需要 256x192 的 2D 模型")
            if video:
                cap = cv2.VideoCapture(video)
                if not cap.isOpened():
                    raise ValueError("Cannot open video / 无法打开视频")
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not np.isfinite(fps) or fps <= 0:
                    fps = 30
            else:
                if region is None:
                    raise ValueError("请选择屏幕区域 / Select a screen region")
                screen = ScreenCapture(region)
                fps = 60
            source_status = (f"Screen capture / 屏幕采集 X {region.x} Y {region.y} · "
                             f"{region.width}x{region.height} px · " if screen is not None else "")
            engine = Stabilizer(self.current_options)
            observations = ImageObservations()
            motion = FrameMotion(scale=mode == MODES[2])
            generation = self.reference_generation
            start = time.perf_counter()
            count = 0
            skipped = 0
            previous_stamp = None
            resets = 0
            while not self.stop_event.is_set():
                tick = time.perf_counter()
                if cap is not None:
                    target = int((tick - start) * fps)
                    # Skip overdue source frames rather than building a playback queue.
                    while count < target and not self.stop_event.is_set():
                        if not cap.grab():
                            break
                        count += 1
                        skipped += 1
                    ok, frame = cap.read()
                    if not ok:
                        break
                    stamp = count / fps
                    count += 1
                else:
                    frame = screen.grab_bgr().copy()
                    stamp = tick
                frame = resize_for_processing(frame, self.processing_edge)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if self.stop_event.is_set():
                    break
                if generation != self.reference_generation:
                    generation = self.reference_generation
                    observations = ImageObservations()
                    motion = FrameMotion(scale=mode == MODES[2])
                if model is None:
                    observation, vectors = motion.update(gray, stamp)
                    marked = frame.copy()
                    for a, b in vectors:
                        cv2.arrowedLine(marked, tuple(a.astype(int)), tuple(b.astype(int)), (255, 220, 40), 1, cv2.LINE_AA, tipLength=0.3)
                    pair = (frame, marked)
                    ms = (time.perf_counter() - tick) * 1000
                    status = source_status + f"{mode} · Analysis size / 分析尺寸 {frame.shape[1]}x{frame.shape[0]} · Processing / 处理 {ms:.1f} ms · Features / 特征 {len(vectors)}"
                    self.publish((pair, status, observation, generation))
                    deadline = start + count / fps if cap is not None else tick + 1 / fps
                    self.stop_event.wait(max(0, deadline - time.perf_counter()))
                    continue
                infer_start = time.perf_counter()
                points, scores = model(frame)
                infer_ms = (time.perf_counter() - infer_start) * 1000
                raw = np.full((17, 2), np.nan, np.float32)
                confidence = np.zeros(17)
                if len(points) and len(scores):
                    if points.shape[-1] != 2 or points.shape[-2] < 17:
                        raise ValueError("Incompatible keypoints / 模型关键点不兼容")
                    raw[:] = points[0, :17, :2]
                    confidence[:] = scores[0, :17]
                if engine.options != self.current_options:
                    engine = Stabilizer(self.current_options)
                filtered, rejected = engine.update(gray, raw, confidence, stamp)
                if engine.reset_reason:
                    observations = ImageObservations()
                    resets += 1
                observation = observations.update(filtered, confidence, rejected, frame.shape, stamp)
                shown = raw.copy()
                shown[confidence < 0.35] = np.nan
                pair = (draw(frame, shown, (40, 180, 255), rejected), draw(frame, filtered, (255, 220, 40)))
                if observation.center is not None:
                    center = tuple(int(v) for v in observation.center)
                    cv2.drawMarker(pair[1], center, (240, 240, 240), cv2.MARKER_CROSS, 16, 2)
                ms = (time.perf_counter() - tick) * 1000
                gap_ms = (stamp - previous_stamp) * 1000 if previous_stamp is not None else 0
                previous_stamp = stamp
                status = source_status + f"Analysis size / 分析尺寸 {frame.shape[1]}x{frame.shape[0]} · Inference / 推理 {infer_ms:.1f} ms · Processing / 处理 {ms:.1f} ms · Gap / 帧间隔 {gap_ms:.0f} ms · Resets / 重置 {resets} · Visible / 可见 {np.isfinite(filtered[:, 0]).sum()}/17"
                if cap is not None:
                    status += f" · Skipped / 视频跳过 {skipped}"
                self.publish((pair, status, observation, generation))
                deadline = start + count / fps if cap is not None else tick + 1 / fps
                self.stop_event.wait(max(0, deadline - time.perf_counter()))
        except Exception as exc:
            self.publish((None, f"Error / 错误: {exc}", None, self.reference_generation))
        finally:
            if cap is not None:
                cap.release()
            if screen is not None:
                screen.close()

    def poll(self):
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                break
        if latest and latest[3] == self.reference_generation:
            pair, status, observation, generation = latest
            self.status.set(status)
            if observation is not None and generation == self.reference_generation:
                self.history.append(observation)
                while self.history and observation.timestamp - self.history[0].timestamp > 8:
                    self.history.popleft()
                self.measurement_status.set({"ready": "相对参考 / Relative to reference",
                                             "calibrating": "建立参考中 / Calibrating",
                                             "missing": "有效特征不足 / Insufficient features"}[observation.state])
                self.render_chart()
            if pair is not None:
                self.last_pair = pair
                self.render()
        if self.worker and not self.worker.is_alive():
            self.worker = None
            self.status.set(self.status.get() + " · Stopped / 已停止")
        self.root.after(16, self.poll)

    def render_chart(self):
        self.chart.delete("all")
        w = max(2, self.chart.winfo_width())
        labels = ("左右 / X (% width)", "上下 / Y (% height)", "尺度 / Size (%)")
        colors = ("#76c6ff", "#e8c16d", "#d5a3ed")
        end = self.history[-1].timestamp if self.history else 0
        for axis, (label, color) in enumerate(zip(labels, colors)):
            top = axis * 50
            value = self.history[-1].values[axis] if self.history and self.history[-1].values else None
            if axis == 2 and self.mode.get() == MODES[1]:
                label, value = "尺度 / Size (N/A)", None
            number = "--" if value is None else f"{value:+.1f}%"
            self.chart.create_text(8, top + 13, text=label, fill=color, anchor="w")
            self.chart.create_text(8, top + 33, text=number, fill="white", anchor="w")
            left, right, middle = 195, max(196, w - 42), top + 25
            self.chart.create_line(left, middle, right, middle, fill="#3d4447")
            extent = max(5, max((abs(s.values[axis]) for s in self.history if s.values), default=0))
            self.chart.create_text(w - 4, top + 8, text=f"{extent:.0f}%", fill="#9ca4a7", anchor="ne")
            previous = None
            for sample in self.history:
                if axis == 2 and self.mode.get() == MODES[1]:
                    break
                if sample.values is None:
                    previous = None
                    continue
                x = left + (sample.timestamp - (end - 8)) / 8 * (right - left)
                y = middle - sample.values[axis] / extent * 18
                if previous is not None and sample.timestamp - previous[2] <= 0.5:
                    self.chart.create_line(previous[0], previous[1], x, y, fill=color, width=2)
                previous = (x, y, sample.timestamp)

    def render(self):
        if self.last_pair is None:
            return
        w, h = max(2, self.canvas.winfo_width()), max(2, self.canvas.winfo_height())
        image = Image.new("RGB", (w, h), "#111111")
        for i, frame in enumerate(self.last_pair):
            part = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            part.thumbnail((max(1, w // 2 - 8), h), Image.Resampling.BILINEAR)
            image.paste(part, (i * (w // 2) + (w // 2 - part.width) // 2, (h - part.height) // 2))
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

    def close(self):
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.status.set("Stopping / 正在停止…")
            self.root.after(100, self.close)
            return
        saved = dict(zip(("reject", "flow", "kalman", "smooth"), (v.get() for v in self.options)))
        saved["model"] = self.model.get()
        saved["mode"] = self.mode.get()
        saved["version"] = VERSION
        saved["resolution"] = self.processing_edge
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Standalone pose preview; no device output")
    parser.add_argument("--smoke", action="store_true", help="Open UI briefly and close")
    args = parser.parse_args()
    configure_dpi_awareness()
    root = tk.Tk()
    app = App(root)
    if args.smoke:
        root.after(1500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
