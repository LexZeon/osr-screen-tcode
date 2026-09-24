"""Output-only dropout estimates; no UI, camera, device or inferred training."""
import math
from types import SimpleNamespace
import unittest

import numpy as np

from osr_screen_tcode.fused_l0 import FusedL0
from osr_screen_tcode.motion_reference import MotionReference
from osr_screen_tcode.motion_rhythm import MotionRhythm


class ContinuationTests(unittest.TestCase):
    def trained(self, period=1., end=6.):
        rhythm = MotionRhythm()
        for index in range(round(end*30)+1):
            stamp = index/30
            rhythm.observe(stamp, .5+.35*math.cos(stamp*2*math.pi/period))
        self.assertIsNotNone(rhythm.model)
        return rhythm

    def test_slow_periods_use_full_history_and_still_obey_two_seconds(self):
        for period in (1., 2.5, 6.):
            with self.subTest(period=period):
                rhythm = self.trained(period, 20.)
                self.assertAlmostEqual(rhythm.model[1], period, delta=.08)
                held = .5+.35*math.cos(20*2*math.pi/period)
                values = [rhythm.predict(20+i/60, held) for i in range(151)]
                self.assertGreater(np.ptp(values[:90]), .02)
                self.assertEqual(values[120:], [values[120]]*31)
                self.assertEqual(rhythm.kind, 'rhythm')
                self.assertEqual(rhythm.state, 'held')

    def test_velocity_bridge_brakes_without_reversal_or_long_running_drift(self):
        for fps in (15, 30, 120):
            for velocity in (-.4, .4, 1.5):
                with self.subTest(fps=fps, velocity=velocity):
                    rhythm = MotionRhythm()
                    start = .8 if velocity < 0 else .1
                    for index in range(round(fps*.4)+1):
                        stamp = index/fps
                        rhythm.observe(stamp, start+velocity*stamp, periodic=False)
                    held = start+velocity*stamp
                    samples = [rhythm.predict(stamp+i/120, held) for i in range(121)]
                    self.assertIsNone(rhythm.model)
                    self.assertEqual(rhythm.kind, 'velocity')
                    self.assertTrue(np.all(np.diff(samples)*velocity >= -1e-12))
                    self.assertLessEqual(abs(samples[-1]-held), rhythm.BRIDGE_TRAVEL+1e-9)
                    self.assertEqual(samples[36:], [samples[36]]*len(samples[36:]))

    def test_noise_still_startup_and_invalid_samples_do_not_create_motion(self):
        rng = np.random.default_rng(7)
        for mode in ('noise', 'still'):
            rhythm = MotionRhythm()
            for index in range(181):
                value = .5 if mode == 'still' else .5+rng.normal(0, .01)
                rhythm.observe(index/30, value)
            self.assertIsNone(rhythm.predict(6.03, .5))
        rhythm = MotionRhythm()
        for stamp, value in ((0., .5), (0., .6), (-1., .7), (math.nan, .5), (.1, math.nan), (.1, 2.)):
            rhythm.observe(stamp, value)
        self.assertEqual(list(rhythm.samples), [(0., .5)])
        self.assertIsNone(rhythm.predict(.03, .5))
        self.assertIsNone(MotionRhythm().predict(0., .5))

    def test_single_frame_reappearances_cannot_renew_dropout_deadline(self):
        rhythm = self.trained()
        held = rhythm.predict(6., .85)
        values = []
        for index in range(1, 101):
            stamp = 6+index/30
            if index % 5 == 0:
                rhythm.observe(stamp, .5+.35*math.cos(stamp*2*math.pi))
            else:
                held = rhythm.predict(stamp, held)
                values.append((stamp, held))
                self.assertEqual(rhythm.loss_at, 6.)
        terminal = [value for stamp, value in values if stamp >= 8.]
        np.testing.assert_allclose(terminal, terminal[0], atol=1e-12)

    def test_only_sustained_recovery_rearms_the_next_episode(self):
        rhythm = self.trained()
        rhythm.predict(6.03, .85)
        for stamp in (6.1, 6.2, 6.299):
            rhythm.observe(stamp, .5+.35*math.cos(stamp*2*math.pi))
        self.assertEqual(rhythm.loss_at, 6.)
        rhythm.observe(6.3, .5+.35*math.cos(6.3*2*math.pi))
        self.assertIsNone(rhythm.loss_at)
        rhythm.predict(6.33, .5)
        self.assertEqual(rhythm.loss_at, 6.3)

    def test_single_frame_reentry_reanchors_from_held_without_renewing_deadline(self):
        rhythm = self.trained()
        rhythm.predict(6.03, .85)
        for stamp, held in ((6.3, .42), (6.7, .65), (7.1, .31), (7.6, .7), (8.3, .4)):
            rhythm.observe(stamp, .5+.35*math.cos(stamp*2*math.pi))
            self.assertAlmostEqual(rhythm.predict(stamp+.03, held), held)
            self.assertEqual(rhythm.loss_at, 6.)
            if stamp >= 8.:
                self.assertEqual(rhythm.predict(stamp+.06, held), held)


