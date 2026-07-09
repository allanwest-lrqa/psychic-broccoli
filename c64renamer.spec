# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec that builds a single-file, windowed c64renamer.exe.
# Build with:  pyinstaller --clean --noconfirm c64renamer.spec

a = Analysis(
    ['c64renamer_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['access_parser'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='c64renamer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed GUI app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
