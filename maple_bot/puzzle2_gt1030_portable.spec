# Puzzle2와 sm_61 지원 CUDA 11.8 런타임을 GT1030 전용 폴더형 EXE로 묶는다.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

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
    hiddenimports=collect_submodules("interception") + [
        "torch",
        "cv2",
        "mss",
        "numpy",
        "core.interception_backend",
        "core.humanize.backend",
        "core.puzzle2.mouse",
        "core.puzzle2.runtime_check",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="puzzle2_gpu",
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
    name="Puzzle2_GPU",
)
