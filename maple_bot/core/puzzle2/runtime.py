# 외부 SOT 코어의 입력과 상태를 안전하게 중계하는 라이브 런타임이다.
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from .vendor import load_default_backend


MoveFunction = Callable[[float, float], bool]
BackendLoader = Callable[[], ModuleType]


class MouseGate:
    def __init__(self, move_function: MoveFunction) -> None:
        self._move_function = move_function
        self._enabled = False
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)

    def move(self, target_x: float, target_y: float) -> bool:
        if not self.enabled:
            return True
        return bool(self._move_function(float(target_x), float(target_y)))


class SotLiveRuntime:
    QUEST_ROI = (396, 196, 488, 328)

    def __init__(
        self,
        *,
        backend_loader: BackendLoader = load_default_backend,
        output_root: str | Path | None = None,
    ) -> None:
        self._backend_loader = backend_loader
        self._backend: ModuleType | None = None
        self._mouse_gate: MouseGate | None = None
        self._mouse_enabled = False
        self._stop_requested = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._preview_capture: Any = None
        self._preview_hwnd: int | None = None
        self.output_root = Path(output_root) if output_root else (
            Path(__file__).resolve().parents[2]
            / "03_output"
            / "2026-08-10_puzzle2_live_sessions"
        )
        self.session_dir: Path | None = None
        self.latest_row: dict[str, Any] | None = None
        self.status: dict[str, str] = {
            "environment": "대기",
            "game": "-",
            "resolution": "-",
            "quest": "-",
            "shape": "-",
            "tracking": "IDLE",
            "mouse": "OFF",
            "result": "-",
        }
        self.result: dict[str, Any] = {}
        self.error = ""

    @property
    def running(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    @property
    def mouse_enabled(self) -> bool:
        with self._lock:
            return self._mouse_enabled

    def set_mouse_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._mouse_enabled = bool(enabled)
            self.status["mouse"] = "ON" if enabled else "OFF"
        if self._mouse_gate is not None:
            self._mouse_gate.set_enabled(enabled)
        self._write_event("MOUSE_TOGGLE", {"enabled": bool(enabled)})

    def request_stop(self) -> None:
        self._stop_requested.set()
        self._write_event("STOP_REQUESTED", {})

    def start(self) -> bool:
        if self.running:
            return False
        self._stop_requested.clear()
        self.error = ""
        self.result = {}
        self.latest_row = None
        self._start_session()
        self._thread = threading.Thread(
            target=self.run_session_sync,
            daemon=True,
            name="Puzzle2SotLive",
        )
        self._thread.start()
        return True

    def run_session_sync(self) -> None:
        backend = self._backend_loader()
        self._backend = backend
        original_move = backend.move_toward_screen
        original_f12 = backend.f12_pressed
        original_run = backend.run
        original_validate = getattr(backend, "validate_runtime", None)
        gate = MouseGate(original_move)
        gate.set_enabled(self.mouse_enabled)
        self._mouse_gate = gate

        def stop_or_f12() -> bool:
            return self._stop_requested.is_set() or bool(original_f12())

        def run_with_trace(*args: Any, **kwargs: Any):
            original_callback = kwargs.get("frame_callback")

            def combined_callback(row: dict[str, Any]) -> None:
                self._accept_row(row)
                if original_callback is not None:
                    original_callback(row)

            kwargs["frame_callback"] = combined_callback
            return original_run(*args, **kwargs)

        backend.move_toward_screen = gate.move
        backend.f12_pressed = stop_or_f12
        backend.run = run_with_trace
        if original_validate is not None:
            backend.validate_runtime = _validate_installed_runtime
        self._update_status(environment="코어 준비", tracking="WAIT_QUEST")
        self._write_event("SESSION_START", {"mouse_enabled": self.mouse_enabled})

        try:
            ok, consumed, result = backend.run_one_shot(
                status_cb=self._update_status,
                consumed_cb=lambda: self._write_event("PUZZLE_CONSUMED", {}),
            )
            self.result = dict(result or {})
            self.result.setdefault("ok", bool(ok))
            self.result.setdefault("consumed", bool(consumed))
            self._write_event("SESSION_RESULT", self.result)
        except Exception as exc:
            self.error = f"{exc.__class__.__name__}: {exc}"
            self.result = {"ok": False, "error": self.error}
            self._update_status(tracking="ERROR", result=self.error)
            self._write_event("SESSION_ERROR", self.result)
        finally:
            backend.move_toward_screen = original_move
            backend.f12_pressed = original_f12
            backend.run = original_run
            if original_validate is not None:
                backend.validate_runtime = original_validate
            self._mouse_gate = None
            self._write_summary()

    def capture_client(self):
        backend = self._backend or self._backend_loader()
        self._backend = backend
        if self._preview_capture is None:
            window = backend.find_game_window()
            if window is None:
                raise RuntimeError("게임창을 찾지 못했습니다")
            self._preview_hwnd = int(window.hwnd)
            self._preview_capture = backend.ScreenCapture(window.hwnd)
        frame, rect = self._preview_capture.grab_client()
        return frame, rect

    def close_preview(self) -> None:
        if self._preview_capture is not None:
            self._preview_capture.close()
        self._preview_capture = None
        self._preview_hwnd = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "mouse_enabled": self._mouse_enabled,
                "status": dict(self.status),
                "row": dict(self.latest_row) if self.latest_row else None,
                "result": dict(self.result),
                "error": self.error,
                "session_dir": str(self.session_dir) if self.session_dir else "",
            }

    def _accept_row(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.latest_row = dict(row)
        compact = {
            key: row.get(key)
            for key in (
                "frame", "center_x", "center_y", "state", "confidence",
                "output_source", "hypothesis_count", "identity_lock_active",
                "owner_guard_action", "owner_guard_reason",
                "overlap_hold", "overlap_events", "h1_x", "h1_y",
                "h1_score", "h2_x", "h2_y", "h2_score",
                "h3_x", "h3_y", "h3_score",
            )
            if key in row
        }
        self._write_event("TRACK", compact)

    def _update_status(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if key == "mouse":
                    continue
                self.status[str(key)] = str(value)
        self._write_event("STATUS", {str(k): str(v) for k, v in kwargs.items() if k != "mouse"})

    def _start_session(self) -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_root / stamp
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _write_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.session_dir is None:
            return
        record = {"time": time.time(), "type": event_type, "payload": payload}
        path = self.session_dir / "events.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _write_summary(self) -> None:
        if self.session_dir is None:
            return
        payload = self.snapshot()
        (self.session_dir / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


def _validate_installed_runtime() -> dict[str, Any]:
    import cv2
    import numpy
    import torch

    info = {
        "python": __import__("sys").version.split()[0],
        "numpy": numpy.__version__,
        "opencv": cv2.__version__,
        "torch": torch.__version__,
        "cuda": bool(torch.cuda.is_available()),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
    }
    if not info["cuda"]:
        raise RuntimeError("CUDA_GPU_NOT_AVAILABLE")
    return info
