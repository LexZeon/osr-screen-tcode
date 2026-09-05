"""DirectML session adapter, retaining rtmlib's pose preprocessing and decoding."""
from __future__ import annotations

import threading

from .gpu_runtime import directml_session_options


def create_directml_pose(model_type, path: str, input_size: tuple[int, int]):
    import onnxruntime as ort
    from rtmlib.tools.base import BaseTool

    class DirectMLTool(BaseTool):
        def __init__(self, onnx_model, model_input_size, mean, std, backend, device):
            self.session = ort.InferenceSession(onnx_model, sess_options=directml_session_options(ort),
                providers=[("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"])
            if "DmlExecutionProvider" not in self.session.get_providers():
                raise RuntimeError("DirectML provider fell back to CPU")
            self.onnx_model = onnx_model
            self.model_input_size = model_input_size
            self.mean, self.std = mean, std
            self.backend, self.device = backend, device
            self._inference_lock = threading.Lock()

        def inference(self, image):
            with self._inference_lock:
                return super().inference(image)

    # MRO routes only BaseTool initialization through our session adapter. RTMPose's
    # constructors, __call__, preprocessing and decoding remain the upstream methods.
    class DirectMLPose(model_type, DirectMLTool):
        pass

    return DirectMLPose(path, model_input_size=input_size, backend="onnxruntime", device="directml")
