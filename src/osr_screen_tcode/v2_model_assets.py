"""Pinned optional v2 models, stored outside the application and release ZIPs.

Checking availability never downloads anything. Downloads use a unique staging
file and become visible only after exact size and SHA-256 verification. Models
are data, never imported Python code or pickle checkpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import config


@dataclass(frozen=True)
class ModelAsset:
    model_id: str
    label: str
    filename: str
    size: int
    sha256: str
    url: str
    source_url: str
    revision: str
    license: str = "Apache-2.0"
    license_url: str = "https://www.apache.org/licenses/LICENSE-2.0.txt"

    @property
    def ready(self) -> bool:
        return (self.size > 0 and len(self.sha256) == 64
                and all(char in "0123456789abcdef" for char in self.sha256)
                and self.url.startswith("https://"))


MODEL_IDS = ("vittrack", "neuflow")
_ASSETS = {
    "vittrack": ModelAsset(
        "vittrack", "ViTTrack", "object_tracking_vittrack_2023sep.onnx", 714726,
        "2990f0b7cd44d92afa48cd97db6de7be113fc1d9594fddb74e2725c10478e91d",
        "https://huggingface.co/opencv/object_tracking_vittrack/resolve/"
        "868e4c941984c6363594ec34ee1c3ba0b75378a3/object_tracking_vittrack_2023sep.onnx",
        "https://huggingface.co/opencv/object_tracking_vittrack",
        "868e4c941984c6363594ec34ee1c3ba0b75378a3",
        license_url="https://huggingface.co/opencv/object_tracking_vittrack/raw/"
                    "868e4c941984c6363594ec34ee1c3ba0b75378a3/LICENSE",
    ),
    "neuflow": ModelAsset(
        "neuflow", "NeuFlow v2 (ONNX)", "NeuFlow-v2-OSR-ONNX-v1.onnx", 58416346,
        "589127d720dfb8fb27d1733381dda4aa73bc23ccda3e0fe008f0d1bf691eac8f",
        "https://github.com/LexZeon/osr-screen-tcode/releases/download/v2.0.2/"
        "NeuFlow-v2-OSR-ONNX-v1.onnx",
        "https://huggingface.co/Study-is-happy/neuflow-v2",
        "79ae2f4589456d4d369aaef4955c7db5918c3436",
        license_url="https://raw.githubusercontent.com/neufieldrobotics/NeuFlow_v2/"
                    "204b5e3744461d90303b9ff82caa7a1bb56a2ca2/LICENSE",
    ),
}
_LOCKS = {key: threading.Lock() for key in MODEL_IDS}
_CACHE: dict[tuple, bool] = {}
_CACHE_LOCK = threading.Lock()
_CHUNK = 64 * 1024
_NETWORK_TIMEOUT = 15
_TOTAL_TIMEOUT = 600


class ModelDownloadError(RuntimeError):
    """A bounded, user-facing error without private paths or signed URLs."""


class ModelDownloadCancelled(ModelDownloadError):
    pass


def model_info(model_id: str) -> ModelAsset:
    """Return the registered asset; IDs cannot provide paths or URLs."""
    if model_id == "neuflow_v2":
        model_id = "neuflow"
    try:
        return _ASSETS[model_id]
    except (KeyError, TypeError):
        raise ValueError("Unknown optional v2 model.") from None


def default_path(model_id: str) -> Path:
    return config.APP_DIR / "models" / "v2_models" / model_info(model_id).filename


def _file_key(path: Path, asset: ModelAsset) -> tuple:
    stat = path.stat()
    return (str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns,
            stat.st_ino, asset.sha256)


def validate_model_path(model_id: str, path: str | Path) -> tuple[bool, str]:
    """Accept only the exact tested ONNX, including for manually selected files."""
    asset = model_info(model_id)
    if not asset.ready:
        return False, "Model artifact is not available."
    try:
        candidate = Path(path)
        if candidate.suffix.lower() != ".onnx":
            return False, "Select the supported ONNX model."
        if not candidate.is_file():
            return False, "Model file is missing."
        key = _file_key(candidate, asset)
        if key[1] != asset.size:
            return False, "Model file size does not match. Download the supported model."
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
        if cached is None:
            digest = hashlib.sha256()
            with candidate.open("rb") as source:
                for chunk in iter(lambda: source.read(_CHUNK), b""):
                    digest.update(chunk)
            # Reject a file replaced or changed during validation.
            cached = digest.hexdigest() == asset.sha256 and _file_key(candidate, asset) == key
            with _CACHE_LOCK:
                if len(_CACHE) >= 64:
                    _CACHE.clear()
                _CACHE[key] = cached
        if not cached:
            return False, "Model checksum does not match. Download the supported model."
        return True, "Model verified."
    except (OSError, ValueError, TypeError):
        return False, "Model file cannot be read."


def find_existing_model(model_id: str) -> Path | None:
    path = default_path(model_id)
    return path if validate_model_path(model_id, path)[0] else None


def model_available(model_id: str) -> bool:
    return find_existing_model(model_id) is not None


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise ModelDownloadCancelled("Model download cancelled.")


class _SecureRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        host = (parts.hostname or "").lower()
        allowed = ("huggingface.co", "hf.co", "xethub.hf.co", "github.com",
                   "githubusercontent.com")
        if (parts.scheme != "https" or parts.username or parts.password
                or parts.port not in (None, 443)
                or not any(host == base or host.endswith("." + base) for base in allowed)):
            raise ModelDownloadError("The model server returned an unsupported redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_download(url: str):
    request = Request(url, headers={"User-Agent": "OSR-Optional-Models/1",
                                    "Accept-Encoding": "identity"})
    return build_opener(_SecureRedirect()).open(request, timeout=_NETWORK_TIMEOUT)


def download_model(model_id: str, cancel: threading.Event | None = None,
                   progress: Callable[[int, int], None] | None = None) -> Path:
    """Download explicitly on a worker thread; callback receives bytes/total.

    Cancellation is checked between reads; a stalled network read is bounded by
    15 seconds. Existing files survive cancellation, network or checksum errors.
    """
    asset = model_info(model_id)
    if not asset.ready:
        raise ModelDownloadError("Model artifact is not available.")
    _check_cancel(cancel)
    lock = _LOCKS[asset.model_id]
    while not lock.acquire(timeout=0.1):
        _check_cancel(cancel)
    partial: Path | None = None
    try:
        _check_cancel(cancel)
        existing = find_existing_model(asset.model_id)
        if existing is not None:
            if progress:
                progress(asset.size, asset.size)
            return existing
        target = default_path(asset.model_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        digest = hashlib.sha256()
        received = 0
        with _open_download(asset.url) as response:
            if response.getcode() != 200:
                raise ModelDownloadError("The model server could not provide the file.")
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) != asset.size:
                raise ModelDownloadError("The downloaded model size does not match.")
            with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent,
                                             prefix=asset.filename + ".", suffix=".part",
                                             delete=False) as output:
                partial = Path(output.name)
                if progress:
                    progress(0, asset.size)
                while True:
                    _check_cancel(cancel)
                    if time.monotonic() - started > _TOTAL_TIMEOUT:
                        raise ModelDownloadError("The model download timed out. Try again.")
                    chunk = response.read(_CHUNK)
                    _check_cancel(cancel)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > asset.size:
                        raise ModelDownloadError("The downloaded model size does not match.")
                    digest.update(chunk)
                    output.write(chunk)
                    if progress:
                        progress(received, asset.size)
                output.flush()
                os.fsync(output.fileno())
        if received != asset.size or digest.hexdigest() != asset.sha256:
            raise ModelDownloadError("Model verification failed. Try downloading again.")
        _check_cancel(cancel)
        os.replace(partial, target)
        partial = None
        return target
    except ModelDownloadError:
        raise
    except Exception:
        # urllib exceptions can contain signed CDN URLs; never surface them.
        raise ModelDownloadError("Model download failed. Check the network and available disk space.") from None
    finally:
        if partial is not None:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
        lock.release()
