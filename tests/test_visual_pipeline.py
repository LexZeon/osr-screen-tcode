import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from osr_screen_tcode import config
from osr_screen_tcode.analyzer import RealtimeAnalyzer
from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE, RTM_POSE_3D_MODE, STROKE_CYCLE_MODE
from osr_screen_tcode.pose_backends import RtmPose3dResult
from osr_screen_tcode.visual_pipeline import LabAnalyzer, VisualSettings, make_analyzer, resize_for_processing
from osr_screen_tcode.visual_lab.stabilizer import Options
from osr_screen_tcode.pose_output import l0_translation_gain, l0_rotation_gain
from osr_screen_tcode.tcode import MultiAxisSafeOutput
from motion_scenes import MotionScene


class FakePose:
    def __init__(self):
        self.points = np.array([(100 + (i % 2) * 50, 40 + i * 15) for i in range(17)], np.float32)
        self.scores = np.ones(17)
        self.calls = 0
        self._load_failed = False
        self.status = "tracking"
        self.missing = False

    def infer(self, frame):
        self.calls += 1
        self.shape = frame.shape
        if self.missing:
            return None
        p3 = np.zeros((17, 3), np.float32)
        p3[:, :2] = self.points
        return RtmPose3dResult(p3, self.points.copy(), self.scores.copy())


