import unittest

import cv2
import numpy as np

from motion_scenes import CompetingScene, MotionScene
from osr_screen_tcode.camera_motion import CameraRelativeMotion
from osr_screen_tcode.motion_focus import MotionFocus
from osr_screen_tcode.motion_reference import MotionReference, reference_lines


class MotionFocusTests(unittest.TestCase):
    def test_priority_is_current_then_previous_reciprocal_then_current_amplitude(self):
        focus = MotionFocus()
        values = np.zeros(2)
        selections = []
        for i in range(241):
            t = i/30
            new = np.array((2*np.sin(min(t, 2)*5),
                            t*6 if t < 4 else 24+4*np.sin((t-4)*5)))
            candidates = []
            for j in range(2):
                x = 30+j*140
                candidates.append(((x, 50, x+60, 120), (x, 50, x+60, 120),
                                   np.array((0, new[j]-values[j], 0))))
            selections.append(focus.choose(candidates, t))
            values = new
        # The former reciprocal target still wins during its stationary pause.
        self.assertEqual(set(selections[90:120]), {0})
        # A newly confirmed current reciprocal motion outranks that memory.
        self.assertEqual(set(selections[195:]), {1})

    def test_without_reciprocal_history_larger_sustained_motion_wins(self):
        focus = MotionFocus()
        selections = []
        for i in range(61):
            candidates = [((x, 50, x+60, 120), (x, 50, x+60, 120), np.array((0, step, 0)))
                          for x, step in ((30, .03), (170, .15))]
            selections.append(focus.choose(candidates, i/30))
        self.assertEqual(set(selections[30:]), {1})
        self.assertFalse(any(r.had_reciprocal for r in focus.regions))

    def test_smaller_reciprocal_region_beats_large_one_way_drift_and_stays_selected(self):
        scene, engine = CompetingScene(), CameraRelativeMotion()
        references = []
        for i in range(181):
            t = i/30
            engine.update(cv2.cvtColor(scene.frame(t), cv2.COLOR_BGR2GRAY), t)
            references.append(engine.reference)
        self.assertTrue(any(r.roi and (r.roi[0]+r.roi[2])/2 < 350 for r in references[:30]))
        late = references[90:]
        self.assertGreater(sum(r.roi and (r.roi[0]+r.roi[2])/2 > 400 for r in late), 80)
        self.assertGreater(sum(r.state == 'ready' for r in late), 80)

    def test_paused_former_target_stays_tracked_and_cut_forgets_region_history(self):
        scene, engine = CompetingScene(), CameraRelativeMotion()
        rows = []
        for i in range(181):
            t = i/30
            frame = scene.frame(t, target=t < 3.2)
            engine.update(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), t)
            rows.append(engine.reference)
        self.assertGreater(sum(r.roi and (r.roi[0]+r.roi[2])/2 > 400 for r in rows[120:]), 55)
        self.assertTrue(any(r.had_reciprocal for r in engine.region_focus.regions))
        engine.update(np.zeros((480, 640), np.uint8), 6.1)
        self.assertFalse(engine.region_focus.regions)
        self.assertFalse(engine.patch_focus.regions)

    def test_isolated_spike_and_high_frequency_jitter_cannot_steal_focus(self):
        focus = MotionFocus()
        previous = np.zeros(2)
        selections = []
        for i in range(181):
            t = i/30
            values = np.array((2*np.sin(t*5), 4*np.sin(t*2*np.pi*10)))
            if i == 100:
                values[1] += 12
            candidates = []
            for j in range(2):
                x = 30+j*140
                candidates.append(((x, 50, x+60, 120), (x, 50, x+60, 120),
                                   np.array((0, values[j]-previous[j], 0))))
            selections.append(focus.choose(candidates, t))
            previous = values
        self.assertEqual(set(selections), {0})

    def test_fast_compact_region_is_measured_instead_of_repeated_cut_resets(self):
        scene, engine = MotionScene(), CameraRelativeMotion()
        scene.foreground[:] = 0
        scene.mask[:] = 0
        scene.foreground[95:145, 135:185] = np.random.default_rng(23).integers(40, 235, (50, 50, 3), np.uint8)
        scene.mask[95:145, 135:185] = 255
        rows = []
        for i in range(73):
            engine.update(cv2.cvtColor(scene.frame(y=40*np.sin(i*2*np.pi/8)), cv2.COLOR_BGR2GRAY), i/30)
            rows.append(engine.reference)
        self.assertGreater(sum(r.state == 'ready' for r in rows), 60)
        self.assertGreater(sum(abs(r.step[1]) > 6 for r in rows), 25)
        self.assertNotIn('jump', [r.reason for r in rows])

    def test_fast_missing_support_is_distinct_from_a_cut_in_both_languages(self):
        ref = MotionReference('v2', 'holding', reason='fast_support')
        self.assertIn('快速运动有效特征不足', '\n'.join(reference_lines(ref, lambda zh, en: zh)))
        self.assertIn('Fast motion lacks reliable tracks', '\n'.join(reference_lines(ref, lambda zh, en: en)))


if __name__ == '__main__':
    unittest.main()
