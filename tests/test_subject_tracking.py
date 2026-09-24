import unittest
from collections import Counter
from types import SimpleNamespace

import cv2
import numpy as np

from motion_scenes import ReachScene
from osr_screen_tcode.config import HYBRID_V2_MODE
from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.fused_l0 import FusedL0
from osr_screen_tcode.motion_reference import MotionReference, reference_lines, target_marker
from osr_screen_tcode.reach_target import ReachObservation
from osr_screen_tcode.subject_tracking import SubjectMemory
from osr_screen_tcode.visual_pipeline import make_analyzer


class SubjectTrackingTests(unittest.TestCase):
    def test_flapping_target_cannot_pin_the_subject_script_at_one_position(self):
        fused, dominant = FusedL0(), DominantMotion(adaptive_l0=True)
        point = SimpleNamespace(state='unresolved', point=None, step=0.)
        values = []
        previous = 0.
        for i in range(301):
            stamp = i/30
            position = 10*np.sin(5*stamp)
            ordinary = dominant.update((position, 0., 0.), stamp)['L0']
            ref = MotionReference('v2', 'ready', (100., 70., 160., 150.), step=(position-previous, 0., 0.))
            phase = .5+.4*np.sin(5*stamp)
            arrival = ReachObservation('ready' if i%2 else 'holding', (300., 100.),
                remaining=phase if i%2 else None, key=1, delta=.01)
            values.append(fused.update(dominant, ref, point, None, ((130., 110.), phase),
                                       stamp, (240, 320), ordinary, arrival))
            previous = position
        self.assertGreater(np.ptp(values[-180:]), .65)  # test.21 produced exactly zero
        self.assertLess(np.max(np.abs(np.diff(values))), .15)
        self.assertFalse(fused.arrival_active)

    def test_subject_anchor_stays_on_same_location_and_missing_object_is_explicitly_assumed(self):
        scene = ReachScene(target=False)
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        errors, values, assumed = [], [], []
        for i in range(151):
            frame, actual, _ = scene.frame(i/30)
            result = engine.process(frame, i/30)
            ref = engine.visual_frame.reference
            if ref.subject_origin is not None and ref.state == 'ready':
                errors.append(np.asarray(ref.subject_origin)-actual)
            values.append(result.positions['L0'])
            if ref.target_kind == 'assumed':
                assumed.append(ref)
                self.assertIsNone(ref.reach_progress)
                self.assertEqual(target_marker(ref.target_kind), 'V?')
        self.assertGreater(len(assumed), 40)
        self.assertLess(np.max(np.ptp(errors, axis=0)), 8.)
        self.assertGreater(np.ptp(values[-90:]), .7)
        self.assertIn('假定客体', '\n'.join(reference_lines(assumed[-1], lambda zh, en: zh)))
        self.assertIn('not observed', '\n'.join(reference_lines(assumed[-1], lambda zh, en: en)))

    def test_blurred_frames_recover_real_subject_pixels_and_do_not_confirm_exposed_background_as_pause(self):
        scene = ReachScene(target=False)
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        states, values = Counter(), []
        for i in range(151):
            frame, _, _ = scene.frame(i/30)
            if i > 25 and i%3 == 0:
                frame[120:244] = cv2.GaussianBlur(frame[120:244], (31, 31), 8)
            result = engine.process(frame, i/30)
            states[engine.motion.reference.reason] += 1
            values.append(result.positions['L0'])
        self.assertGreater(states['subject_recovered'], 20)
        self.assertEqual(states['stationary'], 0)
        self.assertGreater(np.ptp(values[-90:]), .7)
        self.assertLess(engine.resets, 3)

    def test_recovery_cannot_supply_motion_without_verified_background_or_after_timeout(self):
        rng = np.random.default_rng(91)
        gray = rng.integers(0, 255, (240, 320), np.uint8)
        points = np.float32([(x, y) for x in (90, 110, 130, 150) for y in (90, 110, 130)])
        background = np.float32([(x, y) for x in (10, 40, 280, 310) for y in (10, 40, 200, 230)])
        memory = SubjectMemory()
        memory.remember(gray, 0., points, background, (120., 110.), (85., 85., 155., 135.), (0., 0., 0.))
        changed = gray.copy()
        changed[:60] = 0
        changed[180:] = 0
        self.assertIsNone(memory.recover(changed, .1))
        self.assertIsNone(memory.recover(gray, .3))


if __name__ == '__main__':
    unittest.main()
