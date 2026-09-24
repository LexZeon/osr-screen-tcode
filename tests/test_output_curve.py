import math
import unittest

import numpy as np

from osr_screen_tcode.output_curve import OutputCurveFilter
from osr_screen_tcode.pose_output import rtm_motion_amplitudes, rtm_l0_amplitude, rtm_rotation_amplitudes, l0_rotation_gain
from osr_screen_tcode.tcode import MultiAxisSafeOutput


class CurveTests(unittest.TestCase):
    def test_jitter_reduction_at_different_sample_rates(self):
        for fps in (30, 60, 120):
            curve = OutputCurveFilter()
            raw = [0.5 + (0.012 if i % 2 else -0.012) for i in range(fps * 3)]
            fitted = [curve.process({"L0": x}, timestamp=i / fps)["L0"] for i, x in enumerate(raw)]
            self.assertLess(np.std(fitted[fps:]), np.std(raw[fps:]) * 0.4)

    def test_fast_step_is_bounded_monotonic_and_follows_quickly(self):
        curve = OutputCurveFilter()
        curve.process({"L0": 0.5}, timestamp=0)
        values = [curve.process({"L0": 0.9}, timestamp=i / 60)["L0"] for i in range(1, 13)]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0.5 <= value <= 0.9 for value in values))
        self.assertGreater(values[5], 0.86)

    def test_disabled_is_passthrough_and_toggle_does_not_restore_old_history(self):
        curve = OutputCurveFilter()
        curve.process({"L0": 0.1}, timestamp=0)
        values = {"L0": 0.9, "R1": 0.8}
        self.assertEqual(curve.process(values, enabled=False, timestamp=0.02), values)
        self.assertEqual(curve.process(values, enabled=True, timestamp=0.04), values)

    def test_repeated_timestamp_and_nonfinite_input_hold(self):
        curve = OutputCurveFilter()
        curve.process({"L0": 0.4}, timestamp=1)
        self.assertEqual(curve.process({"L0": 0.9}, timestamp=1)["L0"], 0.4)
        self.assertEqual(curve.process({"L0": math.nan}, timestamp=2)["L0"], 0.4)

    def test_all_axes_are_independent(self):
        curve = OutputCurveFilter()
        curve.process({"L0": 0.5, "R1": 0.5}, timestamp=0)
        result = curve.process({"L0": 1, "R1": 0.5}, timestamp=0.02)
        self.assertGreater(result["L0"], 0.5)
        self.assertEqual(result["R1"], 0.5)


class RtmAmplitudeTests(unittest.TestCase):
    def test_pose_base_gains_scale_deviation_and_preserve_raw_observations(self):
        raw = {'L0': .51, 'L1': .55, 'R0': .57, 'R1': .6, 'R2': .4}
        result = rtm_rotation_amplitudes(rtm_l0_amplitude(raw))
        self.assertAlmostEqual(result['L0'], .6)
        self.assertAlmostEqual(result['R1'], .65)
        self.assertAlmostEqual(result['R2'], .35)
        self.assertEqual(result['L1'], .55)
        self.assertAlmostEqual(result['R0'], .71)
        self.assertEqual(raw['L0'], .51)
        for value, expected in ((.4, 0), (.49, .4), (.5, .5), (.6, 1)):
            self.assertAlmostEqual(rtm_l0_amplitude({'L0': value})['L0'], expected)

    def test_l0_controls_translation_gain_and_pose_rotations_have_axis_base_gains(self):
        for l0, gain in ((0, 0.5), (1/3, 1), (0.5, 2.25), (2/3, 3.5), (1, 0.5)):
            raw = {"L0": l0, "L1": 0.55, "L2": 0.45, "R0": 0.57, "R1": 0.6, "R2": 0.4}
            result = rtm_motion_amplitudes(raw)
            self.assertEqual(result["L0"], l0)
            self.assertAlmostEqual(result['R0'], .71)
            self.assertAlmostEqual(result["L1"], 0.5 + 0.05 * gain)
            self.assertAlmostEqual(result["L2"], 0.5 - 0.05 * gain)
            self.assertAlmostEqual(result["R1"], .5+.15*l0_rotation_gain(l0))
            self.assertAlmostEqual(result["R2"], .5-.15*l0_rotation_gain(l0))
            self.assertEqual(raw["L1"], 0.55)

    def test_center_stays_center_and_values_cannot_exceed_range(self):
        for raw, expected in ((0, 0), (.4, .2), (.5, .5), (.6, .8), (1, 1)):
            self.assertAlmostEqual(rtm_rotation_amplitudes({'R0': raw})['R0'], expected)
        self.assertEqual(rtm_motion_amplitudes({"L0": 1, "L1": 0.5})["L1"], 0.5)
        result = rtm_motion_amplitudes({"L0": 0.5, "L1": 0.9, "L2": 0.1, "R1": 0.9, "R2": 0.1})
        self.assertEqual([result[key] for key in ("L1", "L2", "R1", "R2")], [1, 0, 1, 0])

    def test_gains_and_curve_still_obey_safety_step_limits_and_inversion(self):
        curve = OutputCurveFilter()
        output = MultiAxisSafeOutput(["L0", "L1", "L2", "R1", "R2"], min_value=3000, max_value=7000,
                                    max_step=80, axis_position_scales={"L1": 0, "L2": 0.5},
                                    axis_position_inverts={"R1": True}, enable_extreme_reset=False)
        last = dict(output._values)
        for i in range(30):
            raw = rtm_motion_amplitudes({"L0": 1, "L1": 1, "L2": 1, "R1": 1, "R2": 0})
            fitted = curve.process(raw, timestamp=i / 60)
            values = output.next_command(fitted, 1).values
            self.assertEqual(values["L1"], 5000)
            self.assertLessEqual(values["R1"], 5000)
            for axis, value in values.items():
                self.assertTrue(3000 <= value <= 7000)
                self.assertLessEqual(abs(value - last[axis]), 80)
            last = values
