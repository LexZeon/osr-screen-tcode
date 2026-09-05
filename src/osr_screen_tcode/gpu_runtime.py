"""Isolated optional CUDA runtime installation and real, subprocess GPU checks."""
from __future__ import annotations

import json
import ctypes
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from .config import APP_DIR, AppConfig


GPU_ROOT = APP_DIR / "gpu-runtime"
ACTIVE_FILE = GPU_ROOT / "active.json"
# Keep CUDA 12 builds: newer ORT releases can switch the default CUDA major version.
GPU_REQUIREMENT = "onnxruntime-gpu[cuda,cudnn]>=1.21,<1.27"
DML_REQUIREMENT = "onnxruntime-directml>=1.21,<1.25"
PROVIDERS = {"cuda": "CUDAExecutionProvider", "directml": "DmlExecutionProvider"}
# ORT's MIT-licensed arithmetic-only diagnostic graph; no downloaded pose weights.
_GPU_PROBE_MODEL = base64.b64decode("CAMSBmNoZW50YTpwChUKAVgKAVcSAVkaBW11bF8xIgNNdWwSCG11bCB0ZXN0KiMIAwgCEAEiGAAAgD8AAABAAABAQAAAgEAAAKBAAADAQEIBV1oTCgFYEg4KDAgBEggKAggDCgIIAmITCgFZEg4KDAgBEggKAggDCgIIAkIECgAQBw==")
_dll_handles = []
_active_path: Path | None = None
_preloaded = False
_dll_directories: set[str] = set()


def cuda_dll_directories(cuda_major: str) -> list[Path]:
    """Bounded lookup of existing installations, never a recursive disk scan."""
    roots = []
    if _active_path:
        roots.append(_active_path)
    roots.extend(Path(path) for path in sys.path if path and Path(path).is_absolute())
    candidates = []
    for root in dict.fromkeys(roots):
        candidates.extend(sorted((root / "nvidia").glob("*/bin")))
        candidates.append(root / "torch" / "lib")
    for key, value in os.environ.items():
        if key.upper().startswith(("CUDA_PATH", "CUDNN_PATH")) and value:
            root = Path(value)
            candidates.extend([root, root / "bin", root / "bin" / f"{cuda_major}.0"])
            candidates.extend(sorted((root / "bin").glob(f"{cuda_major}.*")))
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    toolkit = program_files / "NVIDIA GPU Computing Toolkit" / "CUDA"
    candidates.extend(sorted(toolkit.glob(f"v{cuda_major}.*/bin"), reverse=True))
    cudnn = program_files / "NVIDIA" / "CUDNN"
    candidates.extend(sorted(cudnn.glob(f"v*/bin/{cuda_major}.*"), reverse=True))
    candidates.extend(sorted(cudnn.glob("v*/bin"), reverse=True))
    candidates.extend(Path(path.strip('"')) for path in os.environ.get("PATH", "").split(os.pathsep) if path)
    found = []
    for candidate in dict.fromkeys(candidates):
        if not candidate.is_absolute() or not candidate.is_dir():
            continue
        # An unrelated CUDA major must not shadow the libraries required by ORT.
        if any(candidate.glob(f"cudart64_{cuda_major}*.dll")) or any(candidate.glob("cudnn64_*.dll")):
            found.append(candidate.resolve())
    return list(dict.fromkeys(found))


def runtime_backend() -> str:
    backend = os.environ.get("OSR_TCODE_GPU_BACKEND")
    if backend is None:
        backend = AppConfig.load().extra.get("rtm_pose_gpu_backend", "cuda")
    return backend if backend in PROVIDERS else "cuda"


def runtime_pointer(backend: str) -> Path:
    return ACTIVE_FILE if backend == "cuda" else GPU_ROOT / "active-directml.json"


