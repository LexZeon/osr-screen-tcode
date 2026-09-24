"""Subject-center regressions, including the test.22 deformation failure.

No downloaded media, models, devices, user preferences, or generated files.
"""
import unittest

import cv2
import numpy as np

from motion_scenes import closeup_scene, deforming_frame, MotionScene
from osr_screen_tcode.camera_motion import CameraRelativeMotion
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.regional_flow import box_fit, coherent_support, DenseRegionFlow
from osr_screen_tcode.subject_tracking import SubjectMemory
from osr_screen_tcode.visual_pipeline import make_analyzer


class RegionalFlowTests(unittest.TestCase):
    def test_local_deformation_can_be_coherent_without_one_rigid_transform(self):
        y, x = np.mgrid[55:205:9, 35:290:9]
        a = np.column_stack((x.ravel(), y.ravel())).astype(np.float32)
        delta = np.column_stack((.7*np.sin(a[:, 1]/20), 3+1.2*np.sin(a[:, 0]/25)))
        self.assertGreater(coherent_support(a, delta, (240, 320)).mean(), .9)
        result = box_fit(a, a+delta, np.float64([[1, 0, 0], [0, 1, 0]]), (240, 320), .16)
        self.assertIsNotNone(result)
        start, end, transform, groups = result
        moved = transform @ np.array((160, 130, 1))-np.array((160, 130))
        self.assertAlmostEqual(moved[0], 0., delta=.5)
        self.assertAlmostEqual(moved[1], 3., delta=.5)
        self.assertGreaterEqual(len(groups), 6)
        self.assertGreater(np.ptp((end-start)[:, 1]), 1.)

    def test_random_independent_flows_and_pure_camera_cannot_define_a_subject(self):
        y, x = np.mgrid[35:215:10, 30:290:10]
        a = np.column_stack((x.ravel(), y.ravel())).astype(np.float32)
        random = np.random.default_rng(2301).normal(0, 8, a.shape)
        self.assertLess(coherent_support(a, random, (240, 320)).mean(), .1)
        camera = np.float64([[1.02, -.01, 2], [.01, 1.02, -3]])
        b = a @ camera[:, :2].T+camera[:, 2]
        self.assertIsNone(box_fit(a, b, camera, (240, 320), .16))
        self.assertIsNone(box_fit(a, a+random, camera, (240, 320), .16))

    def test_partial_cells_do_not_move_the_center_when_other_points_disappear(self):
        y, x = np.mgrid[45:205:8, 45:285:8]
        a = np.column_stack((x.ravel(), y.ravel())).astype(np.float32)
        camera = np.float64([[1, 0, 1], [0, 1, 0]])
        expected = np.float64([[1.015, -.008, 4], [.008, 1.015, -5]])
        origins = []
        for keep in (np.ones(len(a), bool), (a[:, 0] < 130) | (a[:, 1] > 90)):
            result = box_fit(a[keep], a[keep] @ expected[:, :2].T+expected[:, 2],
                             camera, (240, 320), .16, prior=(45, 45, 285, 205))
            self.assertIsNotNone(result)
            origins.append(result[2] @ np.array((165, 125, 1)))
        np.testing.assert_allclose(origins, [expected @ (165, 125, 1)]*2, atol=.1)

    def test_dense_support_is_measured_and_rejects_a_texture_replacement(self):
        scene = MotionScene()
        first = cv2.cvtColor(scene.frame(), cv2.COLOR_BGR2GRAY)
        next_frame = cv2.cvtColor(scene.frame(y=7), cv2.COLOR_BGR2GRAY)
        flow = DenseRegionFlow()
        a, b = flow.track(first, next_frame)
        subject = np.all((a > (125, 95)) & (a < (195, 150)), axis=1)
        self.assertGreater(subject.sum(), 12)
        np.testing.assert_allclose(np.median((b-a)[subject], axis=0), (0, -7), atol=.3)
        random = np.random.default_rng(2302).integers(0, 255, first.shape, np.uint8)
        start, _ = flow.track(first, random)
        self.assertLess(len(start), len(a)*.1)

    def test_background_cohort_cannot_prove_pause_when_subject_anchor_moves(self):
        rng = np.random.default_rng(2303)
        background = rng.integers(20, 180, (240, 320), np.uint8)
        patch = rng.integers(50, 250, (15, 15), np.uint8)
        first, last = background.copy(), background.copy()
        first[103:118, 113:128] = patch
        last[103:118, 125:140] = patch
        source = np.float32([(x, y) for x in (80, 95, 145, 160) for y in (75, 90, 130, 145)])
        bg = np.float32([(x, y) for x in (15, 45, 275, 300) for y in (15, 40, 195, 225)])
        memory = SubjectMemory()
        memory.align_origin(first, (120, 110), new=True)
        # Deliberately contaminated cohort: good background matching alone
        # must not confirm a stationary subject at a different real position.
        memory.remember(first, 0., source, bg, (120, 110), (75, 70, 165, 150), (0, 0, 0))
        self.assertIsNone(memory.recover(last, .05))

    def test_deforming_box_recovers_the_whole_gap_once_from_real_pixels(self):
        scene = closeup_scene()
        first = cv2.cvtColor(deforming_frame(scene, .5, deformation=12), cv2.COLOR_BGR2GRAY)
        last = cv2.cvtColor(deforming_frame(scene, .5, deformation=12, y=12, camera_x=1.5), cv2.COLOR_BGR2GRAY)
        points = CameraRelativeMotion._features(first).reshape(-1, 2)
        source = points[np.all((points > (35, 65)) & (points < (290, 205)), axis=1)]
        background = points[np.all((points > (7, 6)) & (points < (81, 30)), axis=1)]
        memory = SubjectMemory()
        memory.remember(first, 1., source, background, (160, 130), (35, 65, 290, 205), (2, 3, 0), deforming=True)
        recovered = memory.recover(last, 1.12)
        self.assertIsNotNone(recovered)
        self.assertAlmostEqual(recovered.elapsed, .12)
        self.assertAlmostEqual(recovered.step[1], 5., delta=.25)  # all 12 px, not a final-frame fraction
        self.assertAlmostEqual(recovered.values[1], 8., delta=.25)
        self.assertGreaterEqual(len(recovered.groups), 5)
        self.assertEqual(recovered.corners.shape, (4, 2))
        np.testing.assert_allclose(np.ptp(recovered.corners, axis=0), (255, 140), atol=2)
        self.assertIsNone(memory.recover(last, 1.12))
        self.assertIsNone(memory.recover(last, 1.3))

    def test_deforming_closeup_tracks_the_box_center_and_drives_shared_modes(self):
        from test_visual_pipeline import FakePose
        scene = closeup_scene()
        ordinary = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode='Six Axis')
        cycle = make_analyzer(tracker_mode=STROKE_CYCLE_MODE)
        assisted = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode='Six Axis',
                                 hybrid_v2_pose_enabled=True)
        assisted.backend = FakePose()
        samples, l0, modes, cycle_values = [], [], [], []
        for i in range(151):
            t = i/30
            frame = deforming_frame(scene, t, deformation=24, y=20*np.sin(t*5), camera_x=3*np.sin(t*3))
            result = ordinary.process(frame, t)
            cycle_values.append(cycle.process(frame, t).positions['L0'])
            assisted.process(frame, t)
            np.testing.assert_allclose(ordinary.motion.values, cycle.motion.values, atol=1e-6)
            np.testing.assert_allclose(ordinary.motion.values, assisted.motion.values, atol=1e-6)
            ref = ordinary.visual_frame.reference
            modes.append(ref.local_model)
            l0.append(result.positions['L0'])
            if ref.state == 'ready':
                samples.append((i, ordinary.motion.values[1], ref.subject_origin))
                self.assertEqual(ordinary.visual_frame.observation.center, ref.subject_origin)
                # This subject never fills the whole frame. Repeatedly taking
                # an axis-aligned envelope of tiny rotations used to grow the
                # yellow box beyond the image and pollute recovery ownership.
                extent = np.asarray(ref.subject_box[2:])-ref.subject_box[:2]
                self.assertLess(extent[0], frame.shape[1]*1.1)
                self.assertLess(extent[1], frame.shape[0]*1.1)
        # test.22: 5 / 151 measured frames and 2% output span on this scene.
        self.assertGreater(len(samples), 110)
        self.assertGreater(modes.count('box'), 125)
        self.assertEqual(ordinary.resets, 0)
        self.assertGreater(np.ptp(l0[-90:]), .65)
        self.assertGreater(np.ptp(cycle_values[-90:]), .2)
        late = np.array([(i, v) for i, v, _ in samples if i > 40])
        self.assertGreater(np.corrcoef(np.sin(late[:, 0]/30*5), late[:, 1])[0, 1], .9)
        self.assertGreater(abs(ordinary.dominant.basis[0, 0]), .9)
        self.assertLess(np.max(np.abs(np.diff(l0))), .25)


if __name__ == '__main__':
    unittest.main()
