import unittest
from unittest.mock import patch
import cv2
import numpy as np

from motion_scenes import closeup_scene, MotionScene, deforming_frame
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.visual_pipeline import make_analyzer
from osr_screen_tcode.motion_layers import locally_coherent_motion
from osr_screen_tcode.motion_reference import reference_lines


class VideoReferenceTests(unittest.TestCase):
    def test_deforming_subject_uses_a_supported_local_region(self):
        for deformation in (5., 12.):
            scene = closeup_scene()
            engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
            references, positions = [], []
            for i in range(181):
                t = i/30
                frame = deforming_frame(scene, t, deformation, y=6*np.sin(t*5), camera_x=4*np.sin(t*3))
                positions.append(engine.process(frame, t).positions['L0'])
                references.append(engine.motion.reference)
            self.assertGreater(sum(r.state == 'ready' for r in references), 145)
            self.assertGreater(np.ptp(positions[-90:]), .5)
            boxes = [r for r in references if r.local_model == 'box' and r.state == 'ready']
            # test.23 deliberately follows the distributed whole subject,
            # instead of requiring a different tiny rigid patch every frame.
            self.assertGreater(len(boxes), 30)
            self.assertTrue(all(r.roi and len(r.background) >= 4 and len(r.vectors) >= 4 for r in boxes))
            self.assertIn('主体框中心', '\n'.join(reference_lines(boxes[-1], lambda zh, en: zh)))
            self.assertIn('subject-box center', '\n'.join(reference_lines(boxes[-1], lambda zh, en: en)))

    def test_local_flow_support_rejects_random_large_tracking_errors(self):
        x, y = np.meshgrid(np.arange(30, 300, 12), np.arange(40, 225, 12))
        points = np.float32(np.c_[x.ravel(), y.ravel()])
        smooth = np.c_[3+np.sin(points[:, 1]/60), 2+.5*np.cos(points[:, 0]/60)]
        self.assertGreater(locally_coherent_motion(points, smooth, 320, 240).mean(), .9)
        rng = np.random.default_rng(701)
        for _ in range(4):
            noise = rng.normal(0, 4, (len(points), 2))
            self.assertLess(locally_coherent_motion(points, noise, 320, 240).mean(), .1)

    def test_repeated_video_frames_preserve_background_and_do_not_repeat_steps(self):
        for scene in (MotionScene(), closeup_scene()):
            base, repeated = [make_analyzer(tracker_mode=HYBRID_V2_MODE) for _ in range(2)]
            positions, ready = [], 0
            for i in range(181):
                t = i/30
                frame = scene.frame(y=6*np.sin(t*5), camera_x=4*np.sin(t*3))
                base.process(frame, t)
                repeated.process(frame, t)
                np.testing.assert_allclose(repeated.motion.values, base.motion.values, atol=1e-10)
                self.assertAlmostEqual(repeated.motion.reference.motion_dt, base.motion.reference.motion_dt)
                self.assertEqual(repeated.motion.camera_source, base.motion.camera_source)
                for j in (1, 2):
                    before = repeated.motion.values.copy()
                    result = repeated.process(frame, t+j/90)
                    np.testing.assert_array_equal(repeated.motion.values, before)
                    self.assertEqual(repeated.motion.reference.step, (0., 0., 0.))
                    if repeated.visual_frame.observation.values is not None:
                        self.assertEqual(repeated.motion.reference.reason, 'repeated')
                    positions.append(result.positions['L0'])
                if i > 20:
                    ready += repeated.motion.reference.state == 'tracking'
            self.assertGreater(ready, 140)
            self.assertGreater(np.ptp(positions[-180:]), .5)

    def test_repeated_frame_pause_stops_cycle_and_cut_discards_reference(self):
        scene = closeup_scene()
        engine = make_analyzer(tracker_mode=STROKE_CYCLE_MODE)
        for i in range(181):
            t = i/30
            frame = scene.frame(y=6*np.sin(t*5))
            for j in range(2):
                engine.process(frame, t+j/60)
        self.assertNotEqual(engine.cycle.state, 'stopped')
        for i in range(1, 91):
            engine.process(frame, 6+1/60+i/60)
        self.assertEqual(engine.cycle.state, 'stopped')
        held = engine.positions['L0']
        for i in range(91, 121):
            self.assertEqual(engine.process(frame, 6+1/60+i/60).positions['L0'], held)
        engine.process(np.zeros_like(frame), 8.1)
        self.assertEqual(engine.motion.reference.reason, 'jump')
        self.assertIsNone(engine.motion.roi)
        self.assertEqual(engine.motion.local_model, '')

    def test_repeated_rejected_frame_cannot_restore_validity_or_extend_loss_grace(self):
        scene = closeup_scene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        for i in range(91):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        frame = scene.frame(y=6*np.sin(91/30*5))
        with patch.object(engine.motion, '_camera', return_value=(None, None)):
            engine.process(frame, 91/30)
        self.assertEqual(engine.motion.reference.state, 'holding')
        for i in range(1, 61):
            result = engine.process(frame, 91/30+i/60)
            self.assertEqual(result.confidence, 0.)
            self.assertIsNone(engine.visual_frame.observation.values)
        self.assertEqual(engine.motion.reference.state, 'missing')
        self.assertIsNone(engine.motion.roi)


if __name__ == '__main__':
    unittest.main()
