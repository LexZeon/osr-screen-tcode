import unittest

import numpy as np

from stabilizer import Options, Stabilizer


class StabilizerTests(unittest.TestCase):
    def setUp(self):
        self.gray = np.zeros((400, 400), np.uint8)
        self.points = np.array([(100 + (i % 2) * 50, 40 + i * 15) for i in range(17)], np.float32)
        self.scores = np.ones(17)

    def test_duplicate_and_old_timestamps(self):
        s = Stabilizer()
        first, _ = s.update(self.gray, self.points, self.scores, 1)
        for timestamp in (1, 0.5):
            value, _ = s.update(self.gray, self.points + 80, self.scores, timestamp)
            np.testing.assert_equal(first, value)

    def test_reject_jump(self):
        s = Stabilizer(Options(True, False, False, False))
        s.update(self.gray, self.points, self.scores, 1)
        changed = self.points.copy()
        changed[9] += 150
        result, rejected = s.update(self.gray, changed, self.scores, 1.016)
        self.assertTrue(rejected[9])
        np.testing.assert_equal(result[9], self.points[9])

    def test_expiry_and_reacquire(self):
        s = Stabilizer()
        s.update(self.gray, self.points, self.scores, 1)
        value, _ = s.update(self.gray, None, None, 1.3)
        self.assertTrue(np.isnan(value).all())
        value, _ = s.update(self.gray, self.points, self.scores, 1.4)
        self.assertTrue(np.isfinite(value).all())

    def test_disabled_passthrough(self):
        s = Stabilizer(Options(False, False, False, False))
        s.update(self.gray, self.points, self.scores, 1)
        value, _ = s.update(self.gray, self.points + 4, self.scores, 1.02)
        np.testing.assert_equal(value, self.points + 4)

    def test_nonfinite_hidden(self):
        s = Stabilizer()
        self.points[0] = np.nan
        value, _ = s.update(self.gray, self.points, self.scores, 1)
        self.assertTrue(np.isnan(value[0]).all())

    def test_smoothing_reduces_stationary_noise(self):
        s = Stabilizer(Options(False, False, True, True))
        rng = np.random.default_rng(1)
        raw, filtered = [], []
        for i in range(120):
            noisy = self.points + rng.normal(0, 2, self.points.shape).astype(np.float32)
            value, _ = s.update(self.gray, noisy, self.scores, 1 + i / 60)
            if i > 20:
                raw.append(noisy[5, 0])
                filtered.append(value[5, 0])
        self.assertLess(np.std(filtered), np.std(raw))

    def test_micro_smoothing_follows_large_motion_exactly(self):
        s = Stabilizer(Options(False, False, False, True))
        s.update(self.gray, self.points, self.scores, 1)
        value, _ = s.update(self.gray, self.points + 12, self.scores, 1.016)
        np.testing.assert_equal(value, self.points + 12)

    def test_micro_smoothing_reduces_small_alternating_noise(self):
        s = Stabilizer(Options(False, False, False, True))
        samples = []
        for i in range(60):
            noisy = self.points.copy()
            noisy[:, 0] += (-1) ** i
            value, _ = s.update(self.gray, noisy, self.scores, 1 + i / 60)
            if i > 10:
                samples.append(value[5, 0])
        self.assertLess(np.std(samples), 0.6)

    def test_repeated_confident_point_reacquires(self):
        s = Stabilizer(Options(True, False, True, True))
        s.update(self.gray, self.points, self.scores, 1)
        moved = self.points.copy()
        moved[9] += 100
        s.update(self.gray, moved, self.scores, 1.016)
        value, rejected = s.update(self.gray, moved, self.scores, 1.032)
        self.assertFalse(rejected[9])
        np.testing.assert_allclose(value[9], moved[9], atol=0.01)

    def test_flow_anchors_are_observations_not_smoothed_points(self):
        s = Stabilizer(Options(False, True, False, True))
        s.update(self.gray, self.points, self.scores, 1)
        moved = self.points + 1
        s.update(self.gray, moved, self.scores, 1.016)
        np.testing.assert_equal(s.flow_points, moved)

    def test_scene_cut_restarts_at_current_pose(self):
        s = Stabilizer()
        s.update(self.gray, self.points, self.scores, 1)
        moved = self.points + [70, 20]
        value, _ = s.update(np.full_like(self.gray, 220), moved, self.scores, 1.016)
        self.assertEqual(s.reset_reason, "scene")
        np.testing.assert_allclose(value, moved, atol=0.001)

    def test_scene_cut_without_pose_has_no_ghost(self):
        s = Stabilizer()
        s.update(self.gray, self.points, self.scores, 1)
        value, _ = s.update(np.full_like(self.gray, 220), None, None, 1.016)
        self.assertTrue(np.isnan(value).all())

    def test_same_background_pose_relocation_restarts(self):
        s = Stabilizer()
        s.update(self.gray, self.points, self.scores, 1)
        moved = self.points + [80, 20]
        value, _ = s.update(self.gray, moved, self.scores, 1.016)
        self.assertEqual(s.reset_reason, "pose")
        np.testing.assert_allclose(value, moved, atol=0.001)

    def test_frame_gap_does_not_reuse_velocity(self):
        s = Stabilizer()
        s.update(self.gray, self.points, self.scores, 1)
        value, _ = s.update(self.gray, self.points + 3, self.scores, 1.21)
        self.assertEqual(s.reset_reason, "gap")
        np.testing.assert_allclose(value, self.points + 3, atol=0.001)

    def test_continuous_small_motion_does_not_reset(self):
        s = Stabilizer()
        for i in range(20):
            s.update(self.gray, self.points + i, self.scores, 1 + i / 60)
            self.assertEqual(s.reset_reason, "")

    def test_stretched_stale_endpoint_is_hidden(self):
        s = Stabilizer(Options(True, False, False, False))
        s.update(self.gray, self.points, self.scores, 1)
        s.xy[9] = [390, 390]
        scores = self.scores.copy()
        scores[9] = 0
        value, _ = s.update(self.gray, self.points, scores, 1.016)
        self.assertTrue(np.isnan(value[9]).all())


if __name__ == "__main__":
    unittest.main()
