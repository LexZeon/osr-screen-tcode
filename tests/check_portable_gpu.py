"""Explicit online check of the frozen GPU installer in a disposable user profile."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

from osr_screen_tcode import gpu_runtime as gpu


parser = argparse.ArgumentParser()
parser.add_argument("exe", type=Path)
args = parser.parse_args()
exe = args.exe.resolve()
assert exe.is_file()
run_bounded = gpu._run_bounded


def run_with_diagnostics(command, *args, **kwargs):
    try:
        return run_bounded(command, *args, **kwargs)
    except Exception:
        if "--gpu-pip" in command:
            log = Path(command[command.index("--gpu-pip") + 1])
            if log.is_file():
                print(log.read_text(encoding="utf-8", errors="replace")[-12000:], flush=True)
        raise


with tempfile.TemporaryDirectory(prefix="osr-portable-gpu-") as directory:
    home = Path(directory)
    root = home / ".osr_screen_tcode_2_0_test" / "gpu-runtime"
    with patch.dict(os.environ, {"USERPROFILE": str(home), "HOME": str(home)}), \
            patch.object(gpu, "GPU_ROOT", root), patch.object(gpu, "ACTIVE_FILE", root / "active.json"), \
            patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(exe)), \
            patch.object(gpu, "_run_bounded", side_effect=run_with_diagnostics):
        before = gpu.probe_gpu(backend="directml")
        print("CLEAN_PROFILE", before, flush=True)
        assert before["reason"] == "dml_missing"
        result = gpu.install_runtime(threading.Event(), lambda data: print(data, flush=True), backend="directml")
        assert result["ready"]
        after = gpu.probe_gpu(backend="directml")
        assert after["ready"]
        print("PORTABLE_DIRECTML_VERIFIED", after, flush=True)
print("Temporary profile removed; real user runtimes unchanged.", flush=True)
