# Windows 기본 C# 컴파일러로 복구 실행기 코드와 테스트 하네스를 검증한다.
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
SOURCES = [
    ROOT / "recovery_launcher" / "Program.cs",
    ROOT / "recovery_launcher" / "RecoveryModels.cs",
    ROOT / "recovery_launcher" / "RecoveryStore.cs",
    ROOT / "recovery_launcher" / "UpdateClient.cs",
    ROOT / "recovery_launcher" / "RecoveryForm.cs",
    ROOT / "recovery_launcher" / "RollbackWorker.cs",
]


def test_recovery_launcher_core_compiles_and_passes_behavior_tests(
    tmp_path: Path,
) -> None:
    output = tmp_path / "RecoveryLauncherTests.exe"
    command = [
        str(CSC),
        "/nologo",
        "/target:exe",
        "/platform:x64",
        "/main:RecoveryLauncherTests",
        f"/out:{output}",
        "/reference:System.Windows.Forms.dll",
        "/reference:System.Drawing.dll",
        "/reference:System.Web.Extensions.dll",
        *(str(path) for path in SOURCES),
        str(ROOT / "tests" / "recovery_launcher" / "RecoveryLauncherTests.cs"),
    ]

    compiled = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    tested = subprocess.run(
        [str(output)], capture_output=True, text=True, encoding="utf-8"
    )
    assert tested.returncode == 0, tested.stdout + tested.stderr
    assert tested.stdout.strip() == "PASS"


def test_recovery_launcher_winexe_has_no_qt_or_python_imports(tmp_path: Path) -> None:
    from release_bundle_validation import read_pe_imports

    output = tmp_path / "Claude.exe"
    command = [
        str(CSC),
        "/nologo",
        "/target:winexe",
        "/platform:x64",
        "/main:Program",
        f"/out:{output}",
        f"/win32manifest:{ROOT / 'recovery_launcher' / 'app.manifest'}",
        "/reference:System.Windows.Forms.dll",
        "/reference:System.Drawing.dll",
        "/reference:System.Web.Extensions.dll",
        *(str(path) for path in SOURCES),
    ]

    compiled = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    imports = read_pe_imports(output)
    assert not any(name.startswith("qt6") for name in imports)
    assert not any(name.startswith("python") for name in imports)


def test_launcher_build_script_produces_independent_claude_exe(tmp_path: Path) -> None:
    from release_bundle_validation import read_pe_imports

    built = subprocess.run(
        [
            "cmd.exe",
            "/c",
            str(ROOT / "recovery_launcher" / "build_launcher.bat"),
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert built.returncode == 0, built.stdout + built.stderr
    output = tmp_path / "Claude.exe"
    assert output.is_file()
    imports = read_pe_imports(output)
    assert not any(name.startswith("qt6") for name in imports)
    assert not any(name.startswith("python") for name in imports)
