# 투명도형 퍼즐 분석 콘솔 실행 진입점을 제공한다.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.puzzle.candidates import CandidateProvider
from core.puzzle.defaults import fixed_puzzle_rois, roi_to_payload
from core.puzzle.evidence import EvidenceJudges
from core.puzzle.frame_source import ImageSequenceFrameSource, JsonlReplayFrameSource, VideoFrameSource
from core.puzzle.identity import IdentityTracker
from core.puzzle.models import Candidate, CandidateEvidence, FramePacket, IdentityDecision
from core.puzzle.recorder import SessionRecorder
from core.puzzle.report import ReportBuilder
from core.puzzle.session import SessionManager
from core.puzzle.trace import TraceLogger


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="투명도형 퍼즐 분석 콘솔")
    parser.add_argument("--replay", default="", help="나중에 headless replay에서 사용할 입력 경로")
    parser.add_argument("--headless", action="store_true", help="GUI 없이 replay를 실행한다")
    parser.add_argument("--output-root", default="", help="headless replay 산출물 루트")
    return parser


def create_window(args: argparse.Namespace | None = None):
    from ui.puzzle_console import PuzzleConsoleWindow

    window = PuzzleConsoleWindow(replay_runner=_run_replay_from_ui)
    if args is not None and getattr(args, "replay", ""):
        window.append_log(f"replay input: {args.replay}")
    return window


