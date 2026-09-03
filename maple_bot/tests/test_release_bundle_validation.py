# Claude 배포본에 작업 환경 DLL이 섞이지 않는지 검증한다.
import sys
from pathlib import Path


REQUIRED_ANALYSIS = "\n".join(
    (
        "core.recovery_protocol",
        "core.update_recovery",
        "core.updater",
        "ui.dialog_update",
    )
)


def test_rejects_codex_runtime_sources_and_root_poppler_icu(tmp_path: Path) -> None:
    from release_bundle_validation import validate_release_bundle

    analysis = tmp_path / "Analysis-00.toc"
    analysis.write_text(
        "C:\\\\Users\\\\PC\\\\.cache\\\\codex-runtimes\\\\"
        "codex-primary-runtime\\\\dependencies\\\\native\\\\poppler"
        "\\\\Library\\\\bin\\\\icuuc.dll\n" + REQUIRED_ANALYSIS,
        encoding="utf-8",
    )
    internal = tmp_path / "dist" / "Claude" / "_internal"
    internal.mkdir(parents=True)
    (internal / "icuuc.dll").write_bytes(b"foreign-icu")
    (internal / "icudt78.dll").write_bytes(b"foreign-icu-data")
    (internal.parent / "Claude.exe").write_bytes(b"launcher")
    (internal.parent / "ClaudeApp.exe").write_bytes(b"app")

    errors = validate_release_bundle(analysis, internal.parent)

    assert errors == [
        "PyInstaller 분석 목록에 Codex 작업용 런타임 경로가 포함됐습니다.",
        "배포본 _internal 루트에 금지된 DLL이 있습니다: icudt78.dll, icuuc.dll",
    ]


def test_accepts_bundle_without_foreign_runtime_files(tmp_path: Path) -> None:
    from release_bundle_validation import validate_release_bundle

    analysis = tmp_path / "Analysis-00.toc"
    analysis.write_text(
        "C:\\\\Windows\\\\System32\\\\kernel32.dll\n" + REQUIRED_ANALYSIS,
        encoding="utf-8",
    )
    bundle = tmp_path / "dist" / "Claude"
    (bundle / "_internal").mkdir(parents=True)
    (bundle / "Claude.exe").write_bytes(b"launcher")
    (bundle / "ClaudeApp.exe").write_bytes(b"app")

    assert validate_release_bundle(analysis, bundle) == []


def test_rejects_bundle_missing_launcher_and_real_app(tmp_path: Path) -> None:
    from release_bundle_validation import validate_release_bundle

    analysis = tmp_path / "Analysis-00.toc"
    analysis.write_text(
        "C:\\Windows\\System32\\kernel32.dll\n" + REQUIRED_ANALYSIS,
        encoding="utf-8",
    )
    bundle = tmp_path / "dist" / "Claude"
    (bundle / "_internal").mkdir(parents=True)

    assert validate_release_bundle(analysis, bundle) == [
        "복구 실행기 Claude.exe가 없습니다.",
        "실제 앱 ClaudeApp.exe가 없습니다.",
    ]


def test_rejects_bundle_missing_startup_and_update_modules(tmp_path: Path) -> None:
    from release_bundle_validation import validate_release_bundle

    analysis = tmp_path / "Analysis-00.toc"
    analysis.write_text("('core.runtime', 'module')", encoding="utf-8")
    bundle = tmp_path / "dist" / "Claude"
    (bundle / "_internal").mkdir(parents=True)
    (bundle / "Claude.exe").write_bytes(b"launcher")
    (bundle / "ClaudeApp.exe").write_bytes(b"app")

    assert validate_release_bundle(analysis, bundle) == [
        "PyInstaller 분석 목록에 필수 모듈이 없습니다: core.recovery_protocol, core.update_recovery, core.updater, ui.dialog_update"
    ]


def test_startup_probe_requires_ready_signal_not_just_live_process(
    tmp_path: Path,
) -> None:
    from release_bundle_validation import verify_startup_ready

    error = verify_startup_ready(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        tmp_path,
        timeout_seconds=0.2,
    )

    assert error == "배포본이 제한 시간 안에 UI 준비 신호를 생성하지 않았습니다."


def test_startup_probe_accepts_process_that_writes_ready_signal(
    tmp_path: Path,
) -> None:
    from release_bundle_validation import verify_startup_ready

    code = (
        "import json, os, pathlib, time; "
        "pathlib.Path(os.environ['CLAUDE_RECOVERY_READY_FILE']).write_text("
        "json.dumps({'ready': True}), encoding='utf-8'); "
        "time.sleep(2)"
    )
    assert (
        verify_startup_ready(
            [sys.executable, "-c", code],
            tmp_path,
            timeout_seconds=1.0,
        )
        is None
    )
