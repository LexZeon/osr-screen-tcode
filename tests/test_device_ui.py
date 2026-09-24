import json
from pathlib import Path
import tempfile
import threading
import unittest
import tkinter as tk
from unittest.mock import patch

from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode import APP_NAME, __version__
from osr_screen_tcode.config import AppConfig
from osr_screen_tcode.preview import PreviewBridge


class DeviceUiTests(unittest.TestCase):
    def test_warm_v1_handoff_starts_at_final_command_with_travel_and_limits(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import numpy as np
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        from osr_screen_tcode.motion_reference import MotionReference
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from test_visual_pipeline import FakePose
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.app.output_mode.set('L0 Only')
        self.app.pose_auto_l0_enabled.set(False)
        self.app.enable_activity_gate.set(True)
        self.app.output_curve_fitting.set(True)
        self.app.enable_startup_ramp.set(False)
        self.app.enable_endpoint_guard.set(True)
        self.app.enable_extreme_reset.set(False)
        self.app._set_all_axis_limits(1200, 8700)
        frame = np.zeros((400, 400, 3), np.uint8)
        for inverted, travel in ((False, .5), (True, 1.3)):
            self.app.invert.set(inverted)
            self.app.l0_travel_scale.set(travel)
            engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, visual_settings=self.app._visual_settings)
            engine.backend = FakePose()
            engine.pose_recovery.update = Mock(return_value=.85)
            v1 = SimpleNamespace(motion_reference=MotionReference('v1', 'ready', step=(0, .8, 0)))
            v1.process = Mock(return_value=SimpleNamespace(positions={'L0': .1}, confidence=1))
            engine.pose_fast.factory = Mock(return_value=v1)
            output = self.app._new_output(24)
            self.app._refresh_live_output_mapping(output)
            output.max_step = 40  # Applied position intentionally lags the fitted target.
            with patch.object(self.app.preview_bridge, 'broadcast_tcode') as broadcast:
                for i in range(12):
                    self.app._process_frame(engine, output, frame, 0, timestamp=i/30)
                self.assertEqual(v1.process.call_count, 12)
                previous = output._values['L0']
                engine.backend.missing = True
                for i in range(12, 18):
                    self.app._process_frame(engine, output, frame, 0, timestamp=i/30)
                    self.assertEqual(engine.visual_frame.l0_source, 'v1')
                    self.assertEqual(output._values['L0'], previous)
                    self.assertEqual(broadcast.call_args.args[0], self.app.sink.last_payload.decode().strip())
                v1.process.return_value.positions['L0'] = .12
                self.app._process_frame(engine, output, frame, 0, timestamp=18/30)
                delta = output._values['L0']-previous
                self.assertGreater(delta*(-1 if inverted else 1), 0)
                self.assertLessEqual(abs(delta), 40)

    def test_pose_output_options_save_hide_and_restore_defaults(self):
        from osr_screen_tcode.config import RTM_POSE_2D_MODE, HYBRID_V2_MODE
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertTrue(self.app.pose_auto_l0_enabled.get())
        self.assertFalse(self.app.pose_pattern_enabled.get())
        self.assertTrue(self.app.pose_fast_v1_enabled.get())
        self.assertEqual(self.app.pose_pattern_check.winfo_manager(), 'grid')
        self.assertEqual(self.app.integrated_preview.pose_auto_l0_switch.winfo_manager(), 'grid')
        generation = self.app._visual_settings.generation
        self.app.pose_auto_l0_enabled.set(False)
        self.app.pose_pattern_enabled.set(True)
        self.app.pose_fast_v1_enabled.set(False)
        self.assertEqual(self.app._visual_settings.generation, generation)
        self.assertTrue(self.app._visual_settings.pose_pattern)
        self.app._save_config()
        profiles = self.app.config_model.extra['analysis_profiles']
        self.assertTrue(profiles['dance']['pose_pattern_enabled'])
        self.assertFalse(profiles['dance']['pose_auto_l0_enabled'])
        self.assertFalse(profiles['dance']['pose_fast_v1_enabled'])
        self.app._set_tracker_mode(HYBRID_V2_MODE)
        self.assertEqual(self.app.pose_pattern_check.winfo_manager(), '')
        self.assertEqual(self.app.pose_fast_v1_check.winfo_manager(), '')
        self.assertEqual(self.app.integrated_preview.pose_auto_l0_switch.winfo_manager(), '')
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertTrue(self.app.pose_pattern_enabled.get())
        self.assertFalse(self.app.pose_auto_l0_enabled.get())
        self.assertFalse(self.app.pose_fast_v1_enabled.get())
        with patch('osr_screen_tcode.app.messagebox.askyesno', return_value=True):
            self.app.reset_all_settings()
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertTrue(self.app.pose_auto_l0_enabled.get())
        self.assertFalse(self.app.pose_pattern_enabled.get())
        self.assertTrue(self.app.pose_fast_v1_enabled.get())

    def test_generated_pose_l0_reaches_final_output_with_gate_and_curve_enabled(self):
        import numpy as np
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from test_visual_pipeline import FakePose
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.app.output_mode.set('L0 Only')
        self.app.enable_activity_gate.set(True)
        self.app.output_curve_fitting.set(True)
        self.app.enable_startup_ramp.set(False)
        self.app.enable_endpoint_guard.set(False)
        self.app.enable_extreme_reset.set(False)
        self.app.enable_speed_limit.set(False)
        self.app._set_all_axis_limits(1000, 9000)
        self.app.l0_travel_scale.set(.5)
        engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, visual_settings=self.app._visual_settings)
        engine.backend = FakePose()
        engine.geometry._positions_from_rtm_pose_2d = lambda sample, shape, timestamp: ({'R0': .5+.08*np.sin(timestamp*6), 'R1': .5, 'R2': .5}, None)
        output = self.app._new_output(24)
        frame = np.zeros((400, 400, 3), np.uint8)
        with patch.object(self.app.preview_bridge, 'broadcast_tcode') as broadcast:
            for i in range(181):
                self.app._process_frame(engine, output, frame, 0, timestamp=i/60)
            expected = round(1000+8000*(.5+(engine.generated_l0-.5)*.5))
            self.assertEqual(output._values['L0'], expected)
            self.assertGreater(expected, 3900)
            self.assertLess(expected, 5100)
            self.assertEqual(broadcast.call_args.args[0], self.app.sink.last_payload.decode().strip())
        self.assertEqual(engine.positions['L0'], .5)

    def test_braking_controls_save_reset_and_preserve_final_simulator_targets(self):
        self.assertTrue(self.app.endpoint_slowdown_enabled.get())
        self.assertEqual(self.app.endpoint_slowdown_pct.get(), 10)
        self.app.endpoint_slowdown_pct.set(24)
        self.app.endpoint_slowdown_enabled.set(False)
        self.app._save_config()
        self.assertEqual(self.app.config_model.extra["endpoint_slowdown_pct"], 24)
        self.assertFalse(self.app.config_model.extra["endpoint_slowdown_enabled"])
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
            self.app.reset_all_settings()
        self.assertEqual(self.app._endpoint_options, (True, .1))
        self.app.enable_startup_ramp.set(False)
        self.app.enable_endpoint_guard.set(False)
        self.app.enable_extreme_reset.set(False)
        self.app.enable_speed_limit.set(False)
        self.app.l0_travel_scale.set(1)
        slow = self.app._new_output(24)
        slow.next_command({"L0": .95}, 1)
        command = slow.next_command({"L0": 1}, 1)
        self.assertEqual(command.values["L0"], 9999)
        self.assertGreater(command.interval_ms, 24)
        with patch.object(self.app.preview_bridge, "broadcast_tcode") as broadcast:
            text = self.app._emit_command(command)
            broadcast.assert_called_once_with(text)
            self.assertEqual(text, command.encode().decode().strip())

    def test_cycle_mode_saves_and_offers_pose_assistance(self):
        from osr_screen_tcode.config import STROKE_CYCLE_MODE
        self.app._set_tracker_mode(STROKE_CYCLE_MODE)
        self.app.output_mode.set("Six Axis")
        self.app.hybrid_v2_pose_enabled.set(True)
        self.assertTrue(self.app._pose_model_required())
        self.assertEqual(self.app.integrated_preview.v2_pose_switch.winfo_manager(), "grid")
        self.assertNotIn("disabled", self.app.integrated_preview.v2_pose_switch.state())
        self.assertNotIn("disabled", self.app.integrated_preview.edge_box.state())
        self.app._save_config()
        self.assertEqual(self.app.config_model.tracker_mode, STROKE_CYCLE_MODE)
        self.assertTrue(self.app.config_model.extra["hybrid_v2_pose_enabled"])
        self.app.output_mode.set("L0 Only")
        self.assertFalse(self.app._pose_model_required())

    def test_default_analysis_is_v2_and_reset_restores_v2_without_model(self):
        from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE, STROKE_CYCLE_MODE
        self.assertEqual(self.app._tracker_choices()[0], self.app._tracker_display(STROKE_CYCLE_MODE))
        self.assertEqual(self.app._tracker_choices()[1], self.app._tracker_display(RTM_POSE_2D_MODE))
        self.assertEqual(self.app._tracker_internal(self.app.tracker_mode.get()), HYBRID_V2_MODE)
        self.assertFalse(self.app.hybrid_v2_pose_enabled.get())
        self.app._set_tracker_mode(HYBRID_MODE)
        self.app.hybrid_v2_pose_enabled.set(True)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
            self.app.reset_all_settings()
        self.assertEqual(self.app._tracker_internal(self.app.tracker_mode.get()), HYBRID_V2_MODE)
        self.assertFalse(self.app.hybrid_v2_pose_enabled.get())

    def test_v2_model_detection_keeps_selected_analysis_and_uses_2d_path(self):
        from osr_screen_tcode.config import HYBRID_V2_MODE
        self.app._set_tracker_mode(HYBRID_V2_MODE)
        self.app.output_mode.set("Six Axis")
        self.app.hybrid_v2_pose_enabled.set(True)
        self.app._apply_rtm_pose_model_path("example.onnx", HYBRID_V2_MODE)
        self.assertEqual(self.app._tracker_internal(self.app.tracker_mode.get()), HYBRID_V2_MODE)
        self.assertEqual(self.app.rtm_pose_2d_model_path.get(), "example.onnx")
        self.app._queue_latest({"rtm_model_path": "second.onnx", "rtm_model_mode": HYBRID_V2_MODE})
        self.app._poll_worker()
        self.assertEqual(self.app.rtm_pose_2d_model_path.get(), "second.onnx")
        self.assertEqual(self.app._tracker_internal(self.app.tracker_mode.get()), HYBRID_V2_MODE)

    def test_five_presets_only_change_final_travel_and_preserve_analysis(self):
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.app.motion_gain.set(1.71)
        self.app.smoothing.set(0.13)
        self.app.rtm_pose_reject_enabled.set(True)
        excluded = {str(self.app.l0_travel_scale), str(self.app.global_travel_scale), str(self.app.play_preset_level)}
        def snapshot():
            return {str(v): v.get() for v in self.app._config_variables() if str(v) not in excluded}
        before, visual = snapshot(), self.app._visual_settings
        self.app.enable_startup_ramp.set(False)
        self.app.enable_endpoint_guard.set(False)
        self.app.enable_extreme_reset.set(False)
        self.app.enable_speed_limit.set(False)
        before = snapshot()
        output = self.app._new_output(20)
        raw = {"L0": 0.7}
        for level, travel in enumerate((0.55, 0.75, 1.0, 1.15, 1.3), 1):
            self.app.apply_play_preset(level)
            self.assertEqual(snapshot(), before)
            self.assertEqual(self.app._visual_settings, visual)
            self.assertAlmostEqual(self.app._positions_with_travel_controls(raw)["L0"], 0.5 + 0.2 * travel)
            self.app._refresh_live_output_mapping(output)
            command = output.next_command(raw, 1.0)
            self.assertAlmostEqual(self.app._parse_axis_values(command.encode().decode())["L0"] / 9999, 0.5 + 0.2 * travel, places=3)
        self.assertEqual(raw, {"L0": 0.7})
        self.app._save_config()
        self.assertEqual(self.app.config_model.extra["play_preset_level"], 5)
        self.assertEqual(self.app.config_model.global_travel_scale, 1.3)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
            self.app.reset_all_settings()
        self.assertEqual(self.app.play_preset_level.get(), 3)
        self.assertEqual(self.app._axis_position_scales()["L0"], 1)

    def test_export_and_live_analysis_cannot_run_together(self):
        from unittest.mock import Mock
        busy = Mock()
        busy.is_alive.return_value = True
        with patch.object(self.app, "worker", busy), patch("osr_screen_tcode.app.filedialog.asksaveasfilename") as dialog:
            self.app.analyze_video_file()
            dialog.assert_not_called()
        with patch.object(self.app, "_video_worker", busy), patch.object(self.app, "_confirm_realtime_start") as confirm:
            self.app.start()
            self.app.connected = True
            self.app._begin_realtime_output()
            confirm.assert_not_called()
            self.assertIsNone(self.app.worker)
            self.app.stop()
            self.assertTrue(self.app._video_cancel.is_set())

    def test_preview_button_opens_simulator_without_connecting(self):
        self.assertEqual(self.app.preview_tabs.select(), str(self.app.output_tab))
        with patch.object(self.app.preview_bridge, "start") as start, patch.object(self.app.preview_bridge, "open_window") as open_window:
            self.app.preview_button.invoke()
            start.assert_called_once()
            open_window.assert_called_once()
        self.assertEqual(self.app.preview_tabs.select(), str(self.app.output_tab))
        self.assertFalse(self.app.connected)
        self.assertIsNone(self.app.worker)
        self.assertFalse(hasattr(self.app, "preview_lab_button"))

    def test_dance_defaults_and_mode_preferences_are_independent(self):
        from osr_screen_tcode.config import HYBRID_V2_MODE, RTM_POSE_2D_MODE
        from osr_screen_tcode.analysis_preferences import defaults, POSE_OPTIONS
        self.app.fps.set(90)
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertEqual({k: v.get() for k, v in self.app._analysis_variables().items()}, defaults("dance"))
        self.assertEqual(self.app.integrated_preview.v2_pose_switch.winfo_manager(), "")
        self.assertEqual(self.app.rtm_hybrid_source_label.winfo_manager(), "")
        self.app.rtm_hybrid_l0_enabled.set(True)
        self.assertEqual(self.app.rtm_hybrid_source_label.winfo_manager(), "grid")
        self.assertIn("v2", self.app.rtm_hybrid_source_label.cget("text"))
        self.app.rtm_pose_flow_enabled.set(False)
        self.app.fps.set(60)
        self.app._set_tracker_mode(HYBRID_V2_MODE)
        self.assertEqual(self.app.fps.get(), 90)
        self.assertTrue(all(not getattr(self.app, name).get() for name in POSE_OPTIONS))
        self.assertEqual(self.app.integrated_preview.v2_pose_switch.winfo_manager(), "grid")
        self.assertEqual(self.app.rtm_hybrid_source_label.winfo_manager(), "")
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertEqual(self.app.fps.get(), 60)
        self.assertFalse(self.app.rtm_pose_flow_enabled.get())
        self.app._save_config()
        self.assertEqual(self.app.config_model.extra["analysis_profiles"]["hybrid"]["fps"], 90)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
            self.app.reset_all_settings()
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertEqual({k: v.get() for k, v in self.app._analysis_variables().items()}, defaults("dance"))

    def test_popup_dance_defaults_visibility_and_cancel_preserve_main_settings(self):
        from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE
        before = {k: v.get() for k, v in self.app._analysis_variables().items()}
        checked, errors = [], []
        def inspect():
            dialog = next(w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel))
            def walk(w):
                yield w
                for child in w.winfo_children():
                    yield from walk(child)
            widgets = list(walk(dialog))
            try:
                combo = next(w for w in widgets if "textvariable" in w.keys() and "values" in w.keys() and self.app._tracker_display(RTM_POSE_2D_MODE) in w.cget("values"))
                source = next(w for w in widgets if "text" in w.keys() and str(w.cget("text")).startswith("L0 混合来源"))
                assist = next(w for w in widgets if "text" in w.keys() and str(w.cget("text")).startswith("v2："))
                blend = next(w for w in widgets if "text" in w.keys() and w.cget("text") == "混合分析 L0 权重")
                auto_l0 = next(w for w in widgets if 'text' in w.keys() and w.cget('text') == 'L0 静止／小幅时自动生成')
                pattern = next(w for w in widgets if 'text' in w.keys() and w.cget('text') == '小幅往复渐放大')
                for mode in (RTM_POSE_2D_MODE, HYBRID_MODE, HYBRID_V2_MODE):
                    self.app.setvar(str(combo.cget("textvariable")), self.app._tracker_display(mode))
                    if mode == RTM_POSE_2D_MODE:
                        self.assertEqual(auto_l0.winfo_manager(), 'grid')
                        self.assertTrue(int(self.app.getvar(str(auto_l0.cget('variable')))))
                        self.assertFalse(int(self.app.getvar(str(pattern.cget('variable')))))
                        pattern.invoke()
                        auto_l0.invoke()
                        self.assertEqual(assist.winfo_manager(), "")
                        self.assertEqual(source.winfo_manager(), "")
                        for text in ("RTM 光流辅助", "RTM 卡尔曼融合", "异常过滤", "仅微抖平滑"):
                            control = next(w for w in widgets if "text" in w.keys() and w.cget("text") == text)
                            self.assertTrue(int(self.app.getvar(str(control.cget("variable")))))
                        blend.invoke()
                        self.assertEqual(source.winfo_manager(), "grid")
                        blend.invoke()
                        self.assertEqual(source.winfo_manager(), "")
                    else:
                        self.assertEqual(auto_l0.winfo_manager(), '')
                        self.assertEqual(pattern.winfo_manager(), '')
                        self.assertEqual(assist.winfo_manager(), "grid")
                        self.assertEqual(source.winfo_manager(), "")
                checked.append(True)
            except Exception as exc:
                errors.append(exc)
            finally:
                dialog.destroy()
        self.app.after(80, inspect)
        self.assertFalse(self.app._confirm_realtime_start())
        self.assertFalse(errors, errors)
        self.assertTrue(checked)
        self.assertEqual({k: v.get() for k, v in self.app._analysis_variables().items()}, before)

    def test_simulator_receives_final_output_and_not_stale_or_failed_writes(self):
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        from osr_screen_tcode.sinks import LogSink, OutputWriteError
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.app.output_mode.set("Six Axis")
        self.app.apply_play_preset(2)
        output = self.app._new_output(20)
        command = output.next_command({"L0": .5, "L1": .7, "L2": .3}, 1)
        with patch.object(self.app.preview_bridge, "broadcast_tcode") as broadcast:
            text = self.app._emit_command(command)
            broadcast.assert_called_once_with(text)
            self.assertEqual(self.app.sink.last_payload.decode().strip(), text)
            broadcast.reset_mock()
            self.app._output_context.sink = LogSink()
            self.app._emit_command("L09999I20")
            broadcast.assert_not_called()
            self.app._output_context.sink = self.app.sink
            with patch.object(self.app.sink, "write", side_effect=OSError("closed")), self.assertRaises(OutputWriteError) as raised:
                self.app._emit_command("L09999I20")
            self.assertIsInstance(raised.exception.__cause__, OSError)
            self.assertEqual(str(raised.exception), "OSError: closed")
            broadcast.assert_not_called()

    def test_simulator_final_values_include_travel_inversion_coupling_and_limits(self):
        self.app.output_mode.set("Six Axis")
        self.app.enable_startup_ramp.set(False)
        self.app.enable_endpoint_guard.set(False)
        self.app.enable_extreme_reset.set(False)
        self.app.enable_speed_limit.set(False)
        self.app._set_all_axis_limits(1000, 9000)
        self.app.l0_travel_scale.set(.5)
        self.app.global_travel_scale.set(.5)
        self.app.six_axis_travel_scale_vars["L1"].set(.5)
        self.app.six_axis_travel_scale_vars["L2"].set(2)
        self.app.axis_output_invert_vars["L1"].set(True)
        output = self.app._new_output(24)
        raw = {"L0": .5, "L1": .7, "L2": .7, "R0": .8}
        with patch.object(self.app.preview_bridge, "broadcast_tcode") as broadcast:
            command = output.next_command(raw, 1)
            self.assertEqual(command.values["L1"], 4000)  # .7 -> .625 with .5*.5*2.5, then invert
            self.assertEqual(command.values["L2"], 9000)  # .7 -> 1 after .5*2*2.5, then axis range
            self.assertEqual(command.values["R0"], 6200)
            self.app._emit_command(command)
            self.assertEqual(broadcast.call_args.args[0], self.app.sink.last_payload.decode().strip())
            # Recalculate coupling for fixed observations when final L0 moves.
            raw["L0"] = .1
            command = output.next_command(raw, 1)
            self.assertEqual(command.values["L0"], 3400)
            self.assertEqual(command.values["L1"], 4240)
            self.app._emit_command(command)
            self.assertEqual(broadcast.call_args.args[0], self.app.sink.last_payload.decode().strip())
            self.app.enable_speed_limit.set(True)
            self.app.max_step.set(100)
            limited = self.app._new_output(24).next_command(raw, 1)
            self.assertEqual(limited.values["L0"], 4900)
            self.assertTrue(all(abs(v-5000) <= 100 for v in limited.values.values()))
            self.app._emit_command(limited)
            self.assertEqual(broadcast.call_args.args[0], self.app.sink.last_payload.decode().strip())

    def test_visual_settings_save_defaults_and_mode_axis_boundaries(self):
        from osr_screen_tcode.config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE, RTM_POSE_3D_MODE
        self.app.visual_processing_edge.set(960)
        self.app.rtm_pose_reject_enabled.set(True)
        self.app.rtm_pose_micro_smooth_enabled.set(True)
        self.app.rtm_hybrid_source.set(HYBRID_V2_MODE)
        self.app._save_config()
        self.assertEqual(self.app.config_model.extra["visual_processing_edge"], 960)
        self.assertTrue(self.app._visual_settings.options.reject)
        self.assertTrue(self.app._visual_settings.options.smooth)
        self.assertNotIn(RTM_POSE_3D_MODE, self.app._tracker_choices())
        self.app.output_mode.set("Six Axis")
        self.app._set_tracker_mode(HYBRID_MODE)
        self.assertEqual(self.app._active_axes(), ["L0"])
        self.assertFalse(self.app._new_output(20).couple_l0_translation)
        self.app._set_tracker_mode(HYBRID_V2_MODE)
        self.assertEqual(len(self.app._active_axes()), 6)
        self.assertTrue(self.app._new_output(20).couple_l0_translation)
        self.assertEqual(self.app._new_output(20).coupling_endpoint_gain, 1.0)
        self.assertEqual(self.app._new_output(20).coupling_middle_gain, 2.5)
        self.assertEqual(self.app._new_output(20).coupling_peak_position, .5)
        self.assertIsNone(self.app._new_output(20).coupling_lower_knot)
        self.assertFalse(self.app._new_output(20).couple_l0_rotation)
        self.assertFalse(self.app._pose_model_required())
        self.app.hybrid_v2_pose_enabled.set(True)
        self.assertTrue(self.app._pose_model_required())
        self.assertEqual(self.app._new_output(20).coupling_endpoint_gain, 1.0)
        self.app._save_config()
        self.assertTrue(self.app.config_model.extra["hybrid_v2_pose_enabled"])
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.assertTrue(self.app._new_output(20).couple_l0_translation)
        self.assertEqual(self.app._new_output(20).coupling_endpoint_gain, 0.5)
        self.assertEqual(self.app._new_output(20).coupling_middle_gain, 3.5)
        self.assertEqual(self.app._new_output(20).coupling_peak_position, 2/3)
        self.assertEqual(self.app._new_output(20).coupling_lower_knot, (1/3, 1.0))
        self.assertTrue(self.app._new_output(20).couple_l0_rotation)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
            self.app.reset_all_settings()
        self.assertEqual(self.app.visual_processing_edge.get(), 640)
        self.assertFalse(self.app._visual_settings.options.reject)
        self.assertFalse(self.app._visual_settings.options.smooth)
        self.assertFalse(self.app._visual_settings.options.flow)
        self.assertFalse(self.app._visual_settings.options.kalman)
        self.assertFalse(self.app.hybrid_v2_pose_enabled.get())

    def test_directml_controls_and_preferences_without_nvidia(self):
        with patch.object(self.app, "_start_gpu_task"):
            self.app.rtm_pose_gpu_backend.set("directml")
            self.app._gpu_result = {"nvidia": False, "cuda": False, "reason": "dml_missing"}
            self.app.rtm_pose_gpu_enabled.set(True)
            view = self.app._gpu_views[0]
            self.assertIn("DirectML", view[2].get())
            self.assertEqual(view[3].winfo_manager(), "grid")
            self.assertIn("DirectML", view[3].cget("text"))
            self.app._save_config()
            self.assertEqual(self.app.config_model.extra["rtm_pose_gpu_backend"], "directml")
            self.app._finish_gpu_event({"gpu_event": "checked", "backend": "directml",
                "result": {"ready": True, "nvidia": False, "cuda": False, "backend": "directml"}})
            self.assertIn("验证通过", view[2].get())
            self.assertEqual(view[3].winfo_manager(), "")

    def test_gpu_download_progress_shared_in_both_languages(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "cpu_ort", "ort_version": "1.29.0"}
        self.app.rtm_pose_gpu_enabled.set(True)
        self.assertIn("CPU 版", self.app._gpu_views[0][2].get())
        popup = tk.Toplevel(self.app)
        self.addCleanup(popup.destroy)
        enabled, status = tk.BooleanVar(value=True), tk.StringVar()
        self.app._gpu_status_controls(popup, 0, enabled, status)
        self.app._gpu_installing = True
        data = {"stage": "downloading", "component": "nvidia-cudnn-cu12", "downloaded": 25 * 1024 ** 2,
                "total": 100 * 1024 ** 2, "index": 2, "count": 8}
        for language in ("zh", "en"):
            self.app.ui_language = language
            self.app._finish_gpu_event({"gpu_event": "stage", "stage": "downloading", "progress": data})
            self.assertIn("25.0%", status.get())
            self.assertIn("2/8  nvidia-cudnn-cu12", status.get())
            self.assertEqual(status.get(), self.app._gpu_views[0][2].get())
            self.assertEqual(float(self.app._gpu_views[0][5].cget("value")), 25)
            self.assertEqual(str(self.app._gpu_views[0][3].cget("state")), "disabled")
        self.app._finish_gpu_event({"gpu_event": "stage", "stage": "installing"})
        self.assertIn("Extracting", status.get())
        self.assertNotIn("100%", status.get())
        self.app._finish_gpu_event({"gpu_event": "failed", "error": "download_verification_failed"})
        self.assertIn("verification failed", status.get())
        self.assertEqual(self.app._gpu_views[0][5].winfo_manager(), "")

    def test_gpu_recheck_invalidates_cache_and_runs_in_background(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "cpu_ort"}
        self.app.rtm_pose_gpu_enabled.set(True)
        with patch.object(self.app, "_start_gpu_task") as start:
            self.app._recheck_gpu()
            self.assertIsNone(self.app._gpu_result)
            self.assertTrue(self.app._gpu_check_running)
            start.assert_called_once()
            self.app._recheck_gpu()
            start.assert_called_once()

    def test_closing_waits_for_gpu_task_cancellation(self):
        stopped = threading.Event()
        def work():
            self.app._gpu_cancel.wait(2)
            stopped.set()
        self.app._start_gpu_task(work, "gpu-cancel-test")
        self.app._cancel_gpu_tasks()
        self.assertTrue(stopped.is_set())
        self.assertTrue(all(not thread.is_alive() for thread in self.app._gpu_threads))
    def test_gpu_install_button_main_and_popup_share_state(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "runtime"}
        self.app.rtm_pose_gpu_enabled.set(True)
        view = self.app._gpu_views[0]
        self.assertEqual(view[3].winfo_manager(), "grid")
        self.assertIn("NVIDIA", view[2].get())
        popup = tk.Toplevel(self.app)
        enabled, status = tk.BooleanVar(value=True), tk.StringVar()
        self.app._gpu_status_controls(popup, 0, enabled, status)
        self.app._finish_gpu_event({"gpu_event": "installed"})
        self.assertIn("Start.cmd", status.get())
        self.assertIn("Start.cmd", view[2].get())
        self.app._begin_realtime_output()
        self.assertIsNone(self.app.worker)
        popup.destroy()
        self.app._refresh_gpu_views()
        self.assertEqual(len(self.app._gpu_views), 1)

    def test_gpu_install_requires_confirmation_and_never_runs_on_toggle(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "runtime"}
        with patch("osr_screen_tcode.gpu_controls.install_runtime") as install, patch("osr_screen_tcode.gpu_controls.messagebox.askyesno", return_value=False):
            self.app.rtm_pose_gpu_enabled.set(True)
            install.assert_not_called()
            self.app._install_gpu_runtime()
            install.assert_not_called()
            self.assertFalse(self.app._gpu_installing)

    def test_gpu_cpu_and_failed_install_states(self):
        self.app._gpu_result = {"nvidia": True, "cuda": False, "reason": "runtime"}
        self.app.rtm_pose_gpu_enabled.set(True)
        self.app._gpu_installing = True
        self.app._finish_gpu_event({"gpu_event": "stage", "stage": "verifying"})
        view = self.app._gpu_views[0]
        self.assertEqual(str(view[3].cget("state")), "disabled")
        self.assertIn("验证", view[2].get())
        self.app._finish_gpu_event({"gpu_event": "failed"})
        self.assertIn("失败", view[2].get())
        self.assertFalse(self.app._gpu_restart_required)
        self.app.rtm_pose_gpu_enabled.set(False)
        self.assertEqual(view[3].winfo_manager(), "")
    def setUp(self):
        self.restart_patch = patch("osr_screen_tcode.gpu_controls.runtime_needs_restart", return_value=False)
        self.restart_patch.start()
        self.addCleanup(self.restart_patch.stop)
        self.save_patch = patch.object(AppConfig, "save")
        self.save_patch.start()
        self.addCleanup(self.save_patch.stop)
        self.load_patch = patch.object(AppConfig, "load", side_effect=lambda: AppConfig(last_sink="Log only"))
        self.load_patch.start()
        self.addCleanup(self.load_patch.stop)
        self.app = OsrScreenApp(enforce_age_gate=False, ui_language="zh")
        self.app.withdraw()
        self.app.update()
        self.addCleanup(self.app.on_close)

    def test_version_header_and_contact_are_visible_text(self):
        def texts(widget):
            values = []
            if "text" in widget.keys():
                values.append(str(widget.cget("text")))
            for child in widget.winfo_children():
                values.extend(texts(child))
            return values
        labels = texts(self.app)
        self.assertEqual(self.app.title(), f"{APP_NAME} v{__version__}")
        self.assertTrue(any("合作与侵权" in t and "aivnailedeng@gmail.com" in t for t in labels))
        self.assertTrue(any(APP_NAME in t and __version__ in t for t in labels))

    def test_capture_and_curve_preferences_save_and_restore_defaults(self):
        self.assertTrue(self.app.output_curve_fitting.get())
        self.assertEqual(self.app._capture_target_fps, 45)
        self.app.fps.set(120)
        self.app.output_curve_fitting.set(False)
        self.app.interval_ms.set(40)
        self.assertEqual(self.app._capture_target_fps, 120)
        self.assertFalse(self.app._output_curve_enabled)
        self.app._save_config()
        self.assertEqual(self.app.config_model.fps, 120)
        self.assertFalse(self.app.config_model.extra["output_curve_fitting"])
        self.assertEqual(self.app.config_model.output_interval_ms, 40)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True):
            self.app.reset_all_settings()
        self.assertEqual(self.app._capture_target_fps, 45)
        self.assertTrue(self.app._output_curve_enabled)
        self.assertEqual(self.app.interval_ms.get(), 24)
        self.assertTrue(self.app._new_output(24).sync_timing)

    def test_rtm_gain_router_excludes_base_and_l0_only(self):
        from types import SimpleNamespace
        from osr_screen_tcode.pose_output import rtm_rotation_amplitudes
        values = {"L0": 1.0, "L1": 0.55, "R1": 0.6}
        with patch.object(self.app, "_apply_six_axis_tuning", side_effect=dict):
            for rtm, mode in ((False, "Six Axis"), (True, "L0 Only"), (True, "Six Axis")):
                analyzer = SimpleNamespace(_rtm_pose_enabled=lambda: rtm, output_mode=mode)
                actual = self.app._visual_output_positions(analyzer, values)
                expected = rtm_rotation_amplitudes(values) if rtm and mode == "Six Axis" else values
                self.assertEqual(actual, expected)

    def test_dance_l0_base_gain_is_ten_for_single_and_six_axes_only(self):
        from types import SimpleNamespace
        from osr_screen_tcode.config import HYBRID_V2_MODE, RTM_POSE_2D_MODE
        raw = {"L0": .54, "L1": .6, "R0": .6}
        with patch.object(self.app, "_apply_six_axis_tuning", side_effect=dict):
            for mode in ("L0 Only", "Six Axis"):
                for tracker, expected in ((RTM_POSE_2D_MODE, .9), (HYBRID_V2_MODE, .54)):
                    analyzer = SimpleNamespace(tracker_mode=tracker, output_mode=mode, _rtm_pose_enabled=lambda: True)
                    actual = self.app._visual_output_positions(analyzer, raw)
                    self.assertAlmostEqual(actual["L0"], expected)
                    self.assertEqual(actual["L1"], .6)
            self.assertEqual(raw["L0"], .54)

    def test_dance_base_gain_passes_through_travel_and_final_simulator_output(self):
        from types import SimpleNamespace
        from osr_screen_tcode.config import RTM_POSE_2D_MODE
        self.app._set_tracker_mode(RTM_POSE_2D_MODE)
        self.app.output_mode.set("L0 Only")
        self.app.enable_startup_ramp.set(False)
        self.app.enable_endpoint_guard.set(False)
        self.app.enable_extreme_reset.set(False)
        self.app.enable_speed_limit.set(False)
        self.app._set_all_axis_limits(1000, 9000)
        self.app.l0_travel_scale.set(.5)
        analyzer = SimpleNamespace(tracker_mode=RTM_POSE_2D_MODE, output_mode="L0 Only", _rtm_pose_enabled=lambda: True)
        positions = self.app._visual_output_positions(analyzer, {"L0": .54})
        self.assertAlmostEqual(self.app._positions_with_travel_controls(positions)["L0"], .7)
        command = self.app._new_output(24).next_command(positions, 1)
        self.assertEqual(command.values["L0"], 6600)
        with patch.object(self.app.preview_bridge, "broadcast_tcode") as broadcast:
            self.app._emit_command(command)
            broadcast.assert_called_once_with(self.app.sink.last_payload.decode().strip())

    def test_v1_recalibrate_button_clears_the_actual_tracking_reference(self):
        import cv2
        import numpy as np
        from osr_screen_tcode.config import HYBRID_MODE
        from osr_screen_tcode.visual_pipeline import make_analyzer
        self.app._set_tracker_mode(HYBRID_MODE)
        analyzer = make_analyzer(tracker_mode=HYBRID_MODE)
        output = self.app._new_output(24)
        for i in range(4):
            frame = np.zeros((240, 320, 3), np.uint8)
            cv2.rectangle(frame, (70, 30+i*6), (210, 100+i*6), (190, 210, 180), -1)
            self.app._process_frame(analyzer, output, frame, 0)
        self.assertTrue(analyzer.motion_reference.vectors)
        self.app.reset_visual_reference()
        self.app._process_frame(analyzer, output, frame, 0)
        self.assertEqual(analyzer.motion_reference.state, "calibrating")
        self.assertFalse(analyzer.motion_reference.vectors)

    def test_log_only_hides_all_serial_controls_and_ignores_invalid_baudrate(self):
        self.assertEqual(self.app.serial_settings_frame.winfo_manager(), "")
        self.assertEqual(self.app.ble_settings_frame.winfo_manager(), "")
        self.assertEqual(self.app.query_axes_button.winfo_manager(), "")
        self.app.baudrate.set("invalid")
        self.assertEqual(self.app._connection_snapshot(), {"kind": "Log only"})
        self.app.baudrate.set(115200)
        self.app.sink_type.set("Serial COM")
        self.assertEqual(self.app.serial_settings_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.query_axes_button.winfo_manager(), "grid")
        self.app.sink_type.set("BLE UART")
        self.assertEqual(self.app.serial_settings_frame.winfo_manager(), "")
        self.assertEqual(self.app.ble_settings_frame.winfo_manager(), "grid")

    def test_switch_to_log_disconnects_existing_hardware_connection(self):
        self.app.sink_type.set("Serial COM")
        self.app.connected = True
        with patch.object(self.app, "disconnect_sink", wraps=self.app.disconnect_sink) as disconnect:
            self.app.sink_type.set("Log only")
            disconnect.assert_called_once()
        self.assertFalse(self.app.connected)

    def test_measurement_open_on_first_use_and_reset(self):
        self.assertTrue(self.app.show_measurement_limits.get())
        self.assertEqual(self.app.measurement_limits_frame.winfo_manager(), "grid")
        self.app.show_measurement_limits.set(False)
        with patch("osr_screen_tcode.app.messagebox.askyesno", return_value=True), patch("osr_screen_tcode.app.messagebox.showinfo"):
            self.app.reset_all_settings()
        self.assertTrue(self.app.show_measurement_limits.get())
        self.assertEqual(self.app.measurement_limits_frame.winfo_manager(), "grid")

    def test_native_only_connection_path(self):
        self.assertEqual(self.app._connection_snapshot()["kind"], "Log only")
        self.assertFalse(self.app.connected)
        self.assertEqual(self.app.native_connection_frame.winfo_manager(), "grid")
        self.assertFalse(hasattr(self.app, "external_device_frame"))
        with self.assertRaises(ValueError):
            self.app._open_sink_from_snapshot({"kind": "Intiface"})

    def test_critical_events_not_dropped_by_preview_frames(self):
        self.app._queue_latest({"device_scan": 999, "devices": []})
        for _ in range(30):
            self.app._queue_latest({"activity": 0.1})
        self.assertEqual(self.app.control_queue.get_nowait()["device_scan"], 999)

    def test_cancel_connect_on_stop(self):
        self.app._start_after_connect = True
        self.app.stop()
        self.assertFalse(self.app._start_after_connect)

    def test_late_worker_completion_releases_controls(self):
        finished = threading.Thread(target=lambda: None)
        finished.start()
        finished.join()
        self.app.worker = finished
        self.app._set_device_controls_busy(True)
        self.app._poll_worker()
        self.assertIsNone(self.app.worker)
        self.assertEqual(str(self.app.native_output_combo.cget("state")), "readonly")