def run_gui(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.headless:
        if not args.replay:
            parser.error("--headless requires --replay")
        report_path = run_headless_replay(
            args.replay,
            output_root=args.output_root or None,
        )
        print(report_path)
        return 0

    from PyQt6.QtWidgets import QApplication

    from core_ui.theme import apply_font

    app = QApplication.instance() or QApplication(sys.argv if argv is None else ["puzzle.py", *argv])
    app.setStyle("Fusion")
    try:
        apply_font(app)
    except Exception:
        pass
    window = create_window(args)
    window.show()
    return int(app.exec())


def main(argv: list[str] | None = None) -> int:
    return run_gui(argv)


def run_headless_replay(
    replay: str | Path,
    *,
    output_root: str | Path | None = None,
    max_frames: int = 5,
) -> Path:
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")

    replay_path = Path(replay)
    width, height = _probe_replay_size(replay_path)
    source_kind = _source_kind_for(replay_path)
    detect_roi, board_roi = fixed_puzzle_rois(frame_w=width, frame_h=height)
    session = SessionManager(output_root=output_root).start(
        source_kind=source_kind,
        detect_roi=detect_roi,
        board_roi=board_roi,
    )
    trace = TraceLogger(session)
    recorder = SessionRecorder(session, trace_logger=trace)
    candidate_provider = CandidateProvider(_empty_replay_rows, source="replay")
    evidence_judges = EvidenceJudges()
    identity_tracker = IdentityTracker()
    processed = 0

    trace.write_event(
        "SESSION_START",
        None,
        {
            "source_kind": source_kind,
            "replay_path": str(replay_path),
            "max_frames": max_frames,
            "detect_roi": roi_to_payload(session.detect_roi),
            "board_roi": roi_to_payload(session.board_roi),
        },
    )
    try:
        for packet in _open_replay_source(replay_path, session).iter_frames():
            if processed >= max_frames:
                break
            recorder.write(packet, overlay_frame=packet.source_frame)
            candidates = candidate_provider.detect(packet)
            evidence = evidence_judges.score(candidates, packet)
            decision = identity_tracker.update(
                frame_index=packet.frame_index,
                candidates=candidates,
                evidence=evidence,
            )
            trace.write_event(
                "FRAME_REPLAYED",
                packet.frame_index,
                {
                    "timestamp_ms": packet.timestamp_ms,
                    "source_kind": packet.source_kind,
                },
            )
            trace.write_event(
                "CANDIDATES",
                packet.frame_index,
                {
                    "count": len(candidates),
                    "candidates": [_candidate_to_payload(candidate) for candidate in candidates],
                    "debug": candidate_provider.last_debug,
                },
            )
            trace.write_event(
                "EVIDENCE",
                packet.frame_index,
                {
                    "count": len(evidence),
                    "evidence": [_evidence_to_payload(item) for item in evidence.values()],
                },
            )
            trace.write_event(
                "IDENTITY_STATE",
                packet.frame_index,
                _identity_to_payload(decision),
            )
            processed += 1
    finally:
        recorder.close()

    trace.write_event("SESSION_END", None, {"frames": processed})
    return ReportBuilder().build(session, session.trace_path)


def _open_replay_source(replay_path: Path, session):
    if replay_path.suffix.lower() == ".jsonl":
        return JsonlReplayFrameSource(replay_path, session)
    if replay_path.suffix.lower() in VIDEO_EXTENSIONS:
        return VideoFrameSource(replay_path, session)
    return ImageSequenceFrameSource(replay_path, session)


def _run_replay_from_ui(path: str, _kind: str) -> Path:
    return run_headless_replay(path)


def _empty_replay_rows(_packet: FramePacket) -> list[object]:
    return []


def _candidate_to_payload(candidate: Candidate) -> dict[str, object]:
    return {
        "candidate_id": candidate.candidate_id,
        "frame_index": candidate.frame_index,
        "bbox": list(candidate.bbox),
        "center": list(candidate.center),
        "score": candidate.score,
        "source": candidate.source,
        "class_name": candidate.class_name,
    }


def _evidence_to_payload(evidence: CandidateEvidence) -> dict[str, object]:
    return {
        "candidate_id": evidence.candidate_id,
        "bg_score": evidence.bg_score,
        "motion_divergence": evidence.motion_divergence,
        "rigid_violation": evidence.rigid_violation,
        "phase_similarity": evidence.phase_similarity,
        "texture_bg_score": evidence.texture_bg_score,
        "color_residual": evidence.color_residual,
        "merge_likelihood": evidence.merge_likelihood,
        "notes": list(evidence.notes),
    }


def _identity_to_payload(decision: IdentityDecision) -> dict[str, object]:
    return {
        "state": decision.state,
        "point": list(decision.point) if decision.point is not None else None,
        "candidate_id": decision.candidate_id,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "hold_frames": decision.hold_frames,
        "debug": decision.debug,
    }


def _source_kind_for(replay_path: Path) -> str:
    suffix = replay_path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl_replay"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return "image_sequence"


def _probe_replay_size(replay_path: Path) -> tuple[int, int]:
    if replay_path.suffix.lower() in VIDEO_EXTENSIONS:
        return _probe_video_size(replay_path)

    image_path = _first_replay_image_path(replay_path)
    frame = _cv2().imread(str(image_path))
    if frame is None:
        raise ValueError(f"cannot read replay frame: {image_path}")
    height, width = frame.shape[:2]
    return int(width), int(height)


def _first_replay_image_path(replay_path: Path) -> Path:
    if replay_path.is_dir():
        paths = sorted(
            child
            for child in replay_path.iterdir()
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not paths:
            raise ValueError("replay image directory must contain at least one image")
        return paths[0]

    if replay_path.suffix.lower() == ".jsonl":
        with replay_path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if not line.strip():
                    continue
                event = json.loads(line)
                payload = event.get("payload") if isinstance(event, dict) else {}
                if not isinstance(payload, dict):
                    payload = {}
                frame_path = _frame_path_from_event(event, payload)
                if frame_path is not None:
                    path = Path(frame_path)
                    return path if path.is_absolute() else replay_path.parent / path
        raise ValueError("jsonl replay must contain at least one frame path")

    if replay_path.suffix.lower() in IMAGE_EXTENSIONS:
        return replay_path
    raise ValueError(f"unsupported replay input: {replay_path}")


def _probe_video_size(video_path: Path) -> tuple[int, int]:
    capture = _cv2().VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"cannot open video: {video_path}")
    try:
        width = int(round(capture.get(_cv2().CAP_PROP_FRAME_WIDTH)))
        height = int(round(capture.get(_cv2().CAP_PROP_FRAME_HEIGHT)))
        if width > 0 and height > 0:
            return width, height
        ok, frame = capture.read()
        if ok and frame is not None:
            frame_h, frame_w = frame.shape[:2]
            return int(frame_w), int(frame_h)
    finally:
        capture.release()
    raise ValueError(f"cannot read video frame: {video_path}")


def _frame_path_from_event(event: dict[str, object], payload: dict[str, object]) -> str | None:
    for key in ("source_frame_path", "frame_path", "image_path"):
        value = payload.get(key, event.get(key))
        if value:
            return str(value)
    return None


def _cv2():
    import cv2

    return cv2


if __name__ == "__main__":
    raise SystemExit(main())
