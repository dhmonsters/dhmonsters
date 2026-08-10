# 전역 단축키 매니저 — GetAsyncKeyState 폴링 방식 (게임 포커스에서도 동작)
from __future__ import annotations
import queue
import threading
import time
import logging
from typing import Callable

import win32api
import win32con
from PyQt6.QtCore import QTimer, QObject

logger = logging.getLogger(__name__)

POLL_INTERVAL = 0.01   # 10ms마다 키 상태 확인

# 키 이름 → 가상 키코드 변환
_VK_MAP: dict[str, int] = {
    "left":      win32con.VK_LEFT,
    "right":     win32con.VK_RIGHT,
    "up":        win32con.VK_UP,
    "down":      win32con.VK_DOWN,
    "space":     win32con.VK_SPACE,
    "enter":     win32con.VK_RETURN,
    "esc":       win32con.VK_ESCAPE,
    "ctrl":      win32con.VK_CONTROL,
    "shift":     win32con.VK_SHIFT,
    "alt":       win32con.VK_MENU,
    "home":      win32con.VK_HOME,
    "end":       win32con.VK_END,
    "pgup":      win32con.VK_PRIOR,
    "pageup":    win32con.VK_PRIOR,
    "pgdn":      win32con.VK_NEXT,
    "pagedown":  win32con.VK_NEXT,
    "insert":    win32con.VK_INSERT,
    "delete":    win32con.VK_DELETE,
    "tab":       win32con.VK_TAB,
}


def _to_vk(key: str) -> int | None:
    """키 이름을 가상 키코드로 변환. 알 수 없으면 None 반환."""
    key = key.strip().lower()
    if key in _VK_MAP:
        return _VK_MAP[key]
    if key.startswith("f") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return win32con.VK_F1 + (n - 1)
    if len(key) == 1:
        vk = win32api.VkKeyScan(key) & 0xFF
        return vk if vk != 0xFF else None
    return None


class HotkeyManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hotkeys: dict[str, tuple[int, str, Callable]] = {}  # name → (vk, key_str, callback)
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()

        # 키 상태 폴링 스레드 (GetAsyncKeyState)
        self._poll_thread = threading.Thread(
            target=self._key_poll_loop, daemon=True, name="HotkeyPoller"
        )
        self._poll_thread.start()

        # Qt 메인 스레드에서 큐를 소비해 콜백 실행
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._dispatch)
        self._timer.start()

    # ── 공개 API ──────────────────────────────────────────────────────
    def register(self, name: str, key: str, callback: Callable) -> str:
        """name 슬롯에 단축키를 등록한다. 성공 시 빈 문자열 반환."""
        vk = _to_vk(key)
        if vk is None:
            return f"알 수 없는 키: {key}"
        self._hotkeys[name] = (vk, key, callback)
        logger.info("단축키 등록: [%s] → %s (VK=0x%02X)", key, name, vk)
        return ""

    def unregister(self, name: str) -> None:
        self._hotkeys.pop(name, None)

    def get_hotkeys(self) -> dict[str, str]:
        """등록된 단축키 목록 반환. {name: key_str}"""
        return {name: key for name, (_, key, _) in self._hotkeys.items()}

    def stop(self) -> None:
        self._stop_event.set()
        self._timer.stop()

    # ── 키 상태 폴링 (별도 스레드) ───────────────────────────────────
    def _key_poll_loop(self) -> None:
        """10ms마다 GetAsyncKeyState로 키 상태를 확인한다.
        게임이 포커스를 가져도 하드웨어 키 상태를 직접 읽으므로 차단되지 않는다."""
        prev: dict[str, bool] = {}
        while not self._stop_event.is_set():
            for name, (vk, key_str, _) in list(self._hotkeys.items()):
                pressed = bool(win32api.GetAsyncKeyState(vk) & 0x8000)
                was = prev.get(name, False)
                if pressed and not was:
                    # 누른 순간(엣지)만 이벤트 발생
                    self._queue.put(name)
                prev[name] = pressed
            time.sleep(POLL_INTERVAL)

    # ── Qt 메인 스레드 콜백 실행 ─────────────────────────────────────
    def _dispatch(self) -> None:
        while not self._queue.empty():
            try:
                name = self._queue.get_nowait()
                entry = self._hotkeys.get(name)
                cb = entry[2] if entry else None
                if cb:
                    cb()
            except queue.Empty:
                break
