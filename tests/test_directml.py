from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from osr_screen_tcode import gpu_runtime as gpu
from osr_screen_tcode.directml_pose import create_directml_pose
from osr_screen_tcode.pose_backends import OptionalRtmPose2dBackend, _resolve_onnxruntime_device


class DirectMLTests(unittest.TestCase):
    def test_probe_does_not_require_nvidia_or_cuda(self):
        ort = SimpleNamespace(__version__="1.24.4", get_available_providers=lambda: ["DmlExecutionProvider", "CPUExecutionProvider"])
        with patch.dict(sys.modules, {"onnxruntime": ort}), patch.object(gpu, "detect_nvidia") as detect, patch.object(gpu, "_verify_directml") as verify:
            result = gpu.probe_in_process("directml")
            self.assertTrue(result["ready"])
            self.assertFalse(result["cuda"])
            verify.assert_called_once()
            detect.assert_not_called()

    def test_missing_dml_does_not_claim_cuda_is_missing(self):
        ort = SimpleNamespace(__version__="1.29.0", get_available_providers=lambda: ["CPUExecutionProvider"])
        with patch.dict(sys.modules, {"onnxruntime": ort}):
            self.assertEqual(gpu.probe_in_process("directml")["reason"], "dml_missing")
            self.assertEqual(_resolve_onnxruntime_device("directml")[0], "cpu")

    def test_rtmlib_2d_3d_decoder_and_parameters_are_unchanged(self):
        import onnxruntime as ort
        from rtmlib import RTMPose, RTMPose3d

        for model_type, size in ((RTMPose, (192, 256)), (RTMPose3d, (288, 384))):
            session = MagicMock()
            session.get_providers.return_value = ["DmlExecutionProvider", "CPUExecutionProvider"]
            session.get_inputs.return_value = [SimpleNamespace(name="input")]
            lengths = [size[0] * 2, size[1] * 2] + ([size[0] * 2] if model_type is RTMPose3d else [])
            outputs = []
            for length in lengths:
                axis = np.zeros((1, 17, length), dtype=np.float32)
                axis[:, :, length // 2] = 1
                outputs.append(axis)
            session.run.return_value = outputs
            with patch.object(ort, "InferenceSession", return_value=session) as create:
                model = create_directml_pose(model_type, "test.onnx", size)
                self.assertIs(type(model).preprocess, model_type.preprocess)
                self.assertIs(type(model).postprocess, model_type.postprocess)
                self.assertFalse(create.call_args.kwargs["sess_options"].enable_mem_pattern)
                self.assertEqual(create.call_args.kwargs["sess_options"].execution_mode, ort.ExecutionMode.ORT_SEQUENTIAL)
                self.assertEqual(create.call_count, 1)
                result = model(np.zeros((480, 640, 3), dtype=np.uint8))
                self.assertTrue(all(np.isfinite(item).all() for item in result))
                if model_type is RTMPose3d:
                    self.assertEqual(model.z_range, 2.1744869)

    def test_dml_model_load_error_falls_back_to_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.onnx"
            path.touch()
            backend = OptionalRtmPose2dBackend(str(path))
            backend.device = backend.requested_device = "directml"
            with patch("osr_screen_tcode.directml_pose.create_directml_pose", side_effect=RuntimeError("unsupported model")), patch("rtmlib.RTMPose") as cpu_model:
                self.assertTrue(backend._load())
                self.assertEqual(backend.device, "cpu")
                self.assertEqual(cpu_model.call_args.kwargs["device"], "cpu")

    def test_directml_and_cuda_runtime_pointers_are_separate(self):
        self.assertNotEqual(gpu.runtime_pointer("directml"), gpu.runtime_pointer("cuda"))

    def test_probe_passes_backend_to_child(self):
        output = 'GPU_RESULT={"nvidia":false,"cuda":false,"ready":true,"backend":"directml"}'
        with patch.object(gpu, "_run_bounded", return_value=output) as run:
            self.assertTrue(gpu.probe_gpu(backend="directml")["ready"])
            self.assertEqual(run.call_args.kwargs["env"]["OSR_TCODE_GPU_BACKEND"], "directml")