class PipelineTests(unittest.TestCase):
    def test_tiny_and_one_pixel_frames_remain_missing_without_generated_motion(self):
        # Cover the real analysis chain, not only the resize function. A long
        # cross-monitor strip can legitimately reduce to a one-pixel short edge.
        for shape in ((1, 640), (640, 1), (16, 16), (16, 20000), (20000, 16)):
            frame = np.random.default_rng(24).integers(0, 255, (*shape, 3), dtype=np.uint8)
            for mode in (HYBRID_V2_MODE, STROKE_CYCLE_MODE):
                for output_mode in ("L0 Only", "Six Axis"):
                    with self.subTest(shape=shape, mode=mode, output=output_mode):
                        engine = make_analyzer(tracker_mode=mode, output_mode=output_mode)
                        for index in range(3):
                            moved = np.roll(frame, index, axis=int(shape[1] > shape[0]))
                            result = engine.process(moved, timestamp=index / 30)
                            self.assertEqual(result.confidence, 0)
                            self.assertEqual(result.activity, 0)
                            self.assertTrue(all(value == .5 for value in result.positions.values()))
                            self.assertIsNone(engine.visual_frame.observation.values)
                        self.assertEqual(engine.visual_frame.observation.state, "missing")
                        expected = resize_for_processing(frame, 640)
                        np.testing.assert_array_equal(engine.visual_frame.pair[0],
                                                      resize_for_processing(moved, 640))
                        self.assertEqual(result.preview_bgr.shape, expected.shape)

    def test_processing_resize_preserves_complete_extreme_regions(self):
        for height, width in ((1080, 1920), (1920, 1080), (16, 20000), (20000, 16)):
            frame = np.zeros((height, width, 3), np.uint8)
            frame[:] = (30, 90, 180)
            if width >= height:
                frame[:, width // 2:] = (120, 210, 60)
            else:
                frame[height // 2:] = (120, 210, 60)
            for edge in (320, 480, 640, 960, 1280):
                with self.subTest(shape=(height, width), edge=edge):
                    result = resize_for_processing(frame, edge)
                    ratio = edge / max(height, width)
                    self.assertEqual(result.shape, (max(1, round(height * ratio)),
                                                    max(1, round(width * ratio)), 3))
                    np.testing.assert_array_equal(result[0, 0], (30, 90, 180))
                    np.testing.assert_array_equal(result[-1, -1], (120, 210, 60))
        small = np.zeros((16, 64, 3), np.uint8)
        self.assertIs(resize_for_processing(small, 640), small)

    def pose_engine(self, options=Options(False, False, False, False), **kwargs):
        engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, output_mode="Six Axis",
                               visual_settings=VisualSettings(options=options), **kwargs)
        engine.backend = FakePose()
        return engine

    def calibrate(self, engine):
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(21):
            result = engine.process(frame, timestamp=i / 60)
        self.assertEqual(engine.visual_frame.observation.state, "ready")
        return frame, result

    def test_original_hybrid_l0_baseline_and_no_extra_axes(self):
        # Recorded before this port from the unmodified hybrid L0 implementation.
        expected = [0.5, 0.39866160413255103, 0.2722395201178528] + [0.21761736804124848] * 9
        engine = make_analyzer(tracker_mode=HYBRID_MODE, output_mode="Six Axis")
        self.assertIs(type(engine), RealtimeAnalyzer)
        for i, l0 in enumerate(expected):
            frame = np.zeros((240, 320, 3), np.uint8)
            cv2.rectangle(frame, (70, 30+i*6), (210, 100+i*6), (190, 210, 180), -1)
            result = engine.process(frame)
            self.assertEqual(set(result.positions), {"L0"})
            self.assertAlmostEqual(result.positions["L0"], l0, places=7)

    def test_image_motion_v2_single_axis_emits_only_l0(self):
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE, output_mode="L0 Only")
        scene = MotionScene()
        first = scene.frame()
        engine.process(first, timestamp=0)
        engine.process(scene.frame(y=3), timestamp=1/30)
        result = engine.process(scene.frame(y=6), timestamp=2/30)
        self.assertEqual(set(result.positions), {"L0"})
        self.assertGreater(result.positions["L0"], 0.51)
        self.assertEqual(engine.visual_frame.pair[0].shape, first.shape)

    def test_v2_missing_observation_is_not_zero_motion(self):
        engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
        frame = np.zeros((240, 320, 3), np.uint8)
        engine.process(frame, timestamp=0)
        result = engine.process(frame, timestamp=0.05)
        self.assertEqual(engine.visual_frame.observation.state, "missing")
        self.assertEqual(result.confidence, 0)
        self.assertEqual(result.positions, {"L0": 0.5})

    def test_one_inference_per_frame_pair_is_derived_from_same_input(self):
        engine = self.pose_engine()
        frame = np.full((720, 1280, 3), 17, np.uint8)
        engine.process(frame, timestamp=0)
        self.assertEqual(engine.backend.calls, 1)
        self.assertEqual(engine.backend.shape, (360, 640, 3))
        for shown in engine.visual_frame.pair:
            self.assertEqual(shown.shape, (360, 640, 3))
            np.testing.assert_array_equal(shown[350, 630], [17, 17, 17])

    def test_absolute_translation_remains_when_person_stops_moving(self):
        engine = self.pose_engine()
        frame, _ = self.calibrate(engine)
        engine.backend.points += np.float32([12, -8])
        first = engine.process(frame, timestamp=21/60)
        second = engine.process(frame, timestamp=22/60)
        self.assertAlmostEqual(first.positions["L0"], 0.52, places=5)
        self.assertAlmostEqual(first.positions["L2"], 0.53, places=5)
        self.assertEqual(first.positions["L2"], second.positions["L2"])
        self.assertAlmostEqual(second.positions["L1"], 0.5, places=5)

    def test_legacy_blend_source_is_forced_to_v2_and_changes_only_l0(self):
        for source in (HYBRID_MODE, HYBRID_V2_MODE):
            engine = self.pose_engine(rtm_hybrid_l0_enabled=True, rtm_hybrid_l0_weight=1, hybrid_source=source)
            reference = self.pose_engine()
            self.assertEqual(engine.hybrid_source, HYBRID_V2_MODE)
            self.assertFalse(hasattr(engine, "hybrid"))
            frame, _ = self.calibrate(engine)
            self.calibrate(reference)
            engine.backend.points += np.float32([10, -8])
            reference.backend.points += np.float32([10, -8])
            result = engine.process(frame, timestamp=21/60)
            baseline = reference.process(frame, timestamp=21/60)
            for axis in ("L1", "L2", "R0", "R1", "R2"):
                self.assertEqual(result.positions[axis], baseline.positions[axis])

    def test_cut_without_pose_has_no_old_skeleton_or_measurement(self):
        engine = self.pose_engine(Options(True, True, True, True))
        frame, _ = self.calibrate(engine)
        engine.backend.missing = True
        result = engine.process(np.full_like(frame, 240), timestamp=21/60)
        self.assertTrue(engine.visual_frame.reset)
        self.assertTrue(np.isnan(engine.stabilizer.xy).all())
        self.assertEqual(engine.visual_frame.observation.state, "missing")
        self.assertEqual(result.activity, 0)

    def test_v2_blend_uses_image_motion_and_changes_l0_only(self):
        scene = MotionScene(size=(400, 400))
        mixed = self.pose_engine(rtm_hybrid_l0_enabled=True, rtm_hybrid_l0_weight=.6, hybrid_source=HYBRID_MODE)
        reference = self.pose_engine()
        for i in range(40):
            frame = scene.frame(y=i)
            result = mixed.process(frame, i/60)
            base = reference.process(frame, i/60)
        self.assertGreater(result.positions["L0"], base.positions["L0"] + .03)
        for axis in ("L1", "L2", "R0", "R1", "R2"):
            self.assertEqual(result.positions[axis], base.positions[axis])

    def test_gap_clears_velocity_and_recalibrates(self):
        engine = self.pose_engine(Options(True, True, True, True))
        frame, _ = self.calibrate(engine)
        engine.backend.points += 30
        engine.process(frame, timestamp=1)
        self.assertTrue(engine.visual_frame.reset)
        self.assertEqual(engine.visual_frame.observation.state, "calibrating")
        np.testing.assert_allclose(engine.stabilizer.xy, engine.backend.points, atol=1e-4)

    def test_live_resolution_and_options_reset_without_reloading_model(self):
        engine = self.pose_engine()
        frame, _ = self.calibrate(engine)
        backend = engine.backend
        settings = VisualSettings(320, Options(True, False, True, True), 9)
        engine.configure(settings)
        engine.process(frame, timestamp=21/60)
        self.assertIs(engine.backend, backend)
        self.assertEqual(engine.visual_frame.generation, 9)
        self.assertEqual(engine.visual_frame.pair[0].shape, (320, 320, 3))
        self.assertEqual(engine.visual_frame.observation.state, "calibrating")

    def test_video_timestamps_not_wall_clock_control_calibration(self):
        a, b = self.pose_engine(), self.pose_engine()
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(25):
            with patch("osr_screen_tcode.visual_pipeline.time.perf_counter", return_value=1000+i*3):
                left = a.process(frame, timestamp=i/60)
            with patch("osr_screen_tcode.visual_pipeline.time.perf_counter", return_value=2000+i*0.001):
                right = b.process(frame, timestamp=i/60)
            self.assertEqual(left.positions, right.positions)
            self.assertEqual(a.visual_frame.observation, b.visual_frame.observation)

    def test_duplicate_timestamp_does_not_infer_twice(self):
        engine = self.pose_engine()
        frame, _ = self.calibrate(engine)
        count = engine.backend.calls
        engine.process(frame, timestamp=20/60)
        self.assertEqual(engine.backend.calls, count)

    def test_3d_cannot_be_enabled_through_legacy_arguments(self):
        with self.assertRaisesRegex(ValueError, "removed"):
            RealtimeAnalyzer(rtm_pose_3d_enabled=True)


