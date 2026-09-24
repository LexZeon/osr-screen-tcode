"""Distant geometric targets must not be replaced by the tracked ROI center."""
import unittest
from dataclasses import replace
from types import SimpleNamespace

import cv2
import numpy as np

from osr_screen_tcode.fused_l0 import FusedL0
from osr_screen_tcode.interaction_point import InteractionPoint, convergence
from osr_screen_tcode.motion_reference import MotionReference, reference_lines, target_marker


class TargetGeometryTests(unittest.TestCase):
    def setUp(self):
        self.a = np.float64([(x, y) for x in range(55, 136, 8) for y in range(55, 144, 8)])
        self.target = np.array((275., 110.))

    def test_actual_pixels_locate_distant_target_and_keep_camera_measurements_identical(self):
        from unittest.mock import patch
        from motion_scenes import MotionScene, distant_target_frame
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from osr_screen_tcode.config import HYBRID_V2_MODE
        scene = MotionScene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        baseline = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        errors, distances, marked = [], [], 0
        for i in range(241):
            stamp = i/30
            frame, target = distant_target_frame(scene, stamp)
            engine.process(frame, stamp)
            with patch('osr_screen_tcode.camera_motion.long_convergence', return_value=None):
                baseline.process(frame, stamp)
            np.testing.assert_array_equal(engine.motion.values, baseline.motion.values)
            point = engine.motion.interaction
            if point.state == 'ready':
                errors.append(np.linalg.norm(point.point-target))
                x1, y1, x2, y2 = engine.motion.roi
                distances.append(np.linalg.norm(point.point-((x1+x2)/2, (y1+y2)/2)))
                # The distant flow reference remains at its measured position
                # as P?; fusion now separately labels the assumed object V?.
                shown = engine.visual_frame.reference.interaction_point
                if shown is not None:
                    np.testing.assert_allclose(shown, point.point)
                    marked += 1
        self.assertGreater(len(errors), 70)
        self.assertGreater(marked, 60)
        self.assertLess(np.percentile(errors, 95), 4.)
        self.assertGreater(np.percentile(distances, 5), 120.)

    def test_small_expansion_locates_a_distant_focus_outside_the_tracked_region(self):
        rng = np.random.default_rng(20)
        for k in (-.002, .002):
            b = self.a+k*(self.a-self.target)+rng.normal(0, .009, self.a.shape)
            found = convergence(self.a, b, (240, 320))
            self.assertIsNotNone(found)
            np.testing.assert_allclose(found[0], self.target, atol=3.)
            self.assertGreater(np.linalg.norm(found[0]-self.a.mean(axis=0)), 170.)

    def test_reciprocal_region_and_camera_move_without_dragging_target_with_them(self):
        tracker = InteractionPoint()
        rng = np.random.default_rng(21)
        errors, origins, targets, steps = [], [], [], []
        previous_scale = 1.
        for i in range(1, 301):
            t = i/30
            # Every actual frame expands about the same distant point; most
            # pairs have less than the old fixed 0.4% scale threshold.
            scale = np.exp(.013*np.sin(2*np.pi*t))
            old_camera = np.array((6*np.sin((t-1/30)*2), 3*np.sin(t-1/30)))
            new_camera = np.array((6*np.sin(t*2), 3*np.sin(t)))
            a = self.target+(self.a-self.target)*previous_scale+old_camera
            b = self.target+(self.a-self.target)*scale+old_camera
            b += rng.normal(0, .009, b.shape)
            camera = np.column_stack((np.eye(2), new_camera-old_camera))
            tracker.update(a, b, camera, t, (240, 320))
            if tracker.state == 'ready':
                errors.append(np.linalg.norm(tracker.point-new_camera-self.target))
                origins.append(a.mean(axis=0)-old_camera)
                targets.append(tracker.point-new_camera)
                steps.append((scale-previous_scale, tracker.step))
            previous_scale = scale
        self.assertGreater(len(errors), 150)
        self.assertLess(np.percentile(errors, 95), 2.)
        self.assertGreater(np.median(np.linalg.norm(np.asarray(targets)-origins, axis=1)), 170.)
        self.assertLess(np.ptp(np.asarray(targets)[:, 0]), np.ptp(np.asarray(origins)[:, 0])*.65)
        scale_steps, toward = np.asarray(steps).T
        self.assertLess(np.corrcoef(scale_steps, toward)[0, 1], -.98)

    def test_translation_rotation_line_support_and_weak_noisy_flow_do_not_invent_target(self):
        rng = np.random.default_rng(22)
        center = self.a.mean(axis=0)
        rotation = cv2.getRotationMatrix2D(tuple(center), 1., 1.)
        for i in range(50):
            noise = rng.normal(0, .08, self.a.shape)
            self.assertIsNone(convergence(self.a, self.a+(2, -.5)+noise, (240, 320)))
            self.assertIsNone(convergence(self.a, self.a+.0001*(self.a-self.target)+noise, (240, 320)))
        self.assertIsNone(convergence(self.a, self.a @ rotation[:, :2].T+rotation[:, 2], (240, 320)))
        line = np.column_stack((np.arange(40., 240.), np.full(200, 100.)))
        self.assertIsNone(convergence(line, line+.02*(line-self.target), (240, 320)))

    def test_known_camera_motion_transports_missing_point_without_renewing_evidence(self):
        tracker = InteractionPoint()
        camera = np.column_stack((np.eye(2), np.zeros(2)))
        for i in range(12):
            tracker.update(self.a, self.a+.01*(self.a-self.target), camera, i/30, (240, 320))
        self.assertEqual(tracker.state, 'ready')
        last_evidence = tracker.timestamp
        old_value = tracker.value
        shift = np.array((1.2, -.4))
        camera[:, 2] = shift
        for i in range(1, 9):
            a = self.a+(i-1)*shift
            tracker.update(a, a+(2, 0), camera, last_evidence+i/30, (240, 320))
            np.testing.assert_allclose(tracker.point, self.target+i*shift, atol=.01)
            self.assertEqual(tracker.timestamp, last_evidence)
            self.assertEqual(tracker.value, old_value)
            self.assertEqual(tracker.step, 0.)
        tracker.hold(last_evidence+.46, camera)
        self.assertIsNone(tracker.point)


