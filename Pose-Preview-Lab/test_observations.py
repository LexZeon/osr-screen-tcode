import unittest

import cv2
import numpy as np

from frame_motion import FrameMotion
from observations import ImageObservations


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.points = np.full((17, 2), np.nan, np.float32)
        self.points[[5, 6, 11, 12]] = [[150, 100], [250, 100], [150, 220], [250, 220]]
        self.scores = np.ones(17)
        self.rejected = np.zeros(17, bool)
        self.engine = ImageObservations()
        for i in range(12):
            self.update(self.points, i * 0.04)

    def update(self, points, timestamp):
        return self.engine.update(points, self.scores, self.rejected, (400, 400), timestamp)

    def test_position_and_scale(self):
        translated = self.update(self.points + [40, -20], 0.5)
        np.testing.assert_allclose(translated.values, [10, 5, 0], atol=0.001)
        scaled = self.update((self.points - [200, 160]) * 1.2 + [200, 160], 0.6)
        np.testing.assert_allclose(scaled.values, [0, 0, 20], atol=0.001)

    def test_missing_is_not_zero_or_predicted_measurement(self):
        self.scores[5] = 0.1
        value = self.update(self.points, 0.5)
        self.assertIsNone(value.values)
        self.assertEqual(value.state, "missing")

    def test_rejected_observation_not_measured(self):
        self.rejected[11] = True
        self.assertIsNone(self.update(self.points, 0.5).values)

    def test_long_loss_recalibrates(self):
        self.update(np.full_like(self.points, np.nan), 0.5)
        self.assertEqual(self.update(self.points, 1.2).state, "calibrating")

    def test_duplicate_does_not_change_values(self):
        first = self.update(self.points, 0.5)
        self.assertIs(first, self.update(self.points + 20, 0.5))


class FrameMotionTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(4)
        self.frame = cv2.GaussianBlur(rng.integers(0, 255, (320, 400), np.uint8), (3, 3), 0)

    def test_translation(self):
        for use_scale in (False, True):
            engine = FrameMotion(use_scale)
            engine.update(self.frame, 0)
            shifted = cv2.warpAffine(self.frame, np.float32([[1, 0, 4], [0, 1, -3]]), (400, 320))
            result, vectors = engine.update(shifted, 0.02)
            self.assertGreater(len(vectors), 8)
            np.testing.assert_allclose(result.values, [1, 0.9375, 0], atol=0.1)

    def test_scale_about_center(self):
        engine = FrameMotion(True)
        engine.update(self.frame, 0)
        changed = cv2.warpAffine(self.frame, cv2.getRotationMatrix2D((200, 160), 0, 1.03), (400, 320))
        result, _ = engine.update(changed, 0.02)
        np.testing.assert_allclose(result.values, [0, 0, 3], atol=0.2)

    def test_blank_is_missing(self):
        engine = FrameMotion(True)
        engine.update(np.zeros_like(self.frame), 0)
        result, _ = engine.update(np.zeros_like(self.frame), 0.02)
        self.assertEqual(result.state, "missing")

    def test_gap_resets_reference(self):
        engine = FrameMotion(True)
        engine.update(self.frame, 0)
        result, _ = engine.update(self.frame, 1)
        self.assertEqual(result.state, "calibrating")


if __name__ == "__main__":
    unittest.main()
