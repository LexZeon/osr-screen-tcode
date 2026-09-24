import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from motion_scenes import ReachScene
from osr_screen_tcode.reach_target import ReachTarget, ReachObservation, appearance
from osr_screen_tcode.target_regions import proposals
from osr_screen_tcode.motion_reference import MotionReference, draw_reference, reference_lines
from osr_screen_tcode.dominant_motion import DominantMotion
from osr_screen_tcode.fused_l0 import FusedL0
from osr_screen_tcode.visual_pipeline import make_analyzer
from osr_screen_tcode.config import HYBRID_V2_MODE, STROKE_CYCLE_MODE


class ReachGeometryTests(unittest.TestCase):
    def seeded(self):
        tracker = ReachTarget()
        tracker.target = np.array((500., 180.))
        tracker.box = (480., 130., 590., 230.)
        tracker.direction = np.array((1., 0.))
        tracker.far = 300.
        tracker.confirmed = True
        tracker.selected_at, tracker.last_seen, tracker.stamp = -1., 0., 0.
        tracker.support_count, tracker.serial = 6, 1
        return tracker

    def update(self, tracker, x, stamp, *, y=180., pan=0., target=True):
        source = np.array([(x+dx, y+dy) for dx in (-15, 0, 15) for dy in (-12, 0, 12)])
        fixed = np.array([(px, py) for px in (520., 540., 560.) for py in (145., 175., 205.)])
        a = np.concatenate((source, fixed if target else np.empty((0, 2))))
        b = a+(pan, 0)
        # Only actual on-screen points can support a target fit.
        visible = (b[:, 0] < 640) & (b[:, 0] >= 0)
        a, b = a[visible], b[visible]
        camera = np.float64([[1, 0, pan], [0, 1, 0]])
        ref = MotionReference('v2', 'ready', (x+pan-20, y-20, x+pan+20, y+20), step=(1., 0., 0.))
        dominant = SimpleNamespace(stroke_span=20., basis=np.array(((0., 0., 1.), (1., 0., 0.), (0., 1., 0.))))
        return tracker.update(np.zeros((360, 640, 3), np.uint8), dominant, ref,
            (a, b, camera, source, source+(pan, 0)), stamp)

    def test_percentage_uses_axis_origin_and_reaches_exact_bottom_only_at_target(self):
        tracker = self.seeded()
        values = [self.update(tracker, x, (i+1)/10) for i, x in enumerate((200., 350., 500.))]
        np.testing.assert_allclose([v.remaining for v in values], (1., .5, 0.))
        self.assertTrue(all(v.state == 'ready' for v in values))
        # Crossing the target's x coordinate at another height is not arrival.
        result = self.update(tracker, 500., .4, y=200.)
        self.assertGreater(result.remaining, .05)

    def test_passing_beyond_target_rejects_it_instead_of_creating_double_frequency(self):
        tracker = self.seeded()
        self.update(tracker, 450., .1)
        result = self.update(tracker, 550., .2)
        self.assertEqual(result.state, 'unresolved')
        self.assertIsNone(result.point)

    def test_offscreen_position_is_not_clamped_and_missing_tracks_do_not_confirm_arrival(self):
        tracker = self.seeded()
        result = self.update(tracker, 200., .1, pan=200.)
        self.assertEqual(result.state, 'holding')
        self.assertTrue(result.offscreen)
        self.assertEqual(result.point, (700., 180.))
        self.assertIsNone(result.remaining)
        self.assertEqual(tracker.last_seen, 0.)
        ref = MotionReference('v2', 'ready', (380., 160., 420., 200.), target_point=result.point,
            target_kind='tracked_held', target_offscreen=True, reach_state='holding')
        frame = np.zeros((360, 640, 3), np.uint8)
        drawn = draw_reference(frame, ref)
        self.assertGreater(np.count_nonzero(drawn[:, -25:]), 0)
        self.assertEqual(ref.target_point, (700., 180.))
        self.assertIn('画外', '\n'.join(reference_lines(ref, lambda zh, en: zh)))
        self.assertIn('not its position', '\n'.join(reference_lines(ref, lambda zh, en: en)))

    def test_target_appearance_is_compared_to_itself_and_unknown_camera_gap_drops_identity(self):
        tracker = self.seeded()
        pixels = np.full((360, 640, 3), (30, 135, 225), np.uint8)
        fixed = np.array([(x, y) for x in (520., 540., 560.) for y in (145., 175., 205.)])
        tracker.signature = appearance(pixels, fixed)
        # Geometry alone would accept this replacement background; the target's
        # own color signature must prevent false continued ownership.
        missing = self.update(tracker, 200., .1)
        self.assertEqual(missing.state, 'holding')
        self.assertIsNone(missing.remaining)
        dominant = SimpleNamespace(stroke_span=None)
        unregistered = tracker.update(pixels, dominant, MotionReference('v2', 'holding'), None, .2)
        self.assertIsNone(unregistered.point)
        result = self.update(tracker, 200., .3)
        self.assertIsNone(result.point)

    def test_different_appearance_object_is_selected_by_reachable_boundary(self):
        scene = ReachScene()
        frame, _, _ = scene.frame(0)
        source_roi = (269., 132., 341., 232.)
        samples = np.array([(x, y) for x in range(492, 581, 10) for y in range(130, 231, 10)], float)
        centers = np.column_stack((np.linspace(130., 455., 60), np.full(60, 182.)))
        found = proposals(frame, source_roi, (305., 182.), np.array((1., 0.)), centers, samples)
        self.assertTrue(found)
        self.assertAlmostEqual(found[0][1][0], 485., delta=3.)
        self.assertAlmostEqual(found[0][1][1], 182., delta=1.)

    def test_target_keeps_own_tracks_during_source_loss_without_measuring_reach(self):
        tracker = self.seeded()
        fixed = np.array([(x, y) for x in (520., 540., 560.) for y in (145., 175., 205.)])
        empty = np.empty((0, 2))
        camera = np.float64([[1, 0, 5], [0, 1, 0]])
        result = tracker.update(np.zeros((360, 640, 3), np.uint8), SimpleNamespace(),
            MotionReference('v2', 'holding'), (fixed, fixed+(5, 0), camera, empty, empty), .1)
        self.assertEqual(result.state, 'holding')
        np.testing.assert_allclose(result.point, (505., 180.))
        self.assertIsNone(result.remaining)
        self.assertEqual(tracker.last_seen, .1)
        self.assertFalse(tracker.unregistered)
        self.assertFalse(tracker.history)

    def test_own_pixels_keep_object_identity_when_source_camera_pair_is_missing(self):
        tracker = self.seeded()
        rng = np.random.default_rng(731)
        frame = rng.integers(0, 255, (360, 640, 3), np.uint8)
        points = np.float32([(x, y) for x in (520, 540, 560) for y in (145, 175, 205)])
        tracker.signature = appearance(frame, points)
        tracker._remember_pixels(frame, 0., points)
        camera = np.float32([[1, 0, 5], [0, 1, 0]])
        moved = cv2.warpAffine(frame, camera, (640, 360))
        held = tracker.update(moved, SimpleNamespace(), MotionReference('v2', 'holding'), None, .1)
        self.assertEqual(held.key, 1)
        np.testing.assert_allclose(held.point, (505., 180.), atol=.05)
        self.assertIsNone(held.remaining)
        self.assertEqual(held.state, 'holding')
        self.assertEqual(tracker.last_seen, .1)
        source = np.float32([(x, y) for x in (230, 250, 270) for y in (160, 180, 200)])
        a = np.concatenate((source, points+(5, 0)))
        resumed = tracker.update(cv2.warpAffine(moved, camera, (640, 360)), SimpleNamespace(),
            MotionReference('v2', 'ready', (230., 160., 270., 200.), subject_origin=(255., 180.)),
            (a, a+(5, 0), camera, source, source+(5, 0)), .2)
        self.assertEqual(resumed.key, 1)
        self.assertEqual(resumed.state, 'ready')
        np.testing.assert_allclose(resumed.point, (510., 180.), atol=.05)
        self.assertIsNotNone(resumed.remaining)

    def test_object_recovery_does_not_apply_camera_zoom_twice_to_retreat_range(self):
        tracker = self.seeded()
        frame = np.random.default_rng(882).integers(0, 255, (360, 640, 3), np.uint8)
        frame = cv2.GaussianBlur(frame, (5, 5), 1.)
        points = np.float32([(x, y) for x in (520, 540, 560) for y in (145, 175, 205)])
        tracker.ranges.append((0., 300.))
        tracker._remember_pixels(frame, 0., points)
        empty = np.empty((0, 2))
        zoom = np.float32([[1.02, 0, 0], [0, 1.02, 0]])
        held = tracker.update(np.zeros_like(frame), SimpleNamespace(), MotionReference('v2', 'holding'),
                              (empty, empty, zoom, empty, empty), .1)
        self.assertEqual(held.state, 'holding')
        resumed_frame = cv2.warpAffine(frame, np.float32([[1.04, 0, 0], [0, 1.04, 0]]), (640, 360))
        result = tracker.update(resumed_frame, SimpleNamespace(),
            MotionReference('v2', 'ready', (190., 170., 225., 205.), subject_origin=(208., 187.2)),
            (empty, empty, zoom, empty, empty), .2)
        self.assertEqual(result.state, 'ready')
        self.assertAlmostEqual(result.span, 312., delta=.4)