def selected_runtime(backend: str | None = None) -> Path | None:
    override = os.environ.get("OSR_TCODE_GPU_PROBE_PATH")
    if override:
        path = Path(override).resolve()
    else:
        try:
            record = json.loads(runtime_pointer(backend or runtime_backend()).read_text(encoding="utf-8"))
            if record["python"] != list(sys.version_info[:2]):
                return None
            name = record["directory"]
            if not isinstance(name, str) or Path(name).name != name:
                return None
            path = (GPU_ROOT / name).resolve()
        except (OSError, ValueError, TypeError, KeyError):
            return None
    if not path.is_relative_to(GPU_ROOT.resolve()) or not (path / "onnxruntime" / "__init__.py").is_file():
        return None
    return path


def activate_local_runtime() -> None:
    global _active_path
    if "onnxruntime" in sys.modules:
        return
    path = selected_runtime()
    if path is None:
        return
    _active_path = path
    if str(path) not in sys.path:
        # The overlay contains only ORT/NVIDIA, never numpy, OpenCV or other base dependencies.
        sys.path.insert(0, str(path))
    if os.name == "nt":
        for directory in [path / "onnxruntime" / "capi", *sorted((path / "nvidia").glob("*/bin"))]:
            if directory.is_dir():
                _dll_handles.append(os.add_dll_directory(str(directory)))


def preload_cuda_runtime() -> None:
    global _preloaded
    if _preloaded:
        return
    import onnxruntime as ort

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return
    if os.name == "nt":
        cuda_major = str(getattr(ort, "cuda_version", "") or "12").split(".")[0]
        for directory in cuda_dll_directories(cuda_major):
            if str(directory) not in _dll_directories:
                _dll_handles.append(os.add_dll_directory(str(directory)))
                _dll_directories.add(str(directory))
    if hasattr(ort, "preload_dlls"):
        ort.preload_dlls(directory="" if _active_path else None)
    _preloaded = True


def _hidden_process_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def detect_nvidia() -> bool:
    candidates = [shutil.which("nvidia-smi")]
    if os.name == "nt":
        candidates += [str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/nvidia-smi.exe"),
                       str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "NVIDIA Corporation/NVSMI/nvidia-smi.exe")]
    for candidate in dict.fromkeys(c for c in candidates if c):
        try:
            result = subprocess.run([candidate, "--query-gpu=name", "--format=csv,noheader"],
                                    capture_output=True, text=True, timeout=5, **_hidden_process_options())
            if result.returncode == 0 and result.stdout.strip():
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    if os.name == "nt":
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "@(Get-CimInstance Win32_VideoController | Where-Object { $_.PNPDeviceID -match 'VEN_10DE' }).Count"],
                capture_output=True, text=True, timeout=8, **_hidden_process_options())
            return result.returncode == 0 and int(result.stdout.strip()) > 0
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return False


def _verify_cuda(ort) -> None:
    import numpy as np

    preload_cuda_runtime()
    options = ort.SessionOptions()
    options.log_severity_level = 3
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    session = ort.InferenceSession(_GPU_PROBE_MODEL, sess_options=options,
                                   providers=["CUDAExecutionProvider"])
    if "CUDAExecutionProvider" not in session.get_providers():
        raise RuntimeError("provider_fallback")
    output = session.run(None, {"X": np.ones((3, 2), dtype=np.float32)})[0]
    if not np.allclose(output, np.arange(1, 7, dtype=np.float32).reshape(3, 2)):
        raise RuntimeError("invalid_gpu_result")
    # The tiny arithmetic probe does not exercise cuDNN, but pose convolutions need it.
    if os.name == "nt":
        version = tuple(int(part) for part in ort.__version__.split(".")[:2])
        try:
            ctypes.CDLL("cudnn64_9.dll" if version >= (1, 19) else "cudnn64_8.dll")
        except OSError as exc:
            raise RuntimeError("cudnn_missing") from exc


def directml_session_options(ort):
    options = ort.SessionOptions()
    options.enable_mem_pattern = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return options


