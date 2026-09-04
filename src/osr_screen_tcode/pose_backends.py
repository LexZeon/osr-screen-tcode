from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class RtmPose3dResult:
    keypoints3d: np.ndarray
    keypoints2d: np.ndarray
    scores: np.ndarray
    status: str = "ok"


def _resolve_onnxruntime_device(requested_device: str) -> tuple[str, str]:
    requested = str(requested_device or "cpu").strip().lower()
    if requested != "cuda":
        return "cpu", "CPU"
    try:
        import onnxruntime as ort

        providers = set(ort.get_available_providers())
    except Exception:
        providers = set()
    if "CUDAExecutionProvider" in providers:
        return "cuda", "CUDA GPU"
    return "cpu", "GPU unavailable, using CPU"


class OptionalRtmPose3dBackend:
    """Lazy optional RTMPose3D backend used only for preview annotation."""

    def __init__(self, model_path: str, device: str = "cpu") -> None:
        self.model_path = str(model_path or "").strip()
        self.requested_device = str(device or "cpu").strip().lower()
        self.device, self.device_status = _resolve_onnxruntime_device(self.requested_device)
        self._model = None
        self._status = ""
        self._load_failed = False

    @property
    def status(self) -> str:
        if not self.model_path:
            return "RTM Pose 3D: waiting for ONNX model path"
        if self._status:
            return self._status
        return "RTM Pose 3D: ready"

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        if not self.model_path:
            self._status = "RTM Pose 3D: set ONNX model path"
            self._load_failed = True
            return False
        path = Path(self.model_path)
        if not path.exists():
            self._status = f"RTM Pose 3D: model not found: {path.name}"
            self._load_failed = True
            return False
        try:
            from rtmlib import RTMPose3d

            self._model = RTMPose3d(str(path), model_input_size=(288, 384), backend="onnxruntime", device=self.device)
            self._status = f"RTM Pose 3D: loaded ({self.device_status})"
            return True
        except Exception as exc:
            if self.requested_device == "cuda" and self.device == "cuda":
                try:
                    from rtmlib import RTMPose3d

                    self.device = "cpu"
                    self.device_status = "GPU failed, using CPU"
                    self._model = RTMPose3d(str(path), model_input_size=(288, 384), backend="onnxruntime", device=self.device)
                    self._status = f"RTM Pose 3D: loaded ({self.device_status})"
                    return True
                except Exception as cpu_exc:
                    exc = cpu_exc
            self._status = f"RTM Pose 3D load failed: {exc}"
            self._load_failed = True
            return False

    def infer(self, image_bgr: np.ndarray) -> RtmPose3dResult | None:
        if not self._load():
            return None
        try:
            keypoints3d, scores, _keypoints_simcc, keypoints2d = self._model(image_bgr)
        except Exception as exc:
            self._status = f"RTM Pose 3D infer failed: {exc}"
            return None
        keypoints3d = np.asarray(keypoints3d)
        keypoints2d = np.asarray(keypoints2d)
        scores = np.asarray(scores)
        if keypoints3d.size == 0 or keypoints2d.size == 0 or scores.size == 0:
            self._status = "RTM Pose 3D: no person"
            return None
        person_count = min(len(keypoints3d), len(keypoints2d), len(scores))
        if person_count <= 0:
            self._status = "RTM Pose 3D: no person"
            return None
        body_scores = scores[:person_count, : min(17, scores.shape[1])]
        index = int(np.nanargmax(np.nanmean(body_scores, axis=1)))
        self._status = f"RTM Pose 3D: tracking ({self.device_status})"
        return RtmPose3dResult(
            keypoints3d=np.asarray(keypoints3d[index]),
            keypoints2d=np.asarray(keypoints2d[index]),
            scores=np.asarray(scores[index]).reshape(-1),
            status=self._status,
        )


class OptionalRtmPose2dBackend:
    """Lazy optional RTMPose 2D backend for lower-latency dance tracking."""

    def __init__(self, model_path: str, device: str = "cpu") -> None:
        self.model_path = str(model_path or "").strip()
        self.requested_device = str(device or "cpu").strip().lower()
        self.device, self.device_status = _resolve_onnxruntime_device(self.requested_device)
        self._model = None
        self._status = ""
        self._load_failed = False

    @property
    def status(self) -> str:
        if not self.model_path:
            return "RTM Pose 2D: waiting for ONNX model path"
        if self._status:
            return self._status
        return "RTM Pose 2D: ready"

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        if not self.model_path:
            self._status = "RTM Pose 2D: set ONNX model path"
            self._load_failed = True
            return False
        path = Path(self.model_path)
        if not path.exists():
            self._status = f"RTM Pose 2D: model not found: {path.name}"
            self._load_failed = True
            return False
        try:
            from rtmlib import RTMPose

            self._model = RTMPose(str(path), model_input_size=(192, 256), backend="onnxruntime", device=self.device)
            self._status = f"RTM Pose 2D: loaded ({self.device_status})"
            return True
        except Exception as exc:
            if self.requested_device == "cuda" and self.device == "cuda":
                try:
                    from rtmlib import RTMPose

                    self.device = "cpu"
                    self.device_status = "GPU failed, using CPU"
                    self._model = RTMPose(str(path), model_input_size=(192, 256), backend="onnxruntime", device=self.device)
                    self._status = f"RTM Pose 2D: loaded ({self.device_status})"
                    return True
                except Exception as cpu_exc:
                    exc = cpu_exc
            self._status = f"RTM Pose 2D load failed: {exc}"
            self._load_failed = True
            return False

    def infer(self, image_bgr: np.ndarray) -> RtmPose3dResult | None:
        if not self._load():
            return None
        try:
            keypoints2d, scores = self._model(image_bgr)
        except Exception as exc:
            self._status = f"RTM Pose 2D infer failed: {exc}"
            return None
        keypoints2d = np.asarray(keypoints2d)
        scores = np.asarray(scores)
        if keypoints2d.size == 0 or scores.size == 0:
            self._status = "RTM Pose 2D: no person"
            return None
        person_count = min(len(keypoints2d), len(scores))
        if person_count <= 0:
            self._status = "RTM Pose 2D: no person"
            return None
        body_scores = scores[:person_count, : min(17, scores.shape[1])]
        index = int(np.nanargmax(np.nanmean(body_scores, axis=1)))
        points2d = np.asarray(keypoints2d[index], dtype=np.float32)
        points3d = np.zeros((points2d.shape[0], 3), dtype=np.float32)
        points3d[:, :2] = points2d[:, :2]
        self._status = f"RTM Pose 2D: tracking ({self.device_status})"
        return RtmPose3dResult(
            keypoints3d=points3d,
            keypoints2d=points2d,
            scores=np.asarray(scores[index]).reshape(-1),
            status=self._status,
        )
