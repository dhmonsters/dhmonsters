# 실제 Inno Setup 하네스로 설치 시 현재 버전 release.json 생성을 검증한다.
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ISCC = Path(r"C:\Users\PC\AppData\Local\Programs\Inno Setup 6\ISCC.exe")


def test_installer_writes_self_hash_release_metadata(tmp_path: Path) -> None:
    output = tmp_path / "output"
    install = tmp_path / "installed"
    payload = tmp_path / "payload.txt"
    output.mkdir()
    payload.write_text("payload", encoding="utf-8")

    compiled = subprocess.run(
        [
            str(ISCC),
            "/Qp",
            f"/DTestOutput={output}",
            f"/DTestPayload={payload}",
            f"/DTestPayloadSha={hashlib.sha256(payload.read_bytes()).hexdigest()}",
            str(ROOT / "tests" / "installer_recovery_harness.iss"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr

    setup = output / "InstallerRecoveryHarness.exe"
    install_log = tmp_path / "install.log"
    installed = subprocess.run(
        [
            str(setup),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/DIR={install}",
            f"/LOG={install_log}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert installed.returncode == 0, (
        installed.stdout
        + installed.stderr
        + (install_log.read_text(encoding="utf-8-sig", errors="replace") if install_log.exists() else "")
    )

    release = json.loads((install / "release.json").read_text(encoding="utf-8-sig"))
    assert release == {
        "version": "9.9.9",
        "download_url": (
            "https://github.com/dhmonsters/dhmonsters/releases/download/"
            "v9.9.9/Claude_v9.9.9_Setup.exe"
        ),
        "sha256": hashlib.sha256(setup.read_bytes()).hexdigest(),
    }
    recovery = json.loads(
        (install / "Recovery" / "recovery.json").read_text(encoding="utf-8-sig")
    )
    assert recovery["previous_version"] == "2.4.5"
    assert recovery["current_version"] == "2.4.9"
    assert recovery["installation_path"] == str(install)
    assert recovery["previous_sha256"] == hashlib.sha256(payload.read_bytes()).hexdigest()
    assert "T" in recovery["created_at"]
    assert (install / "Recovery" / "previous_setup.exe").read_bytes() == payload.read_bytes()
