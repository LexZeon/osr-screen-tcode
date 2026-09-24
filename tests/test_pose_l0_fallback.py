import math
import unittest
from dataclasses import replace

import numpy as np

from osr_screen_tcode.pose_l0_fallback import PoseL0Fallback, PoseL0Recovery, rotation_l0
from osr_screen_tcode.pose_output import rtm_rotation_amplitudes
from osr_screen_tcode.output_curve import OutputCurveFilter
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings
from osr_screen_tcode.config import RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE
from test_visual_pipeline import FakePose


class FallbackTests(unittest.TestCase):
    def test_all_axes_still_or_missing_never_start_the_fallback_wave(self):
        for missing in (False, True):
            engine = PoseL0Fallback()
            for i in range(301):
                rotations = {} if missing else {a: .5 for a in ('L1', 'L2', 'R0', 'R1', 'R2')}
                self.assertIsNone(engine.update(None if missing else .5, rotations, i/60))
            self.assertEqual(engine.source, 'idle')

    def test_losing_all_axis_activity_freezes_wave_and_resumes_from_held_position(self):
        engine = PoseL0Fallback()
        for i in range(151):
            engine.update(.5, {'R0': .5+.08*math.sin(i/60*6)}, i/60)
        self.assertEqual(engine.source, 'wave')
        held = engine.output
        for i in range(151, 211):
            self.assertEqual(engine.update(None, {}, i/60), held)
            self.assertEqual(engine.source, 'idle')
        previous = held
        resumed = False
        for i in range(211, 241):
            value = engine.update(.5, {'R0': .5+.08*math.sin(i/60*6)}, i/60)
            if engine.source == 'wave' and not resumed:
                self.assertAlmostEqual(value, previous)
                resumed = True
            previous = value
        self.assertTrue(resumed)

    def test_endpoint_recovery_requires_clear_upward_hips_and_rebases_once(self):
        for raw, end in ((.65, 1.), (.35, 0.)):
            recovery = PoseL0Recovery()
            for i in range(181):
                value = recovery.update(raw+math.sin(i)*.001, i/60, .6+math.sin(i)*.003)
            self.assertEqual(recovery.count, 0)
            self.assertEqual(value, end)
            # Downward motion does not rebase either end.
            for i in range(181, 241):
                recovery.update(raw, i/60, .6+(i-180)*.001)
            self.assertEqual(recovery.count, 0)
            values = []
            for i in range(241, 301):
                values.append(recovery.update(raw, i/60, .66-min(.06, (i-240)*.002)))
            self.assertEqual(recovery.count, 1)
            self.assertAlmostEqual(values[-1], .5)
            self.assertLess(max(abs(b-a) for a, b in zip(values, values[1:])), .04)
            self.assertAlmostEqual(recovery.update(raw+.01, 301/60, .6), .6)

    def test_missing_hips_or_single_bad_point_never_trigger_recovery(self):
        recovery = PoseL0Recovery()
        for i in range(301):
            hip = .2 if i == 180 else .6 if i < 200 else None
            recovery.update(.65, i/60, hip)
        self.assertEqual(recovery.count, 0)
        self.assertEqual(recovery.value, 1)
        # A reacquired line starts a new reference, not a fabricated rise.
        for i in range(301, 361):
            recovery.update(.65, i/60, .3)
        self.assertEqual(recovery.count, 0)

    def test_each_rotation_center_and_both_ends_map_to_requested_l0(self):
        for value, expected in ((0, 2/3), (.25, .5), (.5, 1/3), (.75, .5), (1, 2/3)):
            self.assertEqual(rotation_l0(value), expected)

    def test_moving_l0_remains_primary_and_does_not_change_raw_input(self):
        engine = PoseL0Fallback()
        for i in range(241):
            t = i/60
            rotations = {'R1': .5+.2*math.sin(t*6), 'R2': .9}
            self.assertIsNone(engine.update(.5+.02*math.sin(t*5), rotations, t))

    def test_small_moving_l0_uses_larger_rotation_and_releases_on_l0_growth(self):
        for axis in ('R1', 'R2'):
            engine = PoseL0Fallback()
            for i in range(181):
                t = i/60
                value = engine.update(.5+.003*math.sin(t*6), {axis: .5+.2*math.sin(t*6)}, t)
            self.assertEqual(engine.source, axis)
            self.assertIsNotNone(value)
            for i in range(181, 301):
                t = i/60
                engine.update(.5+.02*math.sin(t*6), {axis: .5+.2*math.sin(t*6)}, t)
            self.assertEqual(engine.source, 'detected')
            self.assertIsNone(engine.generated)

    def test_small_l0_alone_and_isolated_rotation_noise_do_not_trigger_takeover(self):
        engine = PoseL0Fallback()
        for i in range(301):
            t = i/60
            rotations = {'R1': 1 if i % 60 == 15 else .5}
            self.assertIsNone(engine.update(.5+.004*math.sin(t*6), rotations, t))

    def test_r1_priority_then_r2_and_each_uses_its_own_current_position(self):
        engine = PoseL0Fallback()
        for i in range(121):
            t = i/60
            rotations = {'R1': .5+.2*math.sin(t*6), 'R2': .5+.2*math.cos(t*6)}
            value = engine.update(.5, rotations, t)
        self.assertEqual(engine.source, 'R1')
        self.assertAlmostEqual(value, rotation_l0(rtm_rotation_amplitudes(rotations)['R1']))
        for i in range(121, 181):
            t = i/60
            rotations = {'R1': .8, 'R2': .5+.2*math.cos(t*6)}
            value = engine.update(.5, rotations, t)
        self.assertEqual(engine.source, 'R2')
        self.assertAlmostEqual(value, rotation_l0(rtm_rotation_amplitudes(rotations)['R2']))

    def test_other_axis_motion_allows_exact_one_second_quarter_half_cosine(self):
        engine = PoseL0Fallback()
        samples = {}
        for i in range(366):
            samples[i] = engine.update(None, {'R0': .5+.08*math.sin(i/100*6)}, i/100)
            if i < 65:
                self.assertIsNone(samples[i])
        self.assertEqual(engine.source, 'wave')
        for i in (165, 265, 365):
            self.assertAlmostEqual(samples[i], .5)
        for i in (115, 215, 315):
            self.assertAlmostEqual(samples[i], .25)
        self.assertAlmostEqual(samples[190], .375)
        self.assertTrue(all(.25 <= v <= .5 for i, v in samples.items() if i >= 85))

    def test_wave_continues_from_current_phase_instead_of_jumping_to_peak(self):
        for value in (.25, .31, .43, .5):
            engine = PoseL0Fallback()
            raw = .5+(value-.5)/10
            for i in range(65):
                engine.update(None, {'R0': .5+.08*math.sin(i/100*6)}, i/100, held_l0=raw)
            previous = engine.output
            self.assertAlmostEqual(engine.update(None, {'R0': .5+.08*math.sin(.65*6)}, .65, held_l0=raw), previous)
            phase = engine.wave_phase
            for i in range(66, 166):
                actual = engine.update(None, {'R0': .5+.08*math.sin(i/100*6)}, i/100, held_l0=raw)
                expected = .375+.125*math.cos(2*math.pi*(i/100-.65)+phase)
                self.assertAlmostEqual(actual, expected)
            self.assertAlmostEqual(actual, previous)

    def test_wave_from_outside_range_enters_smoothly_before_starting_cycle(self):
        for value, endpoint in ((0., .25), (.8, .5)):
            engine = PoseL0Fallback()
            raw = .5+(value-.5)/10
            for i in range(65):
                engine.update(None, {'R0': .5+.08*math.sin(i/100*6)}, i/100, held_l0=raw)
            values = [engine.update(None, {'R0': .5+.08*math.sin(i/100*6)}, i/100, held_l0=raw) for i in range(65, 101)]
            self.assertAlmostEqual(values[0], value)
            self.assertAlmostEqual(values[-1], endpoint)
            self.assertTrue(all(min(value, endpoint)-1e-9 <= v <= max(value, endpoint)+1e-9 for v in values))
            self.assertLess(max(abs(b-a) for a,b in zip(values, values[1:])), .014)
            for i in range(101, 201):
                engine.update(None, {'R0': .5+.08*math.sin(i/100*6)}, i/100, held_l0=raw)
            self.assertAlmostEqual(engine.output, endpoint)

    def test_tiny_l0_noise_does_not_prevent_generation_and_real_motion_returns_smoothly(self):
        engine = PoseL0Fallback()
        for i in range(121):
            t = i/60
            engine.update(.5+(-1)**i*.0003, {'R0': .5+.08*math.sin(t*6)}, t)
        self.assertEqual(engine.source, 'wave')
        outputs = [engine.output]
        for i in range(121, 151):
            t = i/60
            engine.update(.5+(i-120)*.001, {}, t, held_l0=.5+(i-120)*.001)
            outputs.append(engine.output)
        self.assertEqual(engine.source, 'detected')
        self.assertIsNone(engine.generated)
        self.assertLess(max(abs(b-a) for a, b in zip(outputs, outputs[1:])), .06)

    def test_duplicate_and_pause_do_not_advance_or_reuse_stale_generation(self):
        engine = PoseL0Fallback()
        for i in range(61):
            engine.update(None, {'R0': .5+.08*math.sin(i/30*6)}, i/30)
        previous = (engine.generated, engine.wave_origin)
        for stamp in (2, 1, float('nan')):
            self.assertEqual(engine.update(.9, {'R1': 1}, stamp), previous[0])
            self.assertEqual(engine.wave_origin, previous[1])
        self.assertIsNone(engine.update(None, {}, 3))
        self.assertEqual(engine.source, 'waiting')

    def test_curve_bypass_retains_wave_amplitude_and_seeds_return_state(self):
        curve = OutputCurveFilter()
        for i in range(121):
            value = .375+.125*math.cos(2*math.pi*i/60)
            result = curve.process({'L0': value, 'R1': .7}, timestamp=i/60, passthrough=('L0',))
            self.assertEqual(result['L0'], value)
        result = curve.process({'L0': .5, 'R1': .7}, timestamp=121/60)
        self.assertEqual(result['L0'], .5)


