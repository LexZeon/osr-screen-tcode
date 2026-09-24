import math
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch, Mock

import numpy as np

from motion_scenes import MotionScene
from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.motion_reference import MotionReference, reference_lines
from osr_screen_tcode.motion_rhythm import MotionRhythm
from osr_screen_tcode.point_l0 import PointL0
from osr_screen_tcode.region_support import balanced_fit, support_seeds
from osr_screen_tcode.visual_pipeline import VisualSettings, make_analyzer
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.visual_lab.observations import Observation


class MeasuredMotion:
    """Inject a known tracker dropout at the analysis boundary, not output."""
    def __init__(self):
        self.reference = MotionReference('v2')
        self.interaction = SimpleNamespace(state='unresolved', value=0., step=0., point=None)
        self.previous = 0.

    def update(self, gray, stamp):
        value = 12*np.sin(stamp*2*np.pi)
        if 6 < stamp <= 9:
            state = 'holding' if stamp < 6.4 else 'missing'
            self.reference = MotionReference('v2', state, reason='background')
            self.interaction.state = 'unresolved'
            return Observation(stamp, state), []
        step = value-self.previous
        self.previous = value
        self.reference = MotionReference('v2', 'ready', (110, 80-value, 210, 160-value),
                                         step=(0, step, 0), motion_dt=1/30)
        return Observation(stamp, 'ready', (0, value, 0)), []


class RhythmTests(unittest.TestCase):
    def trained(self):
        rhythm = MotionRhythm()
        for i in range(181):
            t = i/30
            rhythm.observe(t, .5+.35*np.cos(t*2*np.pi))
        self.assertIsNotNone(rhythm.model)
        return rhythm

    def test_two_second_continuation_is_continuous_brakes_and_stops(self):
        rhythm = self.trained()
        held = .62
        self.assertAlmostEqual(rhythm.predict(6., held), held)
        values = [rhythm.predict(6+i/120, held) for i in range(301)]
        self.assertGreater(np.ptp(values[:180]), .5)
        self.assertLess(max(abs(np.diff(values))), .025)
        self.assertLess(abs(values[240]-values[239]), .0001)
        self.assertTrue(all(v == values[240] for v in values[240:]))
        self.assertEqual(rhythm.state, 'held')

    def test_noise_drift_and_missing_startup_never_invent_a_cycle(self):
        for kind in ('noise', 'drift', 'still'):
            rhythm = MotionRhythm()
            rng = np.random.default_rng(5)
            for i in range(181):
                value = .5+rng.normal(0, .012) if kind == 'noise' else .3+i*.001 if kind == 'drift' else .5
                rhythm.observe(i/30, value)
            self.assertIsNone(rhythm.predict(6.03, .5), kind)
        self.assertIsNone(MotionRhythm().predict(0, .5))


