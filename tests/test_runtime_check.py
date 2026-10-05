"""No-GUI checks of the portable diagnostic's routing and isolation."""
import builtins
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import numpy as np

from osr_screen_tcode import config
from osr_screen_tcode.runtime_check import (
    _check_neuflow, _check_vittrack, _live_window_origin, _perform_checks,
    isolated_settings, run_runtime_check,
)


class RuntimeCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="osr-diagnostic-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.personal = self.root / "personal" / "config.json"
        self.personal.parent.mkdir()
        self.personal.write_text('{"test": "existing user setting"}', encoding="utf-8")
        self.original = self.personal.read_bytes()
        self.output = self.root / "report.json"
        self.enterContext(patch.object(config, "APP_DIR", self.personal.parent))
        self.enterContext(patch.object(config, "CONFIG_PATH", self.personal))

    def invoke(self, *args):
        with self.assertRaises(SystemExit) as exited:
            run_runtime_check(["--runtime-check", str(self.output), *args])
        return exited.exception.code, json.loads(self.output.read_text(encoding="utf-8"))

    def test_other_commands_are_not_consumed(self):
        with patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            for args in ([], ["--preview-lab", "--smoke"], ["--smoke"], ["--gpu-probe"]):
                self.assertFalse(run_runtime_check(args))
            checks.assert_not_called()

    def test_success_report_has_no_personal_paths(self):
        def checks(args, report):
            report["checks"].append("mock_runtime")
            report["personal_settings_unchanged"] = True
            self.assertEqual(args.language, "en")
            self.assertIsNone(args.live_seconds)

        with patch("osr_screen_tcode.runtime_check._perform_checks", side_effect=checks):
            code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["checks"], ["mock_runtime"])
        self.assertNotIn(str(self.root), self.output.read_text(encoding="utf-8"))
        self.assertEqual(self.personal.read_bytes(), self.original)

    def test_unknown_failure_is_recorded_and_returns_nonzero(self):
        with patch("osr_screen_tcode.runtime_check._perform_checks", side_effect=RuntimeError("missing bundled resource")):
            code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertIn("missing bundled resource", report["error"])

    def test_interrupt_is_recorded_as_failure(self):
        with patch("osr_screen_tcode.runtime_check._perform_checks", side_effect=KeyboardInterrupt()):
            code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertIn("KeyboardInterrupt", report["error"])

    def test_invalid_duration_never_starts_checks(self):
        with patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            for duration in ("1", "31", "nan", "inf"):
                code, report = self.invoke("--live-seconds", duration)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "failed")
            checks.assert_not_called()

    def test_unknown_option_is_reported_without_check_execution(self):
        with patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            code, report = self.invoke("--auto-connect")
        self.assertEqual(code, 1)
        self.assertIn("unrecognized arguments", report["error"])
        checks.assert_not_called()

    def test_diagnostic_refuses_to_overwrite_personal_settings(self):
        with self.assertRaises(SystemExit) as exited:
            run_runtime_check(["--runtime-check", str(self.personal)])
        self.assertNotEqual(exited.exception.code, 0)
        self.assertEqual(self.personal.read_bytes(), self.original)

    def test_paths_and_language_are_forwarded(self):
        model = self.root / "external.onnx"
        with patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            code, _ = self.invoke("--model", str(model), "--live-seconds", "2", "--language", "zh")
        self.assertEqual(code, 0)
        args = checks.call_args.args[0]
        self.assertEqual(args.model, model.resolve())
        self.assertEqual(args.live_seconds, 2)
        self.assertEqual(args.language, "zh")

    def test_v2_flags_forward_existing_models_without_writing_paths_to_report(self):
        vittrack, neuflow = self.root / "vit.onnx", self.root / "flow.onnx"
        vittrack.touch()
        neuflow.touch()
        with patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            code, report = self.invoke("--vittrack-model", str(vittrack), "--neuflow-model", str(neuflow))
        self.assertEqual(code, 0)
        args = checks.call_args.args[0]
        self.assertEqual(args.vittrack_model, vittrack.resolve())
        self.assertEqual(args.neuflow_model, neuflow.resolve())
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_explicit_live_origin_accepts_signed_physical_monitor_coordinates(self):
        monitors = [{"left": -1920, "top": -200, "width": 1920, "height": 1080}]
        with patch("osr_screen_tcode.screen_geometry.screen_monitors", return_value=monitors), \
                patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            code, _ = self.invoke("--live-seconds", "2", "--window-origin", "-1800", "-100")
        self.assertEqual(code, 0)
        self.assertEqual(checks.call_args.args[0].window_origin, (-1800, -100))

    def test_invalid_origins_do_not_start_runtime_or_gui_checks(self):
        monitors = [{"left": 1000, "top": 0, "width": 800, "height": 600}]
        with patch("osr_screen_tcode.screen_geometry.screen_monitors", return_value=monitors), \
                patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            for args in (("--window-origin", "1100", "100"),
                         ("--live-seconds", "2", "--window-origin", "1100.5", "100"),
                         ("--live-seconds", "2", "--window-origin", "1800", "100"),
                         ("--live-seconds", "2", "--window-origin", "1100")):
                self.assertNotEqual(self.invoke(*args)[0], 0)
        checks.assert_not_called()

    def test_default_diagnostic_does_not_patch_geometry_or_query_displays(self):
        import tkinter as tk
        original = tk.Tk.geometry
        with patch("osr_screen_tcode.screen_geometry.screen_monitors") as monitors:
            with _live_window_origin(None):
                self.assertIs(tk.Tk.geometry, original)
        monitors.assert_not_called()
        self.assertIs(tk.Tk.geometry, original)

    def test_explicit_geometry_helper_uses_physical_move_and_restores_on_failure(self):
        import tkinter as tk
        monitors = [{"left": -1920, "top": -200, "width": 1920, "height": 1080}]
        window = object()
        with patch("osr_screen_tcode.screen_geometry.screen_monitors", return_value=monitors), \
                patch("osr_screen_tcode.screen_geometry.move_physical_window") as move, \
                patch.object(tk.Tk, "geometry", return_value="1040x700") as original:
            with self.assertRaisesRegex(RuntimeError, "example failure"):
                with _live_window_origin((-1800, -100)):
                    self.assertEqual(tk.Tk.geometry(window), "1040x700")
                    move.assert_not_called()
                    tk.Tk.geometry(window, "1040x700")
                    original.assert_called_with(window, "1040x700")
                    move.assert_called_once_with(window, -1800, -100)
                    raise RuntimeError("example failure")
            self.assertIs(tk.Tk.geometry, original)

    def test_v2_flags_reject_missing_or_non_onnx_before_gpu_setup(self):
        with patch("osr_screen_tcode.runtime_check._perform_checks") as checks:
            for option in ("--vittrack-model", "--neuflow-model"):
                self.assertNotEqual(self.invoke(option, str(self.root / "missing.onnx"))[0], 0)
                self.assertNotEqual(self.invoke(option, str(self.personal))[0], 0)
        checks.assert_not_called()
        self.assertEqual(self.personal.read_bytes(), self.original)

    def test_optional_cuda_selection_precedes_isolation_and_imports(self):
        events = []
        args = SimpleNamespace(model=None, live_seconds=None, vittrack_model=self.root / "vit.onnx",
                               neuflow_model=self.root / "flow.onnx")

        def prepare():
            self.assertEqual(config.CONFIG_PATH, self.personal)
            events.append("prepare")

        def check(report):
            self.assertNotEqual(config.CONFIG_PATH, self.personal)
            events.append("dependencies")

        def model(path, report):
            self.assertNotEqual(config.CONFIG_PATH, self.personal)
            events.append(path.name)

        report = {"checks": []}
        with patch("osr_screen_tcode.runtime_check._prepare_v2_gpu_runtime", side_effect=prepare), \
                patch("osr_screen_tcode.runtime_check._check_dependencies", side_effect=check), \
                patch("osr_screen_tcode.runtime_check._check_vittrack", side_effect=model), \
                patch("osr_screen_tcode.runtime_check._check_neuflow", side_effect=model):
            _perform_checks(args, report)
        self.assertEqual(events, ["prepare", "dependencies", "vit.onnx", "flow.onnx"])
        self.assertTrue(report["personal_settings_unchanged"])
        self.assertEqual(config.CONFIG_PATH, self.personal)

    def test_default_cpu_diagnostic_does_not_select_private_gpu_runtime(self):
        args = SimpleNamespace(model=None, live_seconds=None)
        with patch("osr_screen_tcode.runtime_check._prepare_v2_gpu_runtime") as prepare, \
                patch("osr_screen_tcode.runtime_check._check_dependencies"):
            _perform_checks(args, {"checks": []})
        prepare.assert_not_called()

    def test_optional_gpu_preparation_is_in_settings_fingerprint_boundary(self):
        args = SimpleNamespace(model=None, live_seconds=None, neuflow_model=self.root / "flow.onnx")

        def prepare():
            self.personal.write_text("external change", encoding="utf-8")
            raise RuntimeError("preparation failed")

        report = {"checks": []}
        with patch("osr_screen_tcode.runtime_check._prepare_v2_gpu_runtime", side_effect=prepare):
            with self.assertRaisesRegex(RuntimeError, "Personal settings changed"):
                _perform_checks(args, report)
        self.assertFalse(report["personal_settings_unchanged"])
        self.assertEqual(self.personal.read_text(encoding="utf-8"), "external change")

    def test_vittrack_diagnostic_requires_correct_subject_not_only_confidence(self):
        backend = Mock()
        backend.initialize.return_value = SimpleNamespace(valid=True)
        backend.update.return_value = SimpleNamespace(valid=True, confidence=.99, bbox_xywh=(0, 0, 80, 80))
        with patch("osr_screen_tcode.v2_models.ViTTrackBackend", return_value=backend):
            with self.assertRaisesRegex(RuntimeError, "incorrect subject"):
                _check_vittrack(self.root / "vit.onnx", {"checks": []})

    def test_neuflow_diagnostic_requires_cuda_and_bidirectional_translation(self):
        forward = np.zeros((384, 640, 2), np.float32)
        forward[..., 0] = 8
        backward = -forward
        backend = Mock(provider="CUDAExecutionProvider")
        backend.infer.return_value = SimpleNamespace(valid=True, reason="ready", forward=forward, backward=backward)
        report = {"checks": []}
        with patch("osr_screen_tcode.v2_models.NeuFlowBackend", return_value=backend) as factory:
            _check_neuflow(self.root / "flow.onnx", report)
            factory.assert_called_once_with(str(self.root / "flow.onnx"), device="cuda", require_gpu=True)
            self.assertEqual(backend.infer.call_count, 2)
            self.assertNotIn(str(self.root), json.dumps(report))
            backend.provider = "CPUExecutionProvider"
            with self.assertRaisesRegex(RuntimeError, "CUDA diagnostic failed"):
                _check_neuflow(self.root / "flow.onnx", {"checks": []})
            backend.provider = "CUDAExecutionProvider"
            backward[..., 0] = 8  # Wrong reverse direction must not pass.
            with self.assertRaisesRegex(RuntimeError, "known frame translation"):
                _check_neuflow(self.root / "flow.onnx", {"checks": []})

    def test_isolation_is_active_before_checks_and_restored_after_failure(self):
        original_load = config.AppConfig.load.__func__

        def fail(report):
            self.assertNotEqual(config.CONFIG_PATH, self.personal)
            self.assertEqual(config.CONFIG_PATH.parent, config.APP_DIR)
            self.assertTrue(config.APP_DIR.is_dir())
            self.assertEqual(config.AppConfig.load().last_sink, "Log only")
            config.AppConfig().save()
            self.assertFalse(config.CONFIG_PATH.exists())
            raise ValueError("checking failed")

        report = {"checks": []}
        args = type("Args", (), {"model": None, "live_seconds": None})()
        with patch("osr_screen_tcode.runtime_check._check_dependencies", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "checking failed"):
                _perform_checks(args, report)
        self.assertEqual(config.CONFIG_PATH, self.personal)
        self.assertIs(config.AppConfig.load.__func__, original_load)
        self.assertTrue(report["personal_settings_unchanged"])
        self.assertEqual(self.personal.read_bytes(), self.original)

    def test_external_settings_change_is_detected_without_overwriting_it(self):
        report = {}
        with self.assertRaisesRegex(RuntimeError, "Personal settings changed"):
            with isolated_settings(report):
                self.personal.write_text("new user setting", encoding="utf-8")
        self.assertFalse(report["personal_settings_unchanged"])
        self.assertEqual(self.personal.read_text(encoding="utf-8"), "new user setting")

    def test_optional_model_and_live_checks_remain_inside_isolation(self):
        report = {"checks": []}
        model = self.root / "model.onnx"
        args = type("Args", (), {"model": model, "live_seconds": 2, "language": "zh"})()

        def live(seconds, language, path, current_report):
            self.assertNotEqual(config.CONFIG_PATH, self.personal)
            self.assertEqual((seconds, language, path), (2, "zh", model))
            self.assertIs(current_report, report)
            config.AppConfig().save()

        with patch("osr_screen_tcode.runtime_check._check_dependencies"), \
                patch("osr_screen_tcode.runtime_check._check_model") as check_model, \
                patch("osr_screen_tcode.runtime_check._check_live", side_effect=live):
            _perform_checks(args, report)
        check_model.assert_called_once_with(model, report)
        self.assertEqual(self.personal.read_bytes(), self.original)
        self.assertTrue(report["personal_settings_unchanged"])

    def test_main_entry_dispatches_before_any_main_or_gpu_import(self):
        original_import = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name in {"osr_screen_tcode.app", "osr_screen_tcode.gpu_runtime", "osr_screen_tcode.preview_lab_launcher"}:
                raise AssertionError("Main entry imported another mode before runtime diagnostics")
            return original_import(name, *args, **kwargs)

        with patch("sys.argv", ["OSR.exe", "--runtime-check", str(self.output)]), \
                patch("osr_screen_tcode.runtime_check.run_runtime_check", side_effect=SystemExit(0)) as check, \
                patch("builtins.__import__", side_effect=guarded):
            with self.assertRaises(SystemExit) as exited:
                runpy.run_module("osr_screen_tcode", run_name="__main__")
        self.assertEqual(exited.exception.code, 0)
        check.assert_called_once_with(["--runtime-check", str(self.output)])
