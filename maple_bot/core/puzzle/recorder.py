# 투명도형 퍼즐 세션의 원본, 보드, 오버레이 영상을 저장한다.
from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from core.puzzle.models import FramePacket, PuzzleSession
from core.puzzle.trace import TraceLogger


class SessionRecorder:
    def __init__(
        self,
        session: PuzzleSession,
        fps: float = 30.0,
        trace_logger: TraceLogger | None = None,
        fourcc: str = "FFV1",
    ) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.session = session
        self.fps = fps
        self.trace_logger = trace_logger
        self.fourcc = fourcc
        self._raw_writer: Any | None = None
        self._board_writer: Any | None = None
        self._overlay_writer: Any | None = None
        self._source_shape: tuple[int, ...] | None = None
        self._board_shape: tuple[int, ...] | None = None
        self._overlay_shape: tuple[int, ...] | None = None
        self.session.output_dir.mkdir(parents=True, exist_ok=True)
        (self.session.output_dir / "snapshots").mkdir(exist_ok=True)

    def write(self, packet: FramePacket, overlay_frame: Any | None = None) -> None:
        overlay = overlay_frame if overlay_frame is not None else packet.source_frame
        if self._raw_writer is None:
            self._open_writers(packet, overlay)
        else:
            self._validate_shapes(packet, overlay)

        self._raw_writer.write(packet.source_frame)
        self._board_writer.write(packet.board_frame)
        self._overlay_writer.write(overlay)

    def snapshot(self, name: str, frame: Any, frame_index: int = 0) -> Path:
        safe_name = _safe_snapshot_name(name)
        path = self.session.output_dir / "snapshots" / f"{frame_index:06d}_{safe_name}.png"
        ok = _cv2().imwrite(str(path), frame)
        if not ok:
            raise ValueError(f"cannot write snapshot: {path}")
        return path

    def close(self) -> None:
        for writer in (self._raw_writer, self._board_writer, self._overlay_writer):
            if writer is not None:
                writer.release()
        self._raw_writer = None
        self._board_writer = None
        self._overlay_writer = None

    def _open_writers(self, packet: FramePacket, overlay_frame: Any) -> None:
        self._source_shape = tuple(packet.source_frame.shape)
        self._board_shape = tuple(packet.board_frame.shape)
        self._overlay_shape = tuple(overlay_frame.shape)
        self._raw_writer = _open_writer(self.session.raw_video_path, self._source_shape, self.fps, self.fourcc)
        self._board_writer = _open_writer(self.session.board_video_path, self._board_shape, self.fps, self.fourcc)
        self._overlay_writer = _open_writer(self.session.overlay_video_path, self._overlay_shape, self.fps, self.fourcc)

    def _validate_shapes(self, packet: FramePacket, overlay_frame: Any) -> None:
        actual_source = tuple(packet.source_frame.shape)
        actual_board = tuple(packet.board_frame.shape)
        actual_overlay = tuple(overlay_frame.shape)
        if (
            actual_source != self._source_shape
            or actual_board != self._board_shape
            or actual_overlay != self._overlay_shape
        ):
            self._log_roi_invalid(packet, actual_source, actual_board, actual_overlay)
            raise ValueError("frame size changed during recording")

    def _log_roi_invalid(
        self,
        packet: FramePacket,
        actual_source: tuple[int, ...],
        actual_board: tuple[int, ...],
        actual_overlay: tuple[int, ...],
    ) -> None:
        if self.trace_logger is None:
            return
        self.trace_logger.write_event(
            "ROI_INVALID",
            packet.frame_index,
            {
                "expected_source_shape": list(self._source_shape or ()),
                "actual_source_shape": list(actual_source),
                "expected_board_shape": list(self._board_shape or ()),
                "actual_board_shape": list(actual_board),
                "expected_overlay_shape": list(self._overlay_shape or ()),
                "actual_overlay_shape": list(actual_overlay),
            },
        )


