import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig, HYBRID_V2_MODE
from osr_screen_tcode.visual_pipeline import LabAnalyzer
from motion_scenes import MotionScene


class MemoryVideo:
    def __init__(self, frames):
        self.frames, self.index, self.released = frames, 0, False

    def isOpened(self):
        return True

    def get(self, key):
        return 30.0 if key == cv2.CAP_PROP_FPS else len(self.frames)

    def read(self):
        if self.index >= len(self.frames):
            return False, None
        frame = self.frames[self.index]
        self.index += 1
        return True, frame.copy()

    def release(self):
        self.released = True

    def grab(self):
        ok, _ = self.read()
        return ok


class OutputPresetTests(unittest.TestCase):
    def test_v1_export_warms_on_every_frame_and_continues_filtered_script_position(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        from osr_screen_tcode.motion_reference import MotionReference
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from osr_screen_tcode.recorder import MultiAxisFunscriptRecorder as MultiAxisRecorder
        from test_visual_pipeline import FakePose
        frames = [np.zeros((400, 400, 3), np.uint8)]*30
        engines, recorded = [], []
        def factory(**kwargs):
            engine = make_analyzer(**kwargs)
            engine.backend = FakePose()
            infer = engine.backend.infer
            def pose(frame):
                engine.backend.missing = engine.backend.calls >= 12
                return infer(frame)
            engine.backend.infer = pose
            engine.pose_recovery.update = Mock(return_value=.68)
            v1 = SimpleNamespace(motion_reference=MotionReference('v1', 'ready', step=(0, .8, 0)))
            v1.process = Mock(side_effect=lambda frame: SimpleNamespace(
                positions={'L0': .1 if engine.backend.calls <= 20 else .15}, confidence=1))
            engine.pose_fast.factory = Mock(return_value=v1)
            engines.append((engine, v1))
            return engine
        original = MultiAxisRecorder.add_at
        def record(recorder, positions, at, *args):
            recorded.append((at, positions['L0']))
            return original(recorder, positions, at, *args)
        with patch.object(AppConfig, 'load', return_value=AppConfig(last_sink='Log only', tracker_mode=RTM_POSE_2D_MODE)), patch.object(AppConfig, 'save'), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language='en')
            app.withdraw()
            app.pose_auto_l0_enabled.set(False)
            app.output_curve_fitting.set(True)
            app.l0_travel_scale.set(.5)
            app.invert.set(True)
            app.endpoint_slowdown_enabled.set(False)
            try:
                with patch('osr_screen_tcode.app.make_analyzer', side_effect=factory), patch('osr_screen_tcode.app.cv2.VideoCapture', return_value=MemoryVideo(frames)), patch.object(MultiAxisRecorder, 'add_at', record):
                    files = app._analyze_video_worker(Path('memory.avi'), Path(temp)/'handoff.funscript')
                self.assertEqual(engines[0][1].process.call_count, len(frames))
                self.assertEqual(len(recorded), len(frames))
                for i in range(12, 20):
                    self.assertAlmostEqual(recorded[i][1], recorded[11][1])
                self.assertAlmostEqual(recorded[20][1]-recorded[19][1], -.025)
                actions = json.loads(files[0].read_text())['actions']
                self.assertLessEqual(max(p['pos'] for p in actions)-min(p['pos'] for p in actions), 3)
            finally:
                app.on_close()

    def test_generated_l0_export_keeps_quarter_half_and_source_one_second_period(self):
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from test_visual_pipeline import FakePose
        frames = [np.zeros((400, 400, 3), np.uint8)]*151
        def factory(**kwargs):
            engine = make_analyzer(**kwargs)
            engine.backend = FakePose()
            engine.geometry._positions_from_rtm_pose_2d = lambda sample, shape, timestamp: ({'R0': .5+.08*np.sin(timestamp*6), 'R1': .5, 'R2': .5}, None)
            return engine
        with patch.object(AppConfig, 'load', return_value=AppConfig(last_sink='Log only', tracker_mode=RTM_POSE_2D_MODE)), patch.object(AppConfig, 'save'), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language='en')
            app.withdraw()
            app.l0_travel_scale.set(1)
            app.endpoint_slowdown_enabled.set(False)
            try:
                with patch('osr_screen_tcode.app.make_analyzer', side_effect=factory), patch('osr_screen_tcode.app.cv2.VideoCapture', return_value=MemoryVideo(frames)):
                    files = app._analyze_video_worker(Path('memory.avi'), Path(temp)/'auto.funscript')
                self.assertEqual(len(files), 1)
                actions = [p for p in json.loads(files[0].read_text())['actions'] if p['at'] > 1800]
                self.assertGreaterEqual(min(p['pos'] for p in actions), 25)
                self.assertLessEqual(min(p['pos'] for p in actions), 26)
                self.assertGreaterEqual(max(p['pos'] for p in actions), 49)
                self.assertLessEqual(max(p['pos'] for p in actions), 50)
                peaks = [b['at'] for a,b,c in zip(actions, actions[1:], actions[2:]) if b['pos'] > a['pos'] and b['pos'] > c['pos']]
                self.assertGreaterEqual(len(peaks), 2)
                self.assertTrue(all(abs(b-a-1000) <= 67 for a,b in zip(peaks, peaks[1:])), peaks)
            finally:
                app.on_close()

    def test_pose_pattern_changes_exported_r0_but_not_observations(self):
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from test_visual_pipeline import FakePose
        frames = [np.zeros((400, 400, 3), np.uint8)]*301
        def factory(**kwargs):
            engine = make_analyzer(**kwargs)
            engine.backend = FakePose()
            engine.geometry._positions_from_rtm_pose_2d = lambda sample, shape, timestamp: (
                {'R0': .5+.02*np.sin(2*np.pi*timestamp), 'R1': .5, 'R2': .5}, None)
            return engine
        with patch.object(AppConfig, 'load', return_value=AppConfig(last_sink='Log only', tracker_mode=RTM_POSE_2D_MODE)), patch.object(AppConfig, 'save'), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language='en')
            app.withdraw()
            app.output_mode.set('Six Axis')
            app.pose_auto_l0_enabled.set(False)
            app.output_curve_fitting.set(False)
            app.endpoint_slowdown_enabled.set(False)
            original = LabAnalyzer.process
            traces, ranges = [], []
            try:
                for enabled in (False, True):
                    app.pose_pattern_enabled.set(enabled)
                    trace = []
                    def observe(engine, frame, timestamp=None):
                        result = original(engine, frame, timestamp)
                        trace.append(dict(result.positions))
                        return result
                    with patch('osr_screen_tcode.app.make_analyzer', side_effect=factory), patch('osr_screen_tcode.app.cv2.VideoCapture', return_value=MemoryVideo(frames)), patch.object(LabAnalyzer, 'process', observe):
                        files = app._analyze_video_worker(Path('memory.avi'), Path(temp)/f'pattern{enabled}.funscript')
                    r0 = next(path for path in files if '.twist.' in path.name)
                    values = [p['pos'] for p in json.loads(r0.read_text())['actions'] if p['at'] >= 8500]
                    ranges.append(max(values)-min(values))
                    traces.append(trace)
                self.assertEqual(traces[0], traces[1])
                self.assertGreater(ranges[1], ranges[0]*1.7)
                self.assertLessEqual(ranges[1], ranges[0]*2+2)
            finally:
                app.on_close()

    def test_quarter_pattern_reaches_the_exported_script(self):
        from osr_screen_tcode.config import STROKE_CYCLE_MODE
        scene = MotionScene()
        frames = [scene.frame(y=2*np.sin(i/30*5)) for i in range(181)]
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only", tracker_mode=STROKE_CYCLE_MODE)), patch.object(AppConfig, "save"), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            app.output_curve_fitting.set(False)
            app.l0_travel_scale.set(1)
            try:
                with patch("osr_screen_tcode.app.cv2.VideoCapture", return_value=MemoryVideo(frames)):
                    files = app._analyze_video_worker(Path("memory.avi"), Path(temp)/"quarter.funscript")
                actions = json.loads(files[0].read_text())["actions"]
                # Exclude the initial smooth approach from the held center.
                steady = [point["pos"] for point in actions if point["at"] > 3000]
                self.assertTrue(steady)
                self.assertLessEqual(min(steady), 1)
                self.assertTrue(24 <= max(steady) <= 25)
            finally:
                app.on_close()

    def test_export_braking_changes_time_only_after_final_travel(self):
        scene = MotionScene()
        frames = [scene.frame(y=6*np.sin(i/30*5)) for i in range(151)]
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            scripts = []
            try:
                for enabled in (False, True):
                    app.endpoint_slowdown_enabled.set(enabled)
                    with patch("osr_screen_tcode.app.cv2.VideoCapture", return_value=MemoryVideo(frames)):
                        files = app._analyze_video_worker(Path("memory.avi"), Path(temp)/f"braking{enabled}.funscript")
                    scripts.append(json.loads(files[0].read_text())["actions"])
                normal, slow = scripts
                self.assertEqual([p["pos"] for p in normal], [p["pos"] for p in slow])
                self.assertGreater(slow[-1]["at"], normal[-1]["at"])
            finally:
                app.on_close()

    def test_offline_v1_preview_carries_the_actual_reference_snapshot(self):
        from osr_screen_tcode.config import HYBRID_MODE
        frames = []
        for i in range(30):
            frame = np.zeros((240, 320, 3), np.uint8)
            cv2.rectangle(frame, (70, 30+i*3), (210, 100+i*3), (190, 210, 180), -1)
            frames.append(frame)
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only", tracker_mode=HYBRID_MODE)), patch.object(AppConfig, "save"), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            shown = []
            try:
                with patch("osr_screen_tcode.app.cv2.VideoCapture", return_value=MemoryVideo(frames)), patch.object(app, "_queue_latest", side_effect=shown.append):
                    files = app._analyze_video_worker(Path("memory.avi"), Path(temp)/"v1.funscript")
                self.assertEqual(len(files), 1)
                previews = [event["visual_frame"] for event in shown if "visual_frame" in event]
                self.assertTrue(previews)
                self.assertTrue(all(frame.reference.method == "v1" for frame in previews))
            finally:
                app.on_close()

    def test_playback_skips_old_frames_using_video_timestamps(self):
        from osr_screen_tcode.visual_pipeline import make_analyzer
        frames = [np.full((32, 32, 3), i, np.uint8) for i in range(20)]
        with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"):
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            app.video_path.set("memory.avi")
            capture = MemoryVideo(frames)
            engine = make_analyzer(tracker_mode=HYBRID_V2_MODE)
            samples = []
            def observe(analyzer, output, frame, preview, timestamp=None):
                samples.append((int(frame[0, 0, 0]), timestamp))
                if len(samples) == 2:
                    app.stop_event.set()
                return 0
            try:
                with patch("osr_screen_tcode.app.cv2.VideoCapture", return_value=capture), patch("osr_screen_tcode.app.time.perf_counter", side_effect=[0, 0, .2, .2, .3]), patch.object(app, "_process_frame", observe):
                    app._run_video(engine, None, 1/30, 0)
                self.assertEqual(samples, [(0, 0), (6, .2)])
                self.assertEqual(engine.skipped, 5)
                self.assertTrue(capture.released)
            finally:
                app.on_close()

    def test_exported_scripts_change_but_sampled_analysis_does_not(self):
        scene = MotionScene()
        frames = [scene.frame(y=6*np.sin(i/30*5)) for i in range(120)]
        with patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"), tempfile.TemporaryDirectory() as temp:
            app = OsrScreenApp(enforce_age_gate=False, ui_language="en")
            app.withdraw()
            app._set_tracker_mode(HYBRID_V2_MODE)
            app.output_mode.set("L0 Only")
            app.output_curve_fitting.set(False)
            app.fps.set(30)
            baseline = None
            scripts = []
            process = LabAnalyzer.process
            try:
                for level in range(1, 6):
                    app.apply_play_preset(level)
                    samples = []
                    def observe(engine, frame, timestamp=None):
                        result = process(engine, frame, timestamp)
                        samples.append((timestamp, dict(result.positions)))
                        return result
                    capture = MemoryVideo(frames)
                    with patch("osr_screen_tcode.app.cv2.VideoCapture", return_value=capture), patch.object(LabAnalyzer, "process", observe):
                        files = app._analyze_video_worker(Path("memory.avi"), Path(temp) / f"preset{level}.funscript")
                    self.assertTrue(capture.released)
                    self.assertEqual(len(files), 1)
                    self.assertEqual([t for t, _ in samples], [i / 30 for i in range(len(frames))])
                    if baseline is None:
                        baseline = samples
                    else:
                        self.assertEqual(samples, baseline)
                    scripts.append(json.loads(files[0].read_text())["actions"])
                ranges = [max(abs(p["pos"] - 50) for p in actions) for actions in scripts]
                # The existing recorder omits changes below two integer
                # points: 99 -> 100 can be omitted after a larger preset
                # reaches 99 sooner. Allow this one-point export quantization.
                self.assertTrue(all(b >= a-1 for a, b in zip(ranges, ranges[1:])), ranges)
                self.assertGreater(ranges[-1], ranges[0]+10)
                # Larger presets may share clipped endpoints; their complete
                # exported curves must still differ, with identical analysis.
                self.assertEqual(len({tuple((p["at"], p["pos"]) for p in actions) for actions in scripts}), 5)
                app._video_cancel.set()
                capture = MemoryVideo(frames)
                target = Path(temp) / "cancelled.funscript"
                with patch("osr_screen_tcode.app.cv2.VideoCapture", return_value=capture):
                    self.assertEqual(app._analyze_video_worker(Path("memory.avi"), target), [])
                self.assertFalse(target.exists())
                self.assertTrue(capture.released)
            finally:
                app.on_close()
