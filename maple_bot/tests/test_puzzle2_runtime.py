# 받은 SOT 코어의 라이브 검증 어댑터 동작을 확인한다.
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.puzzle2.runtime import MouseGate, SotLiveRuntime, resolve_session_root
from core.puzzle2.vendor import VendorLayout, resolve_vendor_root


class FakeMouseController:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float, bool]] = []
        self.offset = (0.0, 0.0)

    def begin_puzzle(self) -> None:
        pass

    def move(self, x: float, y: float, *, learn_offset: bool) -> bool:
        self.moves.append((x, y, learn_offset))
        return True

    def close(self) -> None:
        pass


def test_mouse_gate_defaults_off_and_swallows_move() -> None:
    calls: list[tuple[float, float]] = []
    gate = MouseGate(lambda x, y: calls.append((x, y)) or True)

    assert gate.enabled is False
    assert gate.move(10.0, 20.0) is True
    assert calls == []


def test_mouse_gate_calls_vendor_only_when_enabled() -> None:
    calls: list[tuple[float, float]] = []
    gate = MouseGate(lambda x, y: calls.append((x, y)) or True)

    gate.set_enabled(True)

    assert gate.move(11.0, 21.0) is True
    assert calls == [(11.0, 21.0)]


def test_vendor_layout_requires_only_tracking_files(tmp_path: Path) -> None:
    for name in VendorLayout.REQUIRED_FILES:
        (tmp_path / name).write_text("# fixture\n", encoding="utf-8")

    layout = VendorLayout(tmp_path)

    assert layout.validate() == []
    assert "START_HERE.cmd" not in layout.required_paths


def test_packaged_vendor_root_is_next_to_executable(tmp_path: Path) -> None:
    executable = tmp_path / "portable" / "puzzle2.exe"

    assert resolve_vendor_root(frozen=True, executable=executable) == (
        executable.parent / "vendor"
    )


def test_packaged_session_root_is_next_to_executable(tmp_path: Path) -> None:
    executable = tmp_path / "portable" / "puzzle2.exe"

    assert resolve_session_root(frozen=True, executable=executable) == (
        executable.parent / "sessions"
    )


def test_runtime_intercepts_rows_and_respects_mouse_toggle() -> None:
    vendor_moves: list[tuple[float, float]] = []
    kernel_mouse = FakeMouseController()
    backend = SimpleNamespace()
    backend.move_toward_screen = lambda x, y: vendor_moves.append((x, y)) or True
    backend.f12_pressed = lambda: False

    def tracker_run(*args, **kwargs):
        kwargs["frame_callback"]({
            "frame": 7,
            "center_x": 420.0,
            "center_y": 280.0,
            "state": "MOTION",
            "confidence": 0.73,
            "output_source": "INTERNAL_H1",
        })
        return Path("result"), {"finished_at_sec": 2.0}

    backend.run = tracker_run

    def run_one_shot(status_cb=None, consumed_cb=None):
        status_cb(tracking="TRACKING", mouse="ON")
        backend.move_toward_screen(100.0, 200.0)
        backend.run(frame_callback=lambda row: None)
        return True, True, {"result": "SUCCESS"}

    backend.run_one_shot = run_one_shot
    runtime = SotLiveRuntime(
        backend_loader=lambda: backend,
        mouse_controller_factory=lambda _backend: kernel_mouse,
    )

    runtime.run_session_sync()

    assert vendor_moves == []
    assert runtime.latest_row is not None
    assert runtime.latest_row["center_x"] == 420.0
    assert runtime.status["tracking"] == "WAIT_REARM"
    assert runtime.result["result"] == "SUCCESS"

    runtime.set_mouse_enabled(True)
    runtime.run_session_sync()

    assert vendor_moves == []
    assert kernel_mouse.moves == [(100.0, 200.0, False)]


def test_runtime_stop_prevents_another_vendor_cycle() -> None:
    calls = 0
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: False,
        run=lambda *args, **kwargs: (Path("result"), {}),
    )

    def run_one_shot(status_cb=None, consumed_cb=None):
        nonlocal calls
        calls += 1
        return False, False, {"stopped": backend.f12_pressed()}

    backend.run_one_shot = run_one_shot
    runtime = SotLiveRuntime(backend_loader=lambda: backend)
    runtime.request_stop()

    runtime.run_session_sync()

    assert calls == 0
    assert runtime.status["tracking"] == "STOPPED"


def test_runtime_replaces_vendor_exact_torch_version_gate(monkeypatch) -> None:
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: False,
        run=lambda *args, **kwargs: (Path("result"), {}),
        validate_runtime=lambda: (_ for _ in ()).throw(RuntimeError("TORCH_VERSION_MISMATCH")),
    )

    def run_one_shot(status_cb=None, consumed_cb=None):
        return True, False, backend.validate_runtime()

    backend.run_one_shot = run_one_shot
    monkeypatch.setattr(
        "core.puzzle2.runtime._validate_installed_runtime",
        lambda: {"torch": "2.11.0+cu128", "cuda": True},
    )
    runtime = SotLiveRuntime(backend_loader=lambda: backend)

    runtime.run_session_sync()

    assert runtime.result["torch"] == "2.11.0+cu128"
    assert runtime.result["cuda"] is True


