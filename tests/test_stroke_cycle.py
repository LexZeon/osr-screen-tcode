import unittest
import numpy as np

from motion_scenes import MotionScene
from test_visual_pipeline import FakePose
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings
from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.stroke_cycle import StrokeCycle
from osr_screen_tcode.motion_reference import MotionReference


class StrokeCycleTests(unittest.TestCase):
    def test_higher_quarter_sensitivity_still_requires_real_reciprocal_excursion(self):
        dominant, cycle = DominantMotion(), StrokeCycle()
        previous = 0
        for i in range(240):
            t = i/60
            y = .3*np.sin(t*40)
            dominant.update((0, y, 0), t)
            cycle.update(dominant, MotionReference("v2", step=(0, y-previous, 0)), t, True)
            previous = y
            self.assertEqual(cycle.state, "stopped")
            self.assertEqual(cycle.value, .5)

    def test_small_and_large_reciprocal_motion_generate_half_and_full_endpoints(self):
        scene = MotionScene()
        for amplitude, state, peak in ((2, "quarter", .25), (6, "half", .5), (15, "full", 1.)):
            engine = make_analyzer(tracker_mode=STROKE_CYCLE_MODE, visual_settings=VisualSettings(v2_l0_reference='motion'))
            values = []
            for i in range(241):
                t = i/30
                result = engine.process(scene.frame(y=amplitude*np.sin(t*5), camera_x=8*np.sin(t*3)), t)
                values.append(result.positions["L0"])
            self.assertEqual(engine.cycle.state, state)
            self.assertEqual(min(values[-90:]), 0)
            self.assertEqual(max(values[-90:]), peak)
            self.assertAlmostEqual(engine.cycle.period, 2*np.pi/5, delta=.12)
            self.assertLess(np.max(np.abs(np.diff(values))), .15)

    def test_uses_exact_v2_observations_with_and_without_pose_rotations(self):
        scene = MotionScene(size=(400, 400))
        base = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        single = make_analyzer(tracker_mode=STROKE_CYCLE_MODE)
        assisted = make_analyzer(tracker_mode=STROKE_CYCLE_MODE, output_mode="Six Axis", hybrid_v2_pose_enabled=True)
        assisted.backend = FakePose()
        for i in range(90):
            t = i/30
            frame = scene.frame(y=12*np.sin(t*5))
            base.process(frame, t)
            a, b = single.process(frame, t), assisted.process(frame, t)
            self.assertEqual(base.motion.reference, single.motion.reference)
            self.assertAlmostEqual(a.positions["L0"], b.positions["L0"])
            self.assertEqual(b.positions["L1"], .5)
            self.assertEqual(b.positions["L2"], .5)
        self.assertEqual(assisted.backend.calls, 90)
        self.assertEqual(assisted.visual_frame.rotation_source, "pose")
        single.configure(VisualSettings(generation=1))
        self.assertEqual(single.cycle.state, "stopped")

    def test_camera_only_noise_and_missing_frames_cannot_drive_cycles(self):
        scene = MotionScene()
        engine = make_analyzer(tracker_mode=STROKE_CYCLE_MODE, output_mode="Six Axis")
        for i in range(120):
            t = i/30
            result = engine.process(scene.frame(camera_x=10*np.sin(t*5), camera_scale=1+.04*np.sin(t*3)), t)
            self.assertEqual(set(result.positions.values()), {.5})
            self.assertEqual(engine.cycle.state, "stopped")
        engine.process(np.zeros((240, 320, 3), np.uint8), 4)
        self.assertEqual(engine.cycle.state, "stopped")

    def test_cadence_changes_gradually_and_stops_when_motion_stops(self):
        dominant, cycle = DominantMotion(), StrokeCycle()
        previous = 0
        periods = []
        for i in range(601):
            t = i/60
            # Continuous phase; frequency increases at 5 s.
            phase = t*4 if t < 5 else 20+(t-5)*6
            y = 6*np.sin(phase)
            dominant.update((0, y, 0), t)
            cycle.update(dominant, MotionReference("v2", step=(0, y-previous, 0)), t, True)
            previous = y
            periods.append(cycle.period)
        self.assertLess(periods[-1], periods[280])
        self.assertLess(max(abs(a-b) for a, b in zip(periods, periods[1:])), .2)
        for i in range(601, 721):
            t = i/60
            dominant.update((0, previous, 0), t)
            cycle.update(dominant, MotionReference("v2"), t, True)
        held = cycle.value
        self.assertEqual(cycle.state, "stopped")
        self.assertEqual(cycle.update(dominant, MotionReference("v2"), 12.1, False), held)
