# Puzzle2와 V6497 추적 엔진을 Python 없는 PC용 폴더형 EXE로 묶는 설정이다.
from pathlib import Path

project_root = Path(SPECPATH).resolve()
vendor_root = Path(
    r"C:\Users\PC\Downloads\Telegram Desktop\a\V6497_LIVE_ONE_SHOT_v4_PASSWORD"
)
vendor_files = (
    "live_core.py",
    "win32_live.py",
    "autoseed.py",
    "motion_tracker_v35_base.py",
    "motion_tracker_v645.py",
    "v645_owner_guard.py",
    "v6494_owner_guard.py",
    "triangle_guard_v6496.py",
    "deep_identity_model.py",
)

datas = [(str(vendor_root / name), "vendor") for name in vendor_files]
datas.append(
    (
        str(vendor_root / "triangle_models" / "triangle_guard_v6496.pt"),
        "vendor/triangle_models",
    )
)

a = Analysis(
    [str(project_root / "puzzle2.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["torch", "cv2", "mss", "numpy"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "unittest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="puzzle2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="Puzzle2_Portable",
)
