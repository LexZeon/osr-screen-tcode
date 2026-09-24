import unittest

import numpy as np

from osr_screen_tcode.secondary_motion import SecondaryMotionFilter


class SecondaryMotionTests(unittest.TestCase):
    def test_small_high_frequency_noise_and_brief_spikes_are_ignored(self):
        engine = SecondaryMotionFilter()
        for i in range(240):
            value = .5 + .02 * np.sin(i * 2)
            if i in (50, 51, 120):
                value = .8
            result = engine.update({a: value for a in engine.AXES}, i/60)
            self.assertEqual(result, dict.fromkeys(engine.AXES, .5))

    def test_clear_motion_and_confirmed_reversal_produce_smooth_script_positions(self):
        engine = SecondaryMotionFilter()
        values = []
        for i in range(120):
            values.append(engine.update({"L1": .8}, i/60)["L1"])
        self.assertGreater(values[-1], .79)
        self.assertLessEqual(max(np.abs(np.diff(values))), .65/60 + 1e-9)
        # An isolated opposite excursion does not reverse the target.
        engine.update({"L1": .3}, 120/60)
        engine.update({"L1": .8}, 121/60)
        self.assertEqual(engine.direction["L1"], 1)
        for i in range(122, 242):
            values.append(engine.update({"L1": .3}, i/60)["L1"])
        self.assertEqual(engine.direction["L1"], -1)
        self.assertLess(values[-1], .31)
        self.assertLessEqual(max(np.abs(np.diff(values))), .65/60 + 1e-9)

    def test_frame_rate_consistency_axis_independence_and_no_l0(self):
        ends = []
        for fps in (30, 60, 120):
            engine = SecondaryMotionFilter()
            for i in range(fps):
                result = engine.update({"L0": 1, "R0": .75}, i/fps)
            self.assertNotIn("L0", result)
            self.assertEqual(result["R1"], .5)
            ends.append(result["R0"])
        self.assertLess(max(ends)-min(ends), .005)

    def test_duplicate_gap_and_invalid_samples_hold_filtered_output(self):
        engine = SecondaryMotionFilter()
        for i in range(30):
            result = engine.update({"L2": .7}, i/60)
        self.assertEqual(engine.update({"L2": 0}, 29/60), result)
        self.assertEqual(engine.update({"L2": float("nan")}, 1), result)
        engine.update({"L2": .2}, 2)
        self.assertEqual(engine.direction["L2"], 0)
        self.assertEqual(engine.output, result)
