# 투명도형 퍼즐 분석 콘솔 실행 진입점을 제공한다.
from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

from core.puzzle.candidates import CandidateProvider
from core.puzzle.capture_preflight import CaptureCheckResult, run_capture_check
from core.puzzle.defaults import fixed_puzzle_rois, roi_to_payload
from core.puzzle.evidence import EvidenceJudges
from core.puzzle.frame_source import ImageSequenceFrameSource, JsonlReplayFrameSource, VideoFrameSource
from core.puzzle.identity import IdentityTracker
from core.puzzle.live_recording import LiveRecordingRuntime
from core.puzzle.models import Candidate, CandidateEvidence, FramePacket, IdentityDecision
from core.puzzle.planet_live import render_planet_cctv_preview
from core.puzzle.recorder import SessionRecorder
from core.puzzle.recording_controller import RecordingController
from core.puzzle.report import ReportBuilder
from core.puzzle.session import SessionManager
from core.puzzle.trace import TraceLogger
from core.puzzle.live_watch import LivePuzzleActivationDetector, WatchStartResult


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="투명도형 퍼즐 분석 콘솔")
    parser.add_argument("--replay", default="", help="나중에 headless replay에서 사용할 입력 경로")
    parser.add_argument("--headless", action="store_true", help="GUI 없이 replay를 실행한다")
    parser.add_argument("--transparent-test", action="store_true", help="기본 투명도형 테스트 replay를 실행한다")
    parser.add_argument("--output-root", default="", help="headless replay 산출물 루트")
    parser.add_argument("--max-frames", type=int, default=5, help="replay에서 처리할 최대 frame 수")
    parser.add_argument("--live-record", action="store_true", help="GUI 없이 현재 화면 녹화를 시작한다")
    parser.add_argument("--live-max-frames", type=int, default=0, help="live-record 검증용 최대 frame 수. 0은 수동 종료")
    parser.add_argument("--live-dry-run", action="store_true", help="live solver 판단은 돌리되 마우스 제어는 끈다")
    parser.add_argument("--live-capture-check", action="store_true", help="현재 화면 캡처 가능 여부를 점검한다")
    return parser


