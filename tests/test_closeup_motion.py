import unittest
from collections import Counter

import numpy as np

from motion_scenes import closeup_scene, MotionScene
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.motion_reference import reference_lines
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings


class CloseupMotionTests(unittest.TestCase):
    def test_large_foreground_survives_small_background_and_camera_pan_zoom_roll(self):
        for kind, seed in (("corner", 12), ("corner", 52), ("strip", 15)):
            with self.subTest(kind=kind, seed=seed):
                scene = closeup_scene(kind, seed)
                engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
                values, states, sources = [], [], []
                for i in range(241):
                    t = i/30
                    result = engine.process(scene.frame(y=6*np.sin(t*5),
                        camera_x=4*np.sin(t*3), camera_y=2*np.sin(t*2),
                        camera_scale=1+.025*np.sin(t*2), camera_roll=1.5*np.sin(t*3)), t)
                    values.append(result.positions["L0"])
                    states.append(engine.motion.reference.state)
                    sources.append(engine.motion.reference.camera_model)
                self.assertGreater(np.ptp(values[-90:]), .5)
                self.assertGreater(sum(s in ("ready", "tracking") for s in states[15:]), 180)
                self.assertGreater(sources.count("minority"), 210)
                self.assertLess(states[15:].count("missing"), 4)
                self.assertGreater(engine.dominant.weights[0], .9)

    def test_closeup_camera_only_and_inseparable_scene_do_not_generate_strokes(self):
        for kind in ("corner", "strip", "none"):
            scene = closeup_scene(kind)
            engine = make_analyzer(tracker_mode=STROKE_CYCLE_MODE)
            for i in range(181):
                t = i/30
                result = engine.process(scene.frame(camera_x=4*np.sin(t*3), camera_y=2*np.sin(t*2),
                    camera_scale=1+.025*np.sin(t*2), camera_roll=1.5*np.sin(t*3)), t)
                self.assertEqual(engine.cycle.state, "stopped")
                self.assertEqual(result.positions["L0"], .5)

    def test_small_background_discovery_preserves_quarter_half_and_full_cycles(self):
        for amplitude, state, peak in ((2, "quarter", .25), (6, "half", .5), (15, "full", 1.)):
            with self.subTest(amplitude=amplitude):
                scene = closeup_scene()
                engine = make_analyzer(tracker_mode=STROKE_CYCLE_MODE, visual_settings=VisualSettings(v2_l0_reference='motion'))
                values, states = [], []
                for i in range(241):
                    t = i/30
                    result = engine.process(scene.frame(y=amplitude*np.sin(t*5), camera_x=4*np.sin(t*3)), t)
                    values.append(result.positions["L0"])
                    states.append(engine.cycle.state)
                self.assertGreater(Counter(states[-90:])[state], 80)
                self.assertEqual(min(values[-90:]), 0)
                self.assertEqual(max(values[-90:]), peak)
                # The tracked region must not shrink into the background patch.
                x1, y1, x2, y2 = engine.motion.roi
                self.assertGreater((x2-x1)*(y2-y1), .5*320*240)

    def test_background_occlusion_holds_without_promoting_foreground_to_camera(self):
        scene = closeup_scene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE, visual_settings=VisualSettings(v2_l0_reference='motion'))
        for i in range(121):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        background = scene.background.copy()
        scene.background[:] = 85
        values, states = [], []
        for i in range(121, 150):
            result = engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
            values.append(result.positions["L0"])
            states.append(engine.motion.reference.state)
            self.assertEqual(engine.motion.camera_source, "minority")
        np.testing.assert_allclose(values[2:], values[2], atol=.001)
        self.assertIn("holding", states)
        self.assertEqual(states[-1], "missing")
        scene.background = background
        for i in range(150, 210):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        self.assertIn(engine.motion.reference.state, ("ready", "tracking"))
        self.assertEqual(engine.motion.camera_source, "minority")

    def test_reference_reports_measured_small_background_in_both_languages(self):
        scene = closeup_scene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        for i in range(60):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        ref = engine.motion.reference
        self.assertEqual(ref.camera_model, "minority")
        self.assertTrue(ref.background)
        self.assertIn("分层背景", "\n".join(reference_lines(ref, lambda zh, en: zh)))
        self.assertIn("Layered camera", "\n".join(reference_lines(ref, lambda zh, en: en)))

    def test_cut_clears_minor_background_lock_and_allows_a_new_wide_scene(self):
        scene = closeup_scene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        for i in range(60):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        self.assertEqual(engine.motion.camera_source, "minority")
        engine.process(np.zeros((240, 320, 3), np.uint8), 2)
        self.assertEqual(engine.motion.reference.reason, "jump")
        self.assertEqual(engine.motion.camera_source, "")
        scene = MotionScene(seed=97)
        for i in range(61, 121):
            engine.process(scene.frame(y=6*np.sin(i/30*5)), i/30)
        self.assertIn(engine.motion.reference.state, ("ready", "tracking"))
        self.assertEqual(engine.motion.camera_source, "broad")
