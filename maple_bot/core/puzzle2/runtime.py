# 외부 SOT 코어의 입력과 상태를 안전하게 중계하는 라이브 런타임이다.
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from .vendor import load_default_backend
from .mouse import GameCursorObserver, InterceptionMouseController


MoveFunction = Callable[[float, float], bool]
BackendLoader = Callable[[], ModuleType]
MouseControllerFactory = Callable[[ModuleType], InterceptionMouseController]


def resolve_session_root(
    *,
    frozen: bool | None = None,
    executable: str | Path | None = None,
) -> Path:
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if packaged:
        executable_path = Path(executable or sys.executable).resolve()
        return executable_path.parent / "sessions"
    return (
        Path(__file__).resolve().parents[2]
        / "03_output"
        / "2026-08-10_puzzle2_live_sessions"
    )


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
        mouse_controller_factory: MouseControllerFactory | None = None,
    ) -> None:
        self._backend_loader = backend_loader
        self._backend: ModuleType | None = None
        self._mouse_gate: MouseGate | None = None
        self._mouse_controller: InterceptionMouseController | None = None
        self._mouse_controller_factory = (
            mouse_controller_factory or self._build_mouse_controller
        )
        self._mouse_enabled = False
        self._stop_requested = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._preview_capture: Any = None
        self._preview_hwnd: int | None = None
        self.output_root = Path(output_root) if output_root else resolve_session_root()
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
        self.completed_puzzles = 0
        self.cycle_count = 0

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
        self.completed_puzzles = 0
        self.cycle_count = 0
        self._start_session(clear_existing=True)
        self._thread = threading.Thread(
            target=lambda: self.run_session_sync(max_cycles=None),
            daemon=True,
            name="Puzzle2SotLive",
        )
        self._thread.start()
        return True

    def run_session_sync(
        self,
        *,
        max_cycles: int | None = 1,
        retry_delay: float = 0.5,
        rearm_delay: float = 1.5,
    ) -> None:
        backend = self._backend_loader()
        self._backend = backend
        original_move = backend.move_toward_screen
        original_f12 = backend.f12_pressed
        original_run = backend.run
        original_activate = getattr(backend, "activate", None)
        original_validate = getattr(backend, "validate_runtime", None)
        mouse_controller = self._mouse_controller_factory(backend)
        self._mouse_controller = mouse_controller

        def kernel_move(target_x: float, target_y: float) -> bool:
            tracking = str(self.status.get("tracking", ""))
            moved = mouse_controller.move(
                target_x,
                target_y,
                learn_offset=tracking.startswith("PREPOSITION"),
            )
            offset_x, offset_y = mouse_controller.offset
            self._update_status(
                input_backend="Interception",
                cursor_offset=f"{offset_x:.1f},{offset_y:.1f}",
            )
            return moved

        gate = MouseGate(kernel_move)
        gate.set_enabled(self.mouse_enabled)
        self._mouse_gate = gate

        def stop_or_f12() -> bool:
            if self._stop_requested.is_set():
                return True
            if bool(original_f12()):
                self._stop_requested.set()
                return True
            return False

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
        if original_activate is not None and hasattr(backend, "foreground_is"):
            backend.activate = lambda hwnd: bool(backend.foreground_is(hwnd))
        if original_validate is not None:
            backend.validate_runtime = _validate_installed_runtime
        self._update_status(environment="코어 준비", tracking="WAIT_QUEST")
        self._write_event("SESSION_START", {"mouse_enabled": self.mouse_enabled})

        try:
            cycles_started = 0
            while max_cycles is None or cycles_started < max_cycles:
                if stop_or_f12():
                    break
                if not self._game_is_ready_without_activation(backend):
                    self._update_status(
                        game="게임창 대기",
                        tracking="WAIT_FOREGROUND",
                        result="-",
                    )
                    if self._wait_for_stop(max(0.05, retry_delay), stop_or_f12):
                        break
                    continue

                cycles_started += 1
                self.cycle_count += 1
                self._update_status(tracking="WAIT_QUEST", result="-")
                ok, consumed, result = backend.run_one_shot(
                    status_cb=self._update_status,
                    consumed_cb=lambda: self._write_event("PUZZLE_CONSUMED", {}),
                )
                cycle_result = dict(result or {})
                cycle_result.setdefault("ok", bool(ok))
                cycle_result.setdefault("consumed", bool(consumed))
                cycle_result["cycle"] = self.cycle_count
                self.result = cycle_result
                self._write_event("CYCLE_RESULT", cycle_result)

                error = str(cycle_result.get("error", ""))
                if self._stop_requested.is_set() or error == "F12_ABORT":
                    self._stop_requested.set()
                    break
                if ok and str(cycle_result.get("result", "")) == "SUCCESS":
                    self.completed_puzzles += 1
                    self._update_status(
                        tracking="WAIT_REARM",
                        result=f"SUCCESS #{self.completed_puzzles}",
                    )
                    self._write_event(
                        "PUZZLE_SUCCESS",
                        {"completed_puzzles": self.completed_puzzles},
                    )
                    if self._wait_for_stop(max(0.0, rearm_delay), stop_or_f12):
                        break
                else:
                    self._update_status(
                        tracking="WAIT_RETRY",
                        result=f"재시도 / {error or 'TRACKING_ENDED'}",
                    )
                    if self._wait_for_stop(max(0.0, retry_delay), stop_or_f12):
                        break

            if self._stop_requested.is_set():
                self._update_status(tracking="STOPPED", mouse="OFF", result="사용자 종료")
        except Exception as exc:
            self.error = f"{exc.__class__.__name__}: {exc}"
            self.result = {"ok": False, "error": self.error}
            self._update_status(tracking="ERROR", result=self.error)
            self._write_event("SESSION_ERROR", self.result)
        finally:
            backend.move_toward_screen = original_move
            backend.f12_pressed = original_f12
            backend.run = original_run
            if original_activate is not None:
                backend.activate = original_activate
            if original_validate is not None:
                backend.validate_runtime = original_validate
            self._mouse_gate = None
            mouse_controller.close()
            self._mouse_controller = None
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
                "completed_puzzles": self.completed_puzzles,
                "cycle_count": self.cycle_count,
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
        tracking = str(kwargs.get("tracking", ""))
        previous_tracking = str(self.status.get("tracking", ""))
        if (
            tracking.startswith("PREPOSITION")
            and not previous_tracking.startswith("PREPOSITION")
            and self._mouse_controller is not None
        ):
            self._mouse_controller.begin_puzzle()
        with self._lock:
            for key, value in kwargs.items():
                if key == "mouse":
                    continue
                self.status[str(key)] = str(value)
        self._write_event("STATUS", {str(k): str(v) for k, v in kwargs.items() if k != "mouse"})

    def _start_session(self, *, clear_existing: bool = False) -> None:
        root = self.output_root.resolve()
        if clear_existing:
            _clear_session_root(root)
        root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = root / stamp
        suffix = 1
        while self.session_dir.exists():
            self.session_dir = root / f"{stamp}_{suffix:02d}"
            suffix += 1
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _game_is_ready_without_activation(self, backend: ModuleType) -> bool:
        find_window = getattr(backend, "find_game_window", None)
        foreground_is = getattr(backend, "foreground_is", None)
        if not callable(find_window) or not callable(foreground_is):
            return True
        try:
            window = find_window()
            return bool(window is not None and foreground_is(int(window.hwnd)))
        except Exception:
            return False

    def _wait_for_stop(
        self,
        seconds: float,
        stop_check: Callable[[], bool],
    ) -> bool:
        deadline = time.monotonic() + max(0.0, float(seconds))
        while True:
            if stop_check():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self._stop_requested.wait(min(0.05, remaining))

    def _build_mouse_controller(self, backend: ModuleType) -> InterceptionMouseController:
        observer = GameCursorObserver(backend, self.QUEST_ROI)
        return InterceptionMouseController(cursor_observer=observer)

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


def _clear_session_root(root: Path) -> None:
    root_name = root.name.lower()
    if (
        root == Path(root.anchor)
        or len(root.parts) < 3
        or (root_name != "sessions" and "puzzle2" not in root_name)
    ):
        raise ValueError(f"unsafe session root: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
