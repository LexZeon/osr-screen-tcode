import unittest
import numpy as np

from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.motion_reference import MotionReference, draw_reference, projected_axes, reference_lines
from osr_screen_tcode.stroke_cycle import StrokeCycle
from osr_screen_tcode.visual_pipeline import make_analyzer
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE
from motion_scenes import MotionScene
from test_visual_pipeline import FakePose


class MotionBasisTests(unittest.TestCase):
    def train(self, direction=(8., 4., -6.), seconds=8):
        engine = DominantMotion()
        direction = np.array(direction)
        for i in range(seconds*60+1):
            value = direction*np.sin(i/60*5)
            result = engine.update(value[[2, 0, 1]], i/60)
            np.testing.assert_allclose(engine.basis @ engine.basis.T, np.eye(3), atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(engine.basis), 1., places=12)
        return engine, value, result

    def test_signed_oblique_axis_uses_all_dimensions_without_cancellation(self):
        engine, value, result = self.train()
        direction = np.array((8., 4., -6.))/np.linalg.norm((8., 4., -6.))
        np.testing.assert_allclose(engine.basis[0], direction, atol=2e-6)
        before = np.array(list(result.values()))
        moved = engine.update((value+direction*.2)[[2, 0, 1]], 481/60)
        np.testing.assert_allclose(np.array(list(moved.values()))-before, (.002, 0, 0), atol=1e-8)
        self.assertLess(engine.basis[0, 2], 0)
        self.assertGreater(engine.stroke_span, 19.)

    def test_small_strokes_keep_weak_signed_components_and_combined_span(self):
        for direction in ((1., 1., 1.), (.96, .24, -.14), (0., 1., -1.)):
            direction = np.array(direction)/np.linalg.norm(direction)
            engine, _, _ = self.train(direction*.58)
            np.testing.assert_allclose(engine.basis[0], direction, atol=2e-5)
            self.assertAlmostEqual(engine.stroke_span, 1.11, delta=.03)

    def test_small_stroke_startup_does_not_depend_on_initial_phase(self):
        for phase in (0., np.pi/2, np.pi, 3*np.pi/2):
            engine = DominantMotion(adaptive_l0=True)
            outputs = []
            for i in range(481):
                result = engine.update((0, .58*np.sin(i/60*5+phase), 0), i/60)
                outputs.append(result['L0'])
            self.assertAlmostEqual(engine.stroke_span, 1.11, delta=.03)
            self.assertGreater(np.ptp(outputs[-180:]), .4)

    def test_small_cycles_are_active_at_equal_vector_amplitude_across_fps(self):
        for fps in (30, 45, 60, 120):
            for direction in (np.array((0., 1., 0.)), np.ones(3)/np.sqrt(3)):
                dominant, cycle = DominantMotion(), StrokeCycle()
                previous = np.zeros(3)
                values = []
                for i in range(8*fps+1):
                    t = i/fps
                    point = direction*.58*np.sin(t*5)
                    dominant.update(point, t)
                    values.append(cycle.update(dominant, MotionReference('v2', step=tuple(point-previous)), t, True))
                    previous = point
                    if t >= 5:
                        self.assertEqual(cycle.state, 'quarter', (fps, direction, t))
                self.assertAlmostEqual(cycle.period, 2*np.pi/5, delta=.12)
                self.assertEqual(min(values[-3*fps:]), 0.)
                self.assertEqual(max(values[-3*fps:]), .25)

    def test_transverse_pan_does_not_keep_a_stopped_main_stroke_cycling(self):
        dominant, cycle = DominantMotion(), StrokeCycle()
        previous = np.zeros(3)
        for i in range(541):
            t = i/60
            point = np.array((0., np.sin(t*5), 0.)) if t <= 8 else np.array(((t-8)*10, np.sin(40), 0.))
            dominant.update(point, t)
            cycle.update(dominant, MotionReference('v2', step=tuple(point-previous)), t, True)
            previous = point
        self.assertIsNotNone(dominant.stroke_span)  # recent history alone cannot sustain a cycle
        self.assertEqual(cycle.state, 'stopped')
        np.testing.assert_array_equal(dominant.basis, np.eye(3))

    def test_relative_component_gate_still_rejects_tiny_motion_and_one_way_acceleration(self):
        tiny, drift = DominantMotion(adaptive_l0=True), DominantMotion()
        for i in range(601):
            t = i/60
            tiny.update(np.full(3, .2*np.sin(t*5)), t)
            # Strong varying one-way velocities cannot tilt a smaller real stroke.
            result = drift.update((t*t*4, .58*np.sin(t*5), t*t*2), t)
            self.assertAlmostEqual(result['L0'], .5+.0058*np.sin(t*5), places=9)
        np.testing.assert_array_equal(tiny.basis, np.eye(3))
        self.assertEqual(tiny.stroke_gain, 1.)
        self.assertIsNone(tiny.stroke_span)
        np.testing.assert_array_equal(drift.basis, np.eye(3))

    def test_transverse_translation_and_rotations_share_the_same_basis(self):
        engine, value, result = self.train()
        offset = engine.basis[1]*.1+engine.basis[2]*.15
        moved = engine.update((value+offset)[[2, 0, 1]], 481/60)
        np.testing.assert_allclose(np.array(list(moved.values()))-list(result.values()),
                                   engine.basis @ offset/100, atol=1e-12)
        engine.map_rotations(dict.fromkeys(('R0', 'R1', 'R2'), .5))
        raw = .5+engine.basis[0]*.04
        rotated = engine.map_rotations(dict(zip(('R0', 'R1', 'R2'), raw)))
        np.testing.assert_allclose(list(rotated.values()), (.54, .5, .5), atol=1e-12)
        # Rotating the reference itself must not remap an old rotation offset.
        engine._turn_basis(np.array((1., 0., 0.)), .2)
        self.assertEqual(engine.map_rotations(dict(zip(('R0', 'R1', 'R2'), raw))), rotated)

    def test_reversals_hold_and_reset_preserve_axis_sign(self):
        engine, _, _ = self.train()
        for i in range(481, 901):
            old = engine.basis.copy()
            t = i/60
            engine.update((-6*np.sin(t*5), 8*np.sin(t*5), 4*np.sin(t*5)), t)
            self.assertGreater(engine.basis[0] @ old[0], .999)
        saved = engine.basis.copy()
        engine.hold(15.1)
        np.testing.assert_array_equal(engine.basis, saved)
        self.assertEqual(engine.basis_state, 'holding')
        self.assertIsNone(engine.update((0, 0, 0), float('nan')))
        engine.update((0, 0, 0), 16.)
        np.testing.assert_array_equal(engine.basis, np.eye(3))

    def test_equal_competing_directions_do_not_force_an_arbitrary_axis(self):
        engine = DominantMotion()
        # An exact three-second window has three equal circular cycles.
        for i in range(601):
            t = i/60
            engine.update((5*np.sin(t*2*np.pi), 5*np.cos(t*2*np.pi), 0), t)
        self.assertIn(engine.basis_state, ('learning', 'holding'))
        self.assertEqual(engine.basis_confidence, 0.)
        np.testing.assert_array_equal(engine.basis, np.eye(3))

    def test_cycle_uses_full_oblique_span_not_the_largest_component(self):
        dominant, cycle = DominantMotion(), StrokeCycle()
        previous = np.zeros(3)
        for i in range(601):
            t = i/60
            value = np.full(3, 3*np.sin(t*5))
            dominant.update(value, t)
            cycle.update(dominant, MotionReference('v2', step=tuple(value-previous)), t, True)
            previous = value
        self.assertGreater(dominant.stroke_span, 9.)
        self.assertEqual(cycle.state, 'full')
        self.assertEqual(cycle.peak, 1.)

    def test_preview_draws_actual_immutable_basis_and_describes_proxy_coordinates(self):
        engine, _, _ = self.train()
        reference = MotionReference('v2', 'ready', (40, 30, 280, 210), basis=engine.axes_xyz, basis_state='tracking')
        image = np.zeros((240, 320, 3), np.uint8)
        shown = draw_reference(image, reference)
        self.assertTrue(shown[80:160, 90:230].any())
        self.assertFalse(image.any())
        snapshot = reference.basis
        engine._turn_basis(np.array((1., 0., 0.)), .2)
        self.assertEqual(reference.basis, snapshot)
        self.assertEqual(projected_axes(snapshot).shape, (3, 2))
        self.assertIsNone(projected_axes(((float('nan'), 0, 1),)*3))
        self.assertIn('3D 主轴', '\n'.join(reference_lines(reference, lambda zh, en: zh)))
        self.assertIn('3D axis', '\n'.join(reference_lines(reference, lambda zh, en: en)))

    def test_real_v2_and_cycle_share_oblique_frame_with_pose_assistance(self):
        scene = MotionScene(size=(400, 400))
        engines = [make_analyzer(tracker_mode=mode, output_mode='Six Axis', hybrid_v2_pose_enabled=assisted)
                   for mode, assisted in ((HYBRID_V2_MODE, False), (HYBRID_V2_MODE, True), (STROKE_CYCLE_MODE, False))]
        engines[1].backend = FakePose()
        for i in range(151):
            t = i/30
            wave = np.sin(t*5)
            frame = scene.frame(x=-10*wave, y=14*wave, scale=np.exp(.035*wave), camera_x=4*np.sin(t*3))
            for engine in engines:
                engine.process(frame, t)
            for engine in engines[1:]:
                np.testing.assert_allclose(engine.dominant.basis, engines[0].dominant.basis, atol=1e-12)
        basis = engines[0].dominant.basis[0]
        self.assertTrue(np.all(abs(basis) > .2), basis)
        self.assertLess(basis[2]*basis[0], 0)
        for engine in engines:
            self.assertEqual(engine.visual_frame.reference.basis, engine.dominant.axes_xyz)


if __name__ == '__main__':
    unittest.main()
