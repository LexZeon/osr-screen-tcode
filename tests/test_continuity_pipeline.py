import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from motion_scenes import window_scene
from test_fused_l0 import MeasuredMotion
from osr_screen_tcode.camera_motion import CameraRelativeMotion, same_scene_structure
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE, RTM_POSE_2D_MODE
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings
from osr_screen_tcode.motion_reference import MotionReference
from osr_screen_tcode.visual_lab.observations import Observation


class ContinuityPipelineTests(unittest.TestCase):
    def test_four_second_observed_cycle_can_continue_through_dropout(self):
        class SlowMotion(MeasuredMotion):
            def update(self, gray, stamp):
                if stamp > 20:
                    self.reference = MotionReference('v2', 'holding', reason='background')
                    return Observation(stamp, 'holding'), []
                value = 12*np.sin(stamp*2*np.pi/4)
                step, self.previous = value-self.previous, value
                self.reference = MotionReference('v2', 'ready', (110, 70, 210, 160),
                                                 step=(0., step, 0.), motion_dt=1/30)
                return Observation(stamp, 'ready', (0., value, 0.)), []
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        engine.motion = SlowMotion()
        frame = np.zeros((240, 320, 3), np.uint8)
        for index in range(601):
            engine.process(frame, index/30)
        self.assertIsNotNone(engine.point_l0.fusion.rhythm.model)
        values = [engine.process(frame, 20+index/30).positions['L0'] for index in range(1, 76)]
        self.assertGreater(np.ptp(values[:45]), .2)
        np.testing.assert_allclose(values[60:], values[60], atol=1e-12)
        self.assertIsNone(engine.visual_frame.observation.values)

    def test_blurred_matching_scene_does_not_become_a_hard_cut(self):
        scene, tracker = window_scene(), CameraRelativeMotion()
        for i in range(15):
            gray = cv2.cvtColor(scene.frame(y=i*2), cv2.COLOR_BGR2GRAY)
            tracker.update(gray, i/30)
        blurred = cv2.GaussianBlur(gray, (31, 31), 7.)
        self.assertTrue(same_scene_structure(gray, blurred))
        empty = np.empty((0, 2), np.float32)
        # Simulate corner loss, leaving the real image structure available.
        with patch('osr_screen_tcode.camera_motion.track_pair', return_value=(empty, empty, 0)):
            tracker.update(blurred, .5)
        self.assertNotEqual(tracker.reference.reason, 'jump')
        random = np.random.default_rng(671).integers(0, 255, gray.shape, np.uint8)
        self.assertFalse(same_scene_structure(gray, random))
        self.assertFalse(same_scene_structure(gray, np.zeros_like(gray)))

    def test_estimates_remain_separate_from_observations_and_secondary_axes(self):
        from test_visual_pipeline import FakePose
        for mode, assisted in ((m, a) for m in (HYBRID_V2_MODE, STROKE_CYCLE_MODE) for a in (False, True)):
            engine = make_analyzer(tracker_mode=mode, output_mode='Six Axis', hybrid_v2_pose_enabled=assisted)
            if assisted:
                engine.backend = FakePose()
            engine.motion = MeasuredMotion()
            frame = np.zeros((240, 320, 3), np.uint8)
            for i in range(181):
                engine.process(frame, i/30)
            observed = dict(engine.positions)
            evidence = len(engine.point_l0.fusion.rhythm.samples)
            estimate = SimpleNamespace(state='weak', origin=(162., 119.), box=(110., 80., 210., 160.),
                                       elapsed=.05, step=(0., .25, 0.), stationary=False)
            with patch.object(engine.subject_continuity, 'update', return_value=estimate):
                result = engine.process(frame, 6.05)
            reference = engine.visual_frame.reference
            self.assertIsNone(engine.visual_frame.observation.values)
            self.assertEqual(result.confidence, 0.)
            self.assertEqual(result.activity, 0.)
            self.assertIsNotNone(engine.generated_l0)
            self.assertEqual(reference.estimate_origin, estimate.origin)
            self.assertEqual(reference.estimate_state, 'weak')
            self.assertIsNone(reference.subject_origin)
            self.assertIsNone(reference.reach_progress)
            self.assertEqual(reference.step, (0., 0., 0.))
            self.assertFalse(engine.visual_frame.reset)
            self.assertEqual(len(engine.point_l0.fusion.rhythm.samples), evidence)
            self.assertTrue(all(result.positions[a] == observed[a] for a in ('L1', 'L2', 'R0', 'R1', 'R2')))

    def test_manual_reference_reset_discards_subject_estimates(self):
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        previous = engine.subject_continuity
        engine._subject_basis = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
        engine.configure(VisualSettings(generation=1))
        self.assertIsNot(engine.subject_continuity, previous)
        self.assertEqual(engine._subject_basis, ())
        self.assertIsNone(engine.generated_l0)

    def test_direct_pose_does_not_enter_the_new_v2_estimator(self):
        from test_visual_pipeline import FakePose
        engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, output_mode='Six Axis')
        engine.backend = FakePose()
        with patch.object(engine.subject_continuity, 'update', side_effect=AssertionError('v2 estimate used for Pose')):
            for index in range(4):
                engine.process(np.zeros((240, 320, 3), np.uint8), index/30)

    def test_expired_estimate_cannot_reveal_old_measured_box_after_ready_flash(self):
        class FlashMotion(MeasuredMotion):
            def update(self, gray, stamp):
                ready = stamp == 0. or stamp == 1.9
                state = 'ready' if ready else 'holding' if stamp > 1.9 else 'missing'
                # The detector retains its old geometry for its brief holding
                # grace after a real single-frame reappearance near expiry.
                self.reference = MotionReference('v2', state, (110., 80., 210., 160.),
                    subject_origin=(160., 120.), subject_box=(110., 80., 210., 160.),
                    vectors=(((140., 100.), (141., 101.)), ((180., 140.), (181., 141.))),
                    support_groups=(((140., 100.), (141., 101.)),),
                    step=(0., 1., 0.) if ready else (0., 0., 0.), reason='' if ready else 'region')
                return Observation(stamp, state, (0., stamp, 0.) if ready else None), []

        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        engine.motion = FlashMotion()
        for index, stamp in enumerate((0., .25, .5, .75, 1., 1.25, 1.5, 1.75, 1.9, 1.95, 2.05)):
            # Changed input distinguishes a dropout from a frozen decoder.
            frame = np.zeros((240, 320, 3), np.uint8)
            frame[0, 0] = index
            result = engine.process(frame, stamp)
            if stamp == 1.95:
                self.assertTrue(engine.visual_frame.reference.estimate_state)
                self.assertTrue(engine.subject_continuity.episode)
                self.assertEqual(engine.subject_continuity.strong_at, 0.)
        shown, original = engine.visual_frame.reference, engine.motion.reference
        self.assertEqual(original.state, 'holding')
        self.assertIsNotNone(original.subject_box)
        self.assertTrue(original.vectors)
        self.assertFalse(shown.estimate_state)
        self.assertIsNone(shown.roi)
        self.assertIsNone(shown.subject_origin)
        self.assertIsNone(shown.subject_box)
        self.assertEqual(shown.basis, ())
        self.assertEqual(shown.vectors, ())
        self.assertEqual(shown.support_groups, ())
        self.assertIsNone(engine.visual_frame.observation.values)
        self.assertEqual(result.confidence, 0.)

    def test_isolated_ready_flash_does_not_replace_cached_observed_axes(self):
        class FlashMotion(MeasuredMotion):
            def update(self, gray, stamp):
                ready = stamp in (0., .2)
                state = 'ready' if ready else 'missing'
                self.reference = MotionReference('v2', state, (110., 80., 210., 160.),
                    subject_origin=(160., 120.), subject_box=(110., 80., 210., 160.),
                    step=(0., 1., 0.) if ready else (0., 0., 0.))
                return Observation(stamp, state, (0., stamp, 0.) if ready else None), []

        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        engine.motion = FlashMotion()
        frame = np.zeros((240, 320, 3), np.uint8)
        engine.process(frame, 0.)
        # A previously established diagonal basis differs from the upstream
        # default that the missing-state reset creates before the flash.
        old_axes = ((.70710678, .70710678, 0.), (-.70710678, .70710678, 0.), (0., 0., 1.))
        engine._subject_basis = old_axes
        for index, stamp in enumerate((.1, .2, .3), start=1):
            frame = frame.copy()
            frame[0, 0] = index
            engine.process(frame, stamp)
        self.assertTrue(engine.subject_continuity.episode)
        self.assertEqual(engine._subject_basis, old_axes)
        self.assertEqual(engine.visual_frame.reference.estimate_basis, old_axes)
        self.assertIsNone(engine.visual_frame.observation.values)


if __name__ == '__main__':
    unittest.main()