class TargetMeaningTests(unittest.TestCase):
    def test_endpoint_and_internal_scale_center_never_claim_to_locate_target(self):
        fused = FusedL0()
        dominant = SimpleNamespace(basis=np.eye(3), stroke_span=10.)
        ref = MotionReference('v2', 'ready', (80, 60, 180, 180))
        point = SimpleNamespace(state='unresolved', point=None)
        fused._target(dominant, ref, point, ((130., 120.), .5), (240, 320))
        self.assertEqual(target_marker(fused.target_kind), 'E?')
        np.testing.assert_allclose(fused.target, (130., 132.))
        fused.oriented = True
        for location, kind in (((130., 120.), 'expansion'), ((275., 110.), 'interaction')):
            point = SimpleNamespace(state='ready', point=location)
            fused._target(dominant, ref, point, ((130., 120.), .5), (240, 320))
            self.assertEqual(fused.target_kind, kind)
            self.assertEqual(fused.target, location)
        for kind in ('endpoint', 'unoriented', 'expansion', 'expansion_held'):
            snapshot = replace(ref, target_point=(130., 132.), target_kind=kind)
            zh = '\n'.join(reference_lines(snapshot, lambda zh, en: zh, compact=True))
            en = '\n'.join(reference_lines(snapshot, lambda zh, en: en, compact=True))
            self.assertNotIn('T?', zh)
            self.assertNotIn('T?', en)
            self.assertIn('目标', zh)
            self.assertIn('target', en)


if __name__ == '__main__':
    unittest.main()