class CouplingTests(unittest.TestCase):
    def test_pose_r1_r2_contract_only_above_two_thirds_l0(self):
        output = MultiAxisSafeOutput(['R1', 'L0', 'R2', 'R0'], min_value=0, max_value=9999,
                                     max_step=9999, enable_endpoint_guard=False, enable_extreme_reset=False,
                                     couple_l0_rotation=True)
        for l0, gain in ((0, 1), (1/3, 1), (2/3, 1), (5/6, .75), (1, .5)):
            raw = {'L0': l0, 'R1': .7, 'R2': .3, 'R0': .7}
            self.assertAlmostEqual(l0_rotation_gain(l0), gain)
            values = output.next_command(raw, 1).values
            self.assertAlmostEqual(values['R1'], 9999*(.5+.2*gain), delta=1)
            self.assertAlmostEqual(values['R2'], 9999*(.5-.2*gain), delta=1)
            self.assertEqual(values['R0'], 6999)
            self.assertEqual((raw['R1'], raw['R2']), (.7, .3))

    def test_rotation_coupling_uses_inverted_limited_l0_and_keeps_zero_travel(self):
        output = MultiAxisSafeOutput(['R1', 'L0', 'R2'], min_value=1000, max_value=9000,
                                     max_step=100, invert_l0=True, axis_position_scales={'R1': .5, 'R2': 0},
                                     enable_endpoint_guard=False, enable_extreme_reset=False, couple_l0_rotation=True)
        gains = []
        original = output._map_axis
        def record(axis, position, position_gain=1):
            if axis == 'R1':
                gains.append(position_gain)
            return original(axis, position, position_gain)
        output._map_axis = record
        previous = dict(output._values)
        for i in range(50):
            values = output.next_command({'L0': 0, 'R1': .7, 'R2': .7}, 1).values
            self.assertTrue(all(abs(values[a]-previous[a]) <= 100 for a in values))
            self.assertEqual(values['R2'], 5000)
            previous = values
        self.assertEqual(gains[0], 1)
        self.assertEqual(gains[-1], .5)
        self.assertEqual(values['L0'], 9000)
        self.assertEqual(values['R1'], 5400)

    def output(self, **kwargs):
        return MultiAxisSafeOutput(["L0", "L1", "L2"], min_value=0, max_value=9999,
                                   max_step=kwargs.pop("max_step", 9999),
                                   enable_endpoint_guard=False, enable_extreme_reset=False,
                                   couple_l0_translation=True, **kwargs)

    def test_low_middle_high_gain_is_symmetric(self):
        for position, expected in ((0, 1), (0.25, 1.75), (0.5, 2.5), (0.75, 1.75), (1, 1)):
            self.assertEqual(l0_translation_gain(position), expected)

    def test_pose_gain_contracts_fixed_translations_at_both_l0_limits(self):
        output = self.output(coupling_endpoint_gain=0.5, coupling_middle_gain=3.5, coupling_peak_position=2/3,
                             coupling_lower_knot=(1/3, 1.0))
        raw = {"L0": 0.5, "L1": 0.6, "L2": 0.4}
        for l0, gain in ((0, .5), (1/6, .75), (1/3, 1.0), (.5, 2.25), (2/3, 3.5), (5/6, 2.0), (1, .5)):
            raw["L0"] = l0
            result = output.next_command(raw, 1).values
            self.assertAlmostEqual(l0_translation_gain(l0, .5, 3.5, 2/3, (1/3, 1.0)), gain)
            self.assertAlmostEqual(result["L1"], 9999*(.5+.1*gain), delta=1)
            self.assertAlmostEqual(result["L2"], 9999*(.5-.1*gain), delta=1)
            self.assertEqual((raw["L1"], raw["L2"]), (.6, .4))

    def test_fixed_l1_l2_move_toward_center_as_l0_descends_from_middle(self):
        output = self.output()
        raw = {"L0": 0.5, "L1": 0.6, "L2": 0.4}
        distances = []
        for l0 in (0.5, 0.4, 0.25, 0):
            raw["L0"] = l0
            result = output.next_command(raw, 1).values
            distances.append(abs(result["L1"]-5000))
            self.assertEqual((raw["L1"], raw["L2"]), (0.6, 0.4))
            self.assertLess(result["L2"], 5000)
        self.assertEqual(distances, sorted(distances, reverse=True))
        self.assertGreater(distances[0], distances[-1]*2.4)

    def test_gain_uses_actual_speed_limited_l0_instead_of_requested_l0(self):
        output = self.output(max_step=100, coupling_endpoint_gain=0.5, coupling_middle_gain=3.5, coupling_peak_position=2/3,
                             coupling_lower_knot=(1/3, 1.0))
        calls = []
        original = output._map_axis
        def record(axis, position, position_gain=1):
            calls.append((axis, position_gain))
            return original(axis, position, position_gain)
        output._map_axis = record
        values = output.next_command({"L0": 0, "L1": 0.6, "L2": 0.4}, 1).values
        self.assertEqual(values["L0"], 4900)
        self.assertAlmostEqual(dict(calls)["L1"], l0_translation_gain(4900/9999, .5, 3.5, 2/3, (1/3, 1.0)))
        self.assertTrue(all(abs(v-5000) <= 100 for v in values.values()))

    def test_limits_inversion_zero_travel_and_manual_center_still_apply(self):
        output = self.output(axis_limits={a: (3000, 7000) for a in ("L0", "L1", "L2")},
                             axis_position_scales={"L1": 0}, axis_position_inverts={"L2": True})
        result = output.next_command({"L0": 0.5, "L1": 1, "L2": 1}, 1).values
        self.assertEqual(result["L1"], 5000)
        self.assertEqual(result["L2"], 3000)
        self.assertEqual(output.center_command().values, {a: 5000 for a in result})


