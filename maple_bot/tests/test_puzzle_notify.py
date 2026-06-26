# 투명도형 퍼즐 알림 래퍼가 민감 정보 없이 이벤트를 기록하는지 검증한다.
import json
from pathlib import Path

from core.notify.telegram import TelegramNotifier
from core.puzzle.models import PuzzleSession, RoiSpec
from core.puzzle.notify import PuzzleNotifier
from core.puzzle.trace import TraceLogger


def _roi(name: str) -> RoiSpec:
    return RoiSpec(name=name, basis="window_client", x=0, y=0, w=4, h=3)


def _session(tmp_path: Path) -> PuzzleSession:
    return PuzzleSession(
        session_id="20260626_181100_001",
        started_at="2026-06-26T18:11:00",
        source_kind="image_sequence",
        detect_roi=_roi("detect"),
        board_roi=_roi("board"),
        output_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        raw_video_path=tmp_path / "raw_cctv.mp4",
        board_video_path=tmp_path / "board_crop.mp4",
        overlay_video_path=tmp_path / "overlay.mp4",
    )


def test_puzzle_notifier_sends_event_and_writes_safe_trace(tmp_path):
    sent: list[str] = []
    telegram = TelegramNotifier(
        token="secret-token",
        chat_id="secret-chat",
        enabled=True,
        post_fn=lambda _url, data: sent.append(data["text"]),
    )
    trace = TraceLogger(_session(tmp_path), clock=lambda: 2.5)
    notifier = PuzzleNotifier(telegram=telegram, trace_logger=trace)

    ok = notifier.send_event(
        "PUZZLE_DETECTED",
        "테스트 퍼즐 감지",
        snapshot=tmp_path / "snapshots" / "start.png",
    )

    assert ok is True
    assert sent == ["[PUZZLE_DETECTED] 테스트 퍼즐 감지\nsnapshot: start.png"]
    event = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8"))
    assert event["type"] == "NOTIFY"
    assert event["frame_index"] is None
    assert event["payload"]["event_type"] == "PUZZLE_DETECTED"
    assert event["payload"]["snapshot"] == str(tmp_path / "snapshots" / "start.png")
    assert "secret-token" not in json.dumps(event, ensure_ascii=False)
    assert "secret-chat" not in json.dumps(event, ensure_ascii=False)


def test_puzzle_notifier_is_safe_without_telegram(tmp_path):
    trace = TraceLogger(_session(tmp_path), clock=lambda: 3.0)
    notifier = PuzzleNotifier(trace_logger=trace)

    ok = notifier.send_event("REPORT_CREATED", "리포트 생성")

    assert ok is False
    event = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8"))
    assert event["payload"]["event_type"] == "REPORT_CREATED"
    assert event["payload"]["sent"] is False
