"""Existing RTM model validation, selection and download workflow.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import threading
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from ..config import RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE
from .model_sources import RTM_POSE_2D_MODEL_NAME, RTM_POSE_2D_MODEL_URL


class ModelsMixin:
    def _active_rtm_pose_model_var(self, value: str | None = None) -> tk.StringVar:
        return self.rtm_pose_2d_model_path

    def _refresh_active_rtm_pose_model_path(self) -> None:
        if not hasattr(self, "rtm_pose_model_path"):
            return
        self._rtm_pose_model_path_syncing = True
        try:
            self.rtm_pose_model_path.set(self._active_rtm_pose_model_var().get())
        finally:
            self._rtm_pose_model_path_syncing = False

    def _store_active_rtm_pose_model_path(self) -> None:
        if self._rtm_pose_model_path_syncing or not hasattr(self, "rtm_pose_model_path"):
            return
        self._active_rtm_pose_model_var().set(self.rtm_pose_model_path.get())

    def _rtm_pose_mode_active(self, value: str | None = None) -> bool:
        return self._rtm_pose_2d_mode_active(value)

    def _rtm_pose_2d_mode_active(self, value: str | None = None) -> bool:
        raw_value = self.tracker_mode.get() if value is None else value
        return self._tracker_internal(raw_value) == RTM_POSE_2D_MODE

    def _pose_model_required(self, value=None, output_mode=None, v2_pose=None) -> bool:
        mode = self._tracker_internal(self.tracker_mode.get() if value is None else value)
        six = (self.output_mode.get() if output_mode is None else output_mode) == "Six Axis"
        enabled = self.hybrid_v2_pose_enabled.get() if v2_pose is None else v2_pose
        return mode == RTM_POSE_2D_MODE or (mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE) and six and enabled)

    def _rtm_pose_3d_mode_active(self, value: str | None = None) -> bool:
        return False  # Shared legacy UI helper; 3D is not an analysis mode.

    def _rtm_pose_model_spec(self, mode: str) -> tuple[str, str, int, int, str]:
        return (RTM_POSE_2D_MODEL_NAME, RTM_POSE_2D_MODEL_URL, 5_000_000, 2, "RTM Pose 2D")

    def _validate_rtm_pose_model_path(self, path_value: str, mode: str) -> tuple[bool, str]:
        model_name, _url, min_size, expected_outputs, label = self._rtm_pose_model_spec(mode)
        path_text = str(path_value or "").strip().strip('"')
        if not path_text:
            return False, f"{label} 需要先选择或下载模型。"
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            return False, f"模型文件不存在：{path_text}"
        if path.suffix.lower() != ".onnx":
            return False, "请选择 .onnx 模型文件。"
        try:
            stat = path.stat()
        except OSError as exc:
            return False, f"无法读取模型文件：{exc}"
        if stat.st_size < min_size:
            return False, f"模型文件太小，可能下载不完整。当前模式需要 {model_name}。"

        cache = getattr(self, "_rtm_pose_model_validation_cache", None)
        if cache is None:
            cache = {}
            self._rtm_pose_model_validation_cache = cache
        try:
            cache_path = str(path.resolve())
        except OSError:
            cache_path = str(path)
        cache_key = (self._tracker_internal(mode), cache_path, int(stat.st_size), int(stat.st_mtime_ns))
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import onnxruntime as ort

            session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            output_count = len(session.get_outputs())
        except Exception as exc:
            result = (False, f"ONNX 模型无法读取：{exc}")
            cache[cache_key] = result
            return result

        if output_count != expected_outputs:
            result = (
                False,
                f"模型类型不匹配：当前文件有 {output_count} 个输出，{label} 需要 {expected_outputs} 个输出。请使用 {model_name}。",
            )
            cache[cache_key] = result
            return result

        result = (True, f"{label} 模型可用：{path.name}")
        cache[cache_key] = result
        return result

    def _find_existing_rtm_pose_model(self, mode: str) -> Path | None:
        model_name, _url, _min_size, _expected_outputs, _label = self._rtm_pose_model_spec(mode)
        model_dir = self._rtm_pose_model_dir()
        candidates = [model_dir / model_name]
        if model_dir.exists():
            candidates.extend(path for path in model_dir.glob("*.onnx") if path.name != model_name)
        for candidate in candidates:
            ok, _message = self._validate_rtm_pose_model_path(str(candidate), mode)
            if ok:
                return candidate
        return None

    def _apply_rtm_pose_model_path(self, path: str, mode: str, target_var: tk.StringVar | None = None) -> None:
        self.rtm_pose_2d_model_path.set(path)
        if target_var is not None:
            target_var.set(path)
        self._refresh_active_rtm_pose_model_path()

    def _ensure_rtm_pose_model_ready(self) -> bool:
        if not self._pose_model_required():
            return True
        mode = self._tracker_internal(self.tracker_mode.get())
        model_var = self._active_rtm_pose_model_var(mode)
        ok, message = self._validate_rtm_pose_model_path(model_var.get(), mode)
        if ok:
            self.rtm_model_download_status_text.set(message)
            return True

        detected = self._find_existing_rtm_pose_model(mode)
        if detected is not None:
            self._apply_rtm_pose_model_path(str(detected), mode)
            text = f"{self._t('自动检测到模型')}: {detected.name}"
            self.status.set(text)
            self.rtm_model_download_status_text.set(text)
            return True

        text = f"{self._t('请先选择或下载正确的 RTM Pose 模型。')}\n{message}"
        self.status.set(text)
        self.rtm_model_download_status_text.set(message)
        messagebox.showwarning(self._t("模型不匹配"), text)
        return False

    def pick_rtm_pose_3d_model(self) -> None:
        self._choose_rtm_pose_3d_model_for_var(self.rtm_pose_model_path)

    def _choose_rtm_pose_3d_model_for_var(self, variable: tk.StringVar, mode: str | None = None) -> None:
        path = filedialog.askopenfilename(
            title=self._t("RTM Pose 模型"),
            filetypes=(("ONNX", "*.onnx"), ("All files", "*.*")),
        )
        if path:
            variable.set(path)
            target_mode = self._tracker_internal(mode or self.tracker_mode.get())
            if target_mode in (RTM_POSE_2D_MODE, HYBRID_V2_MODE):
                ok, message = self._validate_rtm_pose_model_path(path, target_mode)
                self.rtm_model_download_status_text.set(message)
                if not ok:
                    messagebox.showwarning(self._t("模型不匹配"), message)

    def download_rtm_pose_3d_model(self, target_var: tk.StringVar | None = None, mode: str | None = None) -> None:
        if self._rtm_pose_3d_downloading:
            self.status.set(self._t("模型下载中..."))
            self.rtm_model_download_status_text.set(self._t("模型下载中..."))
            return
        target_mode = self._tracker_internal(mode or self.tracker_mode.get())
        if target_mode not in (RTM_POSE_2D_MODE, HYBRID_V2_MODE):
            target_mode = RTM_POSE_2D_MODE
        detected = self._find_existing_rtm_pose_model(target_mode)
        if detected is not None:
            self._apply_rtm_pose_model_path(str(detected), target_mode, target_var)
            text = f"{self._t('自动检测到模型')}: {detected.name}"
            self.status.set(text)
            self.rtm_model_download_status_text.set(text)
            return
        self._rtm_pose_3d_download_target = target_var
        self._rtm_pose_3d_download_mode = target_mode
        self._rtm_pose_3d_downloading = True
        self.rtm_model_download_button_text.set(self._t("下载中..."))
        self.rtm_model_download_status_text.set(self._t("未检测到模型，开始下载..."))
        self.status.set(self._t("未检测到模型，开始下载..."))

        def worker() -> None:
            try:
                model_dir = self._rtm_pose_model_dir()
                model_dir.mkdir(parents=True, exist_ok=True)
                model_name, source_url, _min_size, _expected_outputs, _label = self._rtm_pose_model_spec(target_mode)
                target = model_dir / model_name
                partial = target.with_suffix(target.suffix + ".download")
                ok, _message = self._validate_rtm_pose_model_path(str(target), target_mode)
                if ok:
                    self._queue_latest(
                        {
                            "rtm_model_path": str(target),
                            "rtm_model_mode": target_mode,
                            "status_text": f"{self._t('自动检测到模型')}: {target.name}",
                            "rtm_download_status": f"{self._t('自动检测到模型')}: {target.name}",
                        }
                    )
                    return

                last_percent = -1

                def report(block_count: int, block_size: int, total_size: int) -> None:
                    nonlocal last_percent
                    if total_size <= 0:
                        return
                    downloaded = min(total_size, block_count * block_size)
                    percent = int(downloaded * 100 / total_size)
                    if percent >= last_percent + 5:
                        last_percent = percent
                        text = f"{self._t('模型下载中...')} {percent}%"
                        self._queue_latest({"status_text": text, "rtm_download_status": text})

                urllib.request.urlretrieve(source_url, partial, report)
                zip_path = target.with_suffix(".zip")
                partial.replace(zip_path)
                with zipfile.ZipFile(zip_path) as archive:
                    onnx_members = [name for name in archive.namelist() if name.lower().endswith(".onnx")]
                    if not onnx_members:
                        raise ValueError("ONNX model not found in downloaded zip")
                    with archive.open(onnx_members[0]) as source, target.open("wb") as destination:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            destination.write(chunk)
                try:
                    zip_path.unlink()
                except OSError:
                    pass
                ok, message = self._validate_rtm_pose_model_path(str(target), target_mode)
                if not ok:
                    raise ValueError(message)
                self._queue_latest(
                    {
                        "rtm_model_path": str(target),
                        "rtm_model_mode": target_mode,
                        "status_text": self._t("模型下载完成"),
                        "rtm_download_status": self._t("模型下载完成"),
                    }
                )
            except Exception as exc:
                text = f"{self._t('模型下载失败')}: {exc}"
                self._queue_latest({"error": text, "rtm_download_status": text})
            finally:
                self._queue_latest({"rtm_download_done": True})

        threading.Thread(target=worker, daemon=True).start()