class PipelineFallbackTests(unittest.TestCase):
    def engine(self, mode='L0 Only', enabled=True):
        engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, output_mode=mode,
                               visual_settings=VisualSettings(pose_auto_l0=enabled))
        engine.backend = FakePose()
        return engine

    def test_single_axis_also_observes_rotations_without_emitting_other_axes(self):
        engine = self.engine()
        self.assertEqual(engine.geometry.output_mode, 'Six Axis')
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(121):
            engine.backend.points[5:7, 0] = [100+15*np.sin(i/60*5), 150+15*np.sin(i/60*5)]
            result = engine.process(frame, i/60)
            self.assertEqual(set(result.positions), {'L0'})
        self.assertEqual(engine.pose_fallback.source, 'R1')
        self.assertIsNotNone(engine.generated_l0)

    def test_all_missing_pose_does_not_start_wave_or_fabricate_confidence(self):
        engine = self.engine()
        engine.backend.missing = True
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(61):
            result = engine.process(frame, i/30)
        self.assertEqual(result.confidence, 0)
        self.assertEqual(result.positions, {'L0': .5})
        self.assertIsNone(engine.generated_l0)
        self.assertEqual(engine.visual_frame.l0_source, 'idle')

    def test_disabling_and_reenabling_preserve_pose_analysis_reference(self):
        engine = self.engine()
        engine.geometry._positions_from_rtm_pose_2d = lambda sample, shape, timestamp: ({'R0': .5+.08*math.sin(timestamp*6), 'R1': .5, 'R2': .5}, None)
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(61):
            engine.process(frame, i/30)
        self.assertIsNotNone(engine.generated_l0)
        observations, geometry = engine.observations, engine.geometry
        settings = replace(engine.settings, pose_auto_l0=False)
        engine.configure(settings)
        self.assertIs(engine.observations, observations)
        self.assertIs(engine.geometry, geometry)
        self.assertIsNone(engine.generated_l0)
        result = engine.process(frame, 61/30)
        self.assertEqual(engine.visual_frame.l0_source, '')
        self.assertEqual(result.positions['L0'], .5)
        engine.configure(replace(settings, pose_auto_l0=True))
        self.assertIs(engine.observations, observations)
        engine.process(frame, 62/30)
        self.assertIsNone(engine.generated_l0)

    def test_hybrid_and_cycle_never_activate_pose_fallback(self):
        frame = np.zeros((240, 320, 3), np.uint8)
        for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            engine = make_analyzer(tracker_mode=mode, visual_settings=VisualSettings(pose_auto_l0=True))
            for i in range(31):
                result = engine.process(frame, i/30)
                self.assertIsNone(engine.generated_l0)
                self.assertEqual(result.positions['L0'], .5)


if __name__ == '__main__':
    unittest.main()
