"""No-GUI checks of the portable diagnostic's routing and isolation."""
import builtins
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from osr_screen_tcode import config
from osr_screen_tcode.runtime_check import (
    _perform_checks, isolated_settings, run_runtime_check,
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
