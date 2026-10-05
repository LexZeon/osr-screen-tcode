"""Optional local model inference for Hybrid v2.

These wrappers provide image-space proposals only. Their outputs do not prove
background motion, physical depth, contact, or device movement. No model is
downloaded, imported or loaded until an enabled caller requests inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np


@dataclass(frozen=True)
class TrackingResult:
    bbox_xywh: tuple[float, float, float, float] | None = None
    confidence: float = 0.0
    valid: bool = False
    reason: str = "not_initialized"


@dataclass(frozen=True)
class FlowResult:
    forward: np.ndarray | None = None
    backward: np.ndarray | None = None
    valid: bool = False
    reason: str = "not_loaded"


def _valid_frame(frame: np.ndarray) -> bool:
    return (isinstance(frame, np.ndarray) and frame.dtype == np.uint8
            and frame.ndim == 3 and frame.shape[2] == 3
            and min(frame.shape[:2]) >= 8 and max(frame.shape[:2]) <= 8192)


def _box_in_frame(box, shape) -> tuple[float, float, float, float] | None:
    try:
        x, y, w, h = map(float, box)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) < 8:
        return None
    height, width = shape[:2]
    left, top = max(0., x), max(0., y)
    right, bottom = min(float(width), x + w), min(float(height), y + h)
    if min(right - left, bottom - top) < 8:
        return None
    # A mostly out-of-view box is not evidence of a visible tracked subject.
    if (right - left) * (bottom - top) < .65 * w * h:
        return None
    return left, top, right - left, bottom - top


class ViTTrackBackend:
    """OpenCV's official ViTTrack ONNX implementation, with bounded lifecycle.

    Coordinates are pixels in the exact supplied BGR frame. Initialization is
    caller-owned and must use an independently accepted subject ROI. A failed
    update discards identity; callers must reinitialize from fresh evidence.
    """

    def __init__(self, model_path: str, device: str = "auto", *, min_confidence: float = .35) -> None:
        self.model_path = str(model_path or "").strip()
        self.min_confidence = min(.95, max(.05, float(min_confidence)))
        self._tracker = None
        self._shape = None
        self._load_failed = False
        self.provider = "OpenCV CPU"
        self.status = "not_initialized"

    def reset(self) -> None:
        self._tracker = None
        self._shape = None
        self.status = "not_initialized"

    def initialize(self, frame_bgr: np.ndarray, bbox_xywh) -> TrackingResult:
        self.reset()
        if not _valid_frame(frame_bgr):
            self.status = "invalid_frame"
            return TrackingResult(reason=self.status)
        box = _box_in_frame(bbox_xywh, frame_bgr.shape)
        if box is None:
            self.status = "invalid_box"
            return TrackingResult(reason=self.status)
        if self._load_failed:
            self.status = "load_failed"
            return TrackingResult(reason=self.status)
        if not self.model_path or not Path(self.model_path).is_file():
            self.status = "model_missing"
            self._load_failed = True
            return TrackingResult(reason=self.status)
        try:
            import cv2
            from .v2_model_assets import validate_model_path

            if not validate_model_path("vittrack", self.model_path)[0]:
                self._load_failed = True
                self.status = "invalid_model"
                return TrackingResult(reason=self.status)

            params = cv2.TrackerVit_Params()
            params.net = self.model_path
            params.backend = cv2.dnn.DNN_BACKEND_OPENCV
            params.target = cv2.dnn.DNN_TARGET_CPU
            tracker = cv2.TrackerVit_create(params)
            roi = tuple(int(round(value)) for value in box)
            tracker.init(np.ascontiguousarray(frame_bgr), roi)
            self._tracker = tracker
            self._shape = frame_bgr.shape
            self.status = "initialized"
            return TrackingResult(tuple(map(float, roi)), 0., True, self.status)
        except Exception:
            self._load_failed = True
            self.status = "load_failed"
            return TrackingResult(reason=self.status)

    def update(self, frame_bgr: np.ndarray) -> TrackingResult:
        if not _valid_frame(frame_bgr):
            self.reset()
            self.status = "invalid_frame"
            return TrackingResult(reason=self.status)
        if self._tracker is None:
            return TrackingResult(reason=self.status)
        if frame_bgr.shape != self._shape:
            self.reset()
            self.status = "shape_changed"
            return TrackingResult(reason=self.status)
        try:
            located, box = self._tracker.update(np.ascontiguousarray(frame_bgr))
            confidence = float(self._tracker.getTrackingScore())
            clipped = _box_in_frame(box, frame_bgr.shape)
            if (not located or clipped is None or not math.isfinite(confidence)
                    or confidence < self.min_confidence):
                self.reset()
                self.status = "tracking_lost"
                return TrackingResult(reason=self.status)
            self.status = "tracking"
            return TrackingResult(clipped, min(1., max(0., confidence)), True, self.status)
        except Exception:
            self.reset()
            self.status = "inference_failed"
            return TrackingResult(reason=self.status)


class NeuFlowBackend:
    """ONNX NeuFlow v2, fixed input shape and original-frame vector units.

    The exported model accepts BGR float32 0..255, matching upstream infer_hf.py.
    Letterboxing preserves aspect ratio. Output is dense forward displacement,
    indexed in the previous frame; reverse inference is optional and uses the
    same two actual frames. No input arrays are mutated or temporal state held.
    """

    def __init__(self, model_path: str, device: str = "auto", *, require_gpu: bool = False) -> None:
        self.model_path = str(model_path or "").strip()
        self.requested_device = str(device or "cpu").lower()
        self.require_gpu = bool(require_gpu)
        self._session = None
        self._load_failed = False
        self._input_size = None
        self._inputs = None
        self._output = None
        self._dll_handles = []
        self.provider = ""
        self.status = "not_loaded"

    def _load(self) -> bool:
        if self._session is not None:
            return True
        if self._load_failed:
            return False
        if not self.model_path or not Path(self.model_path).is_file():
            self._load_failed = True
            self.status = "model_missing"
            return False
        try:
            from .v2_model_assets import validate_model_path

            if not validate_model_path("neuflow", self.model_path)[0]:
                self._load_failed = True
                self.status = "invalid_model"
                return False
            import onnxruntime as ort

            available = set(ort.get_available_providers())
            desired = {"cuda": "CUDAExecutionProvider", "directml": "DmlExecutionProvider"}.get(self.requested_device)
            if self.requested_device == "auto":
                desired = next((p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in available), None)
            providers = [desired, "CPUExecutionProvider"] if desired in available else ["CPUExecutionProvider"]
            if self.require_gpu and providers == ["CPUExecutionProvider"]:
                self._load_failed = True
                self.status = "gpu_unavailable"
                return False
            if desired == "CUDAExecutionProvider" and desired in available:
                from .gpu_runtime import preload_cuda_runtime, cuda_dll_directories
                preload_cuda_runtime()
                # cuDNN 9's frontend dynamically opens these engines. Windows
                # may not use AddDllDirectory for that inner load; explicitly
                # preload only the already-installed runtime's known libraries.
                import os
                if os.name == "nt":
                    import ctypes
                    for directory in cuda_dll_directories("12"):
                        if not (directory / "cudnn64_9.dll").is_file():
                            continue
                        for name in ("cudnn_engines_tensor_ir64_9.dll", "cudnn_ext64_9.dll",
                                     "cudnn_engines_precompiled64_9.dll"):
                            library = directory / name
                            if library.is_file():
                                self._dll_handles.append(ctypes.WinDLL(str(library)))
                        break
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            options.enable_mem_pattern = desired != "DmlExecutionProvider"
            options.log_severity_level = 3
            try:
                session = ort.InferenceSession(self.model_path, sess_options=options, providers=providers)
            except Exception:
                if providers == ["CPUExecutionProvider"] or self.require_gpu:
                    raise
                session = ort.InferenceSession(self.model_path, sess_options=options, providers=["CPUExecutionProvider"])
            # ORT can silently recreate a GPU session on CPU after EP_FAIL. A
            # live enhancement must instead fail back to the original analysis.
            session.disable_fallback()
            actual_provider = session.get_providers()[0]
            if self.require_gpu and actual_provider == "CPUExecutionProvider":
                raise RuntimeError("GPU provider unavailable")
            inputs, outputs = session.get_inputs(), session.get_outputs()
            if len(inputs) != 2 or len(outputs) != 1:
                raise ValueError("Expected two image inputs and one flow output")
            shape = inputs[0].shape
            if (len(shape) != 4 or shape[:2] != [1, 3] or inputs[1].shape != shape
                    or any(inp.type != "tensor(float)" for inp in inputs)):
                raise ValueError("Expected float BGR NCHW input")
            height, width = shape[2:]
            if (not isinstance(height, int) or not isinstance(width, int)
                    or min(height, width) < 64 or max(height, width) > 640
                    or height % 16 or width % 16 or height * width > 640 * 384
                    or outputs[0].shape != [1, 2, height, width]
                    or outputs[0].type != "tensor(float)"):
                raise ValueError("Unsupported bounded input/output shape")
            self._session = session
            self._input_size = (width, height)
            self._inputs = [inp.name for inp in inputs]
            self._output = outputs[0].name
            self.provider = actual_provider
            self.status = "ready"
            return True
        except Exception:
            self._load_failed = True
            self.status = "load_failed"
            return False

    def _prepare(self, frame: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        import cv2

        width, height = self._input_size
        input_height, input_width = frame.shape[:2]
        ratio = min(width / input_width, height / input_height)
        resized_width = max(1, min(width, int(round(input_width * ratio))))
        resized_height = max(1, min(height, int(round(input_height * ratio))))
        left, top = (width - resized_width) // 2, (height - resized_height) // 2
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        # Replicated borders avoid introducing a black motion edge at the ROI.
        padded = cv2.copyMakeBorder(resized, top, height - resized_height - top,
                                   left, width - resized_width - left, cv2.BORDER_REPLICATE)
        tensor = np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32)
        return tensor, (left, top, resized_width, resized_height)

    def _run(self, first: np.ndarray, second: np.ndarray, rect, shape) -> np.ndarray:
        import cv2

        flow = np.asarray(self._session.run([self._output], dict(zip(self._inputs, (first, second))))[0])
        actual_provider = self._session.get_providers()[0]
        if self.require_gpu and actual_provider not in {"CUDAExecutionProvider", "DmlExecutionProvider"}:
            raise RuntimeError("GPU provider changed")
        if isinstance(actual_provider, str):
            self.provider = actual_provider
        width, height = self._input_size
        if flow.shape != (1, 2, height, width) or not np.isfinite(flow).all():
            raise ValueError("Invalid model flow")
        left, top, resized_width, resized_height = rect
        flow = flow[0, :, top:top + resized_height, left:left + resized_width].transpose(1, 2, 0)
        input_height, input_width = shape[:2]
        restored = cv2.resize(flow, (input_width, input_height), interpolation=cv2.INTER_LINEAR)
        restored[..., 0] *= input_width / resized_width
        restored[..., 1] *= input_height / resized_height
        if not np.isfinite(restored).all() or np.max(np.abs(restored)) > 2 * max(input_height, input_width):
            raise ValueError("Unbounded model flow")
        return np.ascontiguousarray(restored, dtype=np.float32)

    def infer(self, previous_bgr: np.ndarray, current_bgr: np.ndarray, backward: bool = False) -> FlowResult:
        if not _valid_frame(previous_bgr) or not _valid_frame(current_bgr):
            return FlowResult(reason="invalid_frame")
        if previous_bgr.shape != current_bgr.shape:
            return FlowResult(reason="shape_changed")
        if not self._load():
            return FlowResult(reason=self.status)
        try:
            first, rect = self._prepare(previous_bgr)
            second, _ = self._prepare(current_bgr)
            forward = self._run(first, second, rect, previous_bgr.shape)
            reverse = self._run(second, first, rect, previous_bgr.shape) if backward else None
            self.status = "ready"
            return FlowResult(forward, reverse, True, self.status)
        except Exception:
            # Do not retry a broken graph each frame or return stale previous flow.
            self._load_failed = True
            self._session = None
            self.status = "inference_failed"
            return FlowResult(reason=self.status)
