# GT 1030 CUDA 검사기와 NVRTC DLL을 Python 없는 PC용 EXE로 묶는 설정이다.
from pathlib import Path


project_root = Path(SPECPATH).resolve()
nvrtc_root = Path(
    r"C:\Users\PC\AppData\Local\Programs\Python\Python314\Lib\site-packages\torch\lib"
)
nvrtc_files = (
    "nvrtc64_120_0.dll",
    "nvrtc-builtins64_128.dll",
)

a = Analysis(
    [str(project_root / "gt1030_probe.py")],
    pathex=[str(project_root)],
    binaries=[(str(nvrtc_root / name), ".") for name in nvrtc_files],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt6", "torch", "numpy", "cv2"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GT1030_CUDA_Probe",
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
    name="GT1030_CUDA_Probe",
)
