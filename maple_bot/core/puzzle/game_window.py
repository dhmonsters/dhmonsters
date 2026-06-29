# 투명도형 퍼즐 라이브 캡처와 클릭에 사용할 실제 게임창을 고른다.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TARGET_W = 1920
TARGET_H = 1080
MIN_CLIENT_W = 800
MIN_CLIENT_H = 500
GAME_CLASSES = ("MapleStoryClass", "UnityWndClass", "NEXON Plug-in Window")
GAME_KEYWORDS = ("maplestory", "메이플스토리", "maple worlds", "mapleworlds", "worlds")
EXCLUDED_TITLE_KEYWORDS = (
    "거짓말탐지기",
    "감지 영역",
    "투명도형 퍼즐",
    "transparent puzzle",
    "puzzle console",
    "solver",
    "noauth",
    "codex",
)


@dataclass(frozen=True)
class GameWindowCandidate:
    hwnd: int
    title: str
    class_name: str
    client_w: int
    client_h: int
    score: float


def find_game_hwnd(*, win32gui_module: Any | None = None) -> int | None:
    candidates = list_game_window_candidates(win32gui_module=win32gui_module)
    return candidates[0].hwnd if candidates else None


def list_game_window_candidates(*, win32gui_module: Any | None = None) -> list[GameWindowCandidate]:
    win32gui = win32gui_module or _win32gui()
    candidates: list[GameWindowCandidate] = []

    def _cb(hwnd: int, _extra: object) -> None:
        candidate = _candidate_from_hwnd(win32gui, int(hwnd))
        if candidate is not None:
            candidates.append(candidate)

    win32gui.EnumWindows(_cb, None)
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def get_game_client_rect_screen(hwnd: int, *, win32gui_module: Any | None = None) -> tuple[int, int, int, int]:
    win32gui = win32gui_module or _win32gui()
    cl, ct, cr, cb = win32gui.GetClientRect(int(hwnd))
    sx, sy = win32gui.ClientToScreen(int(hwnd), (cl, ct))
    return int(sx), int(sy), int(cr - cl), int(cb - ct)


def _candidate_from_hwnd(win32gui: Any, hwnd: int) -> GameWindowCandidate | None:
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return None
        class_name = str(win32gui.GetClassName(hwnd))
        title = str(win32gui.GetWindowText(hwnd))
        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
    except Exception:
        return None

    client_w = int(cr - cl)
    client_h = int(cb - ct)
    score = _score_window(title=title, class_name=class_name, client_w=client_w, client_h=client_h)
    if score is None:
        return None
    return GameWindowCandidate(
        hwnd=hwnd,
        title=title,
        class_name=class_name,
        client_w=client_w,
        client_h=client_h,
        score=score,
    )


def _score_window(*, title: str, class_name: str, client_w: int, client_h: int) -> float | None:
    title_l = title.lower()
    class_l = class_name.lower()
    if any(keyword in title_l for keyword in EXCLUDED_TITLE_KEYWORDS):
        return None
    if client_w < MIN_CLIENT_W or client_h < MIN_CLIENT_H:
        return None

    class_match = any(game_class.lower() in class_l for game_class in GAME_CLASSES)
    keyword_match = any(keyword in title_l for keyword in GAME_KEYWORDS)
    if not class_match and not keyword_match:
        return None

    score = 0.0
    if class_match:
        score += 100.0
    if keyword_match:
        score += 30.0

    aspect = client_w / float(max(client_h, 1))
    if 1.35 <= aspect <= 2.10:
        score += 15.0
    if abs(client_w - TARGET_W) <= 80 and abs(client_h - TARGET_H) <= 80:
        score += 40.0
    score += min((client_w * client_h) / 100000.0, 30.0)
    return score


def _win32gui() -> Any:
    import win32gui

    return win32gui
