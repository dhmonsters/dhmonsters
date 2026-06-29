# 투명도형 퍼즐 headless replay가 세션 산출물을 생성하는지 검증한다.
import json
from pathlib import Path

import cv2
import numpy as np

import puzzle


def _write_image(path: Path, value: int) -> None:
    frame = np.full((6, 8, 3), value, dtype=np.uint8)
    ok = cv2.imwrite(str(path), frame)
    assert ok


def _event_types(trace_path: Path) -> list[str]:
    return [
        json.loads(line)["type"]
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _events(trace_path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_headless_replay_processes_five_frames_and_writes_artifacts(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    for index in range(7):
        _write_image(image_dir / f"{index:03d}.png", 20 + index)

    report_path = puzzle.run_headless_replay(image_dir, output_root=tmp_path / "out")

    session_dir = report_path.parent
    trace_path = session_dir / "trace.jsonl"
    assert report_path.exists()
    assert trace_path.exists()
    assert (session_dir / "raw_cctv.mkv").stat().st_size > 0
    assert (session_dir / "board_crop.mkv").stat().st_size > 0
    assert (session_dir / "overlay.mkv").stat().st_size > 0

    event_types = _event_types(trace_path)
    assert event_types.count("FRAME_REPLAYED") == 5
    assert event_types[0] == "SESSION_START"
    assert event_types[-1] == "SESSION_END"
    text = report_path.read_text(encoding="utf-8")
    assert "frames: 5" in text
    assert "FRAME_REPLAYED: 5" in text


def test_headless_replay_command_path_returns_zero_without_importing_gui(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    _write_image(image_dir / "000.png", 33)

    code = puzzle.run_gui([
        "--headless",
        "--replay",
        str(image_dir),
        "--output-root",
        str(tmp_path / "out"),
    ])

    assert code == 0
    reports = list((tmp_path / "out").glob("**/report.md"))
    assert len(reports) == 1


def test_headless_replay_command_respects_max_frames(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    for index in range(4):
        _write_image(image_dir / f"{index:03d}.png", 40 + index)

    code = puzzle.run_gui([
        "--headless",
        "--replay",
        str(image_dir),
        "--output-root",
        str(tmp_path / "out"),
        "--max-frames",
        "2",
    ])

    assert code == 0
    report_path = next((tmp_path / "out").glob("**/report.md"))
    assert "frames: 2" in report_path.read_text(encoding="utf-8")


def test_transparent_test_command_uses_default_replay(monkeypatch, tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    _write_image(image_dir / "000.png", 66)
    calls = []

    def fake_default_replay_path():
        return image_dir

    def fake_run_headless_replay(replay, *, output_root=None, max_frames=5):
        calls.append((Path(replay), Path(output_root), max_frames))
        report_path = tmp_path / "out" / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# report\n", encoding="utf-8")
        return report_path

    monkeypatch.setattr(puzzle, "default_transparent_test_replay_path", fake_default_replay_path)
    monkeypatch.setattr(puzzle, "run_headless_replay", fake_run_headless_replay)

    code = puzzle.run_gui([
        "--transparent-test",
        "--output-root",
        str(tmp_path / "out"),
        "--max-frames",
        "2",
    ])

    assert code == 0
    assert calls == [(image_dir, tmp_path / "out", 2)]


def test_headless_replay_records_fixed_roi_snapshot(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    _write_image(image_dir / "000.png", 44)

    report_path = puzzle.run_headless_replay(image_dir, output_root=tmp_path / "out")
    trace_path = report_path.parent / "trace.jsonl"
    start_event = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])

    assert start_event["type"] == "SESSION_START"
    assert start_event["payload"]["detect_roi"]["basis"] == "window_client"
    assert start_event["payload"]["detect_roi"]["x_ratio"] == 0.254
    assert start_event["payload"]["detect_roi"]["y_ratio"] == 0.292
    assert start_event["payload"]["detect_roi"]["w_ratio"] == 0.748 - 0.254
    assert start_event["payload"]["detect_roi"]["h_ratio"] == 0.880 - 0.292
    assert start_event["payload"]["detect_roi"]["x"] == 2
    assert start_event["payload"]["detect_roi"]["y"] == 2
    assert start_event["payload"]["detect_roi"]["w"] == 4
    assert start_event["payload"]["detect_roi"]["h"] == 4
    assert start_event["payload"]["board_roi"]["basis"] == "window_client"
    assert start_event["payload"]["board_roi"]["x_ratio"] == 0.254
    assert start_event["payload"]["board_roi"]["y_ratio"] == 0.292
    assert start_event["payload"]["board_roi"]["w_ratio"] == 0.748 - 0.254
    assert start_event["payload"]["board_roi"]["h_ratio"] == 0.880 - 0.292


def test_headless_replay_records_analysis_events_per_frame(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    for index in range(5):
        _write_image(image_dir / f"{index:03d}.png", 50 + index)

    report_path = puzzle.run_headless_replay(image_dir, output_root=tmp_path / "out")
    trace_path = report_path.parent / "trace.jsonl"
    events = _events(trace_path)
    event_types = [str(event["type"]) for event in events]

    assert event_types.count("CANDIDATES") == 5
    assert event_types.count("EVIDENCE") == 5
    assert event_types.count("IDENTITY_STATE") == 5

    first_candidates = next(event for event in events if event["type"] == "CANDIDATES")
    first_evidence = next(event for event in events if event["type"] == "EVIDENCE")
    first_identity = next(event for event in events if event["type"] == "IDENTITY_STATE")

    assert first_candidates["payload"]["count"] == 0
    assert first_candidates["payload"]["candidates"] == []
    assert first_evidence["payload"]["count"] == 0
    assert first_evidence["payload"]["evidence"] == []
    assert first_identity["payload"]["state"] == "LOST"
    assert first_identity["payload"]["candidate_id"] is None

    report_text = report_path.read_text(encoding="utf-8")
    assert "CANDIDATES: 5" in report_text
    assert "EVIDENCE: 5" in report_text
    assert "IDENTITY_STATE: 5" in report_text


def test_headless_replay_records_frame_source_path_per_frame(tmp_path):
    image_dir = tmp_path / "frames"
    image_dir.mkdir()
    for index in range(5):
        _write_image(image_dir / f"{index:03d}.png", 80 + index)

    report_path = puzzle.run_headless_replay(image_dir, output_root=tmp_path / "out")
    trace_path = report_path.parent / "trace.jsonl"
    replayed = [
        event
        for event in _events(trace_path)
        if event["type"] == "FRAME_REPLAYED"
    ]

    assert [event["payload"]["source_frame_path"] for event in replayed] == [
        str(image_dir / f"{index:03d}.png")
        for index in range(5)
    ]
