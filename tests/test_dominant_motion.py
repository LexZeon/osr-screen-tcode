import unittest
from unittest.mock import patch

import cv2
import numpy as np

from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.frame_rotation import FrameRotation
from osr_screen_tcode.config import HYBRID_V2_MODE
from osr_screen_tcode.visual_pipeline import make_analyzer
from test_visual_pipeline import FakePose
from motion_scenes import MotionScene


class DominantMotionTests(unittest.TestCase):
    def test_all_three_primary_directions_and_remaining_axis_assignment(self):
        # Cardinal inputs are special cases of the continuous local frame.
        # Its handedness may reverse a transverse sign versus an old swap.
        for direction, primary, permutation in ((1, 0, (1, 2, 0)),
                                                 (2, 1, (2, 1, 0)),
                                                 (0, 2, (0, 2, 1))):
            engine = DominantMotion()
            for i in range(481):
                values = np.zeros(3)
                values[direction] = 8 * np.sin(i/60*5)
                result = engine.update(values, i/60)
            self.assertEqual(engine.primary, primary)
            self.assertGreater(engine.weights[primary], .99)
            delta = np.array((.1, .2, .3))
            moved = engine.update(values + delta, 481/60)
            np.testing.assert_allclose(np.array(list(moved.values())) - list(result.values()),
                                       engine.basis @ delta[[1, 2, 0]] / 100, atol=1e-5)
            np.testing.assert_allclose(engine.basis @ engine.basis.T, np.eye(3), atol=1e-12)

    def test_mixed_motion_retains_secondary_contribution_and_static_offsets(self):
        engine = DominantMotion()
        for i in range(481):
            values = (6*np.sin(i/60*5), 8*np.sin(i/60*5), 0)
            result = engine.update(values, i/60)
        self.assertGreater(engine.weights[0], engine.weights[2])
        np.testing.assert_allclose(engine.basis[0], (.8, 0, .6), atol=1e-6)
        previous = result
        for i in range(481, 841):
            result = engine.update(values, i/60)
        np.testing.assert_allclose(list(result.values()), list(previous.values()), atol=1e-12)

    def test_change_of_primary_direction_is_gradual_and_reset_discards_history(self):
        engine = DominantMotion()
        for i in range(1, 121):
            engine.update((0, i*.1, 0), i/60)
        before = engine.weights.copy()
        result = engine.update((.2, 12, 0), 121/60)
        self.assertLess(np.max(np.abs(engine.weights-before)), .07)
        # A sustained pan cannot take over. Repeated left/right motion can.
        for i in range(122, 241):
            engine.update(((i-120)*.2, 12, 0), i/60)
        self.assertGreater(engine.weights[0], .99)
        for i in range(241, 721):
            previous = result
            result = engine.update((24+8*np.sin((i-240)/60*5), 12, 0), i/60)
        self.assertGreater(engine.weights[2], .99)
        self.assertIsNone(engine.update((0, 0, 0), 12))
        engine.update((0, 0, 0), 13)
        np.testing.assert_allclose(engine.weights, [1, 0, 0])

    def test_pan_and_zoom_do_not_overrule_vertical_strokes(self):
        for pan, zoom in ((25, 0), (0, 15), (25, 15)):
            engine = DominantMotion()
            samples, expected = [], []
            for i in range(601):
                t = i/60
                y = 5*np.sin(5*t)
                samples.append(engine.update((pan*t, y, zoom*t), t)["L0"])
                expected.append(.5+y/100)
            np.testing.assert_allclose(samples, expected, atol=1e-9)
            self.assertGreater(engine.weights[0], .99)

    def test_high_frequency_noise_and_short_shake_do_not_establish_an_axis(self):
        engine = DominantMotion()
        for i in range(601):
            t = i/60
            # Small jitter throughout, plus a large but brief camera shake.
            shake = 8*np.sin((t-3)*np.pi/.1) if 3 < t < 3.2 else 0
            result = engine.update((.3*np.sin(90*t)+shake, 3*np.sin(5*t), .4*np.sin(60*t)), t)
            self.assertEqual(engine.primary, 0)
            self.assertAlmostEqual(result["L0"], .5+.03*np.sin(5*t), places=6)

    def test_switch_does_not_reintroduce_a_large_accumulated_pan(self):
        engine = DominantMotion()
        engine.update((0, 0, 0), 0)
        last, point = .5, np.zeros(3)
        for i in range(1, 601):
            t = i/60
            current = np.array((30*t if t < 3 else 90+8*np.sin((t-3)*5), 0, 0))
            result = engine.update(current, t)
            self.assertLessEqual(abs(result["L0"]-last), np.max(np.abs(current-point))/100+1e-12)
            last, point = result["L0"], current
        self.assertGreater(engine.weights[2], .99)

    def test_video_clock_is_consistent_across_frame_rates(self):
        results = []
        for fps in (30, 45, 60, 120):
            engine = DominantMotion()
            samples = []
            for i in range(8*fps+1):
                t = i/fps
                samples.append(engine.update((8*np.sin(t*5), 0, 0), t)["L0"])
            self.assertEqual(engine.primary, 2)
            results.append(np.array(samples)[::fps//15])
        for other in results[1:]:
            np.testing.assert_allclose(other, results[0], atol=.007)

    def test_whole_frame_flow_is_camera_reference_not_a_subject_stroke(self):
        texture = np.random.default_rng(16).integers(0, 256, (240, 320, 3), np.uint8)
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode="L0 Only")
        output, expected = [], []
        for i in range(151):
            y = 4*np.sin(i/30*5)
            frame = cv2.warpAffine(texture, np.float32([[1, 0, i*2], [0, 1, -y]]),
                                   (320, 240), borderMode=cv2.BORDER_WRAP)
            sample = engine.process(frame, i/30)
            if sample.confidence > 0:
                output.append(sample.positions["L0"])
                expected.append(.5+y/240)
        # The entire image moves rigidly; there is no independent subject.
        self.assertEqual(engine.positions["L0"], .5)
        self.assertIsNone(engine.motion.reference.roi)
        self.assertGreater(engine.dominant.weights[0], .98)

    def test_pose_option_changes_only_rotations_and_model_is_not_needed_for_l0(self):
        scene = MotionScene()
        with patch("osr_screen_tcode.analyzer.OptionalRtmPose2dBackend", side_effect=lambda *a, **k: FakePose()) as backend:
            no_pose = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode="Six Axis")
            single = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode="L0 Only", hybrid_v2_pose_enabled=True)
            backend.assert_not_called()
            with_pose = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode="Six Axis", hybrid_v2_pose_enabled=True)
            backend.assert_called_once()
            for i in range(30):
                frame = scene.frame(y=6*np.sin(i/30*5), camera_x=10*np.sin(i/30*3))
                a, b, c = [e.process(frame, i/30) for e in (no_pose, with_pose, single)]
                self.assertEqual(a.positions["L0"], c.positions["L0"])
                for axis in ("L0", "L1", "L2"):
                    self.assertEqual(no_pose.positions[axis], with_pose.positions[axis])
            self.assertEqual(with_pose.backend.calls, 30)
            self.assertEqual(with_pose.visual_frame.rotation_source, "pose")
            self.assertEqual(no_pose.visual_frame.rotation_source, "image")


