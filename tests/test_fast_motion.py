import unittest

import cv2
import numpy as np

from motion_scenes import window_scene, MotionScene
from osr_screen_tcode.camera_motion import CameraRelativeMotion
from osr_screen_tcode.motion_layers import MinorityBackground
from osr_screen_tcode.motion_reference import MotionReference, reference_lines
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.visual_pipeline import make_analyzer


class FastMotionTests(unittest.TestCase):
    def test_fast_window_drag_retains_background_and_measures_large_steps(self):
        scene, engine = window_scene(), CameraRelativeMotion()
        rows = []
        for i in range(97):
            y = 75*np.sin(i*2*np.pi/12)
            engine.update(cv2.cvtColor(scene.frame(y=y), cv2.COLOR_BGR2GRAY), i/30)
            rows.append(engine.reference)
        self.assertGreater(sum(r.state in ('ready', 'tracking') for r in rows[12:]), 65)
        self.assertGreater(sum(r.counts[2] >= 6 for r in rows[12:]), 75)
        self.assertGreater(sum(abs(r.step[1]) > 6 for r in rows), 15)
        self.assertNotIn('jump', [r.reason for r in rows])

    def test_fast_whole_frame_drag_does_not_generate_strokes(self):
        scene = MotionScene(size=(480, 640))
        for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            engine = make_analyzer(tracker_mode=mode)
            for i in range(61):
                result = engine.process(scene.frame(camera_y=75*np.sin(i*2*np.pi/12)), i/30)
                self.assertEqual(result.positions['L0'], .5)

    def test_unrelated_textured_cut_still_resets(self):
        scene, engine = window_scene(), CameraRelativeMotion()
        for i in range(10):
            engine.update(cv2.cvtColor(scene.frame(y=i*3), cv2.COLOR_BGR2GRAY), i/30)
        frame = np.random.default_rng(333).integers(0, 255, (480, 640), np.uint8)
        engine.update(frame, 10/30)
        self.assertEqual(engine.reference.reason, 'jump')
        self.assertIsNone(engine.roi)

    def test_small_background_survives_multiple_foreground_motion_groups(self):
        background = np.float32([(x, y) for x in range(10, 80, 8) for y in range(8, 26, 8)])
        parts = [np.float32([(x, y) for x in range(30+j*65, 90+j*65, 8)
                           for y in range(60, 225, 12)]) for j in range(4)]
        a = np.concatenate([background, *parts])
        b = np.concatenate([background, *[p+(j-2, -2-j) for j, p in enumerate(parts)]]).astype(np.float32)
        model = MinorityBackground()
        self.assertIsNone(model.select(a, b, 320, 240)[0])
        camera, indices = model.select(b, b+(b-a), 320, 240)
        self.assertIsNotNone(camera)
        self.assertTrue(np.all(indices < len(background)))
        np.testing.assert_allclose(camera, [[1, 0, 0], [0, 1, 0]], atol=.01)

    def test_background_diagnostics_distinguish_rejected_from_accepted_points(self):
        ref = MotionReference('v2', 'missing', reason='background', counts=(368, 358, 0, 0),
                              background_diagnostic=('uncertainty', 9, 4), rescued=12)
        zh = '\n'.join(reference_lines(ref, lambda zh, en: zh))
        en = '\n'.join(reference_lines(ref, lambda zh, en: en))
        self.assertIn('背景 0', zh)
        self.assertIn('候选 9', zh)
        self.assertIn('外推误差', zh)
        self.assertIn('Camera extrapolation uncertain', en)
        self.assertIn('recovered 12', en)


if __name__ == '__main__':
    unittest.main()