class WeakFusionTests(unittest.TestCase):
    def setup_fusion(self, periodic=False):
        dominant = SimpleNamespace(basis=np.eye(3), stroke_span=12. if periodic else None,
                                  stroke_gain=1., stroke_evidence=SimpleNamespace(legs=[]))
        point = SimpleNamespace(state='unresolved', step=0., point=None)
        fusion = FusedL0()
        previous = .5
        count = 181 if periodic else 10
        for index in range(count):
            stamp = index/30
            value = .5+.35*math.cos(stamp*2*math.pi) if periodic else .4+index*.01
            reference = MotionReference('v2', 'ready', (30, 30, 100, 100),
                                        step=(0., (value-previous)*12 if periodic else 1., 0.))
            center = ((65., 65.), value) if periodic else None
            fusion.update(dominant, reference, point, None, center, stamp, (240, 320), value)
            previous = value
        return fusion, dominant, point, stamp

    @staticmethod
    def estimate(step=(0., .1, 0.), *, stationary=False):
        return SimpleNamespace(state='weak', step=step, stationary=stationary,
                               elapsed=0., origin=(65., 65.), box=(30, 30, 100, 100))

    def test_ordinary_motion_gets_only_a_short_velocity_bridge(self):
        fusion, dominant, point, stamp = self.setup_fusion()
        held = fusion.output
        missing = MotionReference('v2', 'holding', reason='tracking')
        values = [fusion.update(dominant, missing, point, None, None, stamp+i/60,
                                (240, 320), held) for i in range(1, 61)]
        self.assertGreater(values[0], held)
        self.assertEqual(fusion.continuation_kind, 'velocity')
        self.assertIsNone(fusion.rhythm.model)
        self.assertEqual(values[18:], [values[18]]*len(values[18:]))
        self.assertLess(values[-1]-held, .06)

    def test_weak_steps_use_previous_real_basis_and_actual_output_anchor(self):
        fusion, dominant, point, stamp = self.setup_fusion()
        fusion.applied = .25
        dominant.basis = np.roll(np.eye(3), 1, axis=0)  # upstream missing-state reset
        held = fusion.output
        before = list(fusion.rhythm.velocity_samples)
        missing = MotionReference('v2', 'holding', reason='tracking')
        output = fusion.update(dominant, missing, point, None, None, stamp+1/30,
                               (240, 320), held, estimate=self.estimate((0., 1., 0.)))
        self.assertAlmostEqual(output, .26)
        self.assertTrue(fusion.predicting)
        self.assertEqual(fusion.continuation_kind, 'weak')
        self.assertEqual(list(fusion.rhythm.velocity_samples), before)

    def test_weak_steps_and_isolated_ready_frames_share_one_deadline(self):
        fusion, dominant, point, stamp = self.setup_fusion()
        held = fusion.output
        missing = MotionReference('v2', 'missing', reason='tracking')
        weak_values = []
        for index in range(1, 101):
            at = stamp+index/30
            if index % 5 == 0:
                ready = MotionReference('v2', 'ready', (30, 30, 100, 100), step=(0., .1, 0.))
                fusion.update(dominant, ready, point, None, None, at, (240, 320), fusion.output)
            else:
                before = fusion.output
                value = fusion.update(dominant, missing, point, None, None, at, (240, 320), held,
                                      estimate=self.estimate())
                self.assertEqual(fusion.rhythm.loss_at, stamp)
                if at >= stamp+2.:
                    self.assertEqual(value, before)
                weak_values.append(value)
        self.assertGreater(np.ptp(weak_values[:30]), .01)

    def test_stationary_cut_and_geometry_change_remove_estimation(self):
        for cause in ('stationary', 'jump', 'resize'):
            with self.subTest(cause=cause):
                fusion, dominant, point, stamp = self.setup_fusion(periodic=True)
                missing = MotionReference('v2', 'holding', reason='tracking')
                fusion.update(dominant, missing, point, None, None, stamp+1/30, (240, 320), fusion.output)
                held = fusion.output
                reference = MotionReference('v2', 'missing', reason='jump' if cause == 'jump' else 'tracking')
                shape = (480, 640) if cause == 'resize' else (240, 320)
                estimate = self.estimate(stationary=cause == 'stationary')
                value = fusion.update(dominant, reference, point, None, None, stamp+2/30, shape, held,
                                      estimate=estimate)
                self.assertEqual(value, held)
                self.assertFalse(fusion.predicting)
                self.assertIsNone(fusion.rhythm.model)
                value = fusion.update(dominant, reference, point, None, None, stamp+3/30, shape, held,
                                      estimate=self.estimate())
                self.assertEqual(value, held)

    def test_switching_from_weak_to_rhythm_does_not_jump_or_restart_budget(self):
        fusion, dominant, point, stamp = self.setup_fusion(periodic=True)
        missing = MotionReference('v2', 'holding', reason='tracking')
        first = fusion.update(dominant, missing, point, None, None, stamp+1/30, (240, 320), fusion.output,
                              estimate=self.estimate((0., .2, 0.)))
        second = fusion.update(dominant, missing, point, None, None, stamp+2/30, (240, 320), first)
        self.assertAlmostEqual(second, first)
        self.assertEqual(fusion.continuation_kind, 'rhythm')
        self.assertEqual(fusion.rhythm.loss_at, stamp)

    def test_confirmed_pause_then_one_real_frame_cannot_revive_old_rhythm(self):
        fusion, dominant, point, stamp = self.setup_fusion(periodic=True)
        paused = MotionReference('v2', 'tracking', (30, 30, 100, 100), step=(0., 0., 0.))
        held = fusion.output
        for index in range(1, 10):
            fusion.update(dominant, paused, point, None, None, stamp+index/30,
                          (240, 320), held)
        self.assertIsNone(fusion.rhythm.model)
        ready = MotionReference('v2', 'ready', (30, 30, 100, 100), step=(0., .2, 0.))
        fusion.update(dominant, ready, point, None, ((65., 65.), .7), stamp+10/30,
                      (240, 320), .7)
        held = fusion.output
        missing = MotionReference('v2', 'holding', reason='tracking')
        for index in range(11, 80):
            value = fusion.update(dominant, missing, point, None, None, stamp+index/30,
                                  (240, 320), held)
            self.assertEqual(value, held)
            self.assertFalse(fusion.predicting)
            self.assertIsNone(fusion.rhythm.model)


if __name__ == '__main__':
    unittest.main()
