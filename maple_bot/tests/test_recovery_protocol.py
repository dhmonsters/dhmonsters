# 복구 실행기와 실제 앱 사이의 파일 신호 규약을 검증한다.
from __future__ import annotations

import json
from pathlib import Path

from core import recovery_protocol
import run_integrated


def test_write_ready_uses_configured_path_and_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "ready.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_READY_FILE", str(target))

    assert recovery_protocol.write_ready() is True

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["pid"] > 0
    assert payload["created_at"].endswith("Z")
    assert not (tmp_path / "ready.json.tmp").exists()


def test_write_fatal_records_complete_error_payload(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "crash.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_CRASH_FILE", str(target))

    assert recovery_protocol.write_fatal(
        "BOOT", "QtWidgets load failed", "ImportError: QtWidgets", 7
    ) is True

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {
        "kind": "BOOT",
        "message": "QtWidgets load failed",
        "traceback": "ImportError: QtWidgets",
        "exit_code": 7,
        "pid": payload["pid"],
        "created_at": payload["created_at"],
    }


def test_write_normal_exit_records_reason(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "normal.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_NORMAL_FILE", str(target))

    assert recovery_protocol.write_normal_exit("update_handoff") is True

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["status"] == "normal"
    assert payload["reason"] == "update_handoff"


def test_missing_signal_path_is_a_safe_noop(monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_RECOVERY_READY_FILE", raising=False)

    assert recovery_protocol.write_ready() is False


def test_signal_write_failure_never_escapes(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()
    monkeypatch.setenv("CLAUDE_RECOVERY_CRASH_FILE", str(directory))

    assert recovery_protocol.write_fatal("BOOT", "failure") is False


def test_launcher_managed_requires_exact_enabled_value(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_RECOVERY_MANAGED", "0")
    assert recovery_protocol.is_launcher_managed() is False

    monkeypatch.setenv("CLAUDE_RECOVERY_MANAGED", "1")
    assert recovery_protocol.is_launcher_managed() is True


def test_admin_escalation_is_skipped_for_launcher_managed_process(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(recovery_protocol, "is_launcher_managed", lambda: True)
    monkeypatch.setattr(
        "core.admin_util.ensure_admin", lambda: calls.append("ensure_admin")
    )

    run_integrated._ensure_admin_if_unmanaged()

    assert calls == []


def test_admin_escalation_runs_for_direct_process(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(recovery_protocol, "is_launcher_managed", lambda: False)
    monkeypatch.setattr(
        "core.admin_util.ensure_admin", lambda: calls.append("ensure_admin")
    )

    run_integrated._ensure_admin_if_unmanaged()

    assert calls == ["ensure_admin"]


def test_unhandled_exception_is_written_for_launcher(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "crash.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_CRASH_FILE", str(target))

    try:
        raise ImportError("DLL load failed while importing QtWidgets")
    except ImportError as exc:
        run_integrated._record_unhandled_exception(type(exc), exc, exc.__traceback__)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["kind"] == "UNHANDLED_EXCEPTION"
    assert payload["message"] == "DLL load failed while importing QtWidgets"
    assert "ImportError: DLL load failed while importing QtWidgets" in payload["traceback"]


def test_normal_event_loop_exit_writes_normal_marker(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "normal.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_NORMAL_FILE", str(target))

    assert run_integrated._finalize_event_loop(0) == 0

    assert json.loads(target.read_text(encoding="utf-8"))["reason"] == "user_close"


def test_nonzero_event_loop_exit_does_not_write_normal_marker(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "normal.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_NORMAL_FILE", str(target))

    assert run_integrated._finalize_event_loop(5) == 5

    assert not target.exists()


def test_release_startup_check_builds_real_qt_shell_and_writes_ready(
    tmp_path: Path, monkeypatch
) -> None:
    ready = tmp_path / "ready.json"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("CLAUDE_RECOVERY_READY_FILE", str(ready))

    assert run_integrated._run_release_startup_check() == 0
    assert ready.is_file()
