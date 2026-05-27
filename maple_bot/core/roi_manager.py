# 화면 비율 기반 ROI 계산 및 게임 창 핸들링 모듈
from __future__ import annotations
import win32gui


class ROIManager:
    """화면 비율(0~1) → 절대 픽셀 변환 및 게임 창 위치 감지."""

    def __init__(self) -> None:
        self._hwnd: int | None = None

    # ── 게임 창 탐색 ──────────────────────────────────────────────────
    def find_game_window(self, window_title: str = "MapleStory") -> bool:
        """win32gui로 게임 창 핸들을 탐색. 성공 시 True."""
        hwnd = win32gui.FindWindow(None, window_title)
        if hwnd:
            self._hwnd = hwnd
            return True
        # 부분 매칭 시도
        def _cb(h, _):
            if window_title.lower() in win32gui.GetWindowText(h).lower():
                self._hwnd = h
        win32gui.EnumWindows(_cb, None)
        return self._hwnd is not None

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        """게임 창 절대 위치와 크기 (x, y, w, h). 창 없으면 (0, 0, 1920, 1080)."""
        if self._hwnd:
            try:
                left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
                cx, cy = win32gui.ClientToScreen(self._hwnd, (0, 0))
                return cx, cy, right - left, bottom - top
            except Exception:
                pass
        return 0, 0, 1920, 1080

    # ── 비율 → 픽셀 변환 ─────────────────────────────────────────────
    def get_absolute_roi(
        self,
        frame_shape: tuple,
        ratio: list[float],
    ) -> tuple[int, int, int, int]:
        """
        ratio = [left, top, right, bottom] (0~1 비율, 프레임 기준)
        반환: (x, y, w, h) 절대 픽셀
        """
        h, w = frame_shape[:2]
        x1 = int(w * ratio[0])
        y1 = int(h * ratio[1])
        x2 = int(w * ratio[2])
        y2 = int(h * ratio[3])
        return x1, y1, max(1, x2 - x1), max(1, y2 - y1)
