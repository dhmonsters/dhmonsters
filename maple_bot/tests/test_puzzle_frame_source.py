# 투명도형 퍼즐 replay 입력을 FramePacket으로 변환하는 동작을 검증한다.
import json
from pathlib import Path

import cv2
import numpy as np

from core.puzzle.frame_source import ImageSequenceFrameSource, JsonlReplayFrameSource
from core.puzzle.models import PuzzleSession, RoiSpec


def _roi(name: str) -> RoiSpec:
    return RoiSpec(name=name, basis="window_client", x=1, y=1, w=2, h=2)


def _session(tmp_path: Path, source_kind: str = "image_sequence") -> PuzzleSession:
    return PuzzleSession(
        session_id="20260626_172000_001",
        started_at="2026-06-26T17:20:00",
        source_kind=source_kind,
        detect_roi=_roi("detect"),
        board_roi=_roi("board"),
        output_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        raw_video_path=tmp_path / "raw_cctv.mp4",
        board_video_path=tmp_path / "board_crop.mp4",
        overlay_video_path=tmp_path / "overlay.mp4",
    )


def _write_image(path: Path, value: int) -> None:
    frame = np.full((5, 6, 3), value, dtype=np.uint8)
    cv2.imwrite(str(path), frame)


def test_image_sequence_frame_source_sorts_images_and_crops_board(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    _write_image(image_dir / "002.png", 20)
    _write_image(image_dir / "001.png", 10)

    packets = list(ImageSequenceFrameSource(image_dir, _session(tmp_path)).iter_frames())

    assert [packet.frame_index for packet in packets] == [0, 1]
    assert [int(packet.source_frame[0, 0, 0]) for packet in packets] == [10, 20]
    assert packets[0].board_frame.shape == (2, 2, 3)
    assert packets[0].timestamp_ms == 0
    assert packets[1].timestamp_ms == 33
    assert packets[0].roi_snapshot["board"]["w"] == 2
    assert packets[0].source_path == str(image_dir / "001.png")
    assert packets[1].source_path == str(image_dir / "002.png")


def test_jsonl_replay_frame_source_reads_frame_paths(tmp_path):
    image_path = tmp_path / "frame.png"
    _write_image(image_path, 77)
    jsonl_path = tmp_path / "replay.jsonl"
    jsonl_path.write_text(
        json.dumps(
            {
                "frame_index": 5,
                "timestamp_ms": 123,
                "payload": {"source_frame_path": str(image_path)},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    packets = list(JsonlReplayFrameSource(jsonl_path, _session(tmp_path, "jsonl_replay")).iter_frames())

    assert len(packets) == 1
    assert packets[0].frame_index == 5
    assert packets[0].timestamp_ms == 123
    assert packets[0].source_path == str(image_path)
    assert int(packets[0].board_frame[0, 0, 0]) == 77
