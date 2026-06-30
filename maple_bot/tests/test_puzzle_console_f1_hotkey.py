# 퍼즐 콘솔 F1/F2/F3 단축키 연결을 검증한다.
from __future__ import annotations

import importlib
import os
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

    def test_live_status_timer_polls_like_cctv(self) -> None:
        module = importlib.import_module("ui.puzzle_console")

        window = module.PuzzleConsoleWindow(live_status_handler=lambda: None)

        self.assertIsNotNone(window._live_status_timer)
        self.assertLessEqual(window._live_status_timer.interval, 50)

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
            self.assertTrue(window.cctv_frame_label.pixmap().path.startswith("bytes:"))
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
            self.assertTrue(window.cctv_frame_label.pixmap().path.startswith("bytes:"))

    def test_live_status_poll_updates_armed_preview_from_memory_frame(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        status = types.SimpleNamespace(
            status="armed",
            session_dir=None,
            preview_path=None,
            preview_frame=b"memory preview frame",
        )

        window = module.PuzzleConsoleWindow(
            watch_start_handler=lambda: None,
            live_status_handler=lambda: status,
        )

        window.start_watch_input()
        window._poll_live_status()

        self.assertEqual(window.state_label.text(), "SOLVER_ON")
        self.assertIsNone(window.last_session_dir)
        self.assertTrue(window.cctv_frame_label.pixmap().path.startswith("bytes:"))

    def test_live_status_poll_reloads_same_armed_preview_path(self) -> None:
        module = importlib.import_module("ui.puzzle_console")

        with TemporaryDirectory() as tmp:
            preview_path = Path(tmp) / "watch_preview.png"
            preview_path.write_bytes(b"first frame")
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
            first_pixmap_path = window.cctv_frame_label.pixmap().path
            preview_path.write_bytes(b"second frame")
            os.utime(preview_path, (2_000_000_000, 2_000_000_000))
            window._poll_live_status()

            self.assertEqual(window.state_label.text(), "SOLVER_ON")
            self.assertIsNone(window.last_session_dir)
            self.assertNotEqual(window.cctv_frame_label.pixmap().path, first_pixmap_path)

    def test_apply_trace_event_appends_clear_solver_status_logs(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        window = module.PuzzleConsoleWindow()

        window.apply_trace_event(
            {
                "type": "PUZZLE_ACTIVATED",
                "frame_index": None,
                "payload": {"reason": "popup_board", "score": 0.92},
            }
        )
        window.apply_trace_event(
            {
                "type": "CANDIDATES",
                "frame_index": 0,
                "payload": {
                    "count": 2,
                    "candidates": [
                        {"candidate_id": "c0_a", "center": [30.0, 40.0], "score": 0.81},
                    ],
                },
            }
        )
        window.apply_trace_event(
            {
                "type": "TEMPORAL_SELECTOR",
                "frame_index": 0,
                "payload": {
                    "point": [60.0, 70.0],
                    "family": "good_family",
                    "reason": "selected_family",
                },
            }
        )
        window.apply_trace_event(
            {
                "type": "MOUSE_MOVE",
                "frame_index": 0,
                "payload": {
                    "moved": True,
                    "client_point": [70, 90],
                    "reason": "bg_click",
                },
            }
        )

        text = window.event_log.toPlainText()
        self.assertIn("PUZZLE DETECTED reason=popup_board score=0.92", text)
        self.assertIn("f0 YOLO candidates 2 first=c0_a center=30,40 score=0.81", text)
        self.assertIn("f0 TEMP target 60,70 family=good_family reason=selected_family", text)
        self.assertIn("f0 MOUSE moved client=70,90 reason=bg_click", text)

    def test_puzzle_activation_plays_checked_alarm_once_per_session(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        alarms: list[str] = []
        window = module.PuzzleConsoleWindow(alarm_handler=lambda: alarms.append("beep"))

        event = {
            "type": "PUZZLE_ACTIVATED",
            "session_id": "20260630_010000_001",
            "frame_index": None,
            "payload": {"reason": "popup_board", "score": 0.91},
        }
        window.apply_trace_event(event)
        window.apply_trace_event(event)
        window.apply_trace_event({**event, "session_id": "20260630_010001_001"})

        self.assertEqual(alarms, ["beep", "beep"])
        text = window.event_log.toPlainText()
        self.assertIn("ALARM sound played: 20260630_010000_001", text)
        self.assertIn("ALARM duplicate skipped: 20260630_010000_001", text)

    def test_puzzle_activation_alarm_respects_checkbox(self) -> None:
        module = importlib.import_module("ui.puzzle_console")
        alarms: list[str] = []
        window = module.PuzzleConsoleWindow(alarm_handler=lambda: alarms.append("beep"))
        window.puzzle_detect_alert_checkbox.setChecked(False)

        window.apply_trace_event(
            {
                "type": "PUZZLE_ACTIVATED",
                "session_id": "20260630_010000_001",
                "frame_index": None,
                "payload": {"reason": "popup_board", "score": 0.91},
            }
        )

        self.assertEqual(alarms, [])
        self.assertIn("ALARM disabled", window.event_log.toPlainText())

    def test_live_status_poll_tails_trace_events_into_log(self) -> None:
        module = importlib.import_module("ui.puzzle_console")

        with TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "session"
            session_dir.mkdir()
            trace_path = session_dir / "trace.jsonl"
            trace_path.write_text(
                '{"type":"CANDIDATES","frame_index":0,"payload":{"count":1,'
                '"candidates":[{"candidate_id":"c0_a","center":[11,22],"score":0.7}]}}\n',
                encoding="utf-8",
            )
            status = types.SimpleNamespace(
                status="recording",
                session_dir=session_dir,
                preview_path=None,
            )
            window = module.PuzzleConsoleWindow(live_status_handler=lambda: status)

            window._poll_live_status()
            trace_path.write_text(
                trace_path.read_text(encoding="utf-8")
                + '{"type":"MOUSE_MOVE","frame_index":0,"payload":{"moved":true,'
                '"client_point":[33,44],"reason":"bg_click"}}\n',
                encoding="utf-8",
            )
            window._poll_live_status()

            text = window.event_log.toPlainText()
            self.assertIn("f0 YOLO candidates 1 first=c0_a center=11,22 score=0.70", text)
            self.assertIn("f0 MOUSE moved client=33,44 reason=bg_click", text)

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
