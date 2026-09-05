import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from osr_screen_tcode import gpu_runtime as gpu


class GpuRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in (("GPU_ROOT", self.root), ("ACTIVE_FILE", self.root / "active.json")):
            p = patch.object(gpu, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict("os.environ", {}, clear=False)
        p.start()
        self.addCleanup(p.stop)
        gpu.os.environ.pop("OSR_TCODE_GPU_PROBE_PATH", None)

    def fake_pip(self, args, *_args, **_kwargs):
        self.assertIn("--isolated", args)
        self.assertIn("--only-binary=:all:", args)
        self.assertIn("--no-index", args)
        self.assertIn("--find-links", args)
        self.assertIn(gpu.GPU_REQUIREMENT, args)
        target = Path(args[args.index("--target") + 1])
        self.assertTrue(target.is_relative_to(self.root))
        for name in ("onnxruntime", "nvidia", "numpy", "onnxruntime_gpu-1.26.0.dist-info", "nvidia_cuda_runtime_cu12-12.dist-info"):
            (target / name).mkdir(parents=True)
        (target / "onnxruntime/__init__.py").write_text("", encoding="utf-8")
        return "ok"

    def test_install_is_isolated_verified_and_does_not_overlay_numpy(self):
        stages = []
        with patch("osr_screen_tcode.gpu_downloads.download_runtime_wheels", return_value=self.root / "wheels"), patch.object(gpu, "_run_bounded", side_effect=self.fake_pip), patch.object(gpu, "probe_gpu", return_value={"nvidia": True, "cuda": True}), patch.object(gpu.shutil, "disk_usage", return_value=type("Disk", (), {"free": 10 * 1024 ** 3})()):
            gpu.install_runtime(threading.Event(), stages.append)
        selected = gpu.selected_runtime()
        self.assertTrue((selected / "onnxruntime").is_dir())
        self.assertTrue((selected / "nvidia").is_dir())
        self.assertFalse((selected / "numpy").exists())
        self.assertEqual(stages, [{"stage": "installing"}, {"stage": "verifying"}])
        self.assertFalse(list(self.root.glob("install-*")))

    def test_failed_verification_preserves_existing_runtime(self):
        old = '{"directory": "previous", "python": [3, 12]}'
        gpu.ACTIVE_FILE.write_text(old, encoding="utf-8")
        with patch("osr_screen_tcode.gpu_downloads.download_runtime_wheels", return_value=self.root / "wheels"), patch.object(gpu, "_run_bounded", side_effect=self.fake_pip), patch.object(gpu, "probe_gpu", return_value={"nvidia": True, "cuda": False}), patch.object(gpu.shutil, "disk_usage", return_value=type("Disk", (), {"free": 10 * 1024 ** 3})()):
            with self.assertRaisesRegex(RuntimeError, "verification_failed"):
                gpu.install_runtime(threading.Event(), lambda _: None)
        self.assertEqual(gpu.ACTIVE_FILE.read_text(encoding="utf-8"), old)
        self.assertFalse(list(self.root.glob("install-*")))

    def test_no_space_does_not_start_installer(self):
        with patch.object(gpu.shutil, "disk_usage", return_value=type("Disk", (), {"free": 0})()), patch.object(gpu, "_run_bounded") as run:
            with self.assertRaisesRegex(RuntimeError, "insufficient_disk_space"):
                gpu.install_runtime(threading.Event(), lambda _: None)
            run.assert_not_called()

    def test_unsafe_pointer_and_python_mismatch_are_ignored(self):
        for record in ({"directory": "../other", "python": list(sys.version_info[:2])},
                       {"directory": "runtime-test", "python": [0, 0]}):
            gpu.ACTIVE_FILE.write_text(json.dumps(record), encoding="utf-8")
            self.assertIsNone(gpu.selected_runtime())

    def test_cancel_and_timeout_terminate_child(self):
        for cancel, timeout, message in ((threading.Event(), 0.05, "timeout"), (threading.Event(), 5, "cancelled")):
            if message == "cancelled":
                cancel.set()
            start = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, message):
                gpu._run_bounded([sys.executable, "-c", "import time; time.sleep(10)"], cancel, timeout)
            self.assertLess(time.monotonic() - start, 3)

    def test_probe_parses_subprocess_result_not_provider_listing(self):
        with patch.object(gpu, "_run_bounded", return_value='warning\nGPU_RESULT={"nvidia": true, "cuda": false, "reason": "runtime"}\n'):
            self.assertEqual(gpu.probe_gpu()["cuda"], False)
        with patch.object(gpu, "_run_bounded", return_value="broken"):
            with self.assertRaisesRegex(RuntimeError, "invalid_probe_result"):
                gpu.probe_gpu()

    def test_cpu_only_engine_is_not_reported_as_missing_cuda(self):
        ort = SimpleNamespace(__version__="1.29.0", get_available_providers=lambda: ["CPUExecutionProvider"])
        with patch.dict(sys.modules, {"onnxruntime": ort}), patch.object(gpu, "detect_nvidia", return_value=True), patch.object(gpu, "_verify_cuda") as verify:
            result = gpu.probe_in_process()
            self.assertEqual(result["reason"], "cpu_ort")
            self.assertEqual(result["ort_version"], "1.29.0")
            self.assertFalse(result["cuda"])
            verify.assert_not_called()

    def test_cuda_probe_still_runs_when_nvidia_inventory_misses_gpu(self):
        ort = SimpleNamespace(__version__="1.26.0", cuda_version="12.8", get_available_providers=lambda: ["CUDAExecutionProvider"])
        with patch.dict(sys.modules, {"onnxruntime": ort}), patch.object(gpu, "detect_nvidia", return_value=False), patch.object(gpu, "_verify_cuda"):
            self.assertTrue(gpu.probe_in_process()["cuda"])

    def test_provider_listing_alone_is_never_success(self):
        ort = SimpleNamespace(__version__="1.26.0", get_available_providers=lambda: ["CUDAExecutionProvider"])
        for error, reason in (("provider_fallback", "load_failed"), ("cudnn_missing", "cudnn_missing")):
            with patch.dict(sys.modules, {"onnxruntime": ort}), patch.object(gpu, "detect_nvidia", return_value=True), patch.object(gpu, "_verify_cuda", side_effect=RuntimeError(error)):
                result = gpu.probe_in_process()
                self.assertFalse(result["cuda"])
                self.assertEqual(result["reason"], reason)

    def test_dll_lookup_handles_custom_cuda_and_cudnn_not_on_path(self):
        cuda = self.root / "CUDA" / "bin"
        cudnn = self.root / "cuDNN" / "bin" / "12.9"
        wrong = self.root / "WrongCuda" / "bin"
        for path, dll in ((cuda, "cudart64_12.dll"), (cudnn, "cudnn64_9.dll"), (wrong, "cudart64_13.dll")):
            path.mkdir(parents=True)
            (path / dll).touch()
        with patch.dict(gpu.os.environ, {"CUDA_PATH": str(cuda.parent), "CUDA_PATH_V13_0": str(wrong.parent),
                                        "CUDNN_PATH": str(cudnn.parent.parent), "PATH": "", "ProgramFiles": str(self.root)}, clear=True), patch.object(gpu.sys, "path", []), patch.object(gpu, "_active_path", None):
            found = gpu.cuda_dll_directories("12")
            self.assertEqual(set(found), {cuda.resolve(), cudnn.resolve()})


if __name__ == "__main__":
    unittest.main()