class ConfigTests(unittest.TestCase):
    def test_v1_old_labels_migrate_without_changing_saved_output_tuning(self):
        from osr_screen_tcode.config import HYBRID_MODE
        for old in ("混合分析（内测）", "Hybrid Analysis (Internal Test)"):
            with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp)/"config.json"):
                AppConfig(tracker_mode=old, response_curve="Smoothstep", global_travel_scale=.71,
                          extra={"hybrid_analysis_range_migration_v1": True}).save()
                loaded = AppConfig.load()
                self.assertEqual(loaded.tracker_mode, HYBRID_MODE)
                self.assertEqual(OsrScreenApp._normalize_tracker_mode(old), HYBRID_MODE)
                self.assertEqual(loaded.response_curve, "Smoothstep")
                self.assertEqual(loaded.global_travel_scale, .71)
                loaded.save()
                self.assertEqual(AppConfig.load().tracker_mode, HYBRID_MODE)

    def test_endpoint_options_migrate_and_round_trip_without_private_paths(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp)/"config.json"):
            AppConfig(extra={}).save()
            migrated = AppConfig.load()
            self.assertTrue(migrated.extra["endpoint_slowdown_enabled"])
            self.assertEqual(migrated.extra["endpoint_slowdown_pct"], 10)
            migrated.extra.update(endpoint_slowdown_enabled=False, endpoint_slowdown_pct=23)
            migrated.save()
            loaded = AppConfig.load()
            self.assertFalse(loaded.extra["endpoint_slowdown_enabled"])
            self.assertEqual(loaded.extra["endpoint_slowdown_pct"], 23)

    def test_user_collapsed_state_persists(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp) / "config.json"):
            cfg = AppConfig(extra={"show_measurement_limits": False})
            cfg.save()
            loaded = AppConfig.load()
            self.assertFalse(loaded.extra["show_measurement_limits"])
    def test_legacy_profile_removed_and_migrates_to_log_only(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.config.APP_DIR", Path(temp)), patch("osr_screen_tcode.config.CONFIG_PATH", Path(temp) / "config.json"):
            legacy = {"device_family": "custom", "custom_bindings": {"L0": "old"}, "intiface_url": "ws://localhost:12345", "last_sink": "Serial COM"}
            with patch.object(Path, "exists", return_value=True), patch.object(Path, "read_text", return_value=json.dumps(legacy)):
                loaded = AppConfig.load()
            self.assertEqual(loaded.last_sink, "Log only")
            loaded.save()
            saved = json.loads((Path(temp) / "config.json").read_text())
            for key in ("device_family", "custom_bindings", "intiface_url"):
                self.assertNotIn(key, saved)


class PreviewTests(unittest.TestCase):
    def test_shape_notice_and_safe_name_in_generated_preview(self):
        with tempfile.TemporaryDirectory() as temp, patch("osr_screen_tcode.preview.APP_DIR", Path(temp)), patch("webbrowser.open"):
            preview = PreviewBridge()
            preview.url = "ws://127.0.0.1:1234/test"
            preview.set_device_context("The Handy </script>", True, "en")
            html = preview.open_window().read_text(encoding="utf-8")
            self.assertIn("Preview shape differs from the actual device", html)
            self.assertTrue(__version__ in html)
            self.assertTrue(APP_NAME in html)
            self.assertNotIn("__OSR_PREVIEW_CONTEXT__", html)
            self.assertNotIn("The Handy </script>", html)
            self.assertIn("ws://127.0.0.1:1234/test", html)


if __name__ == "__main__":
    unittest.main()
