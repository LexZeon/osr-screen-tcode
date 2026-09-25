"""Assemble immutable, audited source and Windows onedir release samples.

Run after committing the release and building its PyInstaller spec. No ignored or
untracked file is eligible for the source archive. Existing releases are never
removed or overwritten, including their version-specific checksums.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "SR6-OSR6-Realtime-Screen-TCode"
FORBIDDEN_PARTS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "models",
    "logs", "gpu-runtime", "gpu_runtime", "node_modules", ".mypy_cache",
}
MODEL_SUFFIXES = {
    ".onnx", ".pt", ".pth", ".safetensors", ".whl", ".ckpt", ".weights",
    ".tflite", ".engine", ".gguf", ".h5", ".hdf5",
}
PRIVATE_NAMES = {
    "osr_settings.json", "settings.json", "settings.local.json", "config.json",
    "direct_url.json", ".env", "ai_handoff.local.md",
}
GPU_BINARY = re.compile(r"directml\.dll|providers_(cuda|dml|tensorrt)|cudnn|cublas|cudart|nvrtc", re.I)
# Match actual user paths, including those of another developer, not just this user.
PRIVATE_PATH = re.compile(rb"(?:[a-z]:[\\/]users[\\/]|/(?:home|users)/)[^\s\"'<>]+", re.I)
TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".toml", ".py", ".cmd", ".spec", ".html",
    ".js", ".cjs", ".yaml", ".yml", ".ini", ".cfg", ".ps1",
}
ROOT_FILES = {
    "README.md", "LICENSE", "OPEN_SOURCE_NOTICE.md", "THIRD_PARTY_NOTICES.md",
    "CHANGELOG_CN.txt", "AI_Prompting_Guide.md", "CONTRIBUTING.md", "requirements.txt",
    "pyproject.toml", "Start.cmd", "Start-Source.cmd", "Start.md", ".gitignore", PRODUCT + ".spec",
}
SOURCE_FOLDERS = {"src", "docs", "screenshots", "tests", "tools", "Pose-Preview-Lab"}
LAB_MODULES = ("preview.py", "frame_motion.py", "observations.py", "stabilizer.py")
REQUIRED_SOURCE = ROOT_FILES | {
    "src/osr_screen_tcode/__init__.py", "src/osr_screen_tcode/__main__.py",
    "src/osr_screen_tcode/assets/osr_emu_standalone.html",
    "tools/build_release.py", "tools/Start-Portable.cmd", "tools/README-Portable.md",
    "Pose-Preview-Lab/Start.cmd", "Pose-Preview-Lab/Start.md",
    *(f"Pose-Preview-Lab/{name}" for name in LAB_MODULES),
}
LAB_START = r'''@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist "%CD%\SR6-OSR6-Realtime-Screen-TCode.exe" (
    echo The application is missing. Extract the complete Windows ZIP first.
    echo See Start.md for English and Chinese startup instructions.
    pause
    exit /b 1
)
start "" "%CD%\SR6-OSR6-Realtime-Screen-TCode.exe" --preview-lab %*
exit /b 0
'''
LAB_START_MD = """# Independent preview / 独立预览

## English

Double-click **Start.cmd in this folder** after extracting the complete Windows
ZIP. It launches the bundled application with `--preview-lab`; Python is not
required. Keep this folder next to the main EXE and `_internal`.

The independent preview is for visual checks only and does not feed device output
or script generation. See [the portable instructions](../Start.md) for the main
application. Pose models and downloadable GPU runtimes are not bundled.

## 中文

完整解压 Windows ZIP 后，双击本目录 **Start.cmd**。使用包内同一个程序启动独立
预览，不需要安装 Python。请保留本目录、主程序 EXE 和 `_internal` 的相对位置。
独立预览只用于视觉检查，不参与真实设备输出或脚本生成。