class FrameRotationTests(unittest.TestCase):
    def vectors(self, matrix):
        points = np.float32([[x, y] for y in range(40, 241, 25) for x in range(40, 321, 25)])
        return list(zip(points, cv2.perspectiveTransform(points[None], np.array(matrix, float))[0]))

    def test_translation_and_uniform_scale_do_not_create_rotations(self):
        result = FrameRotation().update(self.vectors([[1.05, 0, 7], [0, 1.05, -9], [0, 0, 1]]), (300, 400))
        np.testing.assert_allclose(list(result.values()), [.5, .5, .5], atol=1e-5)

    def test_roll_and_perspective_have_separate_bounded_signals(self):
        for matrix, axis in (([[.995, -.1, 0], [.1, .995, 0], [0, 0, 1]], "R1"),
                             ([[1, 0, 0], [0, 1, 0], [.0005, 0, 1]], "R0"),
                             ([[1, 0, 0], [0, 1, 0], [0, .0005, 1]], "R2")):
            result = FrameRotation().update(self.vectors(matrix), (300, 400))
            self.assertIsNotNone(result)
            self.assertGreater(abs(result[axis]-.5), .02)
            self.assertTrue(all(0 <= v <= 1 for v in result.values()))

    def test_missing_or_poor_coverage_does_not_replace_rotation_state(self):
        engine = FrameRotation()
        self.assertIsNone(engine.update([], (300, 400)))
        vectors = [(np.float32([i, i]), np.float32([i+1, i+1])) for i in range(20)]
        self.assertIsNone(engine.update(vectors, (300, 400)))
        np.testing.assert_array_equal(engine.transform, np.eye(3))
