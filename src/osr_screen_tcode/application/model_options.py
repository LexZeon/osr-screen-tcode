"""Optional Hybrid v2 model switches, selection and bounded download events.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk
from ..config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from ..ui_layout import ControlSidebar, display_scale
from .tooltips import Tooltip


class ModelOptionsMixin:
    def _v2_model_variables(self):
        return {name: getattr(self, f"v2_{name}") for name in
                ("vittrack_enabled", "neuflow_enabled", "vittrack_model_path", "neuflow_model_path")}

    def _v2_model_options_changed(self, *_args):
        # Only the Tk thread reads variables. Workers receive an independent
        # snapshot when starting, including an explicit mode gate for Pose/v1.
        values = {name: variable.get() for name, variable in self._v2_model_variables().items()}
        values.update(gpu_enabled=self.rtm_pose_gpu_enabled.get(), gpu_backend=self.rtm_pose_gpu_backend.get())
        active = self._tracker_internal(self.tracker_mode.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE)
        if not active:
            values["vittrack_enabled"] = values["neuflow_enabled"] = False
        def relevant(options):
            result = {model: options.get(f"{model}_enabled", False) for model in ("vittrack", "neuflow")}
            for model, enabled in tuple(result.items()):
                if enabled:
                    result[f"{model}_model_path"] = options.get(f"{model}_model_path", "")
            if result["neuflow"]:
                result.update(gpu_enabled=options.get("gpu_enabled"), gpu_backend=options.get("gpu_backend"))
            return result
        changed = relevant(self._v2_model_options) != relevant(values)
        self._v2_model_options = values
        if changed and active and ((self.worker and self.worker.is_alive()) or self._video_analysis_active()):
            self.stop()
            self.status.set(self._dt("模型选项已更改；请重新开始分析。", "Model options changed; restart analysis to apply."))

    def _v2_model_controls(self, parent, row, tracker=None, variables=None, compact=False, gpu_enabled=None, bounded=False):
        tracker = self.tracker_mode if tracker is None else tracker
        variables = self._v2_model_variables() if variables is None else variables
        gpu_enabled = self.rtm_pose_gpu_enabled if gpu_enabled is None else gpu_enabled
        if bounded:
            # Preview space is shared with the image. Keep optional setup closed
            # initially, and retain natural-size controls on a scrollable surface
            # when the user opens it, including in narrow/high-DPI layouts.
            outer = ttk.Frame(parent)
            outer.grid(row=row, column=0, columnspan=3 if compact else 4, sticky="ew", pady=4)
            outer.columnconfigure(0, weight=1)
            expanded = tk.BooleanVar(outer, value=False)
            header = ttk.Button(outer, command=lambda: expanded.set(not expanded.get()))
            header.grid(row=0, column=0, sticky="w")
            scroll = ControlSidebar(outer)
            scroll.configure(width=1)
            scroll.grid_propagate(False)
            scroll.content.configure(padding=4)
            scroll.grid(row=1, column=0, sticky="ew")
            body = self._v2_model_controls(scroll.content, 0, tracker, variables,
                                           compact=True, gpu_enabled=gpu_enabled)
            outer.model_controls = body.model_controls
            outer.model_body = body
            outer.model_scroll = scroll
            outer.model_header = header
            outer.model_expanded = expanded
            preview = parent.master

            def size_scroll(_event=None):
                if outer.winfo_exists():
                    # Also bound by current preview height: a 300% landscape
                    # display must not spend its whole height on setup controls.
                    height = min(round(140 * display_scale(outer)),
                                 max(48, round(preview.winfo_height() * .22)))
                    scroll.configure(height=height)

            def refresh_outer(*_args):
                if not outer.winfo_exists():
                    return
                visible = self._tracker_internal(tracker.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE)
                outer.grid() if visible else outer.grid_remove()
                opened = expanded.get()
                header.configure(text=("− " if opened else "+ ") + self._dt("模型", "Models"))
                size_scroll()
                scroll.grid() if opened else scroll.grid_remove()

            traces = [(v, v.trace_add("write", refresh_outer)) for v in (tracker, expanded)]
            resize_token = preview.bind("<Configure>", size_scroll, add="+")
            def dispose_outer(event):
                if event.widget is outer:
                    preview.unbind("<Configure>", resize_token)
                    for variable, token in traces:
                        variable.trace_remove("write", token)
            outer.bind("<Destroy>", dispose_outer, add="+")
            Tooltip(header, self._dt("展开或收起可选模型设置；两项默认关闭。较窄时可横向、纵向滚动，Tab 自动显示当前控件。",
                "Expand or collapse optional model settings; both default off. Scroll horizontally or vertically when narrow; Tab reveals the focused control."))
            refresh_outer()
            return outer
        box = ttk.LabelFrame(parent, text=self._dt("v2 可选模型（默认关闭）", "v2 optional models (off by default)"), padding=5)
        box.grid(row=row, column=0, columnspan=3 if compact else 4, sticky="ew", pady=4)
        box.columnconfigure(0, weight=1)
        controls = {}
        for index, (model, zh, en) in enumerate((
            ("vittrack", "ViTTrack 主体跟踪", "ViTTrack subject tracking"),
            ("neuflow", "NeuFlow v2 光流辅助", "NeuFlow v2 optical flow assist"),
        )):
            enabled, path = variables[f"{model}_enabled"], variables[f"{model}_model_path"]
            check = ttk.Checkbutton(box, text=self._dt(zh, en), variable=enabled)
            base_row = index * (3 if compact else 2)
            check.grid(row=base_row, column=0, columnspan=3 if compact else 1, sticky="w")
            choose = ttk.Button(box, text=self._dt("选择模型", "Select model"),
                command=lambda m=model, v=path: self._pick_v2_model(m, v, box))
            choose.grid(row=base_row + int(compact), column=1, sticky="e", padx=3)
            download = ttk.Button(box, text=self._dt("下载", "Download"),
                command=lambda m=model, v=path: self._download_v2_model(m, v, box))
            download.grid(row=base_row + int(compact), column=2, sticky="e")
            label = ttk.Label(box, foreground="#555", wraplength=285 if compact else 410)
            label.grid(row=base_row + 1 + int(compact), column=0, columnspan=3, sticky="ew", pady=(0, 3))
            controls[model] = (check, choose, download, label)
            Tooltip(check, self._dt(
                "可单独或同时开启。需要单独下载模型；只辅助混合 v2 与全／半行程的画面观测。缺失或失败时回退原分析，缺测估算仍最多 2 秒。改变模型选项会停止当前分析，再次开始生效。",
                "Enable separately or together. Model files require a separate download. Assists observations in Hybrid v2 and Full/Half Travel only. Missing or failed models fall back to existing analysis; missing-observation estimates remain limited to 2 s. Changing model options stops analysis; restart to apply."))
        gpu_row = 6 if compact else 4
        ttk.Button(box, text=self._dt("GPU 设置", "GPU settings"), command=lambda: self._show_v2_gpu_settings(box, gpu_enabled)).grid(
            row=gpu_row, column=1, columnspan=2, sticky="e", pady=(2, 0))
        ttk.Label(box, text=self._dt("ViTTrack 可用 CPU。NeuFlow 需启用 NVIDIA CUDA，不支持 DirectML；未就绪时使用原光流。",
            "ViTTrack supports CPU. NeuFlow requires enabled NVIDIA CUDA; DirectML is unsupported. Otherwise original flow is used."),
            foreground="#555", wraplength=285 if compact else 410).grid(row=gpu_row + 1, column=0, columnspan=3, sticky="ew")
        box.model_controls = controls

        def refresh(*_args):
            if not box.winfo_exists():
                return
            visible = self._tracker_internal(tracker.get()) in (HYBRID_V2_MODE, STROKE_CYCLE_MODE)
            box.grid() if visible else box.grid_remove()
            for model, (_check, choose, download, label) in controls.items():
                pending = model in self._v2_model_downloads
                download.configure(text=self._dt("取消下载", "Cancel download") if pending else self._dt("下载", "Download"))
                choose.configure(state="disabled" if pending else "normal")
                notice = self._v2_model_notices.get(model, "")
                if pending or notice:
                    label.configure(text=notice)
                elif not variables[f"{model}_enabled"].get():
                    label.configure(text=self._dt("未开启；使用原分析。", "Off; using existing analysis."))
                elif variables[f"{model}_model_path"].get():
                    label.configure(text=self._dt("启动时检查模型：", "Model checked at startup: ") +
                        Path(variables[f"{model}_model_path"].get()).name)
                else:
                    label.configure(text=self._dt("启动时检测已下载模型；未下载请点下载／选择。",
                        "Checks downloaded model at startup; download/select if needed."))

        callbacks = [(variable, variable.trace_add("write", refresh)) for variable in
                     (*variables.values(), tracker, self._v2_model_revision)]
        def dispose(event):
            if event.widget is box:
                for variable, token in callbacks:
                    variable.trace_remove("write", token)
                for model, record in tuple(self._v2_model_downloads.items()):
                    if record["owner"] is box:
                        record["cancel"].set()
        box.bind("<Destroy>", dispose, add="+")
        refresh()
        return box

    def _show_v2_gpu_settings(self, owner=None, enabled=None):
        existing = getattr(self, "_v2_gpu_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        parent = self if owner is None else owner.winfo_toplevel()
        enabled = self.rtm_pose_gpu_enabled if enabled is None else enabled
        previous_grab = self.grab_current()
        dialog = self._v2_gpu_dialog = tk.Toplevel(parent)
        dialog.title(self._dt("共享 GPU 设置", "Shared GPU settings"))
        dialog.transient(parent)
        dialog.grab_set()
        def close():
            dialog.destroy()
            if previous_grab is not None and previous_grab.winfo_exists():
                previous_grab.grab_set()
        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text=self._dt("RTM Pose 与 NeuFlow 共用此设置。NeuFlow 仅支持 NVIDIA CUDA；DirectML 仍可用于 RTM Pose。启用模型不会自动安装运行库，安装后按提示重启。",
            "RTM Pose and NeuFlow share this setting. NeuFlow supports NVIDIA CUDA only; DirectML remains available for RTM Pose. Enabling a model does not install a runtime. Restart after installation when prompted."),
            wraplength=390).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Checkbutton(body, text=self._dt("启用 GPU 加速", "Enable GPU acceleration"),
            variable=enabled).grid(row=1, column=0, columnspan=3, sticky="w")
        self._gpu_status_controls(body, 2, enabled, tk.StringVar())
        token = enabled.trace_add("write", lambda *_args: self._schedule_rtm_pose_gpu_status_refresh())
        def dispose(event):
            if event.widget is dialog:
                enabled.trace_remove("write", token)
        dialog.bind("<Destroy>", dispose, add="+")
        ttk.Button(body, text=self._dt("关闭", "Close"), command=close).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.bind("<Escape>", lambda _event: close())

    def _pick_v2_model(self, model, variable, owner):
        from ..v2_model_assets import validate_model_path
        path = filedialog.askopenfilename(parent=owner, title=self._dt("选择模型", "Select model"),
            filetypes=(("ONNX", "*.onnx"), (self._dt("所有文件", "All files"), "*.*")))
        if not path:
            return
        valid, reason = validate_model_path(model, path)
        if valid:
            self._v2_model_notices.pop(model, None)
            variable.set(path)
        else:
            self._v2_model_notices[model] = self._dt("选择被拒绝，保留原模型：", "Selection rejected; previous model unchanged: ") + self._v2_model_error_text(reason)
        self._v2_model_revision.set(self._v2_model_revision.get() + 1)

    def _download_v2_model(self, model, variable, owner):
        from ..v2_model_assets import download_model
        if model in self._v2_model_downloads:
            self._v2_model_downloads[model]["cancel"].set()
            return
        self._v2_model_download_token += 1
        token = self._v2_model_download_token
        cancel = threading.Event()
        self._v2_model_downloads[model] = {"token": token, "cancel": cancel,
            "variable": variable, "original": variable.get(), "owner": owner}
        self._v2_model_notices[model] = self._dt("模型下载中...", "Downloading model...")
        self._v2_model_revision.set(self._v2_model_revision.get() + 1)

        def worker():
            last_progress = 0.0
            def progress(done, total):
                nonlocal last_progress
                now = time.monotonic()
                if now - last_progress >= 0.25:
                    last_progress = now
                    self._queue_latest({"v2_model_event": {"model": model, "token": token,
                        "kind": "progress", "percent": int(100 * done / max(1, total))}})
            try:
                path = download_model(model, cancel=cancel, progress=progress)
                event = {"kind": "cancelled"} if cancel.is_set() else {"kind": "done", "path": str(path)}
            except Exception as exc:
                event = {"kind": "cancelled"} if cancel.is_set() else {"kind": "error", "reason": str(exc)}
            self._queue_latest({"v2_model_event": {"model": model, "token": token, **event}})

        threading.Thread(target=worker, daemon=True, name=f"v2-model-{model}").start()

    def _finish_v2_model_event(self, event):
        model = event["model"]
        record = self._v2_model_downloads.get(model)
        if record is None or record["token"] != event["token"]:
            return
        kind = event["kind"]
        if kind == "progress":
            self._v2_model_notices[model] = self._dt("模型下载中", "Downloading model") + f": {event['percent']}%"
        else:
            self._v2_model_downloads.pop(model)
            alive = record["owner"].winfo_exists()
            if kind == "done" and alive and not record["cancel"].is_set() and record["variable"].get() == record["original"]:
                self._v2_model_notices.pop(model, None)
                record["variable"].set(event["path"])
            elif kind == "error":
                self._v2_model_notices[model] = self._dt("下载失败，保留原模型：", "Download failed; previous model unchanged: ") + self._v2_model_error_text(event["reason"])
            else:
                self._v2_model_notices.pop(model, None)
        self._v2_model_revision.set(self._v2_model_revision.get() + 1)

    def _cancel_v2_model_downloads(self):
        for record in self._v2_model_downloads.values():
            record["cancel"].set()
        self._v2_model_downloads.clear()
        self._v2_model_notices.clear()
        self._v2_model_revision.set(self._v2_model_revision.get() + 1)

    def _v2_model_error_text(self, reason):
        translations = {
            "Model artifact is not available.": "模型文件暂不可用。",
            "Select the supported ONNX model.": "请选择受支持的 ONNX 模型。",
            "Model file is missing.": "模型文件不存在。",
            "Model file size does not match. Download the supported model.": "模型大小不匹配，请下载受支持的版本。",
            "Model checksum does not match. Download the supported model.": "模型校验不匹配，请下载受支持的版本。",
            "Model file cannot be read.": "无法读取模型文件。",
            "The model server returned an unsupported redirect.": "模型服务器的重定向不受支持。",
            "The model server could not provide the file.": "模型服务器无法提供文件。",
            "The downloaded model size does not match.": "下载的模型大小不匹配。",
            "The model download timed out. Try again.": "模型下载超时，请重试。",
            "Model verification failed. Try downloading again.": "模型校验失败，请重新下载。",
            "Model download failed. Check the network and available disk space.": "模型下载失败，请检查网络和可用磁盘空间。",
        }
        return translations.get(str(reason), str(reason)) if self.ui_language != "en" else str(reason)
