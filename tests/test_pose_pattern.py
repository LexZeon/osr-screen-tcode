import math
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from osr_screen_tcode.pose_pattern import AxisPattern, PosePattern
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings
from osr_screen_tcode.config import RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE
from test_visual_pipeline import FakePose


class PatternTests(unittest.TestCase):
    def train(self, detector, seconds=9, amplitude=.04, center=.5):
        gains = []
        for i in range(round(seconds*60)+1):
            t = i/60
            detector.update(center+amplitude*math.sin(2*math.pi*t), t)
            gains.append(detector.gain)
        return gains

    def test_small_repeat_requires_several_cycles_and_ramps_without_recentering(self):
        detector = AxisPattern()
        gains = self.train(detector, center=.67)
        self.assertTrue(all(g == 1 for g in gains[:180]))
        self.assertEqual(detector.gain, 2)
        self.assertLessEqual(max(b-a for a, b in zip(gains, gains[1:])), 1/60+1e-10)
        first = next(i for i, gain in enumerate(gains) if gain > 1)
        maximum = next(i for i, gain in enumerate(gains) if gain == 2)
        self.assertLessEqual((maximum-first)/60, 1.)
        self.assertGreaterEqual((maximum-first)/60, .95)
        self.assertAlmostEqual(detector.center, .67, places=3)
        self.assertAlmostEqual(detector.apply(.71), .75, places=3)
        self.assertAlmostEqual(detector.apply(.63), .59, places=3)

    def test_axes_are_independent_and_generated_l0_cannot_self_amplify(self):
        detector = PosePattern()
        for i in range(541):
            t = i/60
            positions = {a: .5+.04*math.sin(2*math.pi*t+j*.2)
                         for j, a in enumerate(('L0', 'L1', 'L2', 'R0', 'R1', 'R2'))}
            positions['R1'] = .5
            detector.update(positions, t, excluded=('L0',))
        self.assertEqual(detector.axes['L0'].gain, 1)
        self.assertEqual(detector.axes['R1'].gain, 1)
        self.assertEqual({a for a, g in detector.gains}, {'R0'})
        excluded = {'L1': .6, 'L2': .4, 'R2': .7}
        self.assertEqual(detector.apply(excluded), excluded)
        self.assertEqual(set(detector.axes), {'L0', 'R0', 'R1'})
        self.assertEqual(detector.apply({'L0': .25}, excluded=('L0',)), {'L0': .25})

    def test_l0_r0_r1_use_independent_periods_and_growth_releases_only_one(self):
        detector = PosePattern()
        for i in range(901):
            t = i/60
            detector.update({a: .5+.04*math.sin(t*2*math.pi/period)
                             for a, period in (('L0', 1.), ('R0', .8), ('R1', 1.4))}, t)
        self.assertTrue(all(axis.gain == 2 for axis in detector.axes.values()))
        for i in range(901, 981):
            t = i/60
            detector.update({'L0': .5+.04*math.sin(t*2*math.pi),
                             'R0': .5+.16*math.sin(t*2*math.pi/.8),
                             'R1': .5+.04*math.sin(t*2*math.pi/1.4)}, t)
        self.assertEqual(detector.axes['R0'].gain, 1)
        self.assertEqual(detector.axes['L0'].gain, 2)
        self.assertEqual(detector.axes['R1'].gain, 2)

    def test_real_amplitude_growth_exits_in_a_quarter_second(self):
        detector = AxisPattern()
        self.train(detector)
        gains = []
        for i in range(541, 581):
            detector.update(.5+.16*math.sin(2*math.pi*i/60), i/60)
            gains.append(detector.gain)
        self.assertFalse(detector.active)
        self.assertEqual(detector.gain, 1)
        self.assertTrue(all(b <= a for a, b in zip(gains, gains[1:])))

    def test_no_boost_for_noise_fast_jitter_large_strokes_or_one_way_motion(self):
        rng = np.random.default_rng(17)
        signals = [lambda t: .5+rng.normal(0, .002),
                   lambda t: .5+.04*math.sin(t*2*math.pi*12),
                   lambda t: .5+.18*math.sin(t*2*math.pi),
                   lambda t: .4+t*.01]
        for signal in signals:
            detector = AxisPattern()
            for i in range(601):
                detector.update(signal(i/60), i/60)
                self.assertEqual(detector.gain, 1)

    def test_stopped_or_missing_observations_release_and_gaps_reset(self):
        for value in (.5, None):
            detector = AxisPattern()
            self.train(detector)
            for i in range(541, 631):
                detector.update(value, i/60)
            self.assertEqual(detector.gain, 1)
            self.assertFalse(detector.active)
        detector = AxisPattern()
        self.train(detector)
        detector.update(.5, 11)
        self.assertEqual(detector.gain, 1)
        for stamp in (10, 11, float('nan')):
            detector.update(.9, stamp)
            self.assertEqual(detector.gain, 1)

    def test_switch_changes_output_without_changing_analysis_and_preserves_auto_wave(self):
        settings = VisualSettings(pose_pattern=False)
        baseline = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, output_mode='Six Axis', visual_settings=settings)
        enabled = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, output_mode='Six Axis', visual_settings=replace(settings, pose_pattern=True))
        for engine in (baseline, enabled):
            engine.backend = FakePose()
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(301):
            # Bypass model/geometry heuristics only for a deterministic repeat;
            # still exercise the real shared observations and result routing.
            rotations = {'R0': .5+(.04/3)*math.sin(i/30*2*math.pi), 'R1': .5, 'R2': .5}
            results = []
            for engine in (baseline, enabled):
                with patch.object(engine.geometry, '_positions_from_rtm_pose_2d', return_value=(rotations, None)):
                    results.append(engine.process(frame, i/30))
            self.assertEqual(results[0].positions, results[1].positions)
            self.assertEqual(results[0].confidence, results[1].confidence)
            self.assertEqual(baseline.generated_l0, enabled.generated_l0)
        self.assertEqual(enabled.pose_pattern.axes['R0'].gain, 2)
        self.assertEqual(enabled.pose_pattern.axes['L0'].gain, 1)
        observed, wave = enabled.observations, enabled.pose_fallback
        enabled.configure(replace(enabled.settings, pose_pattern=False))
        self.assertIs(enabled.observations, observed)
        self.assertIs(enabled.pose_fallback, wave)
        self.assertFalse(enabled.pose_pattern.gains)

    def test_pattern_is_default_off_and_excluded_from_hybrid_and_cycle(self):
        self.assertFalse(VisualSettings().pose_pattern)
        frame = np.zeros((120, 160, 3), np.uint8)
        for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            engine = make_analyzer(tracker_mode=mode, visual_settings=VisualSettings(pose_pattern=True))
            for i in range(31):
                engine.process(frame, i/30)
            self.assertFalse(engine.visual_frame.pattern_gains)
            self.assertTrue(all(axis.stamp is None for axis in engine.pose_pattern.axes.values()))


if __name__ == '__main__':
    unittest.main()
