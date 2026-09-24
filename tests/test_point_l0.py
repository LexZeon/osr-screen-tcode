import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from motion_scenes import MotionScene
from osr_screen_tcode.interaction_point import InteractionPoint, convergence
from osr_screen_tcode.point_l0 import PointL0
from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.motion_reference import MotionReference, reference_lines
from osr_screen_tcode.visual_pipeline import make_analyzer, VisualSettings
from osr_screen_tcode.config import AppConfig, HYBRID_V2_MODE, RTM_POSE_2D_MODE, STROKE_CYCLE_MODE, normalize_visual_settings


class PointReferenceTests(unittest.TestCase):
    def setUp(self):
        self.points = np.float64([(x, y) for x in range(65, 270, 15) for y in range(50, 210, 15)])
        self.center = np.array((160., 120.))

    def test_radial_candidate_survives_noise_but_translation_rotation_and_random_flow_reject(self):
        a, c = self.points, self.center
        rng = np.random.default_rng(27)
        for scale in (.98, 1.02):
            b = c+(a-c)*scale+rng.normal(0, .04, a.shape)
            b[:12] += 8
            candidate = convergence(a, b, (240, 320))
            self.assertIsNotNone(candidate)
            np.testing.assert_allclose(candidate[0], c, atol=1.)
        self.assertIsNone(convergence(a, a+(3, -2), (240, 320)))
        angle = .05
        rotation = np.array(((np.cos(angle), -np.sin(angle)), (np.sin(angle), np.cos(angle))))
        self.assertIsNone(convergence(a, c+(a-c) @ rotation.T, (240, 320)))
        self.assertIsNone(convergence(a, a+rng.normal(0, 3, a.shape), (240, 320)))

    def test_candidate_confirms_in_time_follows_camera_and_expires_without_evidence(self):
        tracker = InteractionPoint()
        camera = np.float64([[1, 0, 2], [0, 1, 1]])
        for i in range(12):
            shift = np.array((2., 1.))*i
            a, c = self.points+shift, self.center+shift
            b = c+(a-c)*.98
            tracker.update(a, b, camera, i/30, (240, 320))
            if i < 5:
                self.assertNotEqual(tracker.state, 'ready')
        self.assertEqual(tracker.state, 'ready')
        np.testing.assert_allclose(tracker.point, self.center+(24, 12), atol=.01)
        self.assertGreater(tracker.step, 0)
        tracker.hold(.4)
        self.assertEqual(tracker.state, 'holding')
        self.assertEqual(tracker.step, 0)
        tracker.hold(1.)
        self.assertIsNone(tracker.point)

    def test_center_reference_tracks_video_phase_without_changing_motion_observations(self):
        scene = MotionScene()
        base = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        centered = make_analyzer(tracker_mode=HYBRID_V2_MODE, visual_settings=VisualSettings(v2_l0_reference='center'))
        positions, source = [], []
        for i in range(181):
            t = i/30
            frame = scene.frame(y=10*np.sin(t*5), camera_x=3*np.sin(t*3))
            base.process(frame, t)
            positions.append(centered.process(frame, t).positions['L0'])
            np.testing.assert_allclose(base.motion.values, centered.motion.values)
            source.append(centered.point_l0.source)
        self.assertGreater(source.count('center'), 140)
        self.assertGreater(np.ptp(positions[-90:]), .9)
        expected = np.sin(np.arange(91, 181)/30*5)
        self.assertGreater(np.corrcoef(positions[-90:], expected)[0, 1], .97)
        self.assertIsNotNone(centered.visual_frame.reference.stroke_center)
        self.assertIsNone(centered.visual_frame.reference.interaction_point)

    def test_interaction_script_requires_radial_evidence_and_follows_approach(self):
        scene = MotionScene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE, visual_settings=VisualSettings(v2_l0_reference='interaction'))
        positions, sources, ready = [], [], 0
        for i in range(181):
            t = i/30
            result = engine.process(scene.frame(scale=np.exp(.1*np.sin(t*5)), camera_x=3*np.sin(t*3)), t)
            positions.append(result.positions['L0'])
            sources.append(engine.point_l0.source)
            ready += engine.motion.interaction.state == 'ready'
        self.assertGreater(ready, 50)
        self.assertGreater(sources.count('interaction'), 100)
        self.assertGreater(np.ptp(positions[-90:]), .8)
        expected = np.sin(np.arange(91, 181)/30*5)
        self.assertGreater(np.corrcoef(positions[-90:], expected)[0, 1], .8)
        held = positions[-1]
        for i in range(1, 46):
            self.assertEqual(engine.process(scene.frame(scale=np.exp(.1*np.sin(6*5)), camera_x=3*np.sin(6*3)), 6+i/30).positions['L0'], held)

    def test_source_changes_continue_from_current_target_and_original_mode_is_exact(self):
        dominant, output = DominantMotion(adaptive_l0=True), PointL0()
        point = SimpleNamespace(state='unresolved', value=0.)
        ref = MotionReference('v2', 'ready', (80, 70, 240, 200), step=(0, 1, 0))
        for i in range(100):
            t = i/30
            dominant.update((0, 4*np.sin(t*5), 0), t)
            self.assertEqual(output.update('motion', dominant, ref, point, t, (240, 320), .3), .3)
        before = output.output
        value = output.update('center', dominant, ref, point, 100/30, (240, 320), .3)
        self.assertEqual(value, before)
        self.assertEqual(output.source, 'center')
        for i in range(101, 110):
            dominant.update((0, 4*np.sin(i/30*5), 0), i/30)
            output.update('center', dominant, ref, point, i/30, (240, 320), .3)
        before = output.output
        self.assertEqual(output.update('motion', dominant, ref, point, 110/30, (240, 320), .3), before)

    def test_point_labels_do_not_claim_contact(self):
        ref = MotionReference('v2', 'ready', stroke_center=(50, 50), interaction_point=(80, 80),
                              interaction_state='ready', l0_reference='interaction')
        self.assertIn('未确认接触', '\n'.join(reference_lines(ref, lambda zh, en: zh)))
        self.assertIn('contact unconfirmed', '\n'.join(reference_lines(ref, lambda zh, en: en)))
        compact = '\n'.join(reference_lines(ref, lambda zh, en: en, compact=True))
        self.assertIn('contact unconfirmed', compact)
        self.assertIn('Interaction candidate (before gains)', compact)
        self.assertLess(len(compact.splitlines()), len(reference_lines(ref, lambda zh, en: en)))

    def test_cycle_point_modes_keep_discrete_travel_and_stop_on_frozen_video(self):
        scene = MotionScene()
        for mode in ('center', 'interaction'):
            engine = make_analyzer(tracker_mode=STROKE_CYCLE_MODE, visual_settings=VisualSettings(v2_l0_reference=mode))
            values, sources = [], []
            for i in range(241):
                t = i/30
                frame = scene.frame(scale=np.exp(.1*np.sin(t*5))) if mode == 'interaction' else scene.frame(y=6*np.sin(t*5))
                values.append(engine.process(frame, t).positions['L0'])
                sources.append(engine.point_l0.source)
                if engine.point_l0.driver is not None:
                    self.assertEqual(engine.visual_frame.reference.span, engine.point_l0.driver.stroke_evidence.span)
            self.assertIn(mode, sources)
            self.assertGreater(np.ptp(values[-90:]), .15)
            self.assertLess(np.max(abs(np.diff(values))), .15)
            for i in range(1, 61):
                engine.process(frame, 8+i/30)
            self.assertEqual(engine.cycle.state, 'stopped')
            held = engine.cycle.value
            for i in range(61, 76):
                self.assertEqual(engine.process(frame, 8+i/30).positions['L0'], held)


