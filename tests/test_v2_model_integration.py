import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from motion_scenes import MotionScene
from osr_screen_tcode.camera_motion import CameraRelativeMotion
from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.motion_reference import MotionReference, reference_lines
from osr_screen_tcode.regional_flow import validated_flow_points
from osr_screen_tcode.v2_model_assist import V2ModelAssist, ModelDiagnostic
from osr_screen_tcode.visual_lab.observations import Observation
from osr_screen_tcode.visual_pipeline import make_analyzer


class OptionalModelIntegrationTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(202)
        self.gray = rng.integers(20, 220, (96, 128), np.uint8)
        self.current = np.roll(self.gray, 2, axis=1)
        self.bgr = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        self.next_bgr = cv2.cvtColor(self.current, cv2.COLOR_GRAY2BGR)

    def _flow(self, **changes):
        forward = np.zeros((*self.gray.shape, 2), np.float32)
        forward[..., 0] = 2
        data = dict(valid=True, reason='ready', forward=forward, backward=-forward)
        data.update(changes)
        return SimpleNamespace(**data)

    def test_flow_needs_round_trip_and_image_support(self):
        flow = self._flow()
        a, b = validated_flow_points(self.gray, self.current, flow.forward, flow.backward)
        self.assertGreater(len(a), 100)
        np.testing.assert_allclose(b-a, np.tile((2, 0), (len(a), 1)))
        a, _ = validated_flow_points(self.gray, self.current, flow.forward, flow.forward)
        self.assertEqual(len(a), 0)
        a, _ = validated_flow_points(self.gray, np.zeros_like(self.gray), flow.forward, flow.backward)
        self.assertEqual(len(a), 0)
        with self.assertRaises(ValueError):
            validated_flow_points(self.gray, self.current, flow.forward, None)

    def test_neural_pair_is_computed_once_and_uses_explicit_gpu(self):
        backend = Mock()
        backend.infer.return_value = self._flow()
        factory = Mock(return_value=backend)
        assist = V2ModelAssist({'neuflow_enabled': True, 'gpu_enabled': True,
                                'gpu_backend': 'cuda'}, flow_factory=factory)
        assist.begin(self.bgr, self.next_bgr, 1., None)
        first = assist.flow_points(self.gray, self.current)
        self.assertIs(first, assist.flow_points(self.gray, self.current))
        self.assertEqual(backend.infer.call_count, 1)
        factory.assert_called_once_with('', device='cuda', require_gpu=True)
        self.assertEqual(assist.snapshot()[0].state, 'verified')

    def test_cpu_setting_cannot_start_slow_neural_inference(self):
        factory = Mock()
        assist = V2ModelAssist({'neuflow_enabled': True, 'gpu_enabled': False}, flow_factory=factory)
        assist.begin(self.bgr, self.next_bgr, 1., None)
        self.assertIsNone(assist.flow_points(self.gray, self.current))
        factory.assert_not_called()
        self.assertEqual(assist.snapshot()[0].state, 'gpu_required')

    def test_unsupported_directml_never_loads_neuflow(self):
        factory = Mock()
        assist = V2ModelAssist({'neuflow_enabled': True, 'gpu_enabled': True,
                                'gpu_backend': 'directml'}, flow_factory=factory)
        assist.begin(self.bgr, self.next_bgr, 1., None)
        self.assertIsNone(assist.flow_points(self.gray, self.current))
        factory.assert_not_called()
        self.assertEqual(assist.snapshot()[0].state, 'cuda_required')

    def test_downloaded_model_is_found_after_restoring_defaults(self):
        factory = Mock()
        assist = V2ModelAssist({'vittrack_enabled': True}, tracker_factory=factory)
        with patch('osr_screen_tcode.v2_model_assets.find_existing_model', return_value='verified.onnx'):
            assist._backend('vittrack')
        factory.assert_called_once_with('verified.onnx', device='cpu')
        assist._failure('vittrack', 'gpu_unavailable')
        self.assertEqual(assist.snapshot()[0].state, 'gpu_required')

    def test_valid_original_dense_evidence_does_not_run_neural_flow(self):
        camera = CameraRelativeMotion({'neuflow_enabled': True})
        camera.gray = self.gray
        accepted = object()
        tracks = np.array(((20., 20.), (40., 40.)), np.float32)
        with patch.object(camera, '_dense_points', return_value=(tracks, tracks)), \
             patch.object(camera, '_model_points') as neural, \
             patch('osr_screen_tcode.camera_motion.box_fit', return_value=accepted):
            result = camera._dense_box(np.eye(2, 3), .2, tracks, None)
        self.assertIs(result, accepted)
        neural.assert_not_called()

    def test_failed_original_dense_fit_can_use_verified_neural_samples(self):
        camera = CameraRelativeMotion({'neuflow_enabled': True})
        camera.gray = self.gray
        accepted = object()
        tracks = np.array(((20., 20.), (40., 40.)), np.float32)
        with patch.object(camera, '_dense_points', return_value=(tracks, tracks)), \
             patch.object(camera, '_model_points', return_value=(tracks, tracks+2)) as neural, \
             patch('osr_screen_tcode.camera_motion.box_fit', side_effect=(None, accepted)):
            result = camera._dense_box(np.eye(2, 3), .2, tracks, None)
        self.assertIs(result, accepted)
        neural.assert_called_once()

    def test_backend_failure_falls_back_once_without_leaking_paths(self):
        backend = Mock()
        backend.infer.side_effect = RuntimeError('private/path/model inference failed')
        factory = Mock(return_value=backend)
        assist = V2ModelAssist({'neuflow_enabled': True, 'gpu_enabled': True}, flow_factory=factory)
        for index in range(2):
            assist.begin(self.bgr, self.next_bgr, 1.+index/30, None)
            self.assertIsNone(assist.flow_points(self.gray, self.current))
        self.assertEqual(backend.infer.call_count, 1)
        self.assertEqual(assist.snapshot()[0].state, 'failed')
        self.assertNotIn('private', repr(assist.snapshot()))

    def test_tracker_proposes_only_actual_matching_point_membership(self):
        tracker = Mock()
        tracker.initialize.return_value = True
        tracker.update.return_value = SimpleNamespace(valid=True, reason='tracking', confidence=.9,
                                                       bbox_xywh=(12, 10, 60, 50))
        assist = V2ModelAssist({'vittrack_enabled': True}, tracker_factory=Mock(return_value=tracker))
        assist.begin(self.bgr, self.next_bgr, 1., (10, 10, 70, 60))
        a = np.array(((20., 20.), (90., 20.), (20., 90.)))
        b = a+(2., 0.)
        np.testing.assert_array_equal(assist.subject_mask(a, b), (True, False, False))
        self.assertEqual(assist.snapshot()[0].state, 'candidate')
        assist.reset_tracker()
        self.assertIsNone(assist.subject_mask(a, b))
        self.assertIsNone(assist.current_box)

    def test_low_score_cannot_leave_a_model_box(self):
        tracker = Mock()
        tracker.initialize.return_value = True
        tracker.update.return_value = SimpleNamespace(valid=True, reason='tracking', confidence=.1,
                                                       bbox_xywh=(12, 10, 60, 50))
        assist = V2ModelAssist({'vittrack_enabled': True}, tracker_factory=Mock(return_value=tracker))
        assist.begin(self.bgr, self.next_bgr, 1., (10, 10, 70, 60))
        self.assertIsNone(assist.current_box)
        self.assertIsNone(assist.tracker)

    def test_missing_reference_expiry_hides_model_box_on_repeated_frames(self):
        assist = V2ModelAssist({'vittrack_enabled': True})
        assist.current_box = (10, 10, 70, 70)
        camera = CameraRelativeMotion({'vittrack_enabled': True}, model_assist=assist)
        camera.gray = self.gray.copy()
        camera.timestamp = camera.measured_at = 2.9
        camera.needs_reference = False
        camera.loss_since = 0.
        camera.roi = (10, 10, 70, 70)
        camera.last = Observation(2.9, 'holding')
        camera._hold(3., 'missing')
        camera.update(self.gray, 3.1)
        self.assertIsNone(camera.roi)
        self.assertIsNone(camera.reference.model_box)

    def test_hard_cut_discards_identity_but_keeps_loaded_flow_session(self):
        assist = V2ModelAssist({'vittrack_enabled': True, 'neuflow_enabled': True})
        flow = assist.flow = Mock()
        assist.tracker = Mock()
        assist.current_box = (10, 10, 70, 70)
        camera = CameraRelativeMotion(model_assist=assist)
        camera._hold(1., 'missing', hard=True)
        self.assertIs(assist.flow, flow)
        self.assertIsNone(assist.tracker)
        self.assertIsNone(assist.current_box)

    def test_default_disabled_and_explicit_disabled_have_identical_samples(self):
        scene = MotionScene()
        original = CameraRelativeMotion()
        disabled = CameraRelativeMotion({'vittrack_enabled': False, 'neuflow_enabled': False})
        with patch('osr_screen_tcode.v2_model_assist.V2ModelAssist', side_effect=AssertionError('models disabled')):
            for i in range(24):
                gray = cv2.cvtColor(scene.frame(y=8*np.sin(i*.15)), cv2.COLOR_BGR2GRAY)
                cv2.setRNGSeed(551)
                a, _ = original.update(gray, i/30)
                cv2.setRNGSeed(551)
                b, _ = disabled.update(gray, i/30)
                self.assertEqual(a.state, b.state)
                self.assertEqual(a.values, b.values)
                self.assertEqual(original.reference, disabled.reference)
        self.assertIsNone(disabled.model_assist)

    def test_factory_gates_models_to_v2_and_cycle(self):
        options = {'vittrack_enabled': True, 'neuflow_enabled': True}
        for mode in (HYBRID_MODE, RTM_POSE_2D_MODE):
            analyzer = make_analyzer(tracker_mode=mode, v2_model_options=options)
            self.assertIsNone(getattr(getattr(analyzer, 'motion', None), 'model_assist', None))
        for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            analyzer = make_analyzer(tracker_mode=mode, v2_model_options=options)
            self.assertIsNotNone(analyzer.motion.model_assist)

    def test_unvalidated_model_box_cannot_replace_camera_observation(self):
        tracker = Mock()
        tracker.initialize.return_value = True
        tracker.update.return_value = SimpleNamespace(valid=True, reason='tracking', confidence=.99,
                                                       bbox_xywh=(20, 10, 60, 50))
        assist = V2ModelAssist({'vittrack_enabled': True}, tracker_factory=Mock(return_value=tracker))
        camera = CameraRelativeMotion({'vittrack_enabled': True}, model_assist=assist)
        camera.update(self.gray, 0., self.bgr)
        camera.needs_reference = False
        camera.subject_confirmed = True
        camera.roi = (10, 10, 70, 60)
        with patch.object(camera, '_camera', return_value=(None, None)), \
             patch.object(camera.subject, 'recover', return_value=None):
            observation, _ = camera.update(self.current, .03, self.next_bgr)
        self.assertIsNone(observation.values)
        np.testing.assert_array_equal(camera.values, (0, 0, 0))

    def test_model_diagnostics_are_bilingual_in_compact_preview(self):
        reference = MotionReference('v2', model_diagnostics=(
            ModelDiagnostic('neuflow', 'gpu_required'), ModelDiagnostic('vittrack', 'candidate', 3.2)))
        zh = '\n'.join(reference_lines(reference, lambda a, b: a, compact=True))
        en = '\n'.join(reference_lines(reference, lambda a, b: b, compact=True))
        self.assertIn('需要可用 GPU', zh)
        self.assertIn('GPU required', en)
        self.assertIn('ViTTrack: candidate region', en)


if __name__ == '__main__':
    unittest.main()
