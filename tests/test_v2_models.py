"""Local inference contracts; model files are optional and never fetched here."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import numpy as np

from osr_screen_tcode.v2_models import NeuFlowBackend, ViTTrackBackend


class V2ModelBackendTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((96, 160, 3), (11, 73, 209), dtype=np.uint8)

    def test_disabled_construction_does_not_import_or_load_runtime(self):
        with patch("builtins.__import__", side_effect=AssertionError("unexpected lazy import")):
            tracker = ViTTrackBackend("missing.onnx")
            flow = NeuFlowBackend("missing.onnx")
        self.assertIsNone(tracker._tracker)
        self.assertIsNone(flow._session)

    def test_missing_models_are_failures_not_fake_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = str(Path(folder) / "no-model.onnx")
            tracked = ViTTrackBackend(missing).initialize(self.frame, (20, 20, 40, 40))
            flow = NeuFlowBackend(missing).infer(self.frame, self.frame, backward=True)
        self.assertFalse(tracked.valid)
        self.assertFalse(flow.valid)
        self.assertEqual(flow.reason, "model_missing")
        self.assertIsNone(flow.forward)
        self.assertIsNone(flow.backward)

    def test_invalid_frames_never_reach_models(self):
        flow = NeuFlowBackend("")
        tracker = ViTTrackBackend("")
        for invalid in (None, self.frame.astype(np.float32), self.frame[:, :, 0], self.frame[:1]):
            with self.subTest(shape=getattr(invalid, "shape", None)):
                self.assertEqual(flow.infer(invalid, self.frame).reason, "invalid_frame")
                self.assertEqual(tracker.initialize(invalid, (10, 10, 20, 20)).reason, "invalid_frame")
        self.assertEqual(flow.infer(self.frame, self.frame[:80]).reason, "shape_changed")

    def test_unverified_existing_files_never_reach_inference_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "untrusted.onnx"
            model.write_bytes(b"not the pinned model")
            self.assertEqual(ViTTrackBackend(str(model)).initialize(self.frame, (20, 20, 40, 40)).reason,
                             "invalid_model")
            self.assertEqual(NeuFlowBackend(str(model)).infer(self.frame, self.frame).reason,
                             "invalid_model")

    def test_gpu_required_rejects_cpu_without_loading_session(self):
        runtime = SimpleNamespace(get_available_providers=lambda: ["CPUExecutionProvider"],
                                  InferenceSession=Mock(side_effect=AssertionError("CPU loaded")))
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "model.onnx"
            model.touch()
            flow = NeuFlowBackend(str(model), require_gpu=True)
            with patch("osr_screen_tcode.v2_model_assets.validate_model_path", return_value=(True, "ok")), \
                    patch.dict("sys.modules", {"onnxruntime": runtime}):
                self.assertEqual(flow.infer(self.frame, self.frame).reason, "gpu_unavailable")
        runtime.InferenceSession.assert_not_called()

    def test_tracker_initialization_requires_visible_finite_box(self):
        tracker = ViTTrackBackend("")
        for box in ((0, 0, 0, 2), (np.nan, 5, 40, 40), (-100, 0, 120, 40), (0, 0, 9), None):
            self.assertEqual(tracker.initialize(self.frame, box).reason, "invalid_box")

    def _tracker(self, located=True, score=.8, box=(22, 24, 40, 42)):
        tracker = ViTTrackBackend("")
        tracker._tracker = Mock()
        tracker._tracker.update.return_value = (located, box)
        tracker._tracker.getTrackingScore.return_value = score
        tracker._shape = self.frame.shape
        return tracker

    def test_tracker_low_confidence_or_out_of_view_discards_identity(self):
        for values in ((True, .1, (20, 20, 40, 40)), (False, .9, (20, 20, 40, 40)),
                       (True, np.nan, (20, 20, 40, 40)), (True, .9, (150, 20, 40, 40))):
            tracker = self._tracker(*values)
            result = tracker.update(self.frame)
            self.assertFalse(result.valid)
            self.assertIsNone(result.bbox_xywh)
            self.assertIsNone(tracker._tracker)

    def test_tracker_returns_original_pixel_box_and_shape_reset(self):
        tracker = self._tracker()
        result = tracker.update(self.frame)
        self.assertTrue(result.valid)
        self.assertEqual(result.bbox_xywh, (22., 24., 40., 42.))
        self.assertAlmostEqual(result.confidence, .8)
        self.assertEqual(tracker.update(self.frame[:80]).reason, "shape_changed")
        self.assertIsNone(tracker._tracker)

    def test_tracker_inference_exception_is_nonfatal(self):
        tracker = self._tracker()
        tracker._tracker.update.side_effect = RuntimeError("device failed")
        self.assertEqual(tracker.update(self.frame).reason, "inference_failed")
        self.assertIsNone(tracker._tracker)

    def _flow(self, dx=4., dy=-2.):
        flow = NeuFlowBackend("")
        flow._input_size = (128, 64)
        flow._inputs = ["previous_bgr", "current_bgr"]
        flow._output = "flow"
        flow._session = Mock()
        flow._session.get_providers.return_value = ["CPUExecutionProvider"]
        prediction = np.zeros((1, 2, 64, 128), dtype=np.float32)
        prediction[:, 0] = dx
        prediction[:, 1] = dy
        flow._session.run.return_value = [prediction]
        return flow

    def test_bgr_values_aspect_ratio_and_inputs_preserved(self):
        flow = self._flow()
        original = self.frame.copy()
        tensor, rect = flow._prepare(self.frame)
        self.assertEqual(rect, (10, 0, 107, 64))
        self.assertEqual(tensor.shape, (1, 3, 64, 128))
        np.testing.assert_array_equal(tensor[0, :, 0, 0], [11., 73., 209.])
        np.testing.assert_array_equal(self.frame, original)
        self.assertEqual(tensor.dtype, np.float32)

    def test_flow_vectors_restored_to_original_pixels(self):
        flow = self._flow()
        result = flow.infer(self.frame, self.frame)
        self.assertTrue(result.valid)
        self.assertEqual(result.forward.shape, (96, 160, 2))
        np.testing.assert_allclose(result.forward[..., 0], 4. * 160 / 107, atol=1e-5)
        np.testing.assert_allclose(result.forward[..., 1], -3., atol=1e-5)
        self.assertIsNone(result.backward)

    def test_backward_uses_actual_reversed_frame_pair(self):
        flow = self._flow()
        changed = self.frame.copy()
        changed[:] = (23, 45, 67)
        result = flow.infer(self.frame, changed, backward=True)
        self.assertTrue(result.valid)
        calls = flow._session.run.call_args_list
        self.assertEqual(len(calls), 2)
        np.testing.assert_array_equal(calls[0].args[1]["previous_bgr"], calls[1].args[1]["current_bgr"])
        np.testing.assert_array_equal(calls[0].args[1]["current_bgr"], calls[1].args[1]["previous_bgr"])

    def test_invalid_output_latches_failure_and_returns_no_stale_flow(self):
        for prediction in (np.zeros((1, 2, 8, 8)), np.full((1, 2, 64, 128), np.nan),
                           np.full((1, 2, 64, 128), 1e9)):
            flow = self._flow()
            session = flow._session
            session.run.return_value = [prediction]
            result = flow.infer(self.frame, self.frame)
            self.assertFalse(result.valid)
            self.assertIsNone(result.forward)
            self.assertIsNone(flow._session)
            self.assertFalse(flow.infer(self.frame, self.frame).valid)
            self.assertEqual(session.run.call_count, 1)

    def test_reverse_failure_does_not_return_half_valid_pair(self):
        flow = self._flow()
        prediction = flow._session.run.return_value
        flow._session.run.side_effect = [prediction, RuntimeError("backend failed")]
        result = flow.infer(self.frame, self.frame, backward=True)
        self.assertFalse(result.valid)
        self.assertIsNone(result.forward)
        self.assertIsNone(result.backward)

    def test_provider_fallback_cannot_be_reported_as_valid_gpu_flow(self):
        flow = self._flow()
        flow.require_gpu = True
        flow.provider = "CUDAExecutionProvider"
        self.assertFalse(flow.infer(self.frame, self.frame).valid)
        self.assertEqual(flow.status, "inference_failed")


if __name__ == "__main__":
    unittest.main()
