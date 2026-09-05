"""Explicit online smoke check; quarantined install, no active user setting changes."""
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from osr_screen_tcode import gpu_runtime as gpu


if __name__ == "__main__":
    gpu.GPU_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qa-directml-", dir=gpu.GPU_ROOT) as directory:
        root = Path(directory)
        def progress(data):
            print(data, flush=True)
        with patch.object(gpu, "GPU_ROOT", root), patch.object(gpu, "ACTIVE_FILE", root / "active.json"):
            result = gpu.install_runtime(threading.Event(), progress, backend="directml")
            print("DIRECTML_VERIFIED", result, flush=True)
            assert (root / "active-directml.json").is_file()
    print("Quarantined runtime removed; user runtime pointers and settings unchanged.", flush=True)
