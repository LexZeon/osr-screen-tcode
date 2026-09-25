"""Launch the standalone visual-only lab without sharing analysis or sinks."""
from pathlib import Path
import os
import runpy
import subprocess
import sys


def preview_lab_data_dir() -> Path:
    """Keep the portable lab's preferences separate from the main settings."""
    return Path.home() / ".osr_screen_tcode_2_0_test" / "preview-lab"


def preview_lab_paths(script: Path) -> tuple[Path, Path]:
    """Return writable settings and optional model discovery locations."""
    if getattr(sys, "frozen", False):
        return preview_lab_data_dir() / "settings.json", Path(sys.executable).resolve().parent / "models"
    return script.parent / "settings.local.json", script.parent.parent / "models"


def preview_lab_script(source_root: Path | None = None) -> Path:
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = source_root or Path(__file__).resolve().parents[2]
    script = root / "Pose-Preview-Lab" / "preview.py"
    if not script.is_file():
        raise FileNotFoundError(f"Missing standalone preview: {script}")
    return script


def run_preview_lab(args: list[str]) -> bool:
    """Dispatch before importing the main GUI or optional GPU runtime."""
    if not args or args[0] != "--preview-lab":
        return False
    script = preview_lab_script()
    original_argv, original_path = sys.argv, sys.path
    saved_path = sys.path[:]
    try:
        sys.argv = [str(script), *args[1:]]
        sys.path.insert(0, str(script.parent))
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.argv = original_argv
        sys.path = original_path
        sys.path[:] = saved_path
    return True


class PreviewLabLauncher:
    def __init__(self, source_root: Path | None = None):
        self.root = source_root or Path(__file__).resolve().parents[2]
        self.process = None
        self.log_path = ((preview_lab_data_dir() if getattr(sys, "frozen", False)
                          else self.root / "logs") / "preview-lab.log")

    def start(self) -> bool:
        if self.process is not None and self.process.poll() is None:
            return False
        script = preview_lab_script(self.root)
        frozen = getattr(sys, "frozen", False)
        command = [sys.executable, "--preview-lab"] if frozen else [sys.executable, str(script)]
        working_directory = Path(sys.executable).resolve().parent if frozen else script.parent
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONUTF8"] = "1"
        # The child owns its independent GUI/settings; no device, region, model,
        # or output configuration is passed from the host application.
        with self.log_path.open("w", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                command, cwd=str(working_directory), env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        return True
