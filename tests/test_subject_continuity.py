"""Pixel-owned weak tracks, bounded display estimates and no expiry loopholes."""
from dataclasses import FrozenInstanceError, replace
import unittest

import cv2
import numpy as np

from motion_scenes import MotionScene
from osr_screen_tcode.motion_reference import MotionReference
from osr_screen_tcode.subject_continuity import SubjectContinuity


def gray(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


SOURCE = np.float32([(x, y) for x in (120, 138, 158, 178, 198) for y in (84, 101, 120, 139, 153)])
BACKGROUND = np.float32([(x, y) for x in (20, 60, 260, 290) for y in (20, 50, 185, 215)])


def reference(x=0., y=0., *, state='ready', pixels=True, **kwargs):
    points = SOURCE+(x, y)
    return MotionReference('v2', state, subject_origin=(160.+x, 120.+y),
        subject_box=(112.+x, 76.+y, 208.+x, 162.+y),
        vectors=tuple(((999., 999.), tuple(p)) for p in points) if pixels else (), **kwargs)


def missing(*, background=(), camera_model='', **kwargs):
    return MotionReference('v2', 'missing', background=background, camera_model=camera_model, **kwargs)


def bg_pair(dx=0., dy=0., previous=(0., 0.)):
    return tuple((tuple(p+previous), tuple(p+previous+(dx, dy))) for p in BACKGROUND)


class SubjectContinuityTests(unittest.TestCase):
    def setUp(self):
        self.scene = MotionScene()
        self.engine = SubjectContinuity()
        self.first = gray(self.scene.frame())

    def test_only_valid_strict_subject_can_seed(self):
        for ref in (reference(state='holding'), reference(state='missing'),
                    replace(reference(), subject_box=(0., 0., 0., 0.)),
                    replace(reference(), subject_origin=(float('nan'), 100.)),
                    replace(reference(), subject_box=None)):
            with self.subTest(ref=ref.state):
                engine = SubjectContinuity()
                self.assertIsNone(engine.update(self.first, 0., ref))
                self.assertIsNone(engine.update(gray(self.scene.frame(x=3)), .1, missing()))

    def test_owned_pixels_follow_subject_without_inventing_camera_or_step(self):
        ref = reference()
        self.assertIsNone(self.engine.update(self.first, 0., ref))
        for i in range(1, 7):
            estimate = self.engine.update(gray(self.scene.frame(x=i*3, y=i)), i*.1, missing())
            self.assertEqual(estimate.state, 'weak')
            np.testing.assert_allclose(estimate.origin, (160+i*3, 120-i), atol=.35)
            self.assertIsNone(estimate.step)
            self.assertFalse(estimate.stationary)
        self.assertEqual(ref, reference())
        with self.assertRaises(FrozenInstanceError):
            estimate.state = 'ready'

    def test_same_pair_camera_pixels_allow_relative_step(self):
        self.engine.update(self.first, 0., reference())
        current = gray(self.scene.frame(x=4, y=3, camera_x=2, camera_y=1))
        estimate = self.engine.update(current, .1,
            missing(background=bg_pair(2, -1), camera_model='broad'))
        self.assertEqual(estimate.state, 'weak')
        self.assertIsNotNone(estimate.step)
        np.testing.assert_allclose(estimate.step, (4/320*100, 3/240*100, 0), atol=.05)
        np.testing.assert_allclose(estimate.origin, (166, 116), atol=.2)

    def test_unknown_or_wrong_pair_background_cannot_supply_step(self):
        current = gray(self.scene.frame(x=4, camera_x=2))
        for ref in (missing(background=bg_pair(2, 0)),
                    missing(background=bg_pair(0, 0), camera_model='broad'),
                    missing(background=(((5., 5.), (7., 5.)),)*10, camera_model='broad')):
            with self.subTest(model=ref.camera_model, first=ref.background[0]):
                engine = SubjectContinuity()
                engine.update(self.first, 0., reference())
                estimate = engine.update(current, .1, ref)
                self.assertEqual(estimate.state, 'weak')
                self.assertIsNone(estimate.step)
                self.assertFalse(estimate.stationary)

    def test_camera_motion_with_owned_subject_pixels_can_confirm_relative_pause(self):
        self.engine.update(self.first, 0., reference())
        current = gray(self.scene.frame(camera_x=3, camera_y=2))
        estimate = self.engine.update(current, .1,
            missing(background=bg_pair(3, -2), camera_model='broad'))
        self.assertEqual(estimate.state, 'weak')
        self.assertEqual(estimate.step, (0., 0., 0.))
        self.assertTrue(estimate.stationary)

    def test_partial_point_loss_keeps_distributed_subject_identity(self):
        self.engine.update(self.first, 0., reference())
        current = gray(self.scene.frame(x=5, y=2))
        current[75:165, 180:215] = self.first[75:165, 180:215]
        estimate = self.engine.update(current, .1, missing())
        self.assertEqual(estimate.state, 'weak')
        np.testing.assert_allclose(estimate.origin, (165, 118), atol=.5)

    def test_exposed_background_cannot_become_subject_or_confirm_pause(self):
        self.engine.update(self.first, 0., reference())
        background = gray(self.scene.frame(subject=False))
        for stamp in (.1, .2, .3, .4):
            estimate = self.engine.update(background, stamp,
                missing(background=bg_pair(), camera_model='broad'))
            self.assertNotEqual(estimate.state, 'weak')
            self.assertIsNone(estimate.step)
            # A frozen rejected INPUT may eventually stop continuation; it
            # still has no measured zero step or weak subject confirmation.
            self.assertEqual(estimate.stationary, stamp >= .3)

    def test_rejected_repeated_frame_holds_without_replaying_measured_motion(self):
        self.engine.update(self.first, 0., reference())
        current = gray(self.scene.frame(x=4))
        estimate = self.engine.update(current, .1, missing(background=bg_pair(), camera_model='broad'))
        self.assertGreater(estimate.step[0], 1.)
        for stamp in (.2, .3, .4):
            held = self.engine.update(current, stamp, missing())
            self.assertEqual(held.state, 'held')
            self.assertEqual(held.origin, estimate.origin)
            self.assertIsNone(held.step)
            self.assertEqual(held.stationary, stamp >= .3)

    def test_short_duplicate_decode_frames_do_not_stop_but_frozen_input_does(self):
        self.engine.update(self.first, 0., reference())
        rejected = gray(self.scene.frame(subject=False))
        self.engine.update(rejected, .1, missing(reason='region'))
        for stamp in (.12, .15, .22, .29):
            estimate = self.engine.update(rejected, stamp, missing(reason='region'))
            self.assertFalse(estimate.stationary)
        estimate = self.engine.update(rejected, .3, missing(reason='region'))
        self.assertTrue(estimate.stationary)
        self.assertEqual(estimate.state, 'held')
        self.assertIsNone(estimate.step)
        self.assertAlmostEqual(estimate.elapsed, .3)
        # A new frame clears the input freeze without fabricating recovery.
        changed = rejected.copy()
        changed[0, 0] ^= 1
        estimate = self.engine.update(changed, .32, missing(reason='region'))
        self.assertFalse(estimate.stationary)

    def test_weak_real_pixels_never_renew_two_second_limit(self):
        self.engine.update(self.first, 0., reference())
        for i in range(1, 22):
            estimate = self.engine.update(gray(self.scene.frame(x=10*np.sin(i*.2))), i*.1, missing())
            if i <= 20:
                self.assertIsNotNone(estimate)
                self.assertAlmostEqual(estimate.elapsed, i*.1)
            else:
                self.assertIsNone(estimate)

    def test_single_ready_flash_cannot_renew_expiry(self):
        self.engine.update(self.first, 0., reference())
        for i in range(1, 25):
            x = 8*np.sin(i*.2)
            ref = reference(x) if i in (9, 18, 22) else missing()
            estimate = self.engine.update(gray(self.scene.frame(x=x)), i*.1, ref)
            if i in (9, 18, 22):
                self.assertIsNone(estimate)
            elif i <= 20:
                self.assertAlmostEqual(estimate.elapsed, i*.1)
            else:
                self.assertIsNone(estimate)

    def test_reconfirmation_requires_both_three_frames_and_point_two_seconds(self):
        self.engine.update(self.first, 0., reference())
        self.engine.update(gray(self.scene.frame(x=1)), .1, missing())
        for stamp, x in ((.2, 2), (.25, 3), (.3, 4)):
            self.assertIsNone(self.engine.update(gray(self.scene.frame(x=x)), stamp, reference(x)))
        estimate = self.engine.update(gray(self.scene.frame(x=5)), .31, missing())
        self.assertAlmostEqual(estimate.elapsed, .31)
        for stamp, x in ((.4, 6), (.5, 7), (.6, 8)):
            self.assertIsNone(self.engine.update(gray(self.scene.frame(x=x)), stamp, reference(x)))
        estimate = self.engine.update(gray(self.scene.frame(x=9)), .7, missing())
        self.assertAlmostEqual(estimate.elapsed, .1)

    def test_repeated_ready_frames_do_not_reconfirm_a_missing_episode(self):
        self.engine.update(self.first, 0., reference())
        self.engine.update(gray(self.scene.frame(x=1)), .1, missing())
        current = gray(self.scene.frame(x=2))
        for stamp in (.2, .3, .4, .5):
            self.engine.update(current, stamp, reference(2, reason='repeated'))
        estimate = self.engine.update(gray(self.scene.frame(x=3)), .6, missing())
        self.assertAlmostEqual(estimate.elapsed, .6)

    def test_unmeasured_display_prediction_brakes_then_holds_and_expires(self):
        self.engine.update(self.first, 0., reference(pixels=False))
        self.engine.update(gray(self.scene.frame(x=10)), .1, reference(10, pixels=False))
        positions, states = [], []
        rng = np.random.default_rng(171)
        for i in range(2, 23):
            frame = rng.integers(20, 200, self.first.shape, np.uint8)
            estimate = self.engine.update(frame, i*.1, missing())
            if i <= 21:
                self.assertIsNone(estimate.step)
                positions.append(estimate.origin[0])
                states.append(estimate.state)
            else:
                self.assertIsNone(estimate)
        self.assertIn('predicted', states)
        self.assertEqual(states[-1], 'held')
        self.assertGreater(positions[0], 170.)
        self.assertLessEqual(max(positions), 187.5001)
        np.testing.assert_allclose(positions[3:], positions[3], atol=1e-8)

    def test_explicit_strict_pause_discards_prior_display_velocity(self):
        self.engine.update(self.first, 0., reference(pixels=False))
        self.engine.update(gray(self.scene.frame(x=10)), .1, reference(10, pixels=False))
        current = gray(self.scene.frame(x=10, camera_x=3))
        self.engine.update(current, .2, reference(13, pixels=False, reason='stationary'))
        rejected = gray(self.scene.frame(subject=False))
        estimate = self.engine.update(rejected, .3, missing())
        self.assertEqual(estimate.state, 'held')
        self.assertEqual(estimate.origin, (173., 120.))
        self.assertIsNone(estimate.step)

    def test_whole_gap_pixel_recovery_does_not_mix_with_single_frame_camera(self):
        self.engine.update(self.first, 0., reference())
        occluded = gray(self.scene.frame(subject=False))
        self.engine.update(occluded, .1, missing())
        recovered = self.engine.update(gray(self.scene.frame(x=5)), .2,
            missing(background=bg_pair(), camera_model='broad'))
        self.assertEqual(recovered.state, 'weak')
        self.assertIsNone(recovered.step)
        resumed = self.engine.update(gray(self.scene.frame(x=7)), .3,
            missing(background=bg_pair(), camera_model='broad'))
        self.assertIsNotNone(resumed.step)
        self.assertAlmostEqual(resumed.step[0], 2/320*100, delta=.05)

    def test_cut_shape_and_time_discontinuities_clear_old_subject(self):
        for frame, stamp, ref in ((self.first, .1, missing(reason='jump')),
                                  (self.first[:100], .1, missing()),
                                  (self.first, .6, missing()),
                                  (self.first, 0., missing()),
                                  (self.first, float('nan'), missing()),
                                  (np.zeros_like(self.first), .1, missing())):
            with self.subTest(stamp=stamp, reason=ref.reason, shape=frame.shape):
                engine = SubjectContinuity()
                engine.update(self.first, 0., reference())
                self.assertIsNone(engine.update(frame, stamp, ref))
                self.assertIsNone(engine.update(self.first, .7, missing()))

    def test_new_region_calibration_discards_previous_subject_estimate(self):
        self.engine.update(self.first, 0., reference())
        new_region = MotionReference('v2', 'calibrating', roi=(220., 20., 300., 100.))
        self.assertIsNone(self.engine.update(gray(self.scene.frame(x=4)), .1, new_region))
        self.assertIsNone(self.engine.update(gray(self.scene.frame(x=5)), .2, missing()))

    def test_input_freezing_stops_prediction_but_cannot_extend_expiry(self):
        self.engine.update(self.first, 0., reference())
        rejected = gray(self.scene.frame(subject=False))
        for i in range(1, 23):
            estimate = self.engine.update(rejected, i*.1, missing())
            if 3 <= i <= 20:
                self.assertTrue(estimate.stationary)
                self.assertIsNone(estimate.step)
                self.assertAlmostEqual(estimate.elapsed, i*.1)
            elif i > 20:
                self.assertIsNone(estimate)


if __name__ == '__main__':
    unittest.main()
