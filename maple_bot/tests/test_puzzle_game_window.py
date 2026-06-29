# 투명도형 퍼즐용 게임창 선택기가 도구 UI 대신 실제 게임창을 고르는지 검증한다.
from __future__ import annotations

import unittest

from core.puzzle.game_window import find_game_hwnd, get_game_client_rect_screen, list_game_window_candidates


class _FakeWin32Gui:
    def __init__(self, windows):
        self.windows = dict(windows)

    def EnumWindows(self, callback, extra):
        for hwnd in self.windows:
            callback(hwnd, extra)

    def IsWindowVisible(self, hwnd):
        return self.windows[hwnd]["visible"]

    def GetClassName(self, hwnd):
        return self.windows[hwnd]["class_name"]

    def GetWindowText(self, hwnd):
        return self.windows[hwnd]["title"]

    def GetClientRect(self, hwnd):
        width, height = self.windows[hwnd]["client_size"]
        return (0, 0, width, height)

    def ClientToScreen(self, hwnd, _point):
        return self.windows[hwnd]["origin"]


class GameWindowFinderTest(unittest.TestCase):
    def test_prefers_large_game_window_over_solver_tool_window(self) -> None:
        fake = _FakeWin32Gui(
            {
                10: {
                    "visible": True,
                    "class_name": "Qt5152QWindowIcon",
                    "title": "Planet Solver 거짓말탐지기",
                    "client_size": (430, 350),
                    "origin": (900, 50),
                },
                20: {
                    "visible": True,
                    "class_name": "MapleStoryClass",
                    "title": "MapleStory Worlds",
                    "client_size": (1920, 1080),
                    "origin": (0, 0),
                },
            }
        )

        self.assertEqual(find_game_hwnd(win32gui_module=fake), 20)

    def test_rejects_small_keyword_window(self) -> None:
        fake = _FakeWin32Gui(
            {
                10: {
                    "visible": True,
                    "class_name": "Qt5152QWindowIcon",
                    "title": "planet noauth",
                    "client_size": (500, 400),
                    "origin": (100, 100),
                },
            }
        )

        self.assertIsNone(find_game_hwnd(win32gui_module=fake))

    def test_returns_client_rect_screen_for_selected_window(self) -> None:
        fake = _FakeWin32Gui(
            {
                20: {
                    "visible": True,
                    "class_name": "UnityWndClass",
                    "title": "MapleStory Worlds",
                    "client_size": (1600, 900),
                    "origin": (11, 22),
                },
            }
        )

        self.assertEqual(find_game_hwnd(win32gui_module=fake), 20)
        self.assertEqual(get_game_client_rect_screen(20, win32gui_module=fake), (11, 22, 1600, 900))

    def test_sorts_candidates_by_game_likeness(self) -> None:
        fake = _FakeWin32Gui(
            {
                30: {
                    "visible": True,
                    "class_name": "NEXON Plug-in Window",
                    "title": "MapleStory helper",
                    "client_size": (1000, 700),
                    "origin": (0, 0),
                },
                20: {
                    "visible": True,
                    "class_name": "MapleStoryClass",
                    "title": "MapleStory Worlds",
                    "client_size": (1920, 1080),
                    "origin": (0, 0),
                },
            }
        )

        candidates = list_game_window_candidates(win32gui_module=fake)

        self.assertEqual([candidate.hwnd for candidate in candidates], [20, 30])


if __name__ == "__main__":
    unittest.main()
