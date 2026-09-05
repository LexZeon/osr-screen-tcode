"""Assemble audited portable/source archives after building the current spec."""
from __future__ import annotations

import hashlib
from importlib import metadata
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from osr_screen_tcode import __version__

PRODUCT = "SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility"
NAME = f"{PRODUCT}-v{__version__}"
FORBIDDEN_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "models", "logs", "gpu-runtime"}
MODEL_SUFFIXES = {".onnx", ".pt", ".pth", ".safetensors", ".whl"}
PRIVATE_NAMES = {"osr_settings.json", "settings.json", "direct_url.json"}
GPU_BINARY = re.compile(r"directml\.dll|providers_(cuda|dml|tensorrt)|cudnn|cublas|cudart|nvrtc", re.I)
ROOT_FILES = {"README.md", "LICENSE", "OPEN_SOURCE_NOTICE.md", "THIRD_PARTY_NOTICES.md",
              "CHANGELOG_CN.txt", "AI_Prompting_Guide.md", "CONTRIBUTING.md", "requirements.txt",
              "pyproject.toml", "Start.cmd", "Start-Source.cmd", ".gitignore", PRODUCT + ".spec"}


def audit(folder: Path, source: bool) -> list[Path]:
    files = sorted(path for path in folder.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(folder)
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise RuntimeError(f"Unsafe archive path: {relative}")
        if (FORBIDDEN_PARTS.intersection(relative.parts) or path.suffix.lower() in MODEL_SUFFIXES
                or path.name in PRIVATE_NAMES or GPU_BINARY.search(path.name)):
            raise RuntimeError(f"Forbidden payload: {relative}")
        if source and path.suffix.lower() in {".exe", ".dll", ".pyd", ".pyc", ".pyo", ".zip"}:
            raise RuntimeError(f"Compiled/source payload: {relative}")
        if path.suffix.lower() in {".md", ".txt", ".json", ".toml", ".py", ".cmd", ".spec"}:
            data = path.read_bytes().lower()
            home = str(Path.home()).lower()
            if home.encode() in data or home.replace("\\", "/").encode() in data:
                raise RuntimeError(f"Private build path: {relative}")
    return files


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_licenses(windows: Path) -> None:
    included = []
    # Copy only legal notices, never environment metadata such as direct_url.json.
    for dist in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower().startswith(("nvidia", "onnxruntime-gpu", "onnxruntime-directml")):
            continue
        legal = [path for path in (dist.files or []) if path.name.lower().startswith(("license", "copying", "notice"))]
        copied = False
        for index, path in enumerate(legal):
            original = Path(dist.locate_file(path))
            if not original.is_file():
                continue
            copy_file(original, windows / "licenses" / name / f"{index:03d}-{path.name}")
            copied = True
        if copied:
            included.append(f"{name} {dist.version}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        copy_file(python_license, windows / "licenses" / "Python-LICENSE.txt")
    (windows / "licenses" / "INDEX.txt").write_text(
        "Dependency license notices from the build environment. Some packages are build tools only.\n"
        + "\n".join(included) + "\n", encoding="utf-8")


def main() -> None:
    release = ROOT / "release"
    windows, source = release / (NAME + "-Windows"), release / (NAME + "-Source")
    outputs = [windows, source, Path(str(windows) + ".zip"), Path(str(source) + ".zip")]
    if any(path.exists() for path in outputs):
        raise SystemExit("Release output already exists; inspect it before replacing anything.")
    dist = ROOT / "dist" / PRODUCT
    if not (dist / (PRODUCT + ".exe")).is_file():
        raise SystemExit("Build the PyInstaller spec first.")
    audit(dist, source=False)
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
    ).decode("utf-8").split("\0")
    selected = []
    for item in tracked:
        if not item:
            continue
        path = Path(item)
        if (path.parts[0] in {"src", "docs", "screenshots", "tests", "tools"}
                or item in ROOT_FILES) and (ROOT / path).is_file():
            if not FORBIDDEN_PARTS.intersection(path.parts) and path.suffix.lower() not in MODEL_SUFFIXES:
                selected.append(path)
    source.mkdir(parents=True)
    for path in selected:
        copy_file(ROOT / path, source / path)
    shutil.copytree(dist, windows)
    for path in selected:
        if path.parts[0] in {"docs", "screenshots"} or path.name in {
            "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "OPEN_SOURCE_NOTICE.md",
            "CHANGELOG_CN.txt", "AI_Prompting_Guide.md"
        }:
            copy_file(ROOT / path, windows / path)
    start = (ROOT / "tools" / "Start-Portable.cmd").read_text(encoding="ascii")
    (windows / "Start.cmd").write_bytes(start.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    copy_licenses(windows)
    sums = []
    for folder, is_source in ((windows, False), (source, True)):
        files = audit(folder, source=is_source)
        archive = Path(str(folder) + ".zip")
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in files:
                output.write(path, path.relative_to(release))
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        sums.append(f"{digest}  {archive.name}")
        print(f"AUDITED {folder.name}: {len(files)} files; ZIP {archive.stat().st_size} bytes", flush=True)
    (release / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
