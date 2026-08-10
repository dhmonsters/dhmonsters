# Puzzle2 라이브 검증 화면의 핵심 제어 상태를 확인한다.
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.puzzle2_console import Puzzle2Window


class _FakeRuntime:
    def __init__(self) -> None:
        self.enabled = False
        self.started = 0
        self.stopped = 0

    def set_mouse_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def start(self) -> bool:
        self.started += 1
        return True

    def request_stop(self) -> None:
        self.stopped += 1

    def close_preview(self) -> None:
        pass

    def snapshot(self):
        return {
            "running": False,
            "mouse_enabled": self.enabled,
            "status": {"tracking": "IDLE", "shape": "-", "quest": "-"},
            "row": None,
            "result": {},
            "error": "",
            "session_dir": "",
        }


def test_window_starts_with_mouse_off_and_has_explicit_buttons() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = _FakeRuntime()
    window = Puzzle2Window(runtime=runtime, preview_enabled=False)

    assert window.mouse_off_button.isEnabled() is False
    assert window.mouse_on_button.isEnabled() is True
    assert window.mouse_state_label.text() == "MOUSE OFF"

    window.mouse_on_button.click()
    assert runtime.enabled is True
    assert window.mouse_state_label.text() == "MOUSE ON"

    window.mouse_off_button.click()
    assert runtime.enabled is False
    assert window.mouse_state_label.text() == "MOUSE OFF"
    window.close()
    app.processEvents()


def test_window_start_and_stop_call_runtime() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = _FakeRuntime()
    window = Puzzle2Window(runtime=runtime, preview_enabled=False)

    window.solver_start_button.click()
    window.solver_stop_button.click()

    assert runtime.started == 1
    assert runtime.stopped == 1
    window.close()
    app.processEvents()
