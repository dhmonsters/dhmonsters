# 투명도형 퍼즐 trace JSONL 기록과 민감값 마스킹을 검증한다.
import json
from pathlib import Path

from core.puzzle.models import PuzzleSession, RoiSpec
from core.puzzle.trace import TraceLogger


def _roi(name: str) -> RoiSpec:
    return RoiSpec(name=name, basis="window_client", x=1, y=2, w=30, h=40)


def _session(tmp_path: Path) -> PuzzleSession:
    return PuzzleSession(
        session_id="20260626_171000_001",
        started_at="2026-06-26T17:10:00",
        source_kind="image_sequence",
        detect_roi=_roi("detect"),
        board_roi=_roi("board"),
        output_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        raw_video_path=tmp_path / "raw_cctv.mp4",
        board_video_path=tmp_path / "board_crop.mp4",
        overlay_video_path=tmp_path / "overlay.mp4",
    )


def test_trace_logger_writes_ordered_jsonl_events(tmp_path):
    logger = TraceLogger(_session(tmp_path), clock=lambda: 123.456)

    logger.write_event("session_start", None, {"source": "test"})
    logger.write_event("candidate", 7, {"candidate_id": "raw_7_0"})

    lines = [
        json.loads(line)
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [line["type"] for line in lines] == ["session_start", "candidate"]
    assert lines[0]["session_id"] == "20260626_171000_001"
    assert lines[0]["frame_index"] is None
    assert lines[0]["timestamp_ms"] == 123456
    assert lines[1]["frame_index"] == 7
    assert lines[1]["payload"] == {"candidate_id": "raw_7_0"}


def test_trace_logger_masks_sensitive_payload_values(tmp_path):
    logger = TraceLogger(_session(tmp_path), clock=lambda: 1.0)

    logger.write_event(
        "notify",
        3,
        {
            "tg_token": "secret-token",
            "telegram_token": "secret-token-2",
            "chat_id": "123456",
            "nested": {"chat_id": "654321"},
            "safe": "visible",
        },
    )

    event = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8"))
    assert event["payload"]["tg_token"] == "***"
    assert event["payload"]["telegram_token"] == "***"
    assert event["payload"]["chat_id"] == "***"
    assert event["payload"]["nested"]["chat_id"] == "***"
    assert event["payload"]["safe"] == "visible"