class PointSettingsTests(unittest.TestCase):
    def test_unknown_saved_point_source_restores_original_default(self):
        for saved in (None, '', 'obsolete', 123):
            extra = {'v2_l0_reference': saved}
            normalize_visual_settings(extra)
            self.assertEqual(extra['v2_l0_reference'], 'fusion')

    def test_center_export_receives_saved_source_and_final_travel_gain(self):
        import json
        import tempfile
        from pathlib import Path
        from test_output_presets import MemoryVideo
        from osr_screen_tcode.app import OsrScreenApp
        scene = MotionScene()
        frames = [scene.frame(y=10*np.sin(i/30*5)) for i in range(181)]
        config = AppConfig(last_sink='Log only', tracker_mode=HYBRID_V2_MODE)
        config.extra['v2_l0_reference'] = 'center'
        engines = []
        def factory(**kwargs):
            engine = make_analyzer(**kwargs)
            engines.append(engine)
            return engine
        with patch.object(AppConfig, 'load', return_value=config), patch.object(AppConfig, 'save'), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language='en')
            app.withdraw()
            app.l0_travel_scale.set(.5)
            app.endpoint_slowdown_enabled.set(False)
            app.output_curve_fitting.set(False)
            try:
                with patch('osr_screen_tcode.app.make_analyzer', side_effect=factory), patch('osr_screen_tcode.app.cv2.VideoCapture', return_value=MemoryVideo(frames)):
                    files = app._analyze_video_worker(Path('memory.avi'), Path(temp)/'center.funscript')
                self.assertEqual(engines[0].point_l0.source, 'center')
                actions = [p['pos'] for p in json.loads(files[0].read_text())['actions'] if p['at'] > 3000]
                self.assertGreater(max(actions)-min(actions), 45)
                self.assertGreaterEqual(min(actions), 25)
                self.assertLessEqual(max(actions), 75)
            finally:
                app.on_close()

    def test_default_save_reset_and_pose_visibility_share_settings(self):
        from osr_screen_tcode.app import OsrScreenApp
        with patch.object(AppConfig, 'load', side_effect=lambda: AppConfig(last_sink='Log only')), patch.object(AppConfig, 'save'):
            app = OsrScreenApp(enforce_age_gate=False, ui_language='en')
            app.withdraw()
            try:
                self.assertEqual(app.v2_l0_reference.get(), 'fusion')
                generation = app._visual_settings.generation
                app.v2_l0_reference.set('center')
                self.assertEqual(app._visual_settings.v2_l0_reference, 'center')
                self.assertEqual(app._visual_settings.generation, generation)
                app._save_config()
                self.assertEqual(app.config_model.extra['v2_l0_reference'], 'center')
                app._set_tracker_mode(RTM_POSE_2D_MODE)
                self.assertFalse(app.integrated_preview.point_l0_controls.winfo_manager())
                app._set_tracker_mode(HYBRID_V2_MODE)
                self.assertEqual(app.v2_l0_reference.get(), 'center')
                self.assertFalse(app.integrated_preview.switches[0].winfo_manager())
                with patch('osr_screen_tcode.integrated_preview.messagebox.showinfo') as info:
                    app.integrated_preview.show_reference_details()
                    self.assertIn('No analysis reference', info.call_args.args[1])
                with patch('osr_screen_tcode.app.messagebox.askyesno', return_value=True):
                    app.reset_all_settings()
                self.assertEqual(app.v2_l0_reference.get(), 'fusion')
            finally:
                app.on_close()


if __name__ == '__main__':
    unittest.main()