def create_window(args: argparse.Namespace | None = None):
    from ui.puzzle_console import PuzzleConsoleWindow

    default_test_path = default_transparent_test_replay_path()
    live_runtime = LiveRecordingRuntime(
        output_root=(args.output_root or None) if args is not None else None,
        mouse_enabled=not bool(getattr(args, "live_dry_run", False)),
    )
    live_detector = LivePuzzleActivationDetector()
    live_thread: dict[str, threading.Thread | None] = {"thread": None}
    live_stop: dict[str, threading.Event | None] = {"event": None}
    live_watch_preview: dict[str, object | None] = {"frame": None}

    def start_live_watch() -> WatchStartResult:
        live_runtime.set_mouse_enabled(window.mouse_control_enabled())
        thread = live_thread["thread"]
        if live_runtime.is_recording and live_runtime.session is not None:
            return WatchStartResult(
                "recording",
                live_runtime.session.output_dir,
                live_runtime.latest_preview_path,
            )
        if thread is not None and thread.is_alive():
            return WatchStartResult("armed", preview_frame=live_watch_preview["frame"])
        stop_event = threading.Event()
        live_stop["event"] = stop_event

        def worker() -> None:
            try:
                frame_period_s = 1.0 / live_runtime.fps
                while not stop_event.is_set() and not live_runtime.is_recording:
                    frame = live_runtime.frame_grabber()
                    activation = live_detector.detect(frame)
                    live_watch_preview["frame"] = _build_watch_preview_frame(
                        frame,
                        popup_score=activation.score,
                    )
                    if activation.active:
                        live_runtime.start(
                            initial_frame=frame,
                            detect_roi=activation.detect_roi,
                            board_roi=activation.board_roi,
                        )
                        if live_runtime.trace is not None:
                            live_runtime.trace.write_event(
                                "PUZZLE_ACTIVATED",
                                None,
                                {
                                    "reason": activation.reason,
                                    "score": activation.score,
                                    "detect_roi": (
                                        roi_to_payload(activation.detect_roi)
                                        if activation.detect_roi is not None
                                        else None
                                    ),
                                    "board_roi": (
                                        roi_to_payload(activation.board_roi)
                                        if activation.board_roi is not None
                                        else None
                                    ),
                                    "debug": activation.debug or {},
                                },
                            )
                        break
                    live_runtime.sleeper(frame_period_s)
                if live_runtime.is_recording:
                    live_runtime.run_until_stopped()
            except Exception as exc:
                if live_runtime.trace is not None:
                    live_runtime.trace.write_event(
                        "PLANET_LIVE_SOLVER_FAILED",
                        None,
                        {"error": str(exc), "error_type": exc.__class__.__name__},
                    )
                if live_runtime.is_recording:
                    live_runtime.stop_recording(reason="watch_error")
                if live_runtime.session is not None:
                    live_runtime.finish(reason="watch_error")
                return

        live_thread["thread"] = threading.Thread(target=worker, daemon=True, name="PuzzleLiveWatch")
        live_thread["thread"].start()
        return WatchStartResult("armed")

    def stop_live_solver() -> bool:
        if live_runtime.is_recording:
            return live_runtime.stop_solver(reason="manual_f2")
        stop_event = live_stop.get("event")
        thread = live_thread.get("thread")
        if stop_event is not None and thread is not None and thread.is_alive():
            stop_event.set()
            return True
        return False

    def stop_live_recording() -> bool:
        return live_runtime.stop_recording(reason="manual_f3")

    def live_status() -> WatchStartResult:
        if live_runtime.is_recording and live_runtime.session is not None:
            return WatchStartResult(
                "recording",
                live_runtime.session.output_dir,
                live_runtime.latest_preview_path,
            )
        thread = live_thread.get("thread")
        if thread is not None and thread.is_alive():
            return WatchStartResult("armed", preview_frame=live_watch_preview["frame"])
        return WatchStartResult("idle")

    def run_capture_check_from_ui() -> Path | None:
        result = run_live_capture_check(output_root=(args.output_root or None) if args is not None else None)
        if not result.ok:
            raise RuntimeError(result.error)
        return result.report_path

    window = PuzzleConsoleWindow(
        replay_runner=_run_replay_from_ui,
        watch_start_handler=start_live_watch,
        solver_stop_handler=stop_live_solver,
        live_status_handler=live_status,
        capture_check_handler=run_capture_check_from_ui,
        recording_stop_handler=stop_live_recording,
        default_test_path=default_test_path if default_test_path.exists() else None,
        mouse_control_enabled=not bool(getattr(args, "live_dry_run", False)),
    )
    _attach_puzzle_hotkeys(window)
    if args is not None and getattr(args, "replay", ""):
        window.append_log(f"replay input: {args.replay}")
    return window