class FusionTests(unittest.TestCase):
    def trained(self):
        dominant, output = DominantMotion(adaptive_l0=True), PointL0()
        previous = 0.
        for i in range(241):
            t = i/30
            value = 6*np.sin(t*2*np.pi)
            ordinary = dominant.update((0, value, 0), t)['L0']
            point = SimpleNamespace(state='ready', value=-value, step=-(value-previous), point=(160., 180.))
            ref = MotionReference('v2', 'ready', (110, 70, 210, 150), step=(0, value-previous, 0), motion_dt=1/30)
            output.update('fusion', dominant, ref, point, t, (240, 320), ordinary)
            previous = value
        return dominant, output, ref, point

    def test_fusion_aligns_direction_and_marks_the_target(self):
        dominant, output, ref, point = self.trained()
        self.assertTrue(output.fusion.oriented)
        self.assertTrue(output.fusion.using_point)
        self.assertEqual(output.fusion.target, point.point)
        self.assertGreater(output.fusion.weights[2], 0)
        self.assertIsNotNone(output.fusion.rhythm.model)

    def test_short_loss_preserves_rhythm_without_fabricating_observations(self):
        dominant, output, ref, point = self.trained()
        held = output.output
        missing = replace(ref, state='holding', reason='background', step=(0, 0, 0))
        values = []
        before = dominant.previous.copy()
        for i in range(1, 91):
            values.append(output.update('fusion', dominant, missing, point, 8+i/30, (240, 320), held))
        self.assertGreater(np.ptp(values[:45]), .6)
        self.assertLess(max(abs(np.diff([held]+values))), .13)
        self.assertEqual(values[60:], [values[60]]*len(values[60:]))
        np.testing.assert_array_equal(dominant.previous, before)
        self.assertIsNone(output.fusion.target)
        before = output.output
        output.update('fusion', dominant, ref, point, 11.1, (240, 320), .9)
        self.assertAlmostEqual(output.output, before)

    def test_cut_and_explicit_pause_disable_continuation(self):
        for reason in ('jump', 'repeated', 'stationary'):
            dominant, output, ref, point = self.trained()
            held = output.output
            state = 'missing' if reason == 'jump' else 'tracking'
            stopped = replace(ref, state=state, reason=reason, step=(0, 0, 0))
            for i in range(1, 31):
                self.assertEqual(output.update('fusion', dominant, stopped, point, 8+i/30, (240, 320), held), held)
            self.assertIsNone(output.fusion.rhythm.model)
            self.assertFalse(output.fusion.predicting)

    def test_real_radial_frames_are_far_high_near_low_and_share_motion(self):
        scene = MotionScene()
        fused = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        original = make_analyzer(tracker_mode=HYBRID_V2_MODE, visual_settings=VisualSettings(v2_l0_reference='motion'))
        values = []
        for i in range(181):
            t = i/30
            frame = scene.frame(scale=np.exp(.1*np.sin(t*5)), camera_x=3*np.sin(t*3))
            values.append(fused.process(frame, t).positions['L0'])
            original.process(frame, t)
            np.testing.assert_allclose(fused.motion.values, original.motion.values)
        expected = np.sin(np.arange(91, 181)/30*5)
        self.assertGreater(np.corrcoef(values[-90:], expected)[0, 1], .85)
        self.assertTrue(fused.point_l0.fusion.oriented)
        self.assertTrue(fused.visual_frame.reference.target_kind.startswith('assumed'))
        self.assertIn('V?', '\n'.join(reference_lines(fused.visual_frame.reference, lambda zh, en: zh)))


class RegionSupportTests(unittest.TestCase):
    def test_real_frames_keep_following_when_a_third_of_foreground_tracks_drop(self):
        from osr_screen_tcode.motion_tracking import track_pair
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        scene = MotionScene()
        values, groups, ready = [], [], 0
        index = 0
        def drop(previous, gray, points):
            a, b, rescued = track_pair(previous, gray, points)
            foreground = (a[:, 0] > 105) & (a[:, 0] < 215) & (a[:, 1] > 45) & (a[:, 1] < 200)
            selected = ~foreground | (np.arange(len(a)) % 3 != index % 3)
            return a[selected], b[selected], rescued
        with patch('osr_screen_tcode.camera_motion.track_pair', side_effect=drop):
            for index in range(121):
                t = index/30
                values.append(engine.process(scene.frame(y=12*np.sin(t*5), camera_x=3*np.sin(t*3)), t).positions['L0'])
                ready += engine.motion.reference.state in ('ready', 'tracking')
                groups.append(len(engine.motion.reference.support_groups))
        self.assertGreater(ready, 100)
        self.assertGreater(sum(n >= 3 for n in groups), 90)
        expected = np.sin(np.arange(61, 121)/30*5)
        self.assertGreater(np.corrcoef(values[-60:], expected)[0, 1], .94)

    def test_balanced_groups_tolerate_partial_point_loss_and_do_not_bias_to_texture(self):
        rng = np.random.default_rng(81)
        points = np.array([(x, y) for x in range(20, 121, 10) for y in range(20, 121, 10)], float)
        points = np.vstack((points, rng.uniform((20, 20), (40, 40), (160, 2))))
        matrix = np.array(((1.01, -.015, 8.), (.015, 1.01, -4.)))
        tracked = points @ matrix[:, :2].T+matrix[:, 2]+rng.normal(0, .04, points.shape)
        tracked[121:] += (.3, -.2)
        fitted, groups = balanced_fit(points, tracked, matrix, .7)
        self.assertGreaterEqual(len(groups), 7)
        np.testing.assert_allclose(fitted[:, 2], matrix[:, 2], atol=.12)
        keep = points[:, 0] >= 50
        partial, groups = balanced_fit(points[keep], tracked[keep], matrix, .7)
        np.testing.assert_allclose(partial, matrix, atol=.08)
        seeds = support_seeds(tracked[keep])
        self.assertLessEqual(len(seeds), 54)
        self.assertGreater(np.ptp(seeds[:, 0]), 60)


