"""Pure image/text checks for uncertain subject references; no native windows."""
from collections import deque
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from osr_screen_tcode.motion_reference import MotionReference, draw_reference, reference_lines


BASIS = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


class EstimateDisplayTests(unittest.TestCase):
    def reference(self, **options):
        base = MotionReference('v2', 'missing', roi=(20, 20, 70, 70),
            subject_box=(20, 20, 70, 70), subject_origin=(45, 45), basis=BASIS,
            estimate_state='predicted', estimate_origin=(220, 120),
            estimate_box=(160, 80, 280, 160), estimate_elapsed=.8,
            estimate_basis=BASIS)
        return replace(base, **options)

    def test_estimate_replaces_old_strong_geometry_without_mutating_input(self):
        image = np.zeros((240, 320, 3), np.uint8)
        reference = self.reference()
        with patch('osr_screen_tcode.motion_reference.cv2.putText', wraps=cv2.putText) as text:
            shown = draw_reference(image, reference)
        self.assertFalse(np.any(image))
        self.assertFalse(np.any(shown[10:75, 10:75]))
        self.assertTrue(np.any(shown[75:165, 155:305]))
        labels = [call.args[1] for call in text.call_args_list]
        self.assertIn('A?', labels)
        self.assertNotIn('A', labels)
        self.assertTrue({'L0?', 'L1?', 'L2?'}.issubset(labels))
        self.assertFalse(any('/R' in label for label in labels))
        self.assertEqual(reference.roi, (20, 20, 70, 70))
        self.assertEqual(reference.subject_origin, (45, 45))
        self.assertEqual(reference.step, (0., 0., 0.))
        # Actual gaps along the new border distinguish it from a solid ROI.
        edge = np.any(shown[80, 170:205], axis=1)
        self.assertTrue(edge.any())
        self.assertTrue((~edge).any())
        # The typical preview scales 640 px analysis into a smaller pane.
        # Keep a dark outline on bright footage and a bright stroke on dark
        # footage after that resize; uncertainty remains a dashed shape.
        for background in (0, 245):
            small = cv2.resize(draw_reference(np.full_like(image, background), reference),
                               (224, 168), interpolation=cv2.INTER_AREA)
            border = small[53:60, 117:142]
            self.assertLess(int(border.min()), 150)
            self.assertGreater(int(border.max()), 220)

    def test_strong_observation_retains_its_original_marker_and_axes(self):
        reference = self.reference(state='ready', estimate_state='')
        with patch('osr_screen_tcode.motion_reference.cv2.putText', wraps=cv2.putText) as text:
            shown = draw_reference(np.zeros((240, 320, 3), np.uint8), reference)
        labels = [call.args[1] for call in text.call_args_list]
        self.assertIn('A', labels)
        self.assertNotIn('A?', labels)
        self.assertIn('L0/R0+', labels)
        self.assertTrue(np.any(shown[20:71, 20:71]))
        self.assertFalse(np.any(shown[150:170, 200:300]))

    def test_real_samples_remain_samples_and_target_has_no_old_origin_connector(self):
        reference = self.reference(vectors=(((10., 195.), (25., 195.)),),
            target_point=(100., 195.), target_kind='tracked')
        with patch('osr_screen_tcode.motion_reference.cv2.arrowedLine', wraps=cv2.arrowedLine) as arrows:
            shown = draw_reference(np.zeros((240, 320, 3), np.uint8), reference)
        self.assertEqual(arrows.call_count, 1)  # The one actual sampled vector.
        self.assertEqual(arrows.call_args.args[1:3], ((10, 195), (25, 195)))
        self.assertTrue(np.any(shown[185:206, 85:115]))  # Independent target retained.
        self.assertEqual(reference.vectors, (((10., 195.), (25., 195.)),))
        offscreen = replace(reference, target_point=(-100., 195.), target_offscreen=True)
        for translate, label in ((lambda zh, en: zh, '暂不连线'),
                                 (lambda zh, en: en, 'connector hidden')):
            self.assertIn(label, '\n'.join(reference_lines(offscreen, translate, compact=True)))

    def test_invalid_or_offscreen_estimate_does_not_fall_back_to_old_subject(self):
        image = np.zeros((240, 320, 3), np.uint8)
        for origin, box, basis in (((-20., 120.), None, BASIS),
                                   ((float('nan'), 120.), (float('nan'), 0, 20, 30), BASIS),
                                   (None, (20, 30, 10, 5), BASIS)):
            with self.subTest(origin=origin, box=box):
                shown = draw_reference(image, self.reference(estimate_origin=origin,
                                       estimate_box=box, estimate_basis=basis))
                self.assertFalse(np.any(shown))
        reference = self.reference(estimate_box=(-1e20, 100., 200., 1e20),
                                   estimate_origin=(100., 130.), estimate_basis=((float('nan'), 0., 0.),)*3)
        shown = draw_reference(image, reference)
        self.assertEqual(shown.shape, image.shape)
        self.assertTrue(np.any(shown))

    def test_retained_assumed_target_is_explained_without_inventing_a_location(self):
        reference = self.reference(estimate_state='weak', target_kind='assumed_held',
                                   target_point=None, reach_state='missing')
        for compact in (False, True):
            for translate, explanation in ((lambda zh, en: zh, '不更新到达比例、不连线'),
                                            (lambda zh, en: en, 'reach not updated, no connector')):
                text = '\n'.join(reference_lines(reference, translate, compact=compact))
                self.assertIn('V?', text)
                self.assertIn(explanation, text)
                self.assertNotIn('T?', text)
        with patch('osr_screen_tcode.motion_reference.cv2.putText', wraps=cv2.putText) as labels:
            draw_reference(np.zeros((240, 320, 3), np.uint8), reference)
        self.assertNotIn('V?', [call.args[1] for call in labels.call_args_list])
        tracked = replace(reference, target_kind='tracked', target_point=(100., 195.))
        text = '\n'.join(reference_lines(tracked, lambda zh, en: en, compact=True))
        self.assertIn('T? Object candidate: independently tracked', text)
        self.assertNotIn('V?', text)

    def test_subject_states_are_bilingual_and_visible_in_compact_first_line(self):
        for state, zh_label, en_label in (('weak', '主体弱跟踪', 'Weak subject tracking'),
                                          ('predicted', '主体位置估算', 'Estimated subject position'),
                                          ('held', '主体估计保持', 'Subject estimate held')):
            for language, label in (('zh', zh_label), ('en', en_label)):
                translate = lambda zh, en: zh if language == 'zh' else en
                for compact in (False, True):
                    with self.subTest(state=state, language=language, compact=compact):
                        lines = reference_lines(self.reference(estimate_state=state), translate, compact=compact)
                        self.assertIn(label, lines[0])
                        self.assertIn('0.8/2.0', lines[0])
                        self.assertNotIn('参考不足', lines[0])
                        self.assertNotIn('Insufficient reference', lines[0])
                        self.assertIn('A?', '\n'.join(lines))
                        self.assertNotIn('actual region', '\n'.join(lines))
                        self.assertNotIn('主体框中心：多组采样跟踪', '\n'.join(lines))

    def test_output_continuation_kind_overrides_missing_in_both_first_lines(self):
        for kind, zh_label, en_label in (('rhythm', '节奏接续', 'Rhythm continuation'),
                                        ('velocity', '短速度接续', 'Brief velocity continuation'),
                                        ('weak', '弱跟踪接续', 'Weak-tracking continuation')):
            for state in ('continuing', 'braking', 'held'):
                for language, label in (('zh', zh_label), ('en', en_label)):
                    translate = lambda zh, en: zh if language == 'zh' else en
                    reference = self.reference(continuation=state, continuation_kind=kind,
                                               continuation_elapsed=3. if state == 'held' else 1.7)
                    for compact in (False, True):
                        with self.subTest(kind=kind, state=state, language=language, compact=compact):
                            title = reference_lines(reference, translate, compact=compact)[0]
                            self.assertIn(label, title)
                            elapsed = '0.3/0.3' if kind == 'velocity' else '2.0/2.0' if state == 'held' else '1.7/2.0'
                            self.assertIn(elapsed, title)
                            self.assertNotIn('Insufficient reference', title)
                            if state == 'braking':
                                self.assertIn('减速' if language == 'zh' else 'braking', title)
                            if kind == 'velocity':
                                self.assertNotIn('/2.0', title)
                                self.assertIn('最多' if language == 'zh' else 'maximum', title)
                                if state == 'held':
                                    self.assertIn('速度接续已停止' if language == 'zh' else 'velocity continuation stopped', title)
        for compact in (False, True):
            reference = self.reference(continuation='braking', continuation_kind='velocity',
                                       continuation_elapsed=.2)
            self.assertIn('0.2/0.3', reference_lines(reference, lambda zh, en: en, compact=compact)[0])

    def test_legacy_rhythm_and_nonfinite_elapsed_remain_readable(self):
        reference = MotionReference('v2', 'missing', continuation='continuing',
                                    continuation_elapsed=float('nan'))
        self.assertIn('预测', reference_lines(reference, lambda zh, en: zh, compact=True)[0])
        self.assertIn('0.0/2.0', reference_lines(reference, lambda zh, en: en, compact=True)[0])

    def test_preview_text_accepts_each_source_without_filling_observation_history(self):
        # Invoke display on ordinary Python stand-ins, without constructing Tk.
        from osr_screen_tcode.integrated_preview import IntegratedPreview
        from osr_screen_tcode.visual_lab.observations import Observation
        from osr_screen_tcode.visual_pipeline import VisualFrame

        class Text:
            value = ''
            def set(self, value):
                self.value = value
            def get(self):
                return self.value

        for source, label in (('rhythm', 'Rhythm continuation'),
                              ('velocity', 'Brief velocity continuation'),
                              ('weak', 'Weak-tracking continuation')):
            with self.subTest(source=source):
                observed = Observation(1., 'missing')
                frame = VisualFrame((np.zeros((80, 120, 3), np.uint8),)*2,
                    observed, False, 0, reference=self.reference(continuation='continuing',
                    continuation_kind=source), l0_source=source)
                view = SimpleNamespace(app=SimpleNamespace(_visual_settings=SimpleNamespace(generation=0)),
                    t=lambda zh, en: en, history=deque(), details=Text(), headings=Text(),
                    render=Mock(), render_chart=Mock())
                IntegratedPreview.display(view, frame)
                self.assertIn(label, view.details.get())
                source_caption = view.details.get().split('L0 source: ')[-1]
                if source == 'velocity':
                    self.assertIn('up to 0.3 s', source_caption)
                    self.assertIn('15% before gains', source_caption)
                    self.assertNotIn('up to 2 s', source_caption)
                else:
                    self.assertIn('up to 2 s', source_caption)
                self.assertEqual(list(view.history), [observed])
                self.assertIsNone(view.history[0].values)


if __name__ == '__main__':
    unittest.main()