def _verify_directml(ort) -> None:
    import numpy as np

    options = directml_session_options(ort)
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    session = ort.InferenceSession(_GPU_PROBE_MODEL, sess_options=options,
        providers=[("DmlExecutionProvider", {"device_id": 0})])
    if "DmlExecutionProvider" not in session.get_providers():
        raise RuntimeError("provider_fallback")
    result = session.run(None, {"X": np.ones((3, 2), dtype=np.float32)})[0]
    if not np.allclose(result, np.arange(1, 7, dtype=np.float32).reshape(3, 2)):
        raise RuntimeError("invalid_gpu_result")


def runtime_needs_restart(backend: str) -> bool:
    selected = selected_runtime(backend)
    if selected is not None and selected != _active_path:
        return True
    ort = sys.modules.get("onnxruntime")
    if selected is None or ort is None:
        return False
    return PROVIDERS[backend] not in ort.get_available_providers()


def probe_in_process(backend: str = "cuda") -> dict:
    nvidia = detect_nvidia() if backend == "cuda" else False
    result = {"nvidia": nvidia, "cuda": False, "reason": "no_nvidia" if not nvidia else "runtime"}
    result.update(backend=backend, ready=False)
    try:
        import onnxruntime as ort
        result.update(ort_version=ort.__version__, providers=ort.get_available_providers(),
                      cuda_version=str(getattr(ort, "cuda_version", "") or ""))
        if PROVIDERS[backend] not in result["providers"]:
            result["reason"] = "dml_missing" if backend == "directml" else "cpu_ort" if nvidia else "no_nvidia"
            if backend == "cuda" and nvidia and "DmlExecutionProvider" in result["providers"]:
                result["reason"] = "cuda_engine_missing"
            return result
        if backend == "directml":
            _verify_directml(ort)
            result.update(ready=True, reason="ready")
        else:
            _verify_cuda(ort)
            result.update(nvidia=True, cuda=True, ready=True, reason="ready")
    except ImportError:
        result["reason"] = "ort_missing"
    except Exception as exc:
        # Driver, DLL and provider failures stay in the subprocess; keep the desktop app alive.
        result["reason"] = "cudnn_missing" if str(exc) == "cudnn_missing" else "load_failed"
    return result


def _run_bounded(args: list[str], cancel: threading.Event, timeout: float, env=None) -> str:
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace", env=env, **_hidden_process_options())
    deadline = time.monotonic() + timeout
    while True:
        if cancel.is_set() or time.monotonic() >= deadline:
            process.kill()
            process.communicate()
            raise RuntimeError("cancelled" if cancel.is_set() else "timeout")
        try:
            output, _ = process.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            continue
    if process.returncode:
        raise RuntimeError("subprocess_failed")
    return output


def probe_gpu(cancel: threading.Event | None = None, runtime: Path | None = None, backend: str = "cuda") -> dict:
    env = os.environ.copy()
    env["OSR_TCODE_GPU_BACKEND"] = backend
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    if runtime:
        env["OSR_TCODE_GPU_PROBE_PATH"] = str(runtime)
    if getattr(sys, "frozen", False):
        GPU_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="probe-", dir=GPU_ROOT) as temporary:
            result_file = Path(temporary) / "result.json"
            _run_bounded([sys.executable, "--gpu-probe", str(result_file)],
                         cancel or threading.Event(), 45, env=env)
            output = "GPU_RESULT=" + result_file.read_text(encoding="utf-8")
    else:
        output = _run_bounded([sys.executable, "-m", "osr_screen_tcode.gpu_runtime"],
                              cancel or threading.Event(), 45, env=env)
    for line in reversed(output.splitlines()):
        if line.startswith("GPU_RESULT="):
            result = json.loads(line.removeprefix("GPU_RESULT="))
            if isinstance(result, dict) and isinstance(result.get("cuda"), bool) and isinstance(result.get("nvidia"), bool):
                return result
    raise RuntimeError("invalid_probe_result")


