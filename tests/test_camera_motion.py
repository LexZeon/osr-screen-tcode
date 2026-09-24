import unittest
from unittest.mock import patch

import cv2
import numpy as np

from motion_scenes import MotionScene, difficult_scene
from osr_screen_tcode.camera_motion import CameraRelativeMotion
from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE
from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.motion_reference import reference_lines
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings


class CameraMotionTests(unittest.TestCase):
    def test_background_band_supports_strokes_without_three_quadrants(self):
        scene = difficult_scene("band")
        for local_motion in (False, True):
            engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
            states, values = [], []
            for i in range(181):
                t = i/30
                result = engine.process(scene.frame(y=6*np.sin(t*5) if local_motion else 0,
                                                     camera_x=8*np.sin(t*3)), t)
                states.append(engine.motion.reference.state)
                values.append(result.positions["L0"])
            if local_motion:
                self.assertGreater(states.count("ready"), 140)
                self.assertNotIn("missing", states[3:])
                self.assertGreater(np.ptp(values[-90:]), .5)
            else:
                np.testing.assert_allclose(values, .5, atol=.005)

    def test_intermittent_background_loss_holds_without_recalibrating(self):
        from osr_screen_tcode.config import STROKE_CYCLE_MODE
        for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            engine = make_analyzer(tracker_mode=mode, visual_settings=VisualSettings(v2_l0_reference='motion'))
            scene = MotionScene()
            for i in range(121):
                engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
            dominant, resets = engine.dominant, engine.resets
            for i in range(121, 181):
                frame = scene.frame(y=6*np.sin(i/30*5))
                before = dict(engine.positions)
                if i % 5 == 0:
                    # Neither adjacent-frame nor cached-frame camera evidence
                    # exists in this loss case.
                    with patch.object(engine.motion, "_camera", return_value=(None, None)), \
                         patch.object(engine.motion.subject, "recover", return_value=None):
                        result = engine.process(frame, i/30)
                    self.assertEqual(engine.motion.reference.state, "holding")
                    self.assertIsNone(engine.visual_frame.observation.values)
                    self.assertEqual(result.positions["L0"], before["L0"])
                    self.assertFalse(engine.visual_frame.reset)
                else:
                    engine.process(frame, i/30)
                self.assertIs(engine.dominant, dominant)
            self.assertEqual(engine.resets, resets)
            self.assertGreater(engine.dominant.stroke_gain, 5)
            with patch.object(engine.motion, "_camera", return_value=(None, None)), \
                 patch.object(engine.motion.subject, "recover", return_value=None):
                for i in range(181, 211):
                    engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
            self.assertEqual(engine.motion.reference.state, "missing")
            self.assertIsNone(engine.motion.roi)
            self.assertEqual(engine.dominant.stroke_gain, 1)

    def test_a_tracked_stationary_region_does_not_expire_at_a_pause(self):
        scene = MotionScene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        for i in range(121):
            frame = scene.frame(y=6*np.sin(i/30*5))
            result = engine.process(frame, i/30)
        held, resets = result.positions["L0"], engine.resets
        for i in range(121, 181):
            result = engine.process(frame, i/30)
            self.assertEqual(result.positions["L0"], held)
            self.assertEqual(engine.motion.reference.state, "tracking")
            self.assertIsNotNone(engine.motion.roi)
        self.assertEqual(engine.resets, resets)

    def test_established_background_points_can_survive_partial_occlusion(self):
        engine = CameraRelativeMotion()
        a = np.float32([[15, 20], [75, 20], [15, 45], [75, 45]])
        b = a+np.float32([1, 0])
        engine.background_points = a.copy()
        engine.camera_transform = np.float64([[1, 0, 1], [0, 1, 0]])
        camera, indices = engine._camera(a, b, np.ones(4, bool), .7, 320, 240)
        self.assertIsNotNone(camera)
        self.assertEqual(len(indices), 4)
        self.assertIsNone(engine._camera(a, b+10, np.ones(4, bool), .7, 320, 240)[0])

    def test_blurred_sparse_background_and_edge_subject_remain_observable(self):
        for kind in ("blur", "sparse", "edge"):
            with self.subTest(kind=kind):
                scene = difficult_scene(kind)
                engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
                ready, positions, backgrounds = 0, [], []
                for i in range(181):
                    t = i/30
                    result = engine.process(scene.frame(y=6*np.sin(t*5),
                        x=-100 if kind == "edge" else 0, camera_x=8*np.sin(t*3)), t)
                    ready += engine.motion.reference.state == "ready"
                    backgrounds.append(engine.motion.reference.counts[2])
                    positions.append(result.positions["L0"])
                self.assertGreater(ready, 120)
                self.assertGreater(np.ptp(positions[-90:]), .5)
                if kind == "sparse":
                    self.assertTrue(any(6 <= n < 18 for n in backgrounds))

    def test_sparse_and_blurred_camera_only_motion_still_holds(self):
        for kind in ("blur", "sparse"):
            scene = difficult_scene(kind)
            engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
            for i in range(151):
                t = i/30
                result = engine.process(scene.frame(camera_x=12*np.sin(t*3),
                    camera_y=8*np.sin(t*2), camera_scale=1+.03*np.sin(t*2)), t)
                self.assertAlmostEqual(result.positions["L0"], .5, delta=.01)

    def test_missing_reference_shows_specific_reason_and_feature_counts(self):
        engine = CameraRelativeMotion()
        frame = np.zeros((240, 320), np.uint8)
        engine.update(frame, 0)
        engine.update(frame, 1/30)
        self.assertEqual(engine.reference.reason, "features")
        self.assertEqual(engine.reference.counts, (0, 0, 0, 0))
        self.assertIn("纹理不足", "\n".join(reference_lines(engine.reference, lambda zh, en: zh)))
        self.assertIn("Too few image features", "\n".join(reference_lines(engine.reference, lambda zh, en: en)))

    def test_reciprocal_camera_pan_zoom_and_roll_cannot_create_a_stroke(self):
        scene = MotionScene()
        for subject in (False, True):
            engine = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode="Six Axis")
            for i in range(181):
                t = i/30
                result = engine.process(scene.frame(camera_x=20*np.sin(t*3), camera_y=8*np.sin(t*2),
                    camera_scale=1+.04*np.sin(t*2), camera_roll=2*np.sin(t*3), subject=subject), t)
                self.assertAlmostEqual(result.positions["L0"], .5, places=4)
            self.assertEqual(engine.dominant.stroke_gain, 1)

    def test_small_local_stroke_survives_camera_motion_and_has_useful_travel(self):
        scene = MotionScene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        results, samples = [], []
        for i in range(241):
            t = i/30
            result = engine.process(scene.frame(y=6*np.sin(t*5), camera_x=12*np.sin(t*3),
                                                camera_y=8*np.sin(t*2)), t)
            results.append(result.positions["L0"])
            if engine.motion.reference.state == "ready":
                samples.append(engine.visual_frame.reference)
        self.assertGreater(len(samples), 160)
        # Image travel is only 5% of height; established L0 travel exceeds 50%.
        self.assertGreater(np.ptp(results[-90:]), .5)
        self.assertTrue(all(0 <= value <= 1 for value in results))
        # Compare the continuous unit direction to the known vertical motion.
        # L1-normalized component weights are diagnostics, not angular accuracy:
        # small correlated scale-estimation residuals are now retained too.
        self.assertGreater(engine.dominant.basis[0, 0], np.cos(np.deg2rad(5)))
        shown = samples[-1]
        self.assertGreater(len(shown.background), 18)
        self.assertGreater(len(shown.vectors), 7)
        self.assertIsNotNone(shown.roi)
        self.assertGreater(max(ref.gain for ref in samples), 5)

    def test_actual_lateral_and_scale_strokes_can_still_become_primary(self):
        scene = MotionScene()
        for direction, primary in (("x", 2), ("scale", 1)):
            engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
            late = []
            for i in range(241):
                t = i/30
                values = {direction: 8*np.sin(t*5) if direction == "x" else 1+.08*np.sin(t*5)}
                result = engine.process(scene.frame(**values, camera_x=12*np.sin(t*3), camera_y=8*np.sin(t*2)), t)
                if i > 150:
                    late.append(result.positions["L0"])
            self.assertEqual(engine.dominant.primary, primary)
            self.assertGreater(engine.dominant.weights[primary], .9)
            self.assertGreater(np.ptp(late), .5)

    def test_missing_background_cut_and_recalibration_discard_stale_evidence(self):
        scene = MotionScene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        for i in range(151):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        frame = np.zeros((240, 320, 3), np.uint8)
        old = dict(engine.positions)
        result = engine.process(frame, 5.1)
        self.assertEqual(result.positions, {"L0": old["L0"]})
        self.assertEqual(result.confidence, 0)
        self.assertEqual(engine.dominant.stroke_gain, 1)
        engine.configure(VisualSettings(edge=640, generation=1))
        engine.process(scene.frame(), 6)
        self.assertEqual(engine.dominant.stroke_gain, 1)
        self.assertIsNone(engine.visual_frame.reference.span)
        self.assertFalse(engine.visual_frame.reference.vectors)

    def test_camera_vectors_describe_the_transform_actually_removed(self):
        scene, engine = MotionScene(), CameraRelativeMotion()
        engine.update(cv2.cvtColor(scene.frame(), cv2.COLOR_BGR2GRAY), 0)
        engine.update(cv2.cvtColor(scene.frame(y=2, camera_x=2), cv2.COLOR_BGR2GRAY), 1/30)
        sample, vectors = engine.update(cv2.cvtColor(scene.frame(y=4, camera_x=4), cv2.COLOR_BGR2GRAY), 2/30)
        self.assertEqual(sample.state, "ready")
        self.assertAlmostEqual(engine.reference.camera_step[0], 2/320*100, delta=.06)
        self.assertAlmostEqual(engine.reference.step[1], 2/240*100, delta=.08)
        self.assertAlmostEqual(engine.reference.step[0], 0, delta=.06)
        self.assertGreater(len(vectors), 7)

    def test_compensation_preserves_actual_local_perspective_for_rotation(self):
        engine = CameraRelativeMotion()
        gray = np.zeros((240, 320), np.uint8)
        a = np.float32([[x, y] for y in range(12, 240, 18) for x in range(12, 320, 18)])
        local = (a[:, 0] > 110) & (a[:, 0] < 212) & (a[:, 1] > 75) & (a[:, 1] < 170)
        shape = np.float32([[1, 0, 1], [0, 1, -2], [.00005, 0, 1]])
        deformed = a.copy()
        deformed[local] = cv2.perspectiveTransform(a[local, None], shape)[:, 0]
        b = deformed + np.float32([1.3, -.7])
        status = np.ones((len(a), 1), np.uint8)
        engine.update(gray, 0)
        for stamp in (1/30, 2/30):
            # Mocked motion still needs distinct images; identical frames are held.
            gray = np.full_like(gray, round(stamp * 30))
            # This geometry test supplies a fixed synthetic point set; seed
            # replenishment is exercised separately with actual image pairs.
            engine.foreground_points = None
            with patch.object(engine, "_features", return_value=a[:, None]), patch("osr_screen_tcode.camera_motion.cv2.calcOpticalFlowPyrLK",
                side_effect=[(b[:, None], status, None), (a[:, None], status, None)]):
                sample, vectors = engine.update(gray, stamp)
        self.assertEqual(sample.state, "ready")
        used_a, used_b = (np.array(values) for values in zip(*vectors))
        expected = cv2.perspectiveTransform(used_a.astype(np.float32)[:, None], shape)[:, 0]
        np.testing.assert_allclose(used_b, expected, atol=.001)
        # A fitted similarity would erase this perspective component.
        fitted, _ = cv2.estimateAffinePartial2D(used_a, used_b)
        self.assertGreater(np.max(np.abs(used_b-(used_a @ fitted[:, :2].T+fitted[:, 2]))), .015)

    def test_v1_reference_is_the_used_roi_and_samples_without_changing_l0(self):
        engine = make_analyzer(tracker_mode=HYBRID_MODE)
        for i in range(4):
            frame = np.zeros((240, 320, 3), np.uint8)
            cv2.rectangle(frame, (70, 30+i*6), (210, 100+i*6), (190, 210, 180), -1)
            result = engine.process(frame)
        ref = engine.motion_reference
        self.assertEqual(ref.l0, result.positions["L0"])
        self.assertEqual(ref.method, "v1")
        self.assertTrue(ref.vectors)
        x1, y1, x2, y2 = ref.roi
        self.assertTrue(all(x1 <= a[0] < x2 and y1 <= a[1] < y2 for a, b in ref.vectors))
        self.assertLess(ref.step[1], 0)  # Actual downwards image movement.
        self.assertIn("实际区域", "\n".join(reference_lines(ref, lambda zh, en: zh)))
        self.assertIn("actual region", "\n".join(reference_lines(ref, lambda zh, en: en)))


class StrokeCalibrationTests(unittest.TestCase):
    def test_calibration_requires_reciprocal_excursions_and_does_not_amplify_jitter(self):
        for noise in (False, True):
            engine = DominantMotion(adaptive_l0=True)
            for i in range(241):
                t = i/60
                y = .2*np.sin(t*60) if noise else t*3
                engine.update((0, y, 0), t)
                self.assertEqual(engine.stroke_gain, 1)

    def test_calibration_preserves_stationary_output_and_auxiliary_measurements(self):
        calibrated, raw = DominantMotion(adaptive_l0=True), DominantMotion()
        for i in range(361):
            value = (0, 2*np.sin(i/60*5), 0)
            a, b = calibrated.update(value, i/60), raw.update(value, i/60)
            self.assertEqual(a["L1"], b["L1"])
            self.assertEqual(a["L2"], b["L2"])
        self.assertGreater(calibrated.stroke_gain, 10)
        last = a["L0"]
        for i in range(361, 721):
            self.assertEqual(calibrated.update(value, i/60)["L0"], last)
        calibrated.update((0, 0, 0), 14)
        self.assertEqual(calibrated.stroke_gain, 1)
