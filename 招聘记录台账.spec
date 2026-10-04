# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import runpy
from pathlib import Path

# Search the interpreter and Windows directories, not other tools' DLL folders.
if sys.platform == "win32":
    windows_root = Path(os.environ["SystemRoot"])
    os.environ["PATH"] = os.pathsep.join(map(str, (
        Path(sys.executable).parent, Path(sys.base_prefix),
        windows_root / "System32", windows_root,
    )))


version_file = Path("build/version.txt")
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(runpy.run_path("recruitment_ledger/constants.py")["APP_VERSION"], encoding="utf-8")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[("scripts/sync_local_windows.ps1", "scripts"), (str(version_file), ".")],
    hiddenimports=[],
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
    name="招聘记录台账",
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
    icon=['assets\\ui.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="招聘记录台账",
)