class FusionPipelineTests(unittest.TestCase):
    def engine(self, mode=HYBRID_V2_MODE):
        engine = make_analyzer(tracker_mode=mode, output_mode='Six Axis')
        engine.motion = MeasuredMotion()
        return engine

    def test_dropout_output_labels_actual_confidence_and_cycle_travel(self):
        for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
            engine = self.engine(mode)
            frame = np.zeros((240, 320, 3), np.uint8)
            rows = []
            for i in range(331):
                t = i/30
                result = engine.process(frame, t)
                rows.append(result.positions['L0'])
                if 6.1 < t < 8:
                    self.assertEqual(result.confidence, 0.)
                    self.assertIsNotNone(engine.generated_l0)
                    self.assertEqual(engine.visual_frame.l0_source, 'rhythm')
                    self.assertIn('预测', '\n'.join(reference_lines(engine.visual_frame.reference, lambda zh, en: zh)))
                    self.assertTrue(all(result.positions[a] == .5 for a in ('L1', 'L2', 'R0', 'R1', 'R2')))
            self.assertGreater(np.ptp(rows[183:226]), .35, mode)
            np.testing.assert_allclose(rows[241:271], rows[241], atol=1e-12)
            self.assertLess(abs(rows[271]-rows[270]), .13)
            self.assertLess(max(abs(np.diff(rows))), .2)
            if mode == STROKE_CYCLE_MODE:
                self.assertEqual(engine.cycle.peak, 1.)

    def test_live_export_and_preview_keep_final_mapping_during_prediction(self):
        import json
        import tempfile
        from pathlib import Path
        from osr_screen_tcode.app import OsrScreenApp
        from osr_screen_tcode.config import AppConfig
        from test_output_presets import MemoryVideo
        config = AppConfig(last_sink='Log only', tracker_mode=HYBRID_V2_MODE)
        frame = np.zeros((240, 320, 3), np.uint8)
        with patch.object(AppConfig, 'load', return_value=config), patch.object(AppConfig, 'save'), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language='en')
            app.withdraw()
            app.l0_travel_scale.set(.5)
            app.global_travel_scale.set(.8)
            app.enable_startup_ramp.set(False)
            app.enable_speed_limit.set(False)
            app.endpoint_slowdown_enabled.set(False)
            app.output_curve_fitting.set(True)
            app.connect_sink()
            engine = self.engine()
            engine.configure(app._visual_settings)
            engine.motion = MeasuredMotion()
            output = app._new_output(33)
            app._output_context.sink = app.sink
            emulator = Mock()
            app.preview_bridge.broadcast_tcode = emulator
            try:
                live = []
                for i in range(271):
                    app._process_frame(engine, output, frame, 0., timestamp=i/30)
                    live.append(app._parse_axis_values(app.sink.last_payload.decode())['L0'])
                    if i == 200:
                        app.integrated_preview.display(engine.visual_frame)
                        self.assertIn('predicted', app.integrated_preview.details.get())
                self.assertGreater(np.ptp(live[184:220]), 1500)
                # Existing mapping: L0 has its own travel multiplier; the
                # global six-axis slider scales L1/L2/R0/R1/R2.
                self.assertGreaterEqual(min(live), 2490)
                self.assertLessEqual(max(live), 7510)
                self.assertEqual(emulator.call_args.args[0], app.sink.last_payload.decode().strip())
                def factory(**kwargs):
                    analyzer = make_analyzer(**kwargs)
                    analyzer.motion = MeasuredMotion()
                    return analyzer
                with patch('osr_screen_tcode.app.make_analyzer', side_effect=factory), patch('osr_screen_tcode.app.cv2.VideoCapture', return_value=MemoryVideo([frame]*271)):
                    files = app._analyze_video_worker(Path('synthetic.avi'), Path(temp)/'fusion.funscript')
                actions = json.loads(files[0].read_text())['actions']
                predicted = [p['pos'] for p in actions if 6150 <= p['at'] <= 7400]
                self.assertGreater(np.ptp(predicted), 15)
                self.assertGreaterEqual(min(p['pos'] for p in actions), 25)
                self.assertLessEqual(max(p['pos'] for p in actions), 75)
            finally:
                app.on_close()


if __name__ == '__main__':
    unittest.main()
