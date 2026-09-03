# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/osr_screen_tcode/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/osr_screen_tcode/assets/osr_emu_standalone.html', 'osr_screen_tcode/assets')],
    hiddenimports=['websockets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OSR6-Realtime-Screen',
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
    name='OSR6-Realtime-Screen',
)