class MigrationTests(unittest.TestCase):
    def test_legacy_3d_model_is_not_reused_and_new_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"config.json"
            path.write_text(json.dumps({"tracker_mode": RTM_POSE_3D_MODE,
                "extra": {"rtm_pose_3d_model_path": "old-3d.onnx", "rtm_pose_3d_enabled": True,
                          "rtm_pose_flow_enabled": True, "visual_processing_edge": 960,
                          "rtm_pose_reject_enabled": True, "rtm_hybrid_source": HYBRID_V2_MODE}}), encoding="utf-8")
            with patch.object(config, "CONFIG_PATH", path), patch.object(config, "APP_DIR", Path(directory)):
                cfg = config.AppConfig.load()
                self.assertEqual(cfg.tracker_mode, RTM_POSE_2D_MODE)
                self.assertEqual(cfg.last_sink, "Log only")
                self.assertEqual(cfg.extra.get("rtm_pose_2d_model_path"), "")
                self.assertNotIn("rtm_pose_3d_model_path", cfg.extra)
                cfg.save()
                again = config.AppConfig.load()
                self.assertEqual(again.extra["visual_processing_edge"], 960)
                self.assertTrue(again.extra["rtm_pose_reject_enabled"])
                self.assertTrue(again.extra["rtm_pose_flow_enabled"])
                self.assertEqual(again.extra["rtm_hybrid_source"], HYBRID_V2_MODE)

    def test_new_visual_defaults_and_invalid_resolution(self):
        extra = {"visual_processing_edge": "bad", "rtm_hybrid_source": "bad"}
        config.normalize_visual_settings(extra)
        self.assertEqual(extra["visual_processing_edge"], 640)
        self.assertEqual(extra["rtm_hybrid_source"], HYBRID_V2_MODE)
        self.assertFalse(extra["rtm_pose_flow_enabled"])
