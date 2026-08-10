# 투명도형 퍼즐 녹화 생명주기를 솔버 상태와 분리해 관리한다.
from __future__ import annotations

from typing import Any


class RecordingController:
    def __init__(self, *, recorder: Any, trace_logger: Any | None = None) -> None:
        self.recorder = recorder
        self.trace_logger = trace_logger
        self.is_solver_running = True
        self.is_recording = True

    def write(self, packet: Any, overlay_frame: Any | None = None) -> bool:
        if not self.is_recording:
            return False
        self.recorder.write(packet, overlay_frame=overlay_frame)
        return True

    def stop_solver(self, *, reason: str = "manual") -> bool:
        if not self.is_solver_running:
            return False
        self.is_solver_running = False
        self._write_event("SOLVER_STOPPED", reason)
        return True

    def stop_recording(self, *, reason: str = "manual") -> bool:
        if not self.is_recording:
            return False
        self.is_recording = False
        self._write_event("RECORDING_STOPPED", reason)
        self.recorder.close()
        return True

    def _write_event(self, event_type: str, reason: str) -> None:
        if self.trace_logger is None:
            return
        self.trace_logger.write_event(event_type, None, {"reason": reason})
