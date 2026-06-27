# 투명도형 퍼즐 라이브 화면을 무손실 세션 녹화로 저장한다.
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.puzzle.defaults import fixed_puzzle_rois, roi_to_payload
from core.puzzle.models import FramePacket, PuzzleSession
from core.puzzle.recorder import SessionRecorder
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
    ) -> None:
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.output_root = output_root
        self.frame_grabber = frame_grabber or grab_screen_bgr
        self.fps = fps
        self.sleeper = sleeper or time.sleep
        self.session: PuzzleSession | None = None
        self.trace: TraceLogger | None = None
        self.recording: RecordingController | None = None
        self.report_path: Path | None = None
        self.frame_count = 0
        self._finished = False

    @property
    def is_recording(self) -> bool:
        return self.recording is not None and self.recording.is_recording

    @property
    def is_solver_running(self) -> bool:
        return self.recording is not None and self.recording.is_solver_running

    def start(self, *, initial_frame: Any | None = None) -> PuzzleSession:
        if self.is_recording and self.session is not None:
            return self.session

        first_frame = initial_frame if initial_frame is not None else self.frame_grabber()
        frame_h, frame_w = first_frame.shape[:2]
        detect_roi, board_roi = fixed_puzzle_rois(frame_w=frame_w, frame_h=frame_h)
        session = SessionManager(output_root=self.output_root).start(
            source_kind="live_screen",
            detect_roi=detect_roi,
            board_roi=board_roi,
        )
        trace = TraceLogger(session)
        self.session = session
        self.trace = trace
        self.recording = RecordingController(
            recorder=SessionRecorder(session, fps=self.fps, trace_logger=trace),
            trace_logger=trace,
        )
        self.report_path = None
        self.frame_count = 0
        self._finished = False
        trace.write_event(
            "SESSION_START",
            None,
            {
                "source_kind": "live_screen",
                "fps": self.fps,
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
        self.recording.write(packet, overlay_frame=frame)
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


def _select_main_monitor(monitors: list[dict[str, int]]) -> dict[str, int]:
    physical_monitors = monitors[1:] if len(monitors) > 1 else monitors
    for monitor in physical_monitors:
        if monitor.get("left") == 0 and monitor.get("top") == 0:
            return monitor
    if physical_monitors:
        return physical_monitors[0]
    raise RuntimeError("no monitor available")
