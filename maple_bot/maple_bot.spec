# -*- mode: python ; coding: utf-8 -*-
# MapleBot v0.1 PyInstaller 빌드 스펙

import os
from PyInstaller.utils.hooks import collect_all

# PyQt6 전체 수집 (플러그인/번역 포함)
qt_datas, qt_binaries, qt_hiddenimports = collect_all("PyQt6")

extra_datas = list(qt_datas)
if os.path.exists("templates"):
    extra_datas.append(("templates", "templates"))
if os.path.exists("monsters"):
    extra_datas.append(("monsters", "monsters"))
if os.path.exists("version.txt"):
    extra_datas.append(("version.txt", "."))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=qt_binaries,
    datas=extra_datas,
    hiddenimports=[
        *qt_hiddenimports,
        "win32api", "win32con", "win32gui", "win32clipboard",
        "pywintypes", "win32process",
        "mss", "mss.windows",
        "cv2",
        "numpy",
        "keyboard",
        "winsound",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="dhmonsters",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="dhmonsters",
)
