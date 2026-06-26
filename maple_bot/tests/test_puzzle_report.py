# 투명도형 퍼즐 세션 리포트가 trace를 안전하게 요약하는지 검증한다.
import json
from pathlib import Path

from core.puzzle.models import PuzzleSession, RoiSpec
from core.puzzle.report import ReportBuilder


def _roi(name: str) -> RoiSpec:
    return RoiSpec(name=name, basis="window_client", x=0, y=0, w=4, h=3)


def _session(tmp_path: Path) -> PuzzleSession:
    return PuzzleSession(
        session_id="20260626_181200_001",
        started_at="2026-06-26T18:12:00",
        source_kind="jsonl_replay",
        detect_roi=_roi("detect"),
        board_roi=_roi("board"),
        output_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        raw_video_path=tmp_path / "raw_cctv.mp4",
        board_video_path=tmp_path / "board_crop.mp4",
        overlay_video_path=tmp_path / "overlay.mp4",
    )


def _write_events(path: Path) -> None:
    rows = [
        {"type": "SESSION_START", "frame_index": None, "payload": {"telegram_token": "secret-token"}},
        {"type": "IDENTITY", "frame_index": 0, "payload": {"state": "TRACK_CONFIDENT"}},
        {"type": "IDENTITY", "frame_index": 1, "payload": {"state": "OCCLUSION_SUSPECTED", "merge_likelihood": 0.8}},
        {"type": "IDENTITY", "frame_index": 2, "payload": {"state": "IDENTITY_HOLD", "hold_frames": 2}},
        {"type": "IDENTITY", "frame_index": 3, "payload": {"state": "REACQUIRE"}},
        {"type": "SESSION_END", "frame_index": None, "payload": {"frames": 4, "chat_id": "secret-chat"}},
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_report_builder_summarizes_trace_without_sensitive_values(tmp_path):
    session = _session(tmp_path)
    _write_events(session.trace_path)

    report_path = ReportBuilder().build(session, session.trace_path)
    text = report_path.read_text(encoding="utf-8")

    assert report_path == tmp_path / "report.md"
    assert "# 투명도형 퍼즐 세션 리포트" in text
    assert "session_id: 20260626_181200_001" in text
    assert "source_kind: jsonl_replay" in text
    assert "frames: 4" in text
    assert "TRACK_CONFIDENT: 1" in text
    assert "OCCLUSION_SUSPECTED: 1" in text
    assert "IDENTITY_HOLD: 1" in text
    assert "REACQUIRE: 1" in text
    assert "merge_count: 1" in text
    assert "hold_count: 1" in text
    assert "reacquire_count: 1" in text
    assert str(session.raw_video_path) in text
    assert str(session.board_video_path) in text
    assert str(session.overlay_video_path) in text
    assert str(session.trace_path) in text
    assert "secret-token" not in text
    assert "secret-chat" not in text


def test_report_builder_handles_missing_trace(tmp_path):
    session = _session(tmp_path)

    report_path = ReportBuilder().build(session, session.trace_path)
    text = report_path.read_text(encoding="utf-8")

    assert "frames: 0" in text
    assert "event_count: 0" in text