def install_runtime(cancel: threading.Event, progress, backend: str = "cuda") -> dict:
    GPU_ROOT.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(GPU_ROOT).free < 5 * 1024 ** 3:
        raise RuntimeError("insufficient_disk_space")
    with tempfile.TemporaryDirectory(prefix="install-", dir=GPU_ROOT) as temporary:
        stage = Path(temporary)
        packages = stage / "packages"
        from .gpu_downloads import download_runtime_wheels

        requirement = DML_REQUIREMENT if backend == "directml" else GPU_REQUIREMENT
        pip_command = [sys.executable, "--gpu-pip", str(stage / "pip-output.log")] if getattr(sys, "frozen", False) else [sys.executable, "-m", "pip"]
        wheels = download_runtime_wheels(stage, requirement, cancel, progress, _run_bounded, pip_command=pip_command)
        progress({"stage": "installing"})
        _run_bounded([*pip_command, "--isolated", "install", "--no-input", "--no-compile",
                      "--disable-pip-version-check", "--no-cache-dir", "--only-binary=:all:",
                      "--no-index", "--find-links", str(wheels), "--target", str(packages), requirement],
                     cancel, 1800)
        overlay = stage / "runtime"
        overlay.mkdir()
        for source in packages.iterdir():
            if source.name in {"onnxruntime", "nvidia"} or (
                source.name.endswith(".dist-info") and source.name.startswith(("onnxruntime_gpu-", "onnxruntime_directml-", "nvidia_"))
            ):
                source.rename(overlay / source.name)
        progress({"stage": "verifying"})
        result = probe_gpu(cancel, overlay, backend=backend)
        if not result.get("ready", result.get("cuda")) or cancel.is_set():
            raise RuntimeError("verification_failed")
        destination = GPU_ROOT / ("runtime-" + uuid.uuid4().hex)
        overlay.rename(destination)
        record = {"directory": destination.name, "python": list(sys.version_info[:2])}
        pending = stage / "active.json"
        pending.write_text(json.dumps(record), encoding="utf-8")
        # Only publish a verified runtime. A failed install leaves the previous pointer intact.
        pending.replace(runtime_pointer(backend))
        return result


def run_background_command(args: list[str]) -> bool:
    if not args or args[0] not in {"--gpu-probe", "--gpu-pip"}:
        return False
    if len(args) < 2:
        raise ValueError("Missing diagnostic output path")
    output = Path(args[1]).resolve()
    if not output.is_relative_to(GPU_ROOT.resolve()) or not output.parent.is_dir():
        raise ValueError("Diagnostic output must stay in the private GPU directory")
    if args[0] == "--gpu-probe":
        activate_local_runtime()
        output.write_text(json.dumps(probe_in_process(runtime_backend())), encoding="utf-8")
        return True
    # Windowed executables have no stdout. Pip writes to a private, temporary log;
    # only wheel resolution/target installation is used, never the host environment.
    options = args[2:]
    if options[:2] != ["--isolated", "install"] or "--only-binary=:all:" not in options:
        raise ValueError("Only isolated binary wheel installation is supported")
    location_flag = "--report" if "--dry-run" in options else "--target"
    location = Path(options[options.index(location_flag) + 1]).resolve()
    if location == GPU_ROOT.resolve() or not location.is_relative_to(GPU_ROOT.resolve()):
        raise ValueError("Pip output must stay in the private GPU directory")
    if getattr(sys, "frozen", False):
        import pip._vendor.distlib as distlib
        from pip._vendor.distlib.resources import ResourceFinder, register_finder

        # PyInstaller extracts pip's launcher resources next to the frozen package.
        register_finder(distlib.__loader__, ResourceFinder)
    from pip._internal.cli.main import main as pip_main

    with output.open("w", encoding="utf-8") as log:
        sys.stdout = sys.stderr = log
        raise SystemExit(pip_main(args[2:]))


if __name__ == "__main__":
    activate_local_runtime()
    print("GPU_RESULT=" + json.dumps(probe_in_process(runtime_backend())))
