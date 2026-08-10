# 투명도형 퍼즐 입력 프레임을 세션 FramePacket으로 변환한다.
from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from core.puzzle.models import FramePacket, PuzzleSession, RoiSpec
from core.puzzle.roi import crop_by_roi


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


class ImageSequenceFrameSource:
    def __init__(
        self,
        source: str | Path | Sequence[str | Path],
        session: PuzzleSession,
        fps: float = 30.0,
    ) -> None:
        self.paths = _collect_image_paths(source)
        self.session = session
        self.frame_period_ms = _frame_period_ms(fps)

    def iter_frames(self) -> Iterator[FramePacket]:
        for index, path in enumerate(self.paths):
            frame = _read_image(path)
            yield _make_packet(
                session=self.session,
                source_frame=frame,
                frame_index=index,
                timestamp_ms=index * self.frame_period_ms,
                source_path=str(path),
            )


class VideoFrameSource:
    def __init__(
        self,
        video_path: str | Path,
        session: PuzzleSession,
        fps_fallback: float = 30.0,
    ) -> None:
        self.video_path = Path(video_path)
        self.session = session
        self.fps_fallback = fps_fallback

    def iter_frames(self) -> Iterator[FramePacket]:
        cv2 = _cv2()
        capture = cv2.VideoCapture(str(self.video_path))
        if not capture.isOpened():
            raise ValueError(f"cannot open video: {self.video_path}")

        fps = capture.get(cv2.CAP_PROP_FPS) or self.fps_fallback
        frame_period_ms = _frame_period_ms(fps)
        index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                position_ms = int(round(capture.get(cv2.CAP_PROP_POS_MSEC)))
                timestamp_ms = position_ms if position_ms > 0 else index * frame_period_ms
                yield _make_packet(
                    session=self.session,
                    source_frame=frame,
                    frame_index=index,
                    timestamp_ms=timestamp_ms,
                    source_path=f"{self.video_path}#frame={index}",
                )
                index += 1
        finally:
            capture.release()


class JsonlReplayFrameSource:
    def __init__(
        self,
        jsonl_path: str | Path,
        session: PuzzleSession,
        fps: float = 30.0,
    ) -> None:
        self.jsonl_path = Path(jsonl_path)
        self.session = session
        self.frame_period_ms = _frame_period_ms(fps)

    def iter_frames(self) -> Iterator[FramePacket]:
        emitted = 0
        with self.jsonl_path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if not line.strip():
                    continue
                event = json.loads(line)
                payload = event.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {}
                frame_path = _frame_path_from_event(event, payload)
                if frame_path is None:
                    continue

                resolved_frame_path = self._resolve_frame_path(frame_path)
                frame = _read_image(resolved_frame_path)
                frame_index = int(event.get("frame_index", emitted))
                timestamp_ms = int(event.get("timestamp_ms", emitted * self.frame_period_ms))
                yield _make_packet(
                    session=self.session,
                    source_frame=frame,
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    source_path=str(resolved_frame_path),
                )
                emitted += 1

    def _resolve_frame_path(self, frame_path: str) -> Path:
        path = Path(frame_path)
        if path.is_absolute():
            return path
        return self.jsonl_path.parent / path


def _collect_image_paths(source: str | Path | Sequence[str | Path]) -> list[Path]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.is_dir():
            paths = [
                child
                for child in path.iterdir()
                if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS
            ]
        else:
            paths = [path]
    else:
        paths = [Path(item) for item in source]

    paths = sorted(paths, key=lambda item: item.name)
    if not paths:
        raise ValueError("image sequence must contain at least one image")
    return paths


def _read_image(path: Path) -> Any:
    frame = _cv2().imread(str(path))
    if frame is None:
        raise ValueError(f"cannot read frame image: {path}")
    return frame


def _make_packet(
    *,
    session: PuzzleSession,
    source_frame: Any,
    frame_index: int,
    timestamp_ms: int,
    source_path: str | None = None,
) -> FramePacket:
    return FramePacket(
        session_id=session.session_id,
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        source_frame=source_frame,
        board_frame=crop_by_roi(source_frame, session.board_roi),
        source_kind=session.source_kind,
        roi_snapshot={
            "detect": _roi_to_dict(session.detect_roi),
            "board": _roi_to_dict(session.board_roi),
        },
        source_path=source_path,
    )


def _roi_to_dict(roi: RoiSpec) -> dict[str, object]:
    return {
        "name": roi.name,
        "basis": roi.basis,
        "x": roi.x,
        "y": roi.y,
        "w": roi.w,
        "h": roi.h,
        "dpi_scale": roi.dpi_scale,
        "window_title": roi.window_title,
    }


def _frame_path_from_event(event: dict[str, Any], payload: dict[str, Any]) -> str | None:
    for key in ("source_frame_path", "frame_path", "image_path"):
        value = payload.get(key, event.get(key))
        if value:
            return str(value)
    return None


def _frame_period_ms(fps: float) -> int:
    if fps <= 0:
        raise ValueError("fps must be positive")
    return int(round(1000.0 / fps))


def _cv2() -> Any:
    import cv2

    return cv2
