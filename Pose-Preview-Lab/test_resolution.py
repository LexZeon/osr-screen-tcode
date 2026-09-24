import unittest

import numpy as np

from preview import resize_for_processing
from frame_motion import FrameMotion


class ResolutionTests(unittest.TestCase):
    def test_actual_motion_analysis_keeps_tiny_strips_missing(self):
        for shape in ((1, 640), (640, 1), (16, 16), (16, 20000), (20000, 16)):
            frame = np.random.default_rng(24).integers(0, 255, (*shape, 3), dtype=np.uint8)
            for scale in (False, True):
                with self.subTest(shape=shape, scale=scale):
                    engine = FrameMotion(scale=scale)
                    for index in range(3):
                        moved = np.roll(frame, index, axis=int(shape[1] > shape[0]))
                        gray = resize_for_processing(moved, 640)[..., 0].copy()
                        observation, vectors = engine.update(gray, index / 30)
                        self.assertIsNone(observation.values)
                        self.assertEqual(vectors, [])
                    self.assertEqual(observation.state, "missing")

    def test_landscape_and_portrait_preserve_aspect(self):
        for shape, expected in (((1080, 1920, 3), (360, 640, 3)),
                                ((1920, 1080, 3), (640, 360, 3))):
            self.assertEqual(resize_for_processing(np.zeros(shape, np.uint8), 640).shape, expected)

    def test_no_upscale(self):
        frame = np.zeros((100, 200, 3), np.uint8)
        self.assertIs(resize_for_processing(frame, 640), frame)

    def test_small_setting(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        self.assertEqual(resize_for_processing(frame, 320).shape, (240, 320, 3))

    def test_extreme_multi_monitor_strips_keep_all_pixels_representable(self):
        for height, width in ((16, 20000), (20000, 16), (1, 4096), (4096, 1)):
            frame = np.zeros((height, width, 3), np.uint8)
            frame[:max(1, height // 2), :max(1, width // 2)] = (30, 90, 180)
            frame[height // 2:, width // 2:] = (120, 210, 60)
            for edge in (320, 480, 640, 960, 1280):
                with self.subTest(shape=(height, width), edge=edge):
                    result = resize_for_processing(frame, edge)
                    ratio = edge / max(height, width)
                    self.assertEqual(result.shape, (max(1, round(height * ratio)),
                                                    max(1, round(width * ratio)), 3))
                    self.assertEqual(max(result.shape[:2]), edge)
                    self.assertFalse(np.array_equal(result[0, 0], result[-1, -1]))


if __name__ == "__main__":
    unittest.main()
