# 메인 프로그램의 게임창 기능이 퍼즐 패키지 없이 동작하는지 검증한다.
from __future__ import annotations

import importlib.abc
import sys
from types import ModuleType, SimpleNamespace


class PuzzleImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "core.puzzle" or fullname.startswith("core.puzzle."):
            raise ImportError(f"blocked program dependency: {fullname}")
        return None


def test_program_window_features_work_without_puzzle_package(monkeypatch):
    for name in list(sys.modules):
        if name == "core.puzzle" or name.startswith("core.puzzle."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [PuzzleImportBlocker(), *sys.meta_path])

    game_window = ModuleType("core.game_window")
    game_window.find_game_hwnd = lambda: 123
    game_window.find_window_hwnd_by_title = lambda _title: 123
    game_window.get_game_client_rect_screen = lambda _hwnd: (100, 200, 800, 600)
    monkeypatch.setitem(sys.modules, "core.game_window", game_window)

    win32con = ModuleType("win32con")
    win32con.SW_RESTORE = 9
    monkeypatch.setitem(sys.modules, "win32con", win32con)
    win32gui = ModuleType("win32gui")
    win32gui.ShowWindow = lambda _hwnd, _mode: None
    win32gui.SetForegroundWindow = lambda _hwnd: None
    win32gui.GetWindowText = lambda _hwnd: "MapleStory Worlds"
    monkeypatch.setitem(sys.modules, "win32gui", win32gui)

    from run_integrated import _focus_game_window_before_runtime
    from core.config_manager import _query_window_origin
    from core.config_adapter import _resolve_window_ratio_region
    from core.runtime import BotRuntime

    assert _focus_game_window_before_runtime(SimpleNamespace(game_window_title="Maple")) == "MapleStory Worlds"
    assert _query_window_origin("Maple") == (100, 200, 800, 600)
    assert _resolve_window_ratio_region(
        {"x_ratio": 0.1, "y_ratio": 0.2, "w_ratio": 0.5, "h_ratio": 0.5},
        "Maple",
    ) == {"left": 180, "top": 320, "width": 400, "height": 300}

    runtime = BotRuntime.__new__(BotRuntime)
    runtime._cfg = SimpleNamespace(game_window_title="Maple", coord_anchor=None)
    assert runtime._resolve_region(
        {"x_ratio": 0.1, "y_ratio": 0.2, "w_ratio": 0.5, "h_ratio": 0.5}
    ) == {"left": 180, "top": 320, "width": 400, "height": 300}

