# 퍼즐 콘솔 F1/F2/F3 단축키 연결을 검증한다.
from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.test_puzzle_console_smoke import _install_fake_qt


class _ModulePatch:
    def __init__(self) -> None:
        self._missing = object()
        self._original: list[tuple[dict, object, object]] = []

    def setitem(self, mapping: dict, key: object, value: object) -> None:
        self._original.append((mapping, key, mapping.get(key, self._missing)))
        mapping[key] = value

    def restore(self) -> None:
        for mapping, key, old_value in reversed(self._original):
            if old_value is self._missing:
                mapping.pop(key, None)
            else:
                mapping[key] = old_value


class PuzzleConsoleF1HotkeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.patch = _ModulePatch()
        _install_fake_qt(self.patch)
        sys.modules["PyQt6.QtCore"].Qt.Key.Key_F1 = "f1"
        sys.modules["PyQt6.QtCore"].Qt.Key.Key_F2 = "f2"
        self.addCleanup(self.patch.restore)

    def test_f1_keypress_arms_solver_without_recording_session(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        calls: list[str] = []

        class _Event:
            def key(self):
                return module.Qt.Key.Key_F1

        def start_watch():
            calls.append("start")
            return None

        window = module.PuzzleConsoleWindow(watch_start_handler=start_watch)

        window.keyPressEvent(_Event())

        self.assertEqual(calls, ["start"])
        self.assertEqual(window.state_label.text(), "SOLVER_ON")
        self.assertIsNone(window.last_session_dir)
        self.assertIn("#1f8f4d", window.solver_start_badge.styleSheet())
        self.assertIn("solver on", window.event_log.toPlainText())

    def test_f2_keypress_stops_solver_without_closing_recording(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        calls: list[str] = []

        class _Event:
            def key(self):
                return module.Qt.Key.Key_F2

        window = module.PuzzleConsoleWindow(solver_stop_handler=lambda: calls.append("solver_stop") or True)

        window.keyPressEvent(_Event())

        self.assertEqual(calls, ["solver_stop"])
        self.assertEqual(window.state_label.text(), "SOLVER_STOPPED")
        self.assertIn("#c98217", window.solver_stop_badge.styleSheet())
        self.assertIn("solver stop", window.event_log.toPlainText())

    def test_f3_keypress_marks_recording_stop_badge(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        calls: list[str] = []

        class _Event:
            def key(self):
                return module.Qt.Key.Key_F3

        window = module.PuzzleConsoleWindow(recording_stop_handler=lambda: calls.append("recording_stop") or True)

        window.keyPressEvent(_Event())

        self.assertEqual(calls, ["recording_stop"])
        self.assertIn("#b83a3a", window.recording_stop_badge.styleSheet())

    def test_live_status_poll_marks_recording_after_detection(self) -> None:
        module = importlib.import_module("ui.puzzle_console")

        with TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "session"
            preview_path = session_dir / "latest_preview.png"
            session_dir.mkdir()
            preview_path.write_bytes(b"fake image")
            status = types.SimpleNamespace(
                status="recording",
                session_dir=session_dir,
                preview_path=preview_path,
            )

            window = module.PuzzleConsoleWindow(
                watch_start_handler=lambda: None,
                live_status_handler=lambda: status,
            )

            window.start_watch_input()
            window._poll_live_status()

            self.assertEqual(window.state_label.text(), "RECORDING")
            self.assertEqual(window.last_session_dir, session_dir)
            self.assertEqual(window.cctv_frame_label.pixmap().path, str(preview_path))
            self.assertIn("recording start", window.event_log.toPlainText())

    def test_live_status_poll_updates_armed_preview_before_recording(self) -> None:
        module = importlib.import_module("ui.puzzle_console")

        with TemporaryDirectory() as tmp:
            preview_path = Path(tmp) / "watch_preview.png"
            preview_path.write_bytes(b"fake image")
            status = types.SimpleNamespace(
                status="armed",
                session_dir=None,
                preview_path=preview_path,
            )

            window = module.PuzzleConsoleWindow(
                watch_start_handler=lambda: None,
                live_status_handler=lambda: status,
            )

            window.start_watch_input()
            window._poll_live_status()

            self.assertEqual(window.state_label.text(), "SOLVER_ON")
            self.assertIsNone(window.last_session_dir)
            self.assertEqual(window.cctv_frame_label.pixmap().path, str(preview_path))

    def test_global_f1_f2_and_f3_hotkeys_are_registered(self) -> None:
        fake_hotkey_module = types.ModuleType("core.hotkey_manager")
        registered: list[tuple[str, str, object]] = []

        class _FakeHotkeyManager:
            def __init__(self, _window) -> None:
                self.registered = registered

            def register(self, name: str, key: str, callback) -> str:
                self.registered.append((name, key, callback))
                return ""

        fake_hotkey_module.HotkeyManager = _FakeHotkeyManager
        sys.modules["core.hotkey_manager"] = fake_hotkey_module

        puzzle = importlib.import_module("puzzle")

        class _Window:
            def __init__(self) -> None:
                self.started = 0
                self.solver_stopped = 0
                self.stopped = 0
                self.logs: list[str] = []

            def start_watch_input(self) -> bool:
                self.started += 1
                return True

            def stop_solver_input(self) -> bool:
                self.solver_stopped += 1
                return True

            def stop_recording_input(self) -> bool:
                self.stopped += 1
                return True

            def append_log(self, message: str) -> None:
                self.logs.append(message)

        window = _Window()

        puzzle._attach_puzzle_hotkeys(window)

        keys = {(name, key) for name, key, _callback in registered}
        self.assertIn(("puzzle_start_recording", "f1"), keys)
        self.assertIn(("puzzle_stop_solver", "f2"), keys)
        self.assertIn(("puzzle_stop_recording", "f3"), keys)

        callbacks = {name: callback for name, _key, callback in registered}
        callbacks["puzzle_start_recording"]()
        callbacks["puzzle_stop_solver"]()
        callbacks["puzzle_stop_recording"]()

        self.assertEqual(window.started, 1)
        self.assertEqual(window.solver_stopped, 1)
        self.assertEqual(window.stopped, 1)


if __name__ == "__main__":
    unittest.main()
