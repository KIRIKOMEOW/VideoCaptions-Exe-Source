# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
binaries = []
datas = collect_data_files("faster_whisper")
excludes = [
    # GUI uses tkinter; avoid pulling optional GUI stacks if dependency hooks see them.
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "matplotlib",
    # Not used by the Windows build path or this application.
    "mlx_whisper",
    "torch",
    "tensorflow",
    "keras",
    "scipy",
    "pandas",
    "sklearn",
    "IPython",
    "jupyter",
    "notebook",
    # Development and test-only packages.
    "pytest",
    "ruff",
    "setuptools.tests",
    "numpy.tests",
]

a = Analysis(
    ["src/handler/gui.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "browser_cookie3",
        "opencc",
        "yt_dlp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="VideoCaptions",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
