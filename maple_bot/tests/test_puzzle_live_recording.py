# 투명도형 퍼즐 라이브 화면 녹화 리허설 runtime을 검증한다.

import json
import sys
from types import SimpleNamespace
from unittest import mock

import numpy as np

import core.puzzle.live_recording as live_recording
from core.puzzle.live_recording import LiveRecordingRuntime, _select_main_monitor
from core.puzzle.planet_live import PlanetLiveResult, PlanetLiveSolver


def _frames(count: int):
    values = [30 + index for index in range(count)]

    def grab():
        if not values:
            return np.full((6, 8, 3), 99, dtype=np.uint8)
        return np.full((6, 8, 3), values.pop(0), dtype=np.uint8)

    return grab


def _failing_frames():
    calls = {"count": 0}

    def grab():
        calls["count"] += 1
        if calls["count"] == 1:
            return np.full((6, 8, 3), 40, dtype=np.uint8)
        raise RuntimeError("screen grab failed")

    return grab


def _events(trace_path):
    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_live_recording_runtime_writes_lossless_session_outputs(tmp_path):
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(3),
        fps=10.0,
        sleeper=lambda _seconds: None,
    )

    report_path = runtime.run_until_stopped(max_frames=3)

    session_dir = report_path.parent
    assert report_path.exists()
    assert (session_dir / "raw_cctv.mkv").stat().st_size > 0
    assert (session_dir / "board_crop.mkv").stat().st_size > 0
    assert (session_dir / "overlay.mkv").stat().st_size > 0
    events = _events(session_dir / "trace.jsonl")
    assert [event["type"] for event in events].count("FRAME_RECORDED") == 3
    assert events[-1]["type"] == "SESSION_END"
    assert runtime.session is not None
    assert runtime.report_path == report_path


def test_live_recording_solver_stop_keeps_recording_until_f3(tmp_path):
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(2),
        fps=10.0,
        sleeper=lambda _seconds: None,
    )

    session = runtime.start()
    assert runtime.stop_solver(reason="manual_f2") is True
    assert runtime.is_recording is True
    assert runtime.pump_once() is True
    assert runtime.stop_recording(reason="manual_f3") is True
    report_path = runtime.finish(reason="manual_f3")

    events = _events(session.trace_path)
    event_types = [event["type"] for event in events]
    assert event_types.count("FRAME_RECORDED") == 2
    assert "SOLVER_STOPPED" in event_types
    assert "RECORDING_STOPPED" in event_types
    assert report_path.exists()


def test_live_recording_start_can_use_activation_frame_without_extra_grab(tmp_path):
    grabbed = {"count": 0}

    def grab():
        grabbed["count"] += 1
        return np.full((6, 8, 3), 88, dtype=np.uint8)

    activation_frame = np.full((6, 8, 3), 77, dtype=np.uint8)
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=grab,
        fps=10.0,
        sleeper=lambda _seconds: None,
    )

    session = runtime.start(initial_frame=activation_frame)

    assert session.output_dir.exists()
    assert runtime.frame_count == 1
    assert grabbed["count"] == 0


def test_live_recording_calls_planet_solver_and_records_solver_trace(tmp_path):
    calls = []

    class _FakePlanetSolver:
        def analyze(self, packet, *, solver_running: bool):
            calls.append((packet.frame_index, solver_running))
            return PlanetLiveResult(
                preview_frame=np.full((6, 8, 3), 140, dtype=np.uint8),
                trace_events=[
                    (
                        "PLANET_SOLVER_TEST",
                        {
                            "solver_running": solver_running,
                            "frame_index": packet.frame_index,
                        },
                    )
                ],
                decision=SimpleNamespace(point=(1.0, 2.0)),
            )

    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(1),
        fps=10.0,
        sleeper=lambda _seconds: None,
        live_solver=_FakePlanetSolver(),
    )

    session = runtime.start()

    events = _events(session.trace_path)
    solver_events = [event for event in events if event["type"] == "PLANET_SOLVER_TEST"]
    assert calls == [(0, True)]
    assert solver_events[0]["payload"]["solver_running"] is True
    assert runtime.latest_preview_path is not None
    assert runtime.latest_preview_path.exists()


def test_live_recording_analyzes_before_blocking_recorder_write(monkeypatch, tmp_path):
    order = []

    class _FakeRecorder:
        def write(self, _packet, overlay_frame=None):
            order.append("write")

        def close(self):
            order.append("close")

    class _FakePlanetSolver:
        def analyze(self, packet, *, solver_running: bool):
            order.append("analyze")
            return PlanetLiveResult(preview_frame=np.full((6, 8, 3), packet.frame_index, dtype=np.uint8))

    monkeypatch.setattr(live_recording, "SessionRecorder", lambda *_args, **_kwargs: _FakeRecorder())
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(1),
        fps=10.0,
        sleeper=lambda _seconds: None,
        live_solver=_FakePlanetSolver(),
    )

    runtime.start()
    runtime.stop_recording(reason="test_cleanup")

    assert order[:2] == ["analyze", "write"]