class ReachPipelineTests(unittest.TestCase):
    def test_cycle_and_pose_assistance_share_target_and_finish_paused_arrival(self):
        from test_visual_pipeline import FakePose
        scene = ReachScene()
        base = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        cycle = make_analyzer(tracker_mode=STROKE_CYCLE_MODE)
        assisted = make_analyzer(tracker_mode=STROKE_CYCLE_MODE, output_mode='Six Axis', hybrid_v2_pose_enabled=True)
        assisted.backend = FakePose()
        ready = 0
        for i in range(146):
            frame, _, _ = scene.frame(i/30)
            base.process(frame, i/30)
            single, six = cycle.process(frame, i/30), assisted.process(frame, i/30)
            self.assertEqual(cycle.reach_target.last, base.reach_target.last)
            self.assertEqual(assisted.reach_target.last, base.reach_target.last)
            self.assertAlmostEqual(single.positions['L0'], six.positions['L0'])
            self.assertEqual((six.positions['L1'], six.positions['L2']), (.5, .5))
            ready += base.reach_target.last.state == 'ready'
        self.assertGreater(ready, 20)
        self.assertEqual(cycle.cycle.peak, 1.)
        # A measured arrival followed by identical frames must finish its
        # continuous handoff to bottom rather than freeze partway there.
        arrived = replace(cycle.reach_target.last, state='ready', remaining=0., delta=0.)
        values = [cycle.cycle.value]
        with patch.object(cycle.reach_target, 'update', return_value=arrived):
            for i in range(146, 267):
                values.append(cycle.process(frame, i/30).positions['L0'])
        self.assertEqual(values[-1], 0.)
        self.assertLess(np.max(np.abs(np.diff(values))), .15)
        self.assertEqual(cycle.cycle.state, 'stopped')
        self.assertIsNone(cycle.point_l0.fusion.rhythm.model)

    def test_confirmed_arrival_settles_to_bottom_even_when_pixels_pause(self):
        fused, dominant = FusedL0(.8), DominantMotion(adaptive_l0=True)
        point = SimpleNamespace(state='unresolved', point=None, step=0.)
        ref = MotionReference('v2', 'tracking', (100., 70., 160., 150.), reason='repeated')
        arrival = ReachObservation('ready', (130., 110.), remaining=0., key=1)
        values = []
        for i in range(30):
            values.append(fused.update(dominant, ref, point, None, None, i/30, (240, 320), .8, arrival))
        self.assertEqual(values[0], .8)
        self.assertEqual(values[-1], 0.)
        self.assertLessEqual(np.max(np.abs(np.diff(values))), .14)
        self.assertIsNone(fused.rhythm.model)

    def test_actual_two_object_frames_keep_target_independent_and_camera_measurements_unchanged(self):
        scene = ReachScene()
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        baseline = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        observed, outputs = [], []
        for i in range(226):
            stamp = i/30
            frame, _, _ = scene.frame(stamp)
            result = engine.process(frame, stamp)
            with patch.object(baseline.reach_target, 'update', return_value=ReachObservation()):
                baseline.process(frame, stamp)
            np.testing.assert_array_equal(engine.motion.values, baseline.motion.values)
            reach = engine.reach_target.last
            outputs.append(result.positions['L0'])
            if reach.state == 'ready':
                observed.append((reach.point, reach.remaining, result.positions['L0']))
        self.assertGreater(len(observed), 60)
        self.assertLess(np.max(np.abs(np.array([r[0][0] for r in observed])-485.)), 4.)
        self.assertTrue(all(122 <= r[0][1] <= 240 for r in observed))
        self.assertGreater(np.ptp(outputs[-150:]), .7)
        self.assertGreater(np.corrcoef([r[1] for r in observed], [r[2] for r in observed])[0, 1], .9)

    def test_cut_to_visible_proxy_with_both_contact_objects_absent_still_outputs(self):
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        engine.reach_target = ReachGeometryTests().seeded()
        engine.point_l0.fusion.arrival_active = True
        scene = ReachScene(target=False)
        values = []
        for i in range(166):
            frame, _, _ = scene.frame(i/30)
            values.append(engine.process(frame, i/30).positions['L0'])
            self.assertIsNone(engine.visual_frame.reference.reach_progress)
            self.assertIsNone(engine.reach_target.last.point)
        self.assertGreater(np.ptp(values[-75:]), .7)
        self.assertFalse(engine.point_l0.fusion.arrival_active)

    def test_target_entry_loss_and_recovery_continue_from_current_output(self):
        fused, dominant = FusedL0(.6), DominantMotion(adaptive_l0=True)
        point = SimpleNamespace(state='unresolved', point=None, step=0.)
        ref = MotionReference('v2', 'ready', (100., 70., 160., 150.), step=(1., 0., 0.))
        previous = 0.
        for i in range(1, 121):
            stamp = i/30
            value = 10*np.sin(stamp*5)
            ordinary = dominant.update((value, 0., 0.), stamp)['L0']
            arrival = ReachObservation('ready', (300., 100.), remaining=.5+.3*np.sin(stamp*5), key=1, delta=.01)
            if 60 <= i < 90:
                arrival = ReachObservation('holding', (300., 100.), key=1)
            ref = replace(ref, step=(value-previous, 0., 0.))
            before = fused.output
            old_key = fused.key
            fused.update(dominant, ref, point, None, ((130., 110.), .5), stamp, (240, 320), ordinary, arrival)
            if i in (1, 60) or (fused.key != old_key and fused.key == ('arrival', 1)):
                self.assertAlmostEqual(fused.output, before)
            self.assertLess(abs(fused.output-before), .15)
            previous = value
        self.assertTrue(fused.arrival_active)


if __name__ == '__main__':
    unittest.main()
