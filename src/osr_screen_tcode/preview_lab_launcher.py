"""Launch the standalone visual-only lab without sharing analysis or sinks."""
from pathlib import Path
import os
import subprocess
import sys


class PreviewLabLauncher:
    def __init__(self, source_root: Path | None = None):
        self.root = source_root or Path(__file__).resolve().parents[2]
        self.process = None
        self.log_path = self.root / "logs" / "preview-lab.log"

    def start(self) -> bool:
        if self.process is not None and self.process.poll() is None:
            return False
        if getattr(sys, "frozen", False):
            raise RuntimeError("This source test requires Start.cmd, not a packaged executable.")
        script = self.root / "Pose-Preview-Lab" / "preview.py"
        if not script.is_file():
            raise FileNotFoundError(f"Missing standalone preview: {script}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONUTF8"] = "1"
        # The child owns its independent GUI/settings; no device, region, model,
        # or output configuration is passed from the host application.
        with self.log_path.open("w", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                [sys.executable, str(script)], cwd=str(script.parent), env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        return True
