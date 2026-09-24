from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from osr_screen_tcode.preview_lab_launcher import PreviewLabLauncher


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

    def test_frozen_build_reports_source_requirement(self):
        with patch("sys.frozen", True, create=True):
            with self.assertRaisesRegex(RuntimeError, "Start.cmd"):
                PreviewLabLauncher().start()
