# 투명도형 퍼즐 분석 세션과 산출물 경로를 생성한다.
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.puzzle.models import PuzzleSession, RoiSpec


class SessionManager:
    def __init__(
        self,
        output_root: str | Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.output_root = Path(output_root) if output_root is not None else self._default_output_root()
        self._clock = clock or datetime.now
        self._counters: dict[str, int] = {}

    def start(
        self,
        source_kind: str,
        detect_roi: RoiSpec,
        board_roi: RoiSpec,
    ) -> PuzzleSession:
        now = self._clock()
        date_key = now.strftime("%Y-%m-%d")
        second_key = now.strftime("%Y%m%d_%H%M%S")
        session_root = self.output_root / f"{date_key}_transparent_puzzle_sessions"
        session_root.mkdir(parents=True, exist_ok=True)

        counter = self._counters.get(second_key, 0) + 1
        while True:
            session_id = f"{second_key}_{counter:03d}"
            output_dir = session_root / session_id
            if not output_dir.exists():
                break
            counter += 1
        self._counters[second_key] = counter

        output_dir.mkdir(parents=True)
        (output_dir / "snapshots").mkdir()

        return PuzzleSession(
            session_id=session_id,
            started_at=now.isoformat(timespec="seconds"),
            source_kind=source_kind,
            detect_roi=detect_roi,
            board_roi=board_roi,
            output_dir=output_dir,
            trace_path=output_dir / "trace.jsonl",
            raw_video_path=output_dir / "raw_cctv.mp4",
            board_video_path=output_dir / "board_crop.mp4",
            overlay_video_path=output_dir / "overlay.mp4",
        )

    @staticmethod
    def _default_output_root() -> Path:
        return Path(__file__).resolve().parents[2] / "03_output"
