# 투명도형 퍼즐 라이브 화면을 무손실 세션 녹화로 저장한다.
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.puzzle.defaults import fixed_puzzle_rois, roi_to_payload
from core.puzzle.game_window import find_game_hwnd, get_game_client_rect_screen
from core.puzzle.models import FramePacket, PuzzleSession, RoiSpec
from core.puzzle.live_session_review import LiveSessionReviewBuilder
from core.puzzle.planet_live import PlanetLiveResult, PlanetLiveSolver, render_planet_cctv_preview
from core.puzzle.recorder import AsyncSessionRecorder, SessionRecorder
from core.puzzle.recording_controller import RecordingController
from core.puzzle.report import ReportBuilder
from core.puzzle.roi import crop_by_roi
from core.puzzle.session import SessionManager
from core.puzzle.trace import TraceLogger


FrameGrabber = Callable[[], Any]
Sleeper = Callable[[float], None]


class LiveRecordingRuntime:
    def __init__(
        self,
        *,
        output_root: str | Path | None = None,
        frame_grabber: FrameGrabber | None = None,
        fps: float = 30.0,
        sleeper: Sleeper | None = None,
        live_solver: Any | None = None,
        mouse_enabled: bool = True,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.output_root = output_root
        self.frame_grabber = frame_grabber or GameClientFrameGrabber()
        self.fps = fps
        self.sleeper = sleeper or time.sleep
        self.mouse_enabled = bool(mouse_enabled)
        self.live_solver = (
            live_solver
            if live_solver is not None
            else PlanetLiveSolver(mouse_enabled=self.mouse_enabled)
        )
        self.session: PuzzleSession | None = None
        self.trace: TraceLogger | None = None
        self.recording: RecordingController | None = None
        self.report_path: Path | None = None
        self.review_path: Path | None = None
        self.latest_preview_path: Path | None = None
        self.latest_preview_frame: Any | None = None
        self.frame_count = 0
        self._finished = False

    @property
    def is_recording(self) -> bool:
        return self.recording is not None and self.recording.is_recording

    @property
    def is_solver_running(self) -> bool:
        return self.recording is not None and self.recording.is_solver_running

    def set_mouse_enabled(self, enabled: bool) -> None:
        self.mouse_enabled = bool(enabled)
        if hasattr(self.live_solver, "mouse_enabled"):
            self.live_solver.mouse_enabled = self.mouse_enabled

    def start(
        self,
        *,
        initial_frame: Any | None = None,
        detect_roi: RoiSpec | None = None,
        board_roi: RoiSpec | None = None,
    ) -> PuzzleSession:
        if self.is_recording and self.session is not None:
            return self.session

        first_frame = initial_frame if initial_frame is not None else self.frame_grabber()
        frame_h, frame_w = first_frame.shape[:2]
        if detect_roi is None or board_roi is None:
            default_detect_roi, default_board_roi = fixed_puzzle_rois(frame_w=frame_w, frame_h=frame_h)
            detect_roi = detect_roi or default_detect_roi
            board_roi = board_roi or default_board_roi
        session = SessionManager(output_root=self.output_root).start(
            source_kind="live_screen",
            detect_roi=detect_roi,
            board_roi=board_roi,
        )
        trace = TraceLogger(session)
        self.session = session
        self.trace = trace
        self.recording = RecordingController(
            recorder=_live_recorder(session, fps=self.fps, trace_logger=trace),
            trace_logger=trace,
        )
        self.report_path = None
        self.review_path = None
        self.latest_preview_path = None
        self.latest_preview_frame = None
        self.frame_count = 0
        self._finished = False
        trace.write_event(
            "SESSION_START",
            None,
            {
                "source_kind": "live_screen",
                "fps": self.fps,
                "mouse_enabled": self.mouse_enabled,
                "detect_roi": roi_to_payload(detect_roi),
                "board_roi": roi_to_payload(board_roi),
            },
        )
        self._write_frame(first_frame)
        return session

    def pump_once(self) -> bool:
        if not self.is_recording:
            return False
        return self._write_frame(self.frame_grabber())

    def stop_solver(self, *, reason: str = "manual_f2") -> bool:
        if self.recording is None:
            return False
        return self.recording.stop_solver(reason=reason)

    def stop_recording(self, *, reason: str = "manual_f3") -> bool:
        if self.recording is None:
            return False
        return self.recording.stop_recording(reason=reason)

    def run_until_stopped(self, *, max_frames: int | None = None) -> Path:
        if max_frames is not None and max_frames <= 0:
            raise ValueError("max_frames must be positive")
        self.start()
        frame_period_s = 1.0 / self.fps
        try:
            while self.is_recording:
                if max_frames is not None and self.frame_count >= max_frames:
                    break
                self.pump_once()
                if self.is_recording and (max_frames is None or self.frame_count < max_frames):
                    self.sleeper(frame_period_s)
            if self.is_recording:
                self.stop_recording(reason="max_frames")
            return self.finish()
        except Exception as exc:
            if self.trace is not None:
                self.trace.write_event("LIVE_RECORDING_FAILED", None, {"error": str(exc)})
            if self.is_recording:
                self.stop_recording(reason="recording_error")
            self.finish(reason="recording_error")
            raise

    def finish(self, *, reason: str = "finished") -> Path:
        if self.session is None or self.trace is None:
            raise RuntimeError("live recording has not started")
        if self.is_recording:
            self.stop_recording(reason=reason)
        if not self._finished:
            self.trace.write_event("SESSION_END", None, {"frames": self.frame_count, "reason": reason})
            self.review_path = self.session.output_dir / "live_session_review.md"
            LiveSessionReviewBuilder().build(self.session.trace_path, self.review_path)
            self.report_path = ReportBuilder().build(self.session, self.session.trace_path)
            self._finished = True
        if self.report_path is None:
            raise RuntimeError("live recording report was not created")
        return self.report_path

    def _write_frame(self, frame: Any) -> bool:
        if self.session is None or self.trace is None or self.recording is None:
            raise RuntimeError("live recording has not started")
        if not self.recording.is_recording:
            return False

        frame_index = self.frame_count
        packet = FramePacket(
            session_id=self.session.session_id,
            frame_index=frame_index,
            timestamp_ms=int(round(frame_index * 1000.0 / self.fps)),
            source_frame=frame,
            board_frame=crop_by_roi(frame, self.session.board_roi),
            source_kind=self.session.source_kind,
            roi_snapshot={
                "detect": roi_to_payload(self.session.detect_roi),
                "board": roi_to_payload(self.session.board_roi),
            },
            source_path=f"live_screen#frame={frame_index}",
        )
        live_result = self._analyze_live_frame(packet)
        self.recording.write(packet, overlay_frame=frame)
        self._write_live_preview(packet, preview_frame=live_result.preview_frame if live_result else None)
        self.trace.write_event(
            "FRAME_RECORDED",
            frame_index,
            {
                "timestamp_ms": packet.timestamp_ms,
                "source_kind": packet.source_kind,
                "source_frame_path": packet.source_path,
            },
        )
        self.frame_count += 1
        return True

    def _analyze_live_frame(self, packet: FramePacket) -> PlanetLiveResult | None:
        if self.trace is None or self.recording is None or self.live_solver is None:
            return None
        try:
            result = self.live_solver.analyze(packet, solver_running=self.recording.is_solver_running)
        except Exception as exc:
            self.trace.write_event("PLANET_LIVE_SOLVER_FAILED", packet.frame_index, {"error": str(exc)})
            return None
        for event_type, payload in result.trace_events:
            self.trace.write_event(event_type, packet.frame_index, payload)
        return result

    def _write_live_preview(self, packet: FramePacket, *, preview_frame: Any | None = None) -> None:
        if self.session is None:
            return
        frame = preview_frame if preview_frame is not None else render_planet_cctv_preview(packet.source_frame)
        self.latest_preview_frame = frame
        preview_path = self.session.output_dir / "snapshots" / f"live_preview_{packet.frame_index:06d}.png"
        ok = _cv2().imwrite(str(preview_path), frame)
        if ok:
            self.latest_preview_path = preview_path


class GameClientFrameGrabber:
    def __init__(self) -> None:
        self._hwnd: int | None = None

    def __call__(self) -> Any:
        for retry in range(2):
            hwnd = self._require_hwnd()
            try:
                left, top, width, height = _game_client_rect_screen(hwnd)
                break
            except Exception:
                self._hwnd = None
                if retry == 0:
                    continue
                raise
        else:
            raise RuntimeError("maple game window not found")

        if width <= 0 or height <= 0:
            raise RuntimeError(f"invalid game client rect: {width}x{height}")
        return _grab_screen_region_bgr(left=left, top=top, width=width, height=height)

    def _require_hwnd(self) -> int:
        if self._hwnd is not None:
            return self._hwnd
        self._hwnd = _find_game_hwnd()
        return self._hwnd


def grab_screen_bgr() -> Any:
    import cv2
    import numpy as np

    capture_errors: list[str] = []
    try:
        import mss

        with mss.mss() as sct:
            image = sct.grab(_select_main_monitor(sct.monitors))
        return cv2.cvtColor(np.array(image), cv2.COLOR_BGRA2BGR)
    except Exception as exc:
        capture_errors.append(f"mss: {exc}")

    from PIL import ImageGrab

    try:
        image = ImageGrab.grab(all_screens=False).convert("RGB")
    except Exception as exc:
        capture_errors.append(f"ImageGrab: {exc}")
        details = " | ".join(capture_errors)
        raise RuntimeError(f"screen capture failed ({details})") from exc
    rgb = np.array(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _grab_screen_region_bgr(*, left: int, top: int, width: int, height: int) -> Any:
    import cv2
    import numpy as np

    capture_errors: list[str] = []
    try:
        import mss

        with mss.mss() as sct:
            image = sct.grab({"left": int(left), "top": int(top), "width": int(width), "height": int(height)})
        return cv2.cvtColor(np.array(image), cv2.COLOR_BGRA2BGR)
    except Exception as exc:
        capture_errors.append(f"mss: {exc}")

    from PIL import ImageGrab

    try:
        image = ImageGrab.grab(
            bbox=(int(left), int(top), int(left + width), int(top + height)),
            all_screens=True,
        ).convert("RGB")
    except Exception as exc:
        capture_errors.append(f"ImageGrab: {exc}")
        details = " | ".join(capture_errors)
        raise RuntimeError(f"game client capture failed ({details})") from exc
    rgb = np.array(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _find_game_hwnd() -> int:
    hwnd = find_game_hwnd()
    if hwnd is None:
        raise RuntimeError("maple game window not found")
    return int(hwnd)


def _game_client_rect_screen(hwnd: int) -> tuple[int, int, int, int]:
    left, top, width, height = get_game_client_rect_screen(int(hwnd))
    return int(left), int(top), int(width), int(height)


def _cv2() -> Any:
    import cv2

    return cv2


def _select_main_monitor(monitors: list[dict[str, int]]) -> dict[str, int]:
    physical_monitors = monitors[1:] if len(monitors) > 1 else monitors
    for monitor in physical_monitors:
        if monitor.get("left") == 0 and monitor.get("top") == 0:
            return monitor
    if physical_monitors:
        return physical_monitors[0]
    raise RuntimeError("no monitor available")


def _live_recorder(session: PuzzleSession, *, fps: float, trace_logger: TraceLogger) -> Any:
    recorder = SessionRecorder(session, fps=fps, trace_logger=trace_logger)
    return AsyncSessionRecorder(recorder)