def test_live_recording_writes_preview_snapshot_for_every_frame(tmp_path):
    class _FakePlanetSolver:
        def analyze(self, packet, *, solver_running: bool):
            return PlanetLiveResult(preview_frame=np.full((6, 8, 3), packet.frame_index, dtype=np.uint8))

    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(7),
        fps=30.0,
        sleeper=lambda _seconds: None,
        live_solver=_FakePlanetSolver(),
    )

    report_path = runtime.run_until_stopped(max_frames=7)

    snapshot_names = sorted(path.name for path in (report_path.parent / "snapshots").glob("live_preview_*.png"))
    assert snapshot_names == [f"live_preview_{index:06d}.png" for index in range(7)]


def test_live_recording_runtime_can_create_mouse_disabled_default_solver(tmp_path):
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(1),
        fps=10.0,
        sleeper=lambda _seconds: None,
        mouse_enabled=False,
    )

    assert isinstance(runtime.live_solver, PlanetLiveSolver)
    assert runtime.mouse_enabled is False
    assert runtime.live_solver.mouse_enabled is False


def test_live_recording_runtime_updates_default_solver_mouse_flag(tmp_path):
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(1),
        fps=10.0,
        sleeper=lambda _seconds: None,
        mouse_enabled=False,
    )

    runtime.set_mouse_enabled(True)

    assert runtime.mouse_enabled is True
    assert runtime.live_solver.mouse_enabled is True


def test_live_recording_default_capture_uses_game_client_grabber(tmp_path):
    assert hasattr(live_recording, "GameClientFrameGrabber")

    runtime = LiveRecordingRuntime(output_root=tmp_path)

    assert isinstance(runtime.frame_grabber, live_recording.GameClientFrameGrabber)


def test_game_client_grabber_captures_maple_client_rect():
    assert hasattr(live_recording, "GameClientFrameGrabber")
    captured = {}

    class _FakeMss:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def grab(self, region):
            captured["region"] = dict(region)
            return np.zeros((4, 5, 4), dtype=np.uint8)

    fake_solver = SimpleNamespace(
        find_maple_hwnd=lambda: 1234,
        get_client_rect_screen=lambda hwnd: (10, 20, 5, 4),
    )
    fake_mss = SimpleNamespace(mss=lambda: _FakeMss())

    with mock.patch.dict(sys.modules, {"planet_live_solver": fake_solver, "mss": fake_mss}):
        frame = live_recording.GameClientFrameGrabber()()

    assert captured["region"] == {"left": 10, "top": 20, "width": 5, "height": 4}
    assert frame.shape == (4, 5, 3)


def test_live_recording_session_start_records_mouse_enabled_flag(tmp_path):
    class _NoopSolver:
        def analyze(self, _packet, *, solver_running: bool):
            return PlanetLiveResult()

    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_frames(1),
        fps=10.0,
        sleeper=lambda _seconds: None,
        live_solver=_NoopSolver(),
        mouse_enabled=False,
    )

    session = runtime.start()
    runtime.stop_recording(reason="test_cleanup")
    runtime.finish(reason="test_cleanup")

    start_event = _events(session.trace_path)[0]
    assert start_event["type"] == "SESSION_START"
    assert start_event["payload"]["mouse_enabled"] is False


def test_live_recording_failure_closes_recording_and_writes_report(tmp_path):
    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=_failing_frames(),
        fps=10.0,
        sleeper=lambda _seconds: None,
    )

    try:
        runtime.run_until_stopped(max_frames=2)
    except RuntimeError as exc:
        assert str(exc) == "screen grab failed"
    else:
        raise AssertionError("expected screen grab failure")

    assert runtime.is_recording is False
    assert runtime.report_path is not None
    assert runtime.report_path.exists()
    events = _events(runtime.session.trace_path)
    event_types = [event["type"] for event in events]
    assert "LIVE_RECORDING_FAILED" in event_types
    assert "RECORDING_STOPPED" in event_types
    assert events[-1]["type"] == "SESSION_END"


def test_select_main_monitor_ignores_virtual_all_monitor():
    monitors = [
        {"left": -1280, "top": 0, "width": 3200, "height": 1080},
        {"left": -1280, "top": 0, "width": 1280, "height": 1024},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
    ]

    assert _select_main_monitor(monitors) == monitors[2]


def test_select_main_monitor_falls_back_to_first_physical_monitor():
    monitors = [
        {"left": -1280, "top": 0, "width": 3200, "height": 1080},
        {"left": 100, "top": 100, "width": 1920, "height": 1080},
    ]

    assert _select_main_monitor(monitors) == monitors[1]
