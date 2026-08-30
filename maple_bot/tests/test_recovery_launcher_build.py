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
