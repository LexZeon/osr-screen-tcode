"""Resolve wheels with pip; download verified bytes with honest UI progress."""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen


def _wheel_source(url: str) -> str:
    parsed = urlsplit(url)
    name = unquote(parsed.path.rsplit("/", 1)[-1])
    if (parsed.scheme != "https" or parsed.hostname != "files.pythonhosted.org"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or Path(name).name != name or "/" in name or "\\" in name or not name.endswith(".whl")):
        raise RuntimeError("invalid_wheel_source")
    return name


def download_runtime_wheels(stage: Path, requirement: str, cancel, progress, run, *, pip_command=None) -> Path:
    report = stage / "resolve.json"
    progress({"stage": "resolving"})
    run([*(pip_command or [sys.executable, "-m", "pip"]), "--isolated", "install", "--dry-run", "--ignore-installed",
         "--report", str(report), "--no-input", "--disable-pip-version-check", "--no-cache-dir",
         "--only-binary=:all:", "--index-url", "https://pypi.org/simple", requirement], cancel, 1800)
    plan = json.loads(report.read_text(encoding="utf-8"))
    if plan.get("version") != "1" or not plan.get("install"):
        raise RuntimeError("invalid_download_plan")
    sources = []
    for item in plan["install"]:
        if cancel.is_set():
            raise RuntimeError("cancelled")
        info = item["download_info"]
        url = info["url"]
        name = _wheel_source(url)
        digest = info.get("archive_info", {}).get("hashes", {}).get("sha256", "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise RuntimeError("missing_wheel_hash")
        progress({"stage": "preparing", "component": item["metadata"]["name"]})
        with urlopen(Request(url, method="HEAD"), timeout=20) as response:
            _wheel_source(response.url)
            length = int(response.headers.get("Content-Length", "0"))
        sources.append((url, name, digest, max(0, length), item["metadata"]["name"]))
    total = sum(source[3] for source in sources) if all(source[3] for source in sources) else None
    if shutil.disk_usage(stage).free < max(5 * 1024 ** 3, (total or 0) * 3 + 256 * 1024 ** 2):
        raise RuntimeError("insufficient_disk_space")
    wheels = stage / "wheels"
    wheels.mkdir()
    completed = 0
    for index, (url, name, expected_hash, size, component) in enumerate(sources, 1):
        if cancel.is_set():
            raise RuntimeError("cancelled")
        def notify():
            progress({"stage": "downloading", "component": component, "index": index,
                      "count": len(sources), "downloaded": completed + downloaded, "total": total})

        partial = wheels / (name + ".part")
        for attempt in range(3):
            downloaded = 0
            digest = hashlib.sha256()
            last_update = 0.0
            notify()
            try:
                with urlopen(url, timeout=20) as response, partial.open("wb") as target:
                    _wheel_source(response.url)
                    while True:
                        if cancel.is_set():
                            raise RuntimeError("cancelled")
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
                        if time.monotonic() - last_update >= 0.25:
                            notify()
                            last_update = time.monotonic()
                if (size and downloaded != size) or digest.hexdigest() != expected_hash:
                    raise RuntimeError("download_verification_failed")
                break
            except (OSError, HTTPException, RuntimeError) as exc:
                partial.unlink(missing_ok=True)
                if isinstance(exc, RuntimeError) and str(exc) != "download_verification_failed":
                    raise
                if attempt == 2:
                    raise
                if cancel.wait(attempt + 1):
                    raise RuntimeError("cancelled") from exc
        partial.rename(wheels / name)
        notify()
        completed += downloaded
    return wheels