def test_start_session_removes_previous_session_contents(tmp_path: Path) -> None:
    output_root = tmp_path / "puzzle2_sessions"
    old_session = output_root / "old-session"
    old_session.mkdir(parents=True)
    (old_session / "large.trace").write_bytes(b"old")
    (output_root / "loose.log").write_text("old", encoding="utf-8")
    runtime = SotLiveRuntime(output_root=output_root)

    runtime._start_session(clear_existing=True)

    assert not old_session.exists()
    assert not (output_root / "loose.log").exists()
    assert runtime.session_dir is not None
    assert runtime.session_dir.parent == output_root
    assert runtime.session_dir.is_dir()


def test_continuous_runtime_retries_wait_timeout_until_stop() -> None:
    calls = 0
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: False,
        run=lambda *args, **kwargs: (Path("result"), {}),
        find_game_window=lambda: SimpleNamespace(hwnd=10),
        foreground_is=lambda hwnd: True,
        activate=lambda hwnd: True,
    )
    runtime = SotLiveRuntime(backend_loader=lambda: backend)

    def run_one_shot(status_cb=None, consumed_cb=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return False, False, {"error": "QUEST_WAIT_TIMEOUT", "aborted": False}
        runtime.request_stop()
        return False, False, {"error": "F12_ABORT", "aborted": True}

    backend.run_one_shot = run_one_shot

    runtime.run_session_sync(max_cycles=None, retry_delay=0.0, rearm_delay=0.0)

    assert calls == 2
    assert runtime.status["tracking"] == "STOPPED"


def test_continuous_runtime_returns_to_watch_after_success() -> None:
    calls = 0
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: False,
        run=lambda *args, **kwargs: (Path("result"), {}),
        find_game_window=lambda: SimpleNamespace(hwnd=10),
        foreground_is=lambda hwnd: True,
        activate=lambda hwnd: True,
    )
    runtime = SotLiveRuntime(backend_loader=lambda: backend)

    def run_one_shot(status_cb=None, consumed_cb=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            status_cb(tracking="FINISHED", result="SUCCESS / square")
            return True, True, {"result": "SUCCESS"}
        runtime.request_stop()
        return False, False, {"error": "F12_ABORT", "aborted": True}

    backend.run_one_shot = run_one_shot

    runtime.run_session_sync(max_cycles=None, retry_delay=0.0, rearm_delay=0.0)

    assert calls == 2
    assert runtime.completed_puzzles == 1
    assert runtime.status["tracking"] == "STOPPED"


def test_runtime_does_not_activate_background_game_window() -> None:
    activation_calls: list[int] = []
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: False,
        run=lambda *args, **kwargs: (Path("result"), {}),
        find_game_window=lambda: SimpleNamespace(hwnd=10),
        foreground_is=lambda hwnd: True,
        activate=lambda hwnd: activation_calls.append(hwnd) or True,
    )
    backend.run_one_shot = lambda status_cb=None, consumed_cb=None: (
        False,
        False,
        {"error": "QUEST_WAIT_TIMEOUT", "aborted": False},
    )
    runtime = SotLiveRuntime(backend_loader=lambda: backend)

    runtime.run_session_sync(max_cycles=1, retry_delay=0.0, rearm_delay=0.0)

    assert activation_calls == []


def test_f12_stops_during_success_rearm_wait() -> None:
    f12_checks = iter((False, True))
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: next(f12_checks, True),
        run=lambda *args, **kwargs: (Path("result"), {}),
        find_game_window=lambda: SimpleNamespace(hwnd=10),
        foreground_is=lambda hwnd: True,
        activate=lambda hwnd: True,
        run_one_shot=lambda status_cb=None, consumed_cb=None: (
            True,
            True,
            {"result": "SUCCESS"},
        ),
    )
    runtime = SotLiveRuntime(backend_loader=lambda: backend)

    runtime.run_session_sync(max_cycles=None, retry_delay=0.0, rearm_delay=5.0)

    assert runtime.completed_puzzles == 1
    assert runtime.status["tracking"] == "STOPPED"


def test_session_cleanup_refuses_drive_root() -> None:
    runtime = SotLiveRuntime(output_root=Path(Path.cwd().anchor))

    with pytest.raises(ValueError, match="unsafe session root"):
        runtime._start_session(clear_existing=True)


def test_session_cleanup_refuses_unrelated_directory(tmp_path: Path) -> None:
    runtime = SotLiveRuntime(output_root=tmp_path / "unrelated")

    with pytest.raises(ValueError, match="unsafe session root"):
        runtime._start_session(clear_existing=True)
