"""Release assembly checks use synthetic files only; no application or installer runs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("osr_release_builder", ROOT / "tools" / "build_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="osr-release-files-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        self.dist = self.base / "dist" / release.PRODUCT
        self.output = self.base / "samples"
        self.commit = "a" * 40
        self.version = "2.0.0"
        for name in release.REQUIRED_SOURCE:
            self.write(self.root / name, "Release fixture\n")
        self.write(self.root / "src/osr_screen_tcode/__init__.py", f'__version__ = "{self.version}"\n')
        self.write(self.root / "tools/Start-Portable.cmd", "@echo off\r\necho portable\r\n")
        self.write(self.root / "tools/README-Portable.md", "Portable: extract everything.\n")
        self.tracked = sorted(Path(name) for name in release.REQUIRED_SOURCE)
        self.write(self.dist / (release.PRODUCT + ".exe"), b"fake executable, never launched")
        for name in release.LAB_MODULES:
            self.write(self.dist / "_internal" / "Pose-Preview-Lab" / name, "# bundled Lab\n")
        self.write(self.dist / "_internal" / "python313.dll", b"fake runtime")

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)

    def assemble(self, **kwargs):
        with patch.object(release, "git_snapshot", return_value=(self.commit, self.tracked)), \
                patch.object(release, "copy_licenses", side_effect=lambda folder: self.write(
                    folder / "licenses/NOTICE.txt", "Synthetic legal notice\n")):
            return release.assemble(self.root, self.dist, kwargs.get("output", self.output))

    def test_source_and_windows_archives_are_complete_and_independent(self):
        # Ignored/untracked private files must not even become candidates for a copy.
        self.write(self.root / "Pose-Preview-Lab/settings.local.json", '{"private":true}')
        self.write(self.root / "src/untracked.py", "# not committed\n")
        folder = self.assemble()
        self.assertEqual(folder, self.output / f"v{self.version}")
        source_zip = next(folder.glob("*-Source.zip"))
        windows_zip = next(folder.glob("*-Windows.zip"))
        with zipfile.ZipFile(source_zip) as archive:
            names = {"/".join(name.split("/")[1:]) for name in archive.namelist()}
            self.assertTrue(release.REQUIRED_SOURCE <= names)
            self.assertNotIn("Pose-Preview-Lab/settings.local.json", names)
            self.assertNotIn("src/untracked.py", names)
            source_prefix = archive.namelist()[0].split("/")[0]
            source_info = json.loads(archive.read(f"{source_prefix}/RELEASE_INFO.json"))
        with zipfile.ZipFile(windows_zip) as archive:
            prefix = archive.namelist()[0].split("/")[0]
            self.assertIn(f"{prefix}/{release.PRODUCT}.exe", archive.namelist())
            self.assertIn(f"{prefix}/_internal/python313.dll", archive.namelist())
            self.assertIn("--preview-lab", archive.read(f"{prefix}/Pose-Preview-Lab/Start.cmd").decode("ascii"))
            self.assertEqual(archive.read(f"{prefix}/Start.md"),
                             (self.root / "tools/README-Portable.md").read_bytes())
            self.assertIn(f"{prefix}/docs/Source_Start.md", archive.namelist())
            info = json.loads(archive.read(f"{prefix}/RELEASE_INFO.json"))
            self.assertEqual(info["source_commit"], self.commit)
            self.assertEqual(info["version"], self.version)
            self.assertEqual(info, source_info)
            self.assertEqual(info, json.loads((folder / "RELEASE_INFO.json").read_text(encoding="utf-8")))
            self.assertIs(info["source_tree_dirty"], False)
            self.assertNotIn(str(self.base), json.dumps(info))
            for line in archive.read(f"{prefix}/FILES_SHA256SUMS.txt").decode("utf-8").splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read(f"{prefix}/{name}")).hexdigest(), digest)
        for line in (folder / "SHA256SUMS.txt").read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(release.sha256(folder / name), digest)
        self.assertTrue((folder / "Start.cmd").is_file())
        self.assertFalse((self.output / "SHA256SUMS.txt").exists())

    def test_existing_version_and_old_checksum_are_never_overwritten(self):
        self.write(self.output / "SHA256SUMS.txt", "older releases\n")
        folder = self.assemble()
        before = (folder / "SHA256SUMS.txt").read_bytes()
        with self.assertRaises(FileExistsError):
            self.assemble()
        self.assertEqual((folder / "SHA256SUMS.txt").read_bytes(), before)
        self.assertEqual((self.output / "SHA256SUMS.txt").read_text(), "older releases\n")

    def test_missing_lab_bundle_is_rejected_before_creating_output(self):
        (self.dist / "_internal/Pose-Preview-Lab/preview.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "independent preview"):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_missing_required_tracked_source_cannot_silently_make_incomplete_zip(self):
        self.tracked.remove(Path("Pose-Preview-Lab/Start.md"))
        with self.assertRaisesRegex(RuntimeError, "Required release source"):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_accidentally_tracked_private_file_is_rejected_not_silently_omitted(self):
        relative = Path("Pose-Preview-Lab/settings.local.json")
        self.write(self.root / relative, "{}")
        self.tracked.append(relative)
        with self.assertRaisesRegex(RuntimeError, "Forbidden payload"):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_models_gpu_downloads_settings_logs_and_caches_are_rejected(self):
        for relative in (
            "models/pose.onnx", "MODELS/pose.data", "runtime/weights.safetensors",
            "runtime/DirectML.dll", "runtime/onnxruntime_providers_cuda.dll", "runtime/cudnn64_9.dll",
            "runtime/download.whl", "logs/session.txt", "runtime/debug.log", "runtime/__pycache__/code.pyc",
            "runtime/settings.local.json", "runtime/direct_url.json", "runtime/.env.local",
        ):
            with self.subTest(relative=relative):
                folder = self.base / "audit" / str(abs(hash(relative)))
                self.write(folder / relative, "private")
                with self.assertRaisesRegex(RuntimeError, "Forbidden payload"):
                    release.audit(folder, source=False)

    def test_private_path_of_another_user_is_rejected(self):
        folder = self.base / "private-path"
        # Construct sample private paths rather than embedding one in public test source.
        for index, value in enumerate(("C:" + "/Users/" + "OtherPerson/model.onnx",
                                       "/" + "home/" + "other_person/project",
                                       "C:" + "\\\\Users\\\\" + "OtherPerson\\\\model.onnx")):
            path = folder / f"source{index}.py"
            self.write(path, value)
            with self.assertRaisesRegex(RuntimeError, "Private build path"):
                release.audit_file(path, folder, source=True)
        # Regression fixtures and the scanner itself must also be publishable.
        release.audit_file(Path(__file__), ROOT, source=True)
        release.audit_file(ROOT / "tools/build_release.py", ROOT, source=True)

    def test_cpu_runtime_is_allowed_but_compiled_files_are_not_source(self):
        folder = self.base / "cpu-runtime"
        self.write(folder / "_internal/onnxruntime/capi/onnxruntime.dll", b"CPU DLL")
        self.assertEqual(len(release.audit(folder, source=False)), 1)
        with self.assertRaisesRegex(RuntimeError, "Compiled/source payload"):
            release.audit(folder, source=True)

    def test_source_paths_cannot_escape_the_repository(self):
        with self.assertRaisesRegex(RuntimeError, "Unsafe Git path"):
            release.select_source(self.root, [Path("../outside.py")])

    def test_git_snapshot_rejects_dirty_tree_and_never_includes_untracked_files(self):
        with patch.object(subprocess, "check_output", return_value=b" M Start.md\n"):
            with self.assertRaisesRegex(RuntimeError, "working tree must be clean"):
                release.git_snapshot(self.root)
        with patch.object(subprocess, "check_output", side_effect=[
            b"", (self.commit + "\n").encode(), b"Start.cmd\0Start.md\0",
        ]) as git:
            commit, paths = release.git_snapshot(self.root)
            self.assertEqual(commit, self.commit)
            self.assertEqual(paths, [Path("Start.cmd"), Path("Start.md")])
            self.assertEqual(git.call_args_list[-1].args[0], ["git", "ls-files", "--cached", "-z"])

    def test_source_change_during_packaging_fails_and_keeps_output_for_inspection(self):
        with patch.object(release, "git_snapshot", side_effect=[
            (self.commit, self.tracked), ("b" * 40, self.tracked),
        ]), patch.object(release, "copy_licenses"):
            with self.assertRaisesRegex(RuntimeError, "Source changed during packaging"):
                release.assemble(self.root, self.dist, self.output)
        self.assertTrue((self.output / f"v{self.version}").is_dir())

    def test_license_collection_keeps_embedded_notices_and_excludes_own_and_gpu_metadata(self):
        installed = self.base / "installed"
        packages = {
            "onnxruntime": ("ThirdPartyNotices.txt", "direct_url.json"),
            "numpy": ("dragon4_LICENSE.txt",),
            "osr-screen-tcode": ("LICENSE",),
            "onnxruntime-directml": ("LICENSE",),
            "onnxruntime-gpu": ("LICENSE",),
            "nvidia-cudnn-cu12": ("LICENSE",),
        }
        distributions = []
        for name, filenames in packages.items():
            package_root = installed / name
            for filename in filenames:
                self.write(package_root / filename, f"Original notice from {name}: {filename}\n")
            distributions.append(SimpleNamespace(
                metadata={"Name": name}, version="1.0", files=[Path(filename) for filename in filenames],
                locate_file=lambda path, base=package_root: base / path,
            ))
        destination = self.base / "licenses-output"
        self.write(destination / "LICENSE", "Project root license\n")
        original_license = (destination / "LICENSE").read_bytes()
        with patch.object(release.metadata, "distributions", return_value=distributions):
            release.copy_licenses(destination)
        for package, filename in (("onnxruntime", "ThirdPartyNotices.txt"), ("numpy", "dragon4_LICENSE.txt")):
            matches = list((destination / "licenses" / package).glob(f"*-{filename}"))
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].read_bytes(), (installed / package / filename).read_bytes())
        for excluded in ("osr-screen-tcode", "onnxruntime-directml", "onnxruntime-gpu", "nvidia-cudnn-cu12"):
            self.assertFalse((destination / "licenses" / excluded).exists())
        self.assertFalse(list(destination.rglob("direct_url.json")))
        self.assertEqual((destination / "LICENSE").read_bytes(), original_license)
        index = (destination / "licenses/INDEX.txt").read_text(encoding="utf-8")
        self.assertIn("onnxruntime 1.0", index)
        self.assertIn("numpy 1.0", index)
        self.assertNotIn("osr-screen-tcode", index)
        self.assertNotIn("onnxruntime-gpu", index)


if __name__ == "__main__":
    unittest.main()
