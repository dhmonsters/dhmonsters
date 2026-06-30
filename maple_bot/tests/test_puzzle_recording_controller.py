# 투명도형 퍼즐 녹화와 솔버 생명주기 분리를 검증한다.

from core.puzzle.recording_controller import RecordingController


class _FakeRecorder:
    def __init__(self) -> None:
        self.writes = []
        self.closed = 0

    def write(self, packet, overlay_frame=None) -> None:
        self.writes.append((packet, overlay_frame))

    def close(self) -> None:
        self.closed += 1


class _FakeTrace:
    def __init__(self) -> None:
        self.events = []

    def write_event(self, event_type, frame_index, payload) -> None:
        self.events.append((event_type, frame_index, payload))


class _RecorderThatChecksTraceBeforeClose:
    def __init__(self, trace: _FakeTrace) -> None:
        self.trace = trace
        self.closed = 0

    def write(self, packet, overlay_frame=None) -> None:
        raise AssertionError("late write should not be used")

    def close(self) -> None:
        self.closed += 1
        assert self.trace.events[-1][0] == "RECORDING_STOPPED"


def test_solver_stop_keeps_recording_until_recording_stop():
    recorder = _FakeRecorder()
    trace = _FakeTrace()
    controller = RecordingController(recorder=recorder, trace_logger=trace)

    assert controller.is_solver_running is True
    assert controller.is_recording is True

    controller.stop_solver(reason="manual_f2")

    assert controller.is_solver_running is False
    assert controller.is_recording is True
    assert recorder.closed == 0
    assert trace.events[-1][0] == "SOLVER_STOPPED"

    assert controller.write("manual_frame", overlay_frame="manual_overlay") is True
    assert recorder.writes == [("manual_frame", "manual_overlay")]

    controller.stop_recording(reason="manual_f3")

    assert controller.is_recording is False
    assert recorder.closed == 1
    assert trace.events[-1][0] == "RECORDING_STOPPED"


def test_recording_stop_is_idempotent_and_blocks_late_writes():
    recorder = _FakeRecorder()
    controller = RecordingController(recorder=recorder)

    assert controller.stop_recording(reason="manual_f3") is True
    assert controller.stop_recording(reason="manual_f3") is False
    assert controller.write("late_frame") is False

    assert recorder.closed == 1
    assert recorder.writes == []


def test_recording_stop_writes_trace_before_closing_recorder():
    trace = _FakeTrace()
    recorder = _RecorderThatChecksTraceBeforeClose(trace)
    controller = RecordingController(recorder=recorder, trace_logger=trace)

    assert controller.stop_recording(reason="manual_f3") is True

    assert recorder.closed == 1
    assert trace.events[-1] == ("RECORDING_STOPPED", None, {"reason": "manual_f3"})
