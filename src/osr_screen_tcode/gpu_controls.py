"""Shared GPU detection/installation controls for the main panel and start dialog."""
from __future__ import annotations

import threading
import time
from tkinter import messagebox, ttk
import tkinter as tk

from .gpu_runtime import install_runtime, probe_gpu, runtime_needs_restart
from .ui_widgets import WideCombobox


GPU_BACKENDS = {"cuda": "CUDA (NVIDIA)", "directml": "ONNX + DirectML (AMD / NVIDIA / Intel)"}


class GpuControls:
    def _gpu_backend_labels(self):
        return {"cuda": self._dt("CUDA（NVIDIA，运行库较大）", "CUDA (NVIDIA, larger runtime)"),
                "directml": self._dt("ONNX + DirectML（多显卡，运行库较小）", "ONNX + DirectML (multi-GPU vendors, smaller runtime)")}

    def _build_gpu_state(self) -> None:
        self._gpu_views = []
        self._gpu_result = None
        self._gpu_check_running = False
        self._gpu_installing = False
        self._gpu_restart_required = False
        self._gpu_stage = ""
        self._gpu_progress = {}
        self._gpu_error = ""
        self._gpu_cancel = threading.Event()
        self._gpu_threads = []
        self._gpu_backend_views = []
        self._gpu_installed_restart = False

    def _start_gpu_task(self, work, name: str) -> None:
        self._gpu_threads = [thread for thread in self._gpu_threads if thread.is_alive()]
        thread = threading.Thread(target=work, name=name, daemon=True)
        self._gpu_threads.append(thread)
        thread.start()

    def _cancel_gpu_tasks(self) -> None:
        self._gpu_cancel.set()
        deadline = time.monotonic() + 2
        for thread in self._gpu_threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))

    def _gpu_status_controls(self, parent, row, enabled, status) -> None:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 2))
        label = ttk.Label(frame, textvariable=status, foreground="#555", wraplength=300)
        label.grid(row=1, column=0, sticky="ew")
        frame.bind("<Configure>", lambda event: label.configure(wraplength=max(80, event.width - 4)), add="+")
        bar = ttk.Progressbar(frame, maximum=100)
        bar.grid(row=2, column=0, sticky="ew", pady=3)
        button = ttk.Button(frame, command=self._install_gpu_runtime)
        button.grid(row=3, column=0, sticky="ew", pady=3)
        recheck = ttk.Button(frame, command=self._recheck_gpu)
        recheck.grid(row=4, column=0, sticky="ew", pady=3)
        choice = tk.StringVar(value=self._gpu_backend_labels()[self.rtm_pose_gpu_backend.get()])
        combo = WideCombobox(frame, textvariable=choice, values=tuple(self._gpu_backend_labels().values()), state="readonly", width=18)
        combo.grid(row=0, column=0, sticky="ew", pady=3)
        def select_backend(_event):
            if self._gpu_installing or (self.worker and self.worker.is_alive()):
                choice.set(self._gpu_backend_labels()[self.rtm_pose_gpu_backend.get()])
                messagebox.showwarning(self._dt("请先停止输出", "Stop Output First"), self._dt(
                    "请等待安装结束并停止实时输出后切换 GPU 后端。", "Wait for installation and stop realtime output before switching GPU backends."))
                return
            self.rtm_pose_gpu_backend.set(next(key for key, value in self._gpu_backend_labels().items() if value == choice.get()))
        combo.bind("<<ComboboxSelected>>", select_backend)
        self._gpu_backend_views.append((combo, choice, enabled))
        self._gpu_views.append((frame, enabled, status, button, recheck, bar))
        self._schedule_rtm_pose_gpu_status_refresh()

    def _refresh_gpu_views(self) -> None:
        backend = self.rtm_pose_gpu_backend.get()
        engine = "DirectML" if backend == "directml" else "CUDA"
        self._gpu_backend_views = [view for view in self._gpu_backend_views if view[0].winfo_exists()]
        for combo, choice, enabled in self._gpu_backend_views:
            choice.set(self._gpu_backend_labels()[backend])
            combo.configure(values=tuple(self._gpu_backend_labels().values()))
            combo.configure(state="disabled" if self._gpu_installing or self._gpu_check_running else "readonly")
            combo.grid() if enabled.get() else combo.grid_remove()
        self._gpu_views = [view for view in self._gpu_views if view[0].winfo_exists()]
        for frame, enabled, status, button, recheck, bar in self._gpu_views:
            show_install = False
            text = self._t("RTM GPU 状态：CPU")
            if self._gpu_installing:
                show_install = True
                stages = {
                    "resolving": ("正在解析兼容组件（可能下载元数据），请保持联网...", "Resolving compatible components (may download metadata)..."),
                    "preparing": ("正在获取下载大小...", "Checking download sizes..."),
                    "installing": ("下载完成，正在解压并安装 GPU 运行库...", "Downloads complete. Extracting and installing GPU libraries..."),
                    "verifying": (f"安装完成，正在验证 {engine} 实际推理...", f"Installation complete. Verifying {engine} inference..."),
                }
                text = self._dt(*stages.get(self._gpu_stage, ("正在准备下载...", "Preparing download...")))
                data = self._gpu_progress
                if self._gpu_stage == "downloading":
                    downloaded, total = data.get("downloaded", 0), data.get("total")
                    amount = f"{downloaded / 1024 ** 2:.1f} MB"
                    if total:
                        amount = f"{min(100, downloaded * 100 / total):.1f}%  ({amount} / {total / 1024 ** 2:.1f} MB)"
                    else:
                        amount += self._dt("（总大小未知）", " (total size unknown)")
                    text = self._dt("正在下载 GPU 运行库：", "Downloading GPU libraries: ") + amount
                    text += f"\n{data.get('index', 1)}/{data.get('count', 1)}  {data.get('component', '')}"
                elif data.get("component") and self._gpu_stage == "preparing":
                    text += "\n" + data["component"]
            elif self._gpu_restart_required:
                text = self._dt(f"启用 {engine} 运行库需要重启，请关闭软件，再双击 Start.cmd。", f"Restart required to activate {engine}. Close the app and run Start.cmd again.")
            elif enabled.get():
                if self._gpu_check_running or self._gpu_result is None:
                    text = self._t("RTM GPU 状态：检测中...")
                elif self._gpu_result.get("ready", self._gpu_result.get("cuda")):
                    text = self._dt(f"RTM GPU 状态：{engine} 推理验证通过", f"RTM GPU Status: {engine} inference verified")
                elif backend == "directml":
                    show_install = self._gpu_result.get("reason") in {"dml_missing", "ort_missing", "load_failed"}
                    if self._gpu_result.get("reason") in {"dml_missing", "ort_missing"}:
                        text = self._dt("软件缺少 ONNX Runtime DirectML 组件。可一键安装，无需 CUDA；需要支持 DirectX 12 的显卡和驱动。", "ONNX Runtime DirectML is not installed. Install below; CUDA is not needed. Requires a DirectX 12 GPU and driver.")
                    else:
                        text = self._dt("DirectML 实际推理失败，当前使用 CPU。请检查 Windows 版本及 DirectX 12 显卡驱动。", "DirectML inference failed; using CPU. Check Windows and your DirectX 12 GPU driver.")
                elif self._gpu_result.get("nvidia"):
                    show_install = True
                    text = self._dt("已检测到 NVIDIA 显卡；GPU 运行库缺失或不兼容，当前使用 CPU。", "NVIDIA GPU detected; GPU runtime is missing or incompatible. Using CPU.")
                    reason = self._gpu_result.get("reason")
                    if reason == "cpu_ort":
                        text = self._dt("已检测到 NVIDIA 显卡，但软件使用 CPU 版 ONNX Runtime。仅安装 CUDA 不够，请安装 GPU 运行库；当前使用 CPU。", "NVIDIA GPU detected, but this app uses CPU-only ONNX Runtime. Installing CUDA alone is not enough. Install GPU Runtime; currently using CPU.")
                    elif reason == "cuda_engine_missing":
                        text = self._dt("当前 ONNX Runtime 是 DirectML 版，不包含 CUDA 引擎。请选择 DirectML 或安装 CUDA 运行库。", "Current ONNX Runtime uses DirectML and does not include CUDA. Select DirectML or install the CUDA runtime.")
                    elif reason == "cudnn_missing":
                        text = self._dt("CUDA 推理可用，但 cuDNN 缺失或无法加载。Pose 模型需要匹配的 cuDNN；当前使用 CPU。", "CUDA inference works, but cuDNN is missing or cannot load. Pose models need matching cuDNN; currently using CPU.")
                    elif reason == "load_failed":
                        text = self._dt("GPU 引擎已找到，但实际推理失败。请检查 CUDA/cuDNN 版本、NVIDIA 驱动及 VC++ 运行库；当前使用 CPU。", "GPU engine found, but inference failed. Check CUDA/cuDNN versions, NVIDIA driver and VC++ runtime; currently using CPU.")
                    elif reason == "ort_missing":
                        text = self._dt("未能加载 ONNX Runtime 推理组件，当前使用 CPU。请安装 GPU 运行库。", "ONNX Runtime could not be imported. Using CPU; please install GPU Runtime.")
                else:
                    text = self._dt("未检测到可用 NVIDIA 显卡/驱动，当前使用 CPU。", "No available NVIDIA GPU/driver detected. Using CPU.")
                if self._gpu_stage == "failed":
                    text = self._dt("安装/验证失败。检查网络、磁盘空间和 NVIDIA 驱动后重试；原环境未覆盖。", "Installation/verification failed. Check network, disk space and NVIDIA driver, then retry. Existing runtime was not replaced.")
                    errors = {
                        "insufficient_disk_space": ("磁盘空间不足，请至少预留 5 GB。", "Not enough disk space; allow at least 5 GB."),
                        "download_verification_failed": ("下载文件校验失败，请重新下载。", "Downloaded file verification failed. Please retry."),
                        "verification_failed": (f"安装后 {engine} 验证未通过，请检查显卡驱动。", f"{engine} verification failed after installation. Check the GPU driver."),
                        "timeout": ("操作超时，请检查网络后重试。", "Operation timed out. Check the network and retry."),
                    }
                    if self._gpu_error in errors:
                        text = self._dt(*errors[self._gpu_error]) + self._dt(" 原环境未覆盖。", " Existing runtime was not replaced.")
                elif self._gpu_result and self._gpu_result.get("reason") == "check_failed":
                    text = self._dt("GPU 检测未完成，请点重新检测。", "GPU check incomplete. Select Check GPU Again.")
                if self._gpu_result and self._gpu_result.get("ort_version") and not self._gpu_check_running:
                    text += "\nONNX Runtime " + self._gpu_result["ort_version"]
                    if self._gpu_result.get("cuda_version"):
                        text += self._dt(" / 所需 CUDA ", " / requires CUDA ") + self._gpu_result["cuda_version"]
            status.set(text)
            label = self._dt(f"一键安装 {engine} 运行库", f"Install {engine} Runtime")
            if self._gpu_installing:
                label = self._dt("下载中...", "Downloading...") if self._gpu_stage == "downloading" else self._dt("安装处理中...", "Setting Up...")
            button.configure(text=label, state="disabled" if self._gpu_installing else "normal")
            button.grid() if show_install else button.grid_remove()
            recheck.configure(text=self._dt("重新检测 GPU", "Check GPU Again"),
                state="disabled" if self._gpu_check_running or self._gpu_installing or self._gpu_restart_required else "normal")
            recheck.grid() if enabled.get() else recheck.grid_remove()
            if self._gpu_installing:
                bar.grid()
                total = self._gpu_progress.get("total")
                bar.stop()
                if self._gpu_stage == "downloading" and total:
                    bar.configure(mode="determinate", value=min(100, self._gpu_progress.get("downloaded", 0) * 100 / total))
                else:
                    bar.configure(mode="indeterminate")
                    bar.start(25)
            else:
                bar.stop()
                bar.grid_remove()

    def _recheck_gpu(self) -> None:
        if self._gpu_check_running or self._gpu_installing or self._gpu_restart_required:
            return
        self._gpu_result = None
        self._gpu_stage = ""
        self._gpu_error = ""
        self._schedule_rtm_pose_gpu_status_refresh()

    def _on_gpu_backend_changed(self) -> None:
        self._gpu_result = None
        self._gpu_stage = ""
        self._gpu_restart_required = self._gpu_installed_restart or runtime_needs_restart(self.rtm_pose_gpu_backend.get())
        self._schedule_rtm_pose_gpu_status_refresh()

    def _schedule_rtm_pose_gpu_status_refresh(self) -> None:
        enabled = self.rtm_pose_gpu_enabled.get() or any(view[0].winfo_exists() and view[1].get() for view in self._gpu_views)
        if enabled and self._gpu_result is None and not self._gpu_check_running and not self._gpu_installing:
            self._gpu_check_running = True
            backend = self.rtm_pose_gpu_backend.get()
            def work():
                try:
                    result = probe_gpu(self._gpu_cancel, backend=backend)
                except Exception:
                    result = {"nvidia": False, "cuda": False, "reason": "check_failed"}
                self._queue_latest({"gpu_event": "checked", "result": result, "backend": backend})
            self._start_gpu_task(work, "gpu-check")
        self._refresh_gpu_views()

    def _install_gpu_runtime(self) -> None:
        if self._gpu_installing:
            return
        if self._gpu_check_running:
            return
        backend = self.rtm_pose_gpu_backend.get()
        if not self._gpu_result or (backend == "cuda" and not self._gpu_result.get("nvidia")):
            self._gpu_result = None
            self._schedule_rtm_pose_gpu_status_refresh()
            return
        if self._connecting or (self.worker and self.worker.is_alive()):
            messagebox.showwarning(self._dt("请先停止输出", "Stop Output First"), self._dt(
                "请停止实时输出并等待连接结束后安装。", "Stop realtime output and wait for connection attempts to finish before installing."))
            return
        components = "ONNX Runtime DirectML" if backend == "directml" else "ONNX Runtime GPU + NVIDIA CUDA/cuDNN"
        download_note = self._dt("DirectML 无需 CUDA，大小以下载进度为准。", "DirectML does not need CUDA; download sizes are shown in progress.") if backend == "directml" else self._dt(
            "CUDA 下载可能超过 1 GB。", "CUDA downloads may exceed 1 GB.")
        prompt = self._dt(
            f"将从 PyPI 下载 {components} 到本测试版用户目录。{download_note} 请预留至少 5 GB 空间。不会修改系统驱动或正式版环境。安装完成需重启软件。继续？",
            f"Download {components} from PyPI into this test's user folder? {download_note} Allow at least 5 GB free space. System drivers and the formal runtime are not changed. Restart the app afterwards. Continue?")
        if not messagebox.askyesno(self._dt("安装 GPU 运行库", "Install GPU Runtime"), prompt):
            return
        self.stop()
        self.disconnect_sink()
        self._gpu_installing = True
        self._gpu_stage = "resolving"
        self._gpu_progress = {}
        self._gpu_error = ""
        self._refresh_gpu_views()
        def work():
            try:
                install_runtime(self._gpu_cancel, lambda data: self._queue_latest({"gpu_event": "stage", "stage": data["stage"], "progress": data}), backend=backend)
                self._queue_latest({"gpu_event": "installed"})
            except Exception as exc:
                self._queue_latest({"gpu_event": "failed", "error": str(exc)})
        self._start_gpu_task(work, "gpu-installer")

    def _finish_gpu_event(self, item) -> None:
        event = item["gpu_event"]
        if event == "checked":
            self._gpu_check_running = False
            if item.get("backend", self.rtm_pose_gpu_backend.get()) != self.rtm_pose_gpu_backend.get():
                self._schedule_rtm_pose_gpu_status_refresh()
                return
            self._gpu_result = item["result"]
        elif event == "stage":
            self._gpu_stage = item["stage"]
            self._gpu_progress = item.get("progress", {})
        elif event in {"installed", "failed"}:
            self._gpu_installing = False
            self._gpu_stage = "failed" if event == "failed" else ""
            self._gpu_restart_required = event == "installed"
            self._gpu_installed_restart = event == "installed"
            self._gpu_error = item.get("error", "")
        self._refresh_gpu_views()