class SnapshotOnlySessionRecorder(SessionRecorder):
    def write(self, packet: FramePacket, overlay_frame: Any | None = None) -> None:
        return None

    def close(self) -> None:
        return None


class AsyncSessionRecorder:
    def __init__(self, recorder: SessionRecorder, *, max_queue: int = 180) -> None:
        self.recorder = recorder
        self._queue: queue.Queue[tuple[FramePacket, Any] | None] = queue.Queue(maxsize=max_queue)
        self._error: BaseException | None = None
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="PuzzleSessionRecorder", daemon=True)
        self._thread.start()

    def write(self, packet: FramePacket, overlay_frame: Any | None = None) -> None:
        self._raise_if_failed()
        if self._closed:
            return
        overlay = overlay_frame if overlay_frame is not None else packet.source_frame
        self._queue.put((_copy_packet_frames(packet), _copy_frame(overlay)))

    def snapshot(self, name: str, frame: Any, frame_index: int = 0) -> Path:
        return self.recorder.snapshot(name, frame, frame_index=frame_index)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._queue.put(None)
            self._thread.join(timeout=10.0)
        self._raise_if_failed()

    def _run(self) -> None:
        try:
            while True:
                item = self._queue.get()
                try:
                    if item is None:
                        return
                    packet, overlay = item
                    self.recorder.write(packet, overlay_frame=overlay)
                except BaseException as exc:
                    self._error = exc
                    return
                finally:
                    self._queue.task_done()
        finally:
            self.recorder.close()

    def _raise_if_failed(self) -> None:
        if self._error is not None:
            raise RuntimeError(f"async recorder failed: {self._error}") from self._error


def _open_writer(path: Path, shape: tuple[int, ...], fps: float, fourcc: str) -> Any:
    if len(shape) < 2:
        raise ValueError("frame shape must include height and width")
    height, width = int(shape[0]), int(shape[1])
    encoded_width, encoded_height = _encoded_video_size(width, height, fourcc)
    writer = _cv2().VideoWriter(
        str(path),
        _cv2().VideoWriter_fourcc(*fourcc),
        fps,
        (encoded_width, encoded_height),
    )
    if not writer.isOpened():
        raise ValueError(f"cannot open video writer: {path}")
    return _VideoWriterAdapter(writer, encoded_width=encoded_width, encoded_height=encoded_height)


class _VideoWriterAdapter:
    def __init__(self, writer: Any, *, encoded_width: int, encoded_height: int) -> None:
        self.writer = writer
        self.encoded_width = encoded_width
        self.encoded_height = encoded_height

    def write(self, frame: Any) -> None:
        self.writer.write(_pad_frame_to_size(frame, self.encoded_width, self.encoded_height))

    def release(self) -> None:
        self.writer.release()


def _encoded_video_size(width: int, height: int, fourcc: str) -> tuple[int, int]:
    if fourcc.upper() == "FFV1":
        width += width % 2
        height += height % 2
    return width, height


def _pad_frame_to_size(frame: Any, width: int, height: int) -> Any:
    frame_h, frame_w = frame.shape[:2]
    pad_right = max(0, width - int(frame_w))
    pad_bottom = max(0, height - int(frame_h))
    if pad_right == 0 and pad_bottom == 0:
        return frame
    return _cv2().copyMakeBorder(frame, 0, pad_bottom, 0, pad_right, _cv2().BORDER_REPLICATE)


def _copy_packet_frames(packet: FramePacket) -> FramePacket:
    return FramePacket(
        session_id=packet.session_id,
        frame_index=packet.frame_index,
        timestamp_ms=packet.timestamp_ms,
        source_frame=_copy_frame(packet.source_frame),
        board_frame=_copy_frame(packet.board_frame),
        source_kind=packet.source_kind,
        roi_snapshot=packet.roi_snapshot,
        source_path=packet.source_path,
    )


def _copy_frame(frame: Any) -> Any:
    return frame.copy() if hasattr(frame, "copy") else frame


def _safe_snapshot_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name.strip())
    return safe or "snapshot"


def _cv2() -> Any:
    import cv2

    return cv2
