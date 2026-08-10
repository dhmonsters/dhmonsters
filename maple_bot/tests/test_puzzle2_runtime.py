# 받은 SOT 코어의 라이브 검증 어댑터 동작을 확인한다.
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.puzzle2.runtime import MouseGate, SotLiveRuntime, resolve_session_root
from core.puzzle2.vendor import VendorLayout, resolve_vendor_root


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
    runtime = SotLiveRuntime(backend_loader=lambda: backend)

    runtime.run_session_sync()

    assert vendor_moves == []
    assert runtime.latest_row is not None
    assert runtime.latest_row["center_x"] == 420.0
    assert runtime.status["tracking"] == "TRACKING"
    assert runtime.result["result"] == "SUCCESS"

    runtime.set_mouse_enabled(True)
    runtime.run_session_sync()

    assert vendor_moves == [(100.0, 200.0)]


def test_runtime_stop_is_seen_as_vendor_f12() -> None:
    backend = SimpleNamespace(
        move_toward_screen=lambda x, y: True,
        f12_pressed=lambda: False,
        run=lambda *args, **kwargs: (Path("result"), {}),
    )

    def run_one_shot(status_cb=None, consumed_cb=None):
        return False, False, {"stopped": backend.f12_pressed()}

    backend.run_one_shot = run_one_shot
    runtime = SotLiveRuntime(backend_loader=lambda: backend)
    runtime.request_stop()

    runtime.run_session_sync()

    assert runtime.result["stopped"] is True


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
