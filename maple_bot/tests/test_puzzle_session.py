# 투명도형 퍼즐 세션 산출물 경로와 ID 생성을 검증한다.
from datetime import datetime

from core.puzzle.models import RoiSpec
from core.puzzle.session import SessionManager


def _roi(name: str) -> RoiSpec:
    return RoiSpec(name=name, basis="window_client", x=10, y=20, w=300, h=200)


def test_session_manager_creates_output_paths(tmp_path):
    manager = SessionManager(
        output_root=tmp_path,
        clock=lambda: datetime(2026, 6, 26, 16, 45, 1),
    )

    session = manager.start(
        source_kind="image_sequence",
        detect_roi=_roi("detect"),
        board_roi=_roi("board"),
    )

    assert session.session_id == "20260626_164501_001"
    assert session.started_at == "2026-06-26T16:45:01"
    assert session.output_dir == tmp_path / "2026-06-26_투명도형퍼즐_sessions" / session.session_id
    assert session.output_dir.is_dir()
    assert (session.output_dir / "snapshots").is_dir()
    assert session.trace_path == session.output_dir / "trace.jsonl"
    assert session.raw_video_path == session.output_dir / "raw_cctv.mp4"
    assert session.board_video_path == session.output_dir / "board_crop.mp4"
    assert session.overlay_video_path == session.output_dir / "overlay.mp4"


def test_session_manager_increments_ids_within_same_second(tmp_path):
    manager = SessionManager(
        output_root=tmp_path,
        clock=lambda: datetime(2026, 6, 26, 16, 45, 1),
    )

    first = manager.start("video", _roi("detect"), _roi("board"))
    second = manager.start("video", _roi("detect"), _roi("board"))

    assert first.session_id == "20260626_164501_001"
    assert second.session_id == "20260626_164501_002"
    assert first.output_dir != second.output_dir

