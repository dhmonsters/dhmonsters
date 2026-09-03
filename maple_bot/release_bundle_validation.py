# Claude 배포본에 외부 작업 환경 DLL이 섞였는지 검사한다.
from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Sequence


_FORBIDDEN_ROOT_DLLS = ("icudt78.dll", "icuuc.dll")
_REQUIRED_MODULES = (
    "core.recovery_protocol",
    "core.update_recovery",
    "core.updater",
    "ui.dialog_update",
)


def read_pe_imports(path: Path) -> set[str]:
    """PE 파일이 정적으로 가져오는 DLL 이름을 소문자로 반환한다."""
    import pefile

    image = pefile.PE(str(path), fast_load=True)
    try:
        image.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        return {
            entry.dll.decode("ascii", errors="replace").lower()
            for entry in getattr(image, "DIRECTORY_ENTRY_IMPORT", [])
        }
    finally:
        image.close()


def validate_release_bundle(analysis_path: Path, bundle_path: Path) -> list[str]:
    errors: list[str] = []
    analysis_text = analysis_path.read_text(encoding="utf-8", errors="replace")
    if re.search(
        r"[\\/]+\.cache[\\/]+codex-runtimes[\\/]+", analysis_text.lower()
    ):
        errors.append("PyInstaller 분석 목록에 Codex 작업용 런타임 경로가 포함됐습니다.")
    missing_modules = [
        module
        for module in _REQUIRED_MODULES
        if not re.search(
            rf"(?<![\w.]){re.escape(module)}(?![\w.])", analysis_text
        )
    ]
    if missing_modules:
        errors.append(
            "PyInstaller 분석 목록에 필수 모듈이 없습니다: "
            + ", ".join(missing_modules)
        )

    internal = bundle_path / "_internal"
    forbidden = sorted(
        name for name in _FORBIDDEN_ROOT_DLLS if (internal / name).is_file()
    )
    if forbidden:
        errors.append(
            "배포본 _internal 루트에 금지된 DLL이 있습니다: "
            + ", ".join(forbidden)
        )
    if not (bundle_path / "Claude.exe").is_file():
        errors.append("복구 실행기 Claude.exe가 없습니다.")
    if not (bundle_path / "ClaudeApp.exe").is_file():
        errors.append("실제 앱 ClaudeApp.exe가 없습니다.")
    return errors


def verify_startup_ready(
    command: Sequence[str], signal_directory: Path, timeout_seconds: float
) -> str | None:
    """배포 프로그램이 실제 UI 준비 신호를 생성하는지 확인한다."""
    signal_directory.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    ready_path = signal_directory / f"startup_ready_{run_id}.json"
    crash_path = signal_directory / f"startup_crash_{run_id}.json"
    normal_path = signal_directory / f"startup_normal_{run_id}.json"
    environment = os.environ.copy()
    environment.update(
        {
            "CLAUDE_RECOVERY_MANAGED": "1",
            "CLAUDE_RECOVERY_READY_FILE": str(ready_path),
            "CLAUDE_RECOVERY_CRASH_FILE": str(crash_path),
            "CLAUDE_RECOVERY_NORMAL_FILE": str(normal_path),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )
    process = subprocess.Popen(list(command), env=environment)
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            if ready_path.is_file():
                return None
            exit_code = process.poll()
            if exit_code is not None:
                return f"배포본이 UI 준비 전에 종료되었습니다. 종료 코드 {exit_code}."
            time.sleep(0.05)
        return "배포본이 제한 시간 안에 UI 준비 신호를 생성하지 않았습니다."
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for path in (ready_path, crash_path, normal_path):
            path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", type=Path)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--startup-executable", type=Path)
    parser.add_argument("--startup-argument", action="append", default=[])
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    args = parser.parse_args()
    errors = validate_release_bundle(args.analysis, args.bundle)
    if not errors and args.startup_executable is not None:
        startup_error = verify_startup_ready(
            [str(args.startup_executable), *args.startup_argument],
            args.bundle,
            args.startup_timeout,
        )
        if startup_error:
            errors.append(startup_error)
    for error in errors:
        print(f"[release validation error] {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
