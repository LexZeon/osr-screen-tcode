import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np

from osr_screen_tcode.pose_fast_fallback import PoseFastFallback
from osr_screen_tcode.motion_reference import MotionReference
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings
from osr_screen_tcode.config import RTM_POSE_2D_MODE
from test_visual_pipeline import FakePose


class FastFallbackTests(unittest.TestCase):
    def test_output_anchor_undoes_travel_inversion_guard_and_startup_ramp(self):
        from unittest.mock import patch
        from osr_screen_tcode.tcode import MultiAxisSafeOutput
        for invert, scale, guard in ((False, .5, False), (True, 1.3, True)):
            with patch('osr_screen_tcode.tcode.time.perf_counter', return_value=1.) as clock:
                output = MultiAxisSafeOutput(axes=['L0'], min_value=1000, max_value=9000,
                    invert_l0=invert, position_scale=scale, enable_endpoint_guard=guard,
                    enable_extreme_reset=False, max_step=40, startup_ramp_ms=1000)
                clock.return_value = 1.5
                previous = output.next_command({'L0': .8}, 1).values['L0']
                command = output.next_command({'L0': output.input_position('L0')}, 1)
                self.assertEqual(command.values['L0'], previous)

    def fake(self, step=.8):
        engine = SimpleNamespace(motion_reference=MotionReference('v1', 'ready', step=(0, step, 0)))
        engine.process = Mock(return_value=SimpleNamespace(positions={'L0': .8}, confidence=1))
        factory = Mock(return_value=engine)
        return PoseFastFallback(factory), factory, engine

    def test_fast_loss_hands_off_l0_and_pose_recovery_is_continuous(self):
        controller, factory, engine = self.fake()
        frame = np.zeros((80, 80, 3), np.uint8)
        for i in range(4):
            self.assertIsNone(controller.update(frame, i/30, True, .4))
        factory.assert_called_once_with()
        self.assertEqual(engine.process.call_count, 4)
        self.assertAlmostEqual(controller.update(frame, 4/30, False, .4), .4)
        for i in range(5, 15):
            controller.update(frame, i/30, False, .4)
        self.assertEqual(controller.source, 'v1')
        self.assertAlmostEqual(controller.override, .4)
        self.assertIs(controller.reference, engine.motion_reference)
        engine.process.return_value.positions['L0'] = .85
        self.assertAlmostEqual(controller.update(frame, 15/30, False, .4), .45)
        self.assertAlmostEqual(controller.update(frame, 16/30, True, .3), .45)
        for i in range(17, 25):
            controller.update(frame, i/30, True, .3)
        self.assertIsNone(controller.override)
        self.assertEqual(controller.value, .3)
        factory.assert_called_once_with()
        self.assertEqual(engine.process.call_count, 25)

    def test_missing_at_start_and_static_loss_do_not_activate_v1(self):
        frame = np.zeros((80, 80, 3), np.uint8)
        controller, factory, _ = self.fake()
        for i in range(30):
            self.assertIsNone(controller.update(frame, i/30, False, .4))
        factory.assert_called_once_with()
        controller, _, _ = self.fake(step=0)
        controller.update(frame, 0, True, .4)
        for i in range(1, 30):
            self.assertIsNone(controller.update(frame, i/30, False, .4))

    def test_missing_v1_reference_or_long_gap_cannot_reuse_active_motion(self):
        frame = np.zeros((80, 80, 3), np.uint8)
        controller, factory, engine = self.fake()
        controller.update(frame, 0, True, .4)
        for i in range(1, 12):
            controller.update(frame, i/30, False, .4)
        self.assertTrue(controller.active)
        engine.motion_reference = MotionReference('v1', 'missing')
        for i in range(12, 24):
            controller.update(frame, i/30, False, .4)
        self.assertIsNone(controller.override)
        controller.update(frame, 2, False, .4)
        self.assertEqual(factory.call_count, 2)
        self.assertIsNone(controller.override)
        self.assertIsNone(controller.last_pose)

    def test_applied_output_is_entry_anchor_and_limits_do_not_store_hidden_travel(self):
        controller, factory, engine = self.fake()
        frame = np.zeros((80, 80, 3), np.uint8)
        controller.update(frame, 0, True, .2)
        controller.remember_output(.96)
        self.assertAlmostEqual(controller.update(frame, 1/30, False, .2), .96)
        engine.process.return_value.positions['L0'] = 1.
        self.assertEqual(controller.update(frame, 2/30, False, .2), 1.)
        engine.process.return_value.positions['L0'] = .97
        self.assertAlmostEqual(controller.update(frame, 3/30, False, .2), .97)
        controller.remember_output(.71)
        self.assertAlmostEqual(controller.update(frame, 4/30, True, .3), .71)
        controller.remember_output(.70)
        self.assertAlmostEqual(controller.update(frame, 5/30, False, .3), .70)
        factory.assert_called_once_with()
        before = engine.process.call_count
        for stamp in (4/30, 5/30, float('nan'), float('inf')):
            self.assertAlmostEqual(controller.update(frame, stamp, False, .3), .70)
        self.assertEqual(engine.process.call_count, before)

    def test_real_v1_pipeline_takes_over_fast_pose_loss_without_changing_pose_observations(self):
        engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE,
                               visual_settings=VisualSettings(pose_auto_l0=False))
        engine.backend = FakePose()
        previous_v1 = previous_output = None
        for i in range(50):
            frame = np.zeros((400, 400, 3), np.uint8)
            y = 120 if i < 20 else 120+(i-20)*5
            cv2.rectangle(frame, (95, y), (245, y+80), (200, 210, 180), -1)
            engine.backend.missing = i >= 20
            result = engine.process(frame, i/30)
            if engine.pose_fast.active:
                current_v1 = engine.pose_fast.engine._positions['L0']
                if previous_v1 is None:
                    self.assertAlmostEqual(engine.generated_l0, .5)
                else:
                    expected = np.clip(previous_output + current_v1-previous_v1, 0, 1)
                    self.assertAlmostEqual(engine.generated_l0, expected)
                previous_v1, previous_output = current_v1, engine.generated_l0
        self.assertEqual(result.confidence, 0)
        self.assertEqual(result.positions['L0'], .5)
        self.assertEqual(engine.visual_frame.l0_source, 'v1')
        self.assertEqual(engine.visual_frame.reference.method, 'v1')
        self.assertIsNotNone(engine.generated_l0)
        geometry, observations = engine.geometry, engine.observations
        engine.configure(replace(engine.settings, pose_fast_v1=False))
        self.assertIs(engine.geometry, geometry)
        self.assertIs(engine.observations, observations)
        result = engine.process(frame, 50/30)
        self.assertIsNone(engine.generated_l0)
        self.assertIsNone(engine.pose_fast.engine)

    def test_disabled_and_non_pose_modes_never_start_v1(self):
        from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
        frame = np.zeros((160, 160, 3), np.uint8)
        for mode in (RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            engine = make_analyzer(tracker_mode=mode, visual_settings=VisualSettings(pose_fast_v1=mode != RTM_POSE_2D_MODE))
            engine.backend = FakePose()
            for i in range(3):
                engine.process(frame, i/30)
            self.assertIsNone(engine.pose_fast.engine)


if __name__ == '__main__':
    unittest.main()
