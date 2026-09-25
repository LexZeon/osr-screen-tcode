from pathlib import Path
import builtins
import os
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from osr_screen_tcode.preview_lab_launcher import (
    PreviewLabLauncher, preview_lab_paths, preview_lab_script, run_preview_lab,
)


class PreviewLabLauncherTests(unittest.TestCase):
    def test_missing_lab_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                PreviewLabLauncher(Path(root)).start()

    def test_existing_process_does_not_spawn_duplicate(self):
        launcher = PreviewLabLauncher()
        launcher.process = Mock()
        launcher.process.poll.return_value = None
        with patch("osr_screen_tcode.preview_lab_launcher.subprocess.Popen") as spawn:
            self.assertFalse(launcher.start())
            spawn.assert_not_called()

    def test_launch_passes_no_host_configuration(self):
        with tempfile.TemporaryDirectory() as root:
            launcher = PreviewLabLauncher(Path(root))
            with patch.object(Path, "is_file", return_value=True), patch("osr_screen_tcode.preview_lab_launcher.subprocess.Popen") as spawn:
                self.assertTrue(launcher.start())
                argv = spawn.call_args.args[0]
                self.assertEqual(len(argv), 2)
                self.assertEqual(Path(argv[1]).name, "preview.py")
                self.assertNotIn("PYTHONPATH", spawn.call_args.kwargs["env"])
                self.assertEqual(Path(spawn.call_args.kwargs["cwd"]).name, "Pose-Preview-Lab")

    def test_frozen_launcher_uses_executable_and_private_log(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            resources = root / "portable" / "_internal"
            lab = resources / "Pose-Preview-Lab"
            lab.mkdir(parents=True)
            (lab / "preview.py").touch()
            executable = str(root / "portable" / "OSR.exe")
            home = root / "user"
            with patch("sys.frozen", True, create=True), patch("sys._MEIPASS", str(resources), create=True), \
                    patch("sys.executable", executable), patch.object(Path, "home", return_value=home), \
                    patch.dict(os.environ, {"PYTHONPATH": "host-source"}), \
                    patch("osr_screen_tcode.preview_lab_launcher.subprocess.Popen") as spawn:
                launcher = PreviewLabLauncher()
                self.assertTrue(launcher.start())
                self.assertEqual(spawn.call_args.args[0], [executable, "--preview-lab"])
                self.assertEqual(spawn.call_args.kwargs["cwd"], str(root / "portable"))
                self.assertNotIn("PYTHONPATH", spawn.call_args.kwargs["env"])
                self.assertEqual(launcher.log_path,
                                 home / ".osr_screen_tcode_2_0_test" / "preview-lab" / "preview-lab.log")
                self.assertTrue(launcher.log_path.is_file())
                self.assertFalse((resources / "logs").exists())

    def test_frozen_missing_resource_does_not_launch(self):
        with tempfile.TemporaryDirectory() as root, patch("sys.frozen", True, create=True), \
                patch("sys._MEIPASS", root, create=True), \
                patch("osr_screen_tcode.preview_lab_launcher.subprocess.Popen") as spawn:
            with self.assertRaisesRegex(FileNotFoundError, "Missing standalone preview"):
                PreviewLabLauncher().start()
            spawn.assert_not_called()

    def test_source_paths_preserve_local_settings_and_models(self):
        script = Path("checkout") / "Pose-Preview-Lab" / "preview.py"
        with patch("sys.frozen", False, create=True):
            settings, models = preview_lab_paths(script)
        self.assertEqual(settings, script.parent / "settings.local.json")
        self.assertEqual(models, Path("checkout") / "models")

    def test_frozen_paths_do_not_write_resource_folder_or_main_configuration(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            home = root / "user"
            executable = root / "portable" / "OSR.exe"
            script = root / "portable" / "_internal" / "Pose-Preview-Lab" / "preview.py"
            with patch("sys.frozen", True, create=True), patch("sys.executable", str(executable)), \
                    patch.object(Path, "home", return_value=home):
                settings, models = preview_lab_paths(script)
            self.assertEqual(settings, home / ".osr_screen_tcode_2_0_test" / "preview-lab" / "settings.json")
            self.assertEqual(models, executable.parent / "models")
            self.assertFalse(settings.parent.exists())  # Path discovery has no write side effects.
            self.assertFalse(settings.is_relative_to(script.parent))

    def test_frozen_resource_uses_bundle_not_cwd_or_source_override(self):
        with tempfile.TemporaryDirectory() as root:
            resources = Path(root) / "_internal"
            script = resources / "Pose-Preview-Lab" / "preview.py"
            script.parent.mkdir(parents=True)
            script.touch()
            with patch("sys.frozen", True, create=True), patch("sys._MEIPASS", str(resources), create=True):
                self.assertEqual(preview_lab_script(Path("unrelated-source")), script)

    def test_other_command_is_not_consumed(self):
        with patch("osr_screen_tcode.preview_lab_launcher.runpy.run_path") as execute:
            for args in ([], ["--smoke"], ["--gpu-probe", "result.json"]):
                self.assertFalse(run_preview_lab(args))
            execute.assert_not_called()

    def test_dispatch_forwards_only_lab_arguments_and_restores_process_state(self):
        script = Path("bundle") / "Pose-Preview-Lab" / "preview.py"
        original_argv, original_path = sys.argv, sys.path
        previous_path = sys.path[:]
        seen = []

        def execute(path, *, run_name):
            seen.append((path, run_name, sys.argv[:], sys.path[0]))
            sys.path.append("temporary-lab-import")

        with patch("osr_screen_tcode.preview_lab_launcher.preview_lab_script", return_value=script), \
                patch("osr_screen_tcode.preview_lab_launcher.runpy.run_path", side_effect=execute):
            self.assertTrue(run_preview_lab(["--preview-lab", "--smoke"]))
        self.assertEqual(seen, [(str(script), "__main__", [str(script), "--smoke"], str(script.parent))])
        self.assertIs(sys.argv, original_argv)
        self.assertIs(sys.path, original_path)
        self.assertEqual(sys.path, previous_path)

    def test_dispatch_failure_restores_process_state(self):
        script = Path("bundle") / "Pose-Preview-Lab" / "preview.py"
        original_argv, original_path = sys.argv, sys.path
        previous_path = sys.path[:]
        with patch("osr_screen_tcode.preview_lab_launcher.preview_lab_script", return_value=script), \
                patch("osr_screen_tcode.preview_lab_launcher.runpy.run_path", side_effect=SystemExit(2)):
            with self.assertRaises(SystemExit) as error:
                run_preview_lab(["--preview-lab", "--invalid"])
        self.assertEqual(error.exception.code, 2)
        self.assertIs(sys.argv, original_argv)
        self.assertIs(sys.path, original_path)
        self.assertEqual(sys.path, previous_path)

    def test_main_entry_dispatches_lab_before_main_gui_and_gpu(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name in {"osr_screen_tcode.app", "osr_screen_tcode.gpu_runtime"}:
                raise AssertionError(f"Lab must not import {name}")
            return original_import(name, *args, **kwargs)

        with patch("sys.argv", ["OSR.exe", "--preview-lab", "--smoke"]), \
                patch("osr_screen_tcode.preview_lab_launcher.run_preview_lab", return_value=True) as dispatch, \
                patch("builtins.__import__", side_effect=guarded_import):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_module("osr_screen_tcode", run_name="__main__")
        self.assertEqual(stopped.exception.code, 0)
        dispatch.assert_called_once_with(["--preview-lab", "--smoke"])