主程序说明见 [Start.md](../Start.md)。模型与可下载 GPU 运行库不包含在本包内。
"""


def _safe_path(path: Path, folder: Path) -> None:
    relative = path.relative_to(folder)
    if not path.resolve().is_relative_to(folder.resolve()):
        raise RuntimeError(f"Unsafe archive path: {relative}")
    for part in (path, *path.parents):
        if part == folder:
            break
        attributes = getattr(part.lstat(), "st_file_attributes", 0)
        if part.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise RuntimeError(f"Linked archive path: {relative}")


def audit_file(path: Path, folder: Path, *, source: bool) -> None:
    _safe_path(path, folder)
    relative = path.relative_to(folder)
    parts = {part.lower() for part in relative.parts}
    name, suffix = path.name.lower(), path.suffix.lower()
    if (FORBIDDEN_PARTS.intersection(parts) or suffix in MODEL_SUFFIXES
            or name in PRIVATE_NAMES or name.startswith(".env.")
            or ".local." in name or suffix in {".log", ".jsonl", ".pyc", ".pyo"}
            or GPU_BINARY.search(name)):
        raise RuntimeError(f"Forbidden payload: {relative}")
    if source and suffix in {".exe", ".dll", ".pyd", ".zip", ".7z", ".tar", ".gz"}:
        raise RuntimeError(f"Compiled/source payload: {relative}")
    if suffix in TEXT_SUFFIXES:
        data = path.read_bytes().lower().replace(b"\\\\", b"\\")
        home = str(Path.home()).lower()
        if (PRIVATE_PATH.search(data) or home.encode() in data
                or home.replace("\\", "/").encode() in data):
            raise RuntimeError(f"Private build path: {relative}")


def audit(folder: Path, source: bool) -> list[Path]:
    files = []
    for path in sorted(folder.rglob("*")):
        _safe_path(path, folder)
        if path.is_file():
            audit_file(path, folder, source=source)
            files.append(path)
    return files


def read_version(root: Path) -> str:
    module = ast.parse((root / "src/osr_screen_tcode/__init__.py").read_text(encoding="utf-8-sig"))
    for statement in module.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in statement.targets
        ):
            version = ast.literal_eval(statement.value)
            if isinstance(version, str) and re.fullmatch(r"[0-9][0-9A-Za-z.-]*", version):
                return version
    raise RuntimeError("A safe __version__ could not be read from source.")


def git_snapshot(root: Path) -> tuple[str, list[Path]]:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=root)

    # Ignored personal files may exist locally, but may never enter the archive.
    if git("status", "--porcelain=v1", "--untracked-files=normal").strip():
        raise RuntimeError("Commit the reviewed release first: the source working tree must be clean.")
    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise RuntimeError("Invalid source commit identifier.")
    # Do not add --others: the archive is strictly a committed source snapshot.
    paths = [Path(name) for name in git("ls-files", "--cached", "-z").decode("utf-8").split("\0") if name]
    return commit, paths


def select_source(root: Path, tracked: list[Path]) -> list[Path]:
    selected = []
    for relative in tracked:
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"Unsafe Git path: {relative}")
        if relative.parts[0] not in SOURCE_FOLDERS and relative.as_posix() not in ROOT_FILES:
            continue
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"Missing tracked source file: {relative}")
        # Reject accidentally committed sensitive assets instead of silently hiding them.
        audit_file(path, root, source=True)
        selected.append(relative)
    missing = REQUIRED_SOURCE - {path.as_posix() for path in selected}
    if missing:
        raise RuntimeError("Required release source is not tracked: " + ", ".join(sorted(missing)))
    return sorted(selected)


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_licenses(windows: Path) -> None:
    included = []
    legal_root = windows / "licenses"
    legal_root.mkdir(parents=True, exist_ok=True)
    # Legal notices only, never environment metadata such as direct_url.json.
    for dist in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower() == "osr-screen-tcode" or name.lower().startswith(("nvidia", "onnxruntime-gpu", "onnxruntime-directml")):
            continue
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        legal = [path for path in (dist.files or [])
                 if any(word in path.name.lower() for word in ("license", "copying", "notice"))]
        copied = False
        for index, path in enumerate(legal):
            original = Path(dist.locate_file(path))
            if original.is_file():
                copy_file(original, legal_root / safe_name / f"{index:03d}-{path.name}")
                copied = True
        if copied:
            included.append(f"{name} {dist.version}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        copy_file(python_license, legal_root / "Python-LICENSE.txt")
    (legal_root / "INDEX.txt").write_text(
        "Dependency legal notices from the build environment. Some packages are build tools only.\n"
        + "\n".join(included) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_cmd(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))


def assemble(root: Path, dist: Path, output: Path) -> Path:
    root, dist, output = root.resolve(), dist.resolve(), output.resolve()
    version = read_version(root)
    commit, tracked = git_snapshot(root)
    selected = select_source(root, tracked)
    if output.is_relative_to(dist) or dist.is_relative_to(output / f"v{version}"):
        raise RuntimeError("Build input and release output must be separate directories.")
    if not (dist / (PRODUCT + ".exe")).is_file():
        raise RuntimeError("Build the PyInstaller spec first; the onedir EXE is missing.")
    for name in LAB_MODULES:
        if not (dist / "_internal" / "Pose-Preview-Lab" / name).is_file():
            raise RuntimeError(f"Frozen independent preview is missing: {name}")
    audit(dist, source=False)
    release = output / f"v{version}"
    # A partial earlier attempt is retained for inspection, never removed implicitly.
    release.mkdir(parents=True, exist_ok=False)
    name = f"{PRODUCT}-v{version}"
    windows, source = release / (name + "-Windows"), release / (name + "-Source")
    source.mkdir()
    for relative in selected:
        copy_file(root / relative, source / relative)
    shutil.copytree(dist, windows)
    for relative in selected:
        if relative.parts[0] in {"docs", "screenshots"} or relative.as_posix() in {
            "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "OPEN_SOURCE_NOTICE.md",
            "CHANGELOG_CN.txt", "AI_Prompting_Guide.md",
        }:
            copy_file(root / relative, windows / relative)
    copy_file(root / "Start.md", windows / "docs" / "Source_Start.md")
    portable_help = root / "tools" / "README-Portable.md"
    copy_file(portable_help, windows / "Start.md")
    copy_file(portable_help, windows / "README-Portable.md")
    start = (root / "tools" / "Start-Portable.cmd").read_text(encoding="ascii")
    write_cmd(windows / "Start.cmd", start)
    write_cmd(windows / "Pose-Preview-Lab" / "Start.cmd", LAB_START)
    (windows / "Pose-Preview-Lab" / "Start.md").write_text(LAB_START_MD, encoding="utf-8")
    copy_licenses(windows)
    info = {
        "application": PRODUCT, "version": version, "source_commit": commit,
        "source_tree_dirty": False, "packaged_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows_format": "PyInstaller onedir; extract the whole ZIP",
        "models_bundled": False, "downloadable_gpu_runtimes_bundled": False,
    }
    info_text = json.dumps(info, ensure_ascii=False, indent=2) + "\n"
    (release / "RELEASE_INFO.json").write_text(info_text, encoding="utf-8")
    sums = []
    for folder, is_source in ((windows, False), (source, True)):
        (folder / "RELEASE_INFO.json").write_text(info_text, encoding="utf-8")
        files = audit(folder, source=is_source)
        (folder / "FILES_SHA256SUMS.txt").write_text(
            "".join(f"{sha256(path)}  {path.relative_to(folder).as_posix()}\n" for path in files), encoding="utf-8"
        )
        files = audit(folder, source=is_source)
        archive = Path(str(folder) + ".zip")
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
            for path in files:
                stream.write(path, path.relative_to(release))
        sums.append(f"{sha256(archive)}  {archive.name}")
        print(f"AUDITED {folder.name}: {len(files)} files; ZIP {archive.stat().st_size} bytes", flush=True)
    # A downloadable launcher is a convenience; it still requires the complete Windows ZIP.
    write_cmd(release / "Start.cmd", start)
    copy_file(portable_help, release / "README-Portable.md")
    for filename in ("Start.cmd", "README-Portable.md", "RELEASE_INFO.json"):
        sums.append(f"{sha256(release / filename)}  {filename}")
    (release / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    # The source tree must not have changed while files were being copied.
    final_commit, final_tracked = git_snapshot(root)
    if final_commit != commit or final_tracked != tracked:
        raise RuntimeError("Source changed during packaging; do not publish these preserved outputs.")
    return release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist" / PRODUCT,
                        help="Complete PyInstaller onedir folder containing the EXE and _internal.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "release",
                        help="Archive parent; a new immutable v<version> folder is created here.")
    args = parser.parse_args()
    try:
        folder = assemble(ROOT, args.dist_dir, args.output_dir)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Release not completed: {exc}") from exc
    print(f"Release ready: {folder}")


if __name__ == "__main__":
    main()
