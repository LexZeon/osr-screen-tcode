import unittest
from unittest.mock import patch

from osr_screen_tcode.command_cadence import CommandCadence
from osr_screen_tcode.tcode import MultiAxisSafeOutput


class CommandCadenceTests(unittest.TestCase):
    def test_slow_analysis_extends_arrival_time_without_changing_targets(self):
        fixed = MultiAxisSafeOutput(['L0'], max_step=9999, enable_endpoint_guard=False,
                                    enable_extreme_reset=False, interval_ms=24)
        timed = MultiAxisSafeOutput(['L0'], max_step=9999, enable_endpoint_guard=False,
                                    enable_extreme_reset=False, interval_ms=24, sync_timing=True)
        for i, value in enumerate((.5, .6, .4, .7, .3)):
            with patch('osr_screen_tcode.tcode.time.perf_counter', return_value=i*.066):
                a, b = fixed.next_command({'L0': value}, 1), timed.next_command({'L0': value}, 1)
            self.assertEqual(a.values, b.values)
            self.assertEqual(b.interval_ms, 24 if i == 0 else 66)

    def test_minimum_pause_and_isolated_hitch(self):
        cadence = CommandCadence()
        for now in (0, .02, .04, .06, .08):
            self.assertEqual(cadence.interval_ms(now, 24), 24)
        self.assertEqual(cadence.interval_ms(.28, 24), 24)
        self.assertEqual(cadence.interval_ms(1, 24), 24)
        self.assertEqual(cadence.interval_ms(1.1, 24), 100)

    def test_endpoint_timing_is_applied_after_cadence_and_center_resets_it(self):
        output = MultiAxisSafeOutput(['L0'], 0, 9999, max_step=9999, interval_ms=24,
            enable_endpoint_guard=False, enable_extreme_reset=False, sync_timing=True,
            endpoint_slowdown=True)
        with patch('osr_screen_tcode.tcode.time.perf_counter', return_value=0):
            output.next_command({'L0': .9}, 1)
        with patch('osr_screen_tcode.tcode.time.perf_counter', return_value=.05):
            command = output.next_command({'L0': 1}, 1)
        self.assertEqual(command.values['L0'], 9999)
        self.assertGreater(command.interval_ms, 50)
        self.assertEqual(output.center_command(600).interval_ms, 600)
        self.assertIsNone(output._cadence.previous)