def run_gui(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.live_capture_check:
        result = run_live_capture_check(output_root=args.output_root or None)
        print(result.report_path)
        if not result.ok:
            print(result.error, file=sys.stderr)
            return 2
        return 0

    if args.live_record:
        report_path = run_live_recording(
            output_root=args.output_root or None,
            max_frames=args.live_max_frames or None,
            mouse_enabled=not args.live_dry_run,
        )
        print(report_path)
        return 0

    if args.transparent_test:
        replay_path = Path(args.replay) if args.replay else default_transparent_test_replay_path()
        if not replay_path.exists():
            parser.error(f"transparent test replay not found: {replay_path}")
        report_path = run_headless_replay(
            replay_path,
            output_root=args.output_root or None,
            max_frames=args.max_frames,
        )
        print(report_path)
        return 0

    if args.headless:
        if not args.replay:
            parser.error("--headless requires --replay")
        report_path = run_headless_replay(
            args.replay,
            output_root=args.output_root or None,
            max_frames=args.max_frames,
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
    recording = RecordingController(
        recorder=SessionRecorder(session, trace_logger=trace),
        trace_logger=trace,
    )
    candidate_provider = CandidateProvider(
        _candidate_rows_from_replay_companion(replay_path),
        source="replay",
    )
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
            recording.write(packet, overlay_frame=packet.source_frame)
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
                    "source_frame_path": packet.source_path,
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
        recording.stop_recording(reason="replay_finished")

    trace.write_event("SESSION_END", None, {"frames": processed})
    return ReportBuilder().build(session, session.trace_path)


def run_live_recording(
    *,
    output_root: str | Path | None = None,
    max_frames: int | None = None,
    mouse_enabled: bool = True,
) -> Path:
    runtime = LiveRecordingRuntime(output_root=output_root, mouse_enabled=mouse_enabled)
    try:
        return runtime.run_until_stopped(max_frames=max_frames)
    except KeyboardInterrupt:
        runtime.stop_recording(reason="keyboard_interrupt")
        return runtime.finish(reason="keyboard_interrupt")


def run_live_capture_check(*, output_root: str | Path | None = None) -> CaptureCheckResult:
    return run_capture_check(output_root=output_root)


def _build_watch_preview_frame(
    frame: object,
    *,
    popup_score: float | None,
) -> object:
    return render_planet_cctv_preview(frame, popup_score=popup_score)


def _attach_puzzle_hotkeys(window: object) -> None:
    try:
        from core.hotkey_manager import HotkeyManager
    except Exception as exc:
        if hasattr(window, "append_log"):
            window.append_log(f"global puzzle hotkey unavailable: {exc}")
        return

    try:
        manager = HotkeyManager(window)
        manager.register("puzzle_start_recording", "f1", window.start_watch_input)
        manager.register("puzzle_stop_solver", "f2", window.stop_solver_input)
        manager.register("puzzle_stop_recording", "f3", window.stop_recording_input)
        setattr(window, "_puzzle_hotkey_manager", manager)
    except Exception as exc:
        if hasattr(window, "append_log"):
            window.append_log(f"global puzzle hotkey unavailable: {exc}")


def _open_replay_source(replay_path: Path, session):
    if replay_path.suffix.lower() == ".jsonl":
        return JsonlReplayFrameSource(replay_path, session)
    if replay_path.suffix.lower() in VIDEO_EXTENSIONS:
        return VideoFrameSource(replay_path, session)
    return ImageSequenceFrameSource(replay_path, session)


def _run_replay_from_ui(path: str, _kind: str) -> Path:
    return run_headless_replay(path)


def default_transparent_test_replay_path() -> Path:
    return Path(__file__).resolve().parent / "_record_debug" / "000_0621_180636_png"


def _empty_replay_rows(_packet: FramePacket) -> list[object]:
    return []


def _candidate_rows_from_replay_companion(replay_path: str | Path):
    companion = _companion_candidate_jsonl_path(replay_path)
    if companion is None:
        return _empty_replay_rows

    rows_by_frame: dict[int, list[object]] = {}
    with companion.open("r", encoding="utf-8") as fp:
        for frame_index, line in enumerate(fp):
            if not line.strip():
                continue
            row = json.loads(line)
            cands = row.get("cands") if isinstance(row, dict) else None
            if isinstance(cands, list):
                rows_by_frame[frame_index] = cands

    def provider(packet: FramePacket) -> list[object]:
        return rows_by_frame.get(int(packet.frame_index), [])

    return provider


def _companion_candidate_jsonl_path(replay_path: str | Path) -> Path | None:
    path = Path(replay_path)
    if path.suffix.lower() == ".jsonl":
        return path if path.exists() else None
    stem = path.stem
    if stem.endswith("_png"):
        stem = stem[:-4]
    candidate = path.with_name(f"{stem}.jsonl")
    return candidate if candidate.exists() else None


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
