import unittest
from unittest.mock import patch

from osr_screen_tcode.endpoint_slowdown import approach_time_factor, ScriptEndpointTiming
from osr_screen_tcode.tcode import MultiAxisSafeOutput
from osr_screen_tcode.recorder import MultiAxisFunscriptRecorder


class EndpointSlowdownTests(unittest.TestCase):
    def test_repeating_target_does_not_cancel_an_ongoing_slow_approach(self):
        output = MultiAxisSafeOutput(["L0"], max_step=9999, endpoint_slowdown=True,
                                     enable_endpoint_guard=False, enable_extreme_reset=False)
        with patch("osr_screen_tcode.tcode.time.perf_counter", return_value=10):
            output.next_command({"L0": .99}, 1)
            first = output.next_command({"L0": 1}, 1)
        with patch("osr_screen_tcode.tcode.time.perf_counter", return_value=10.01):
            repeated = output.next_command({"L0": 1}, 1)
        self.assertEqual(first.values, repeated.values)
        self.assertGreaterEqual(repeated.interval_ms, first.interval_ms-10)

    def test_middle_and_movement_away_from_limit_keep_original_time(self):
        for current, target in ((.5, .9), (.5, .1), (.98, .91), (.02, .09)):
            self.assertAlmostEqual(approach_time_factor(current, target), 1)

    def test_approach_time_is_symmetric_and_zone_controls_when_braking_starts(self):
        for target in (.91, .95, .99, 1.):
            factor = approach_time_factor(.9, target)
            self.assertGreater(factor, 1)
            self.assertAlmostEqual(approach_time_factor(.1, 1-target), factor)
        self.assertGreater(approach_time_factor(.5, 1, .2), approach_time_factor(.5, 1, .1))
        self.assertAlmostEqual(approach_time_factor(.8, .9, .1), 1)
        self.assertGreater(approach_time_factor(.8, .9, .2), 1)

    def test_script_coordinates_identical_only_arrival_times_change(self):
        normal, slow = MultiAxisFunscriptRecorder(), MultiAxisFunscriptRecorder()
        normal.start()
        slow.start()
        source = [.5, .9, .95, 1., .95, .9, .5, .1, .05, 0]
        for i, value in enumerate(source):
            normal.add_at({"L0": value}, i*100)
            slow.add_at({"L0": value}, i*100, True, .1)
        a, b = normal._actions["L0"], slow._actions["L0"]
        self.assertEqual([p["pos"] for p in a], [p["pos"] for p in b])
        self.assertEqual(b[1]["at"], a[1]["at"])
        self.assertGreater(b[3]["at"], a[3]["at"])
        self.assertEqual(b[4]["at"]-b[3]["at"], 100)  # Away from upper limit.
        slow.start()
        slow.add_at({"L0": .5}, 0, True)
        self.assertEqual(slow._actions["L0"], [{"at": 0, "pos": 50}])

    def test_disabled_timing_and_toggle_never_move_time_backwards(self):
        timer = ScriptEndpointTiming()
        self.assertEqual(timer.timestamp({"L0": .9}, 0), 0)
        slow = timer.timestamp({"L0": 1}, 100)
        self.assertGreater(slow, 100)
        self.assertEqual(timer.timestamp({"L0": .9}, 200, False), slow+100)

    def test_tcode_preserves_targets_after_gains_inversion_coupling_and_limits(self):
        options = dict(axes=["L0", "L1"], axis_limits={"L0": (1000, 9000), "L1": (3000, 7000)},
            axis_position_scales={"L0": 2, "L1": .5}, invert_l0=True, max_step=400,
            couple_l0_translation=True, enable_endpoint_guard=False, enable_extreme_reset=False)
        normal = MultiAxisSafeOutput(**options)
        slow = MultiAxisSafeOutput(**options, endpoint_slowdown=True)
        delays = []
        for i in range(30):
            positions = {"L0": .75 if i < 15 else .25, "L1": .6}
            a = normal.next_command(positions, 1)
            b = slow.next_command(positions, 1)
            self.assertEqual(a.values, b.values)
            self.assertGreaterEqual(b.interval_ms, a.interval_ms)
            delays.append(b.interval_ms)
        self.assertGreater(max(delays), normal.interval_ms)
        self.assertEqual(slow.center_command(500).interval_ms, 500)
        self.assertEqual(slow.center_command().values["L0"], 5000)
