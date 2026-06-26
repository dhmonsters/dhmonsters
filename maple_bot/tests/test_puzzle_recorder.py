# 투명도형 퍼즐 세션 녹화와 스냅샷 저장 동작을 검증한다.
import json
from pathlib import Path

import numpy as np

from core.puzzle.models import FramePacket, PuzzleSession, RoiSpec
from core.puzzle.recorder import SessionRecorder
from core.puzzle.trace import TraceLogger


def _roi(name: str) -> RoiSpec:
    return RoiSpec(name=name, basis="window_client", x=0, y=0, w=4, h=3)


def _session(tmp_path: Path) -> PuzzleSession:
    return PuzzleSession(
        session_id="20260626_173000_001",
        started_at="2026-06-26T17:30:00",
        source_kind="image_sequence",
        detect_roi=_roi("detect"),
        board_roi=_roi("board"),
        output_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        raw_video_path=tmp_path / "raw_cctv.mkv",
        board_video_path=tmp_path / "board_crop.mkv",
        overlay_video_path=tmp_path / "overlay.mkv",
    )


def _packet(session: PuzzleSession, frame_index: int, value: int, shape=(6, 8, 3)) -> FramePacket:
    source = np.full(shape, value, dtype=np.uint8)
    board = source[0:3, 0:4].copy()
    return FramePacket(
        session_id=session.session_id,
        frame_index=frame_index,
        timestamp_ms=frame_index * 33,
        source_frame=source,
        board_frame=board,
        source_kind=session.source_kind,
        roi_snapshot={"board": {"x": 0, "y": 0, "w": 4, "h": 3}},
    )


def test_session_recorder_writes_three_video_outputs_and_snapshot(tmp_path):
    session = _session(tmp_path)
    recorder = SessionRecorder(session, fps=10.0)

    for index in range(3):
        packet = _packet(session, index, 20 + index)
        recorder.write(packet, overlay_frame=packet.source_frame)
    snapshot_path = recorder.snapshot("start", _packet(session, 3, 55).board_frame, frame_index=3)
    recorder.close()

    assert session.raw_video_path.exists()
    assert session.board_video_path.exists()
    assert session.overlay_video_path.exists()
    assert session.raw_video_path.stat().st_size > 0
    assert session.board_video_path.stat().st_size > 0
    assert session.overlay_video_path.stat().st_size > 0
    assert snapshot_path == session.output_dir / "snapshots" / "000003_start.png"
    assert snapshot_path.exists()


def test_session_recorder_defaults_to_lossless_ffv1(tmp_path):
    session = _session(tmp_path)
    recorder = SessionRecorder(session, fps=10.0)

    try:
        assert recorder.fourcc == "FFV1"
    finally:
        recorder.close()


def test_session_recorder_logs_roi_invalid_when_frame_size_changes(tmp_path):
    session = _session(tmp_path)
    trace = TraceLogger(session, clock=lambda: 1.5)
    recorder = SessionRecorder(session, fps=10.0, trace_logger=trace)

    recorder.write(_packet(session, 0, 10))
    try:
        recorder.write(_packet(session, 1, 20, shape=(7, 8, 3)))
    except ValueError as exc:
        assert "frame size changed" in str(exc)
    else:
        raise AssertionError("SessionRecorder should reject changing frame size")
    finally:
        recorder.close()

    events = [
        json.loads(line)
        for line in session.trace_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["type"] == "ROI_INVALID"
    assert events[-1]["frame_index"] == 1
    assert events[-1]["payload"]["expected_source_shape"] == [6, 8, 3]
    assert events[-1]["payload"]["actual_source_shape"] == [7, 8, 3]
