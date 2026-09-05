# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path
import sys

source_root = str(Path(SPECPATH) / 'src')
# A shared development venv may have another checkout installed editable.
sys.path[:] = [source_root, *[path for path in sys.path
                            if not (Path(path) / 'osr_screen_tcode').is_dir()]]


a = Analysis(
    ['src/osr_screen_tcode/__main__.py'],
    pathex=[source_root],
    binaries=[],
    datas=[('src/osr_screen_tcode/assets/osr_emu_standalone.html', 'osr_screen_tcode/assets')] + collect_data_files('pip'),
    hiddenimports=['websockets', 'rtmlib', 'onnxruntime', 'bleak', 'serial.tools.list_ports'] + collect_submodules('pip'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'nvidia', 'tensorflow', 'onnxruntime.training'],
    noarchive=False,
    optimize=0,
)
a.datas = [entry for entry in a.datas if not entry[0].lower().endswith(('.onnx', '.pt', '.pth', '.safetensors'))]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility',
)
