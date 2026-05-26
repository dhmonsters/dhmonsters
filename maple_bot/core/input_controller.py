# 게임 창 포커스 및 키보드/마우스 입력을 담당하는 InputController 모듈
from __future__ import annotations

import ctypes
import time


# ── Win32 SendInput 상수 ────────────────────────────────────────────────
INPUT_KEYBOARD = 1
INPUT_MOUSE    = 0

KEYEVENTF_KEYUP      = 0x0002
KEYEVENTF_SCANCODE   = 0x0008

MOUSEEVENTF_MOVE     = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
MOUSEEVENTF_WHEEL    = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

# 키 이름 → 가상 키 코드 매핑
_VK_MAP: dict[str, int] = {
    "ctrl":   0x11, "left ctrl": 0x11, "control": 0x11,
    "shift":  0x10, "alt":    0x12,
    "space":  0x20, "enter":  0x0D, "esc":    0x1B, "escape": 0x1B,
    "up":     0x26, "down":   0x28, "left":   0x25, "right":  0x27,
    "home":   0x24, "end":    0x23, "pgup":   0x21, "pgdn":   0x22,
    "insert": 0x2D, "delete": 0x2E, "back":   0x08, "tab":    0x09,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "num0": 0x60, "num1": 0x61, "num2": 0x62, "num3": 0x63,
    "num4": 0x64, "num5": 0x65, "num6": 0x66, "num7": 0x67,
    "num8": 0x68, "num9": 0x69,
}

for _c in "abcdefghijklmnopqrstuvwxyz":
    _VK_MAP[_c] = ord(_c.upper())


# ── ctypes 구조체 ────────────────────────────────────────────────────────
class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.c_ulong),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT_UNION)]


def _send_key(vk: int, flags: int = 0) -> None:
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp._input.ki = _KEYBDINPUT(wVk=vk, dwFlags=flags)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _vk(key: str) -> int:
    return _VK_MAP.get(key.lower(), ord(key.upper()[0]) if len(key) == 1 else 0)


# ── 마우스 절대 좌표 이동 / 클릭 ─────────────────────────────────────────
def _screen_size() -> tuple[int, int]:
    return (
        ctypes.windll.user32.GetSystemMetrics(0),
        ctypes.windll.user32.GetSystemMetrics(1),
    )


def _move_mouse(x: int, y: int) -> None:
    sw, sh = _screen_size()
    ax = int(x * 65535 / max(1, sw - 1))
    ay = int(y * 65535 / max(1, sh - 1))
    inp = _INPUT(type=INPUT_MOUSE)
    inp._input.mi = _MOUSEINPUT(
        dx=ax, dy=ay,
        dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _click_mouse(down: bool) -> None:
    flag = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
    inp = _INPUT(type=INPUT_MOUSE)
    inp._input.mi = _MOUSEINPUT(dwFlags=flag)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


# ── InputController ──────────────────────────────────────────────────────
class InputController:
    """게임 창 포커스 및 키보드/마우스 입력 제어."""

    def __init__(self, window_title: str = "") -> None:
        self._window_title = window_title

    # ── 창 포커스 ─────────────────────────────────────────────────────
    def focus_game_window(self) -> None:
        """게임 창을 전면으로 가져온다."""
        try:
            import win32gui
            import win32con
            hwnd = win32gui.FindWindow(None, self._window_title)
            if hwnd:
                # 최소화된 경우에만 복원 — 최대화/일반 상태에서 SW_RESTORE 호출 시 창이 축소되므로 방지
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.05)
        except Exception:
            pass

    # ── 키보드 ───────────────────────────────────────────────────────
    def press_key(self, key: str, hold_sec: float = 0.05) -> None:
        """키를 hold_sec초 동안 누른 뒤 뗀다."""
        vk = _vk(key)
        if not vk:
            return
        _send_key(vk)
        time.sleep(max(0.02, hold_sec))
        _send_key(vk, KEYEVENTF_KEYUP)

    def key_down(self, key: str) -> None:
        """키를 누른 상태로 유지한다."""
        vk = _vk(key)
        if vk:
            _send_key(vk)

    def key_up(self, key: str) -> None:
        """누르고 있던 키를 뗀다."""
        vk = _vk(key)
        if vk:
            _send_key(vk, KEYEVENTF_KEYUP)

    # ── 마우스 ───────────────────────────────────────────────────────
    def click(self, x: int, y: int) -> None:
        """(x, y) 화면 절대 좌표를 좌클릭한다."""
        _move_mouse(x, y)
        time.sleep(0.03)
        _click_mouse(True)
        time.sleep(0.05)
        _click_mouse(False)

    def double_click(self, x: int, y: int) -> None:
        """(x, y) 화면 절대 좌표를 더블클릭한다."""
        _move_mouse(x, y)
        time.sleep(0.03)
        _click_mouse(True)
        time.sleep(0.05)
        _click_mouse(False)
        time.sleep(0.08)
        _click_mouse(True)
        time.sleep(0.05)
        _click_mouse(False)

    def scroll(self, x: int, y: int, clicks: int = -3) -> None:
        """(x, y) 위치에서 마우스 휠 스크롤.

        clicks > 0 : 위로 (스크롤 업), clicks < 0 : 아래로 (스크롤 다운).
        Windows WHEEL_DELTA = 120 단위.
        """
        _move_mouse(x, y)
        time.sleep(0.03)
        delta = int(clicks * 120)
        # mouseData에 부호 있는 값을 c_ulong으로 전달 (음수는 wrap-around)
        inp = _INPUT(type=INPUT_MOUSE)
        inp._input.mi = _MOUSEINPUT(
            mouseData=ctypes.c_ulong(delta & 0xFFFFFFFF).value,
            dwFlags=MOUSEEVENTF_WHEEL,
        )
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    def drag(
        self,
        from_pos: tuple[int, int],
        to_pos:   tuple[int, int],
        duration: float = 0.3,
    ) -> None:
        """from_pos → to_pos 로 드래그한다."""
        fx, fy = int(from_pos[0]), int(from_pos[1])
        tx, ty = int(to_pos[0]),   int(to_pos[1])
        _move_mouse(fx, fy)
        time.sleep(0.05)
        _click_mouse(True)
        # 직선 보간 이동
        steps = max(10, int(duration / 0.01))
        for i in range(1, steps + 1):
            ix = fx + int((tx - fx) * i / steps)
            iy = fy + int((ty - fy) * i / steps)
            _move_mouse(ix, iy)
            time.sleep(duration / steps)
        _click_mouse(False)

    def drag_slider(
        self,
        from_pos: tuple[float, float],
        to_pos:   tuple[float, float],
        duration: float = 0.4,
    ) -> None:
        """슬라이더용 느린 드래그 — drag()와 동일하나 duration 기본값이 다름."""
        self.drag(
            (int(from_pos[0]), int(from_pos[1])),
            (int(to_pos[0]),   int(to_pos[1])),
            duration=duration,
        )

    # ── 채팅 ─────────────────────────────────────────────────────────
    def send_chat(self, msg: str) -> None:
        """게임 채팅창에 메시지를 전송한다 (Enter → 메시지 입력 → Enter)."""
        self.press_key("enter", hold_sec=0.05)
        time.sleep(0.15)
        # 클립보드로 한국어 포함 텍스트 붙여넣기
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(msg, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            # Ctrl+V 붙여넣기
            vk_ctrl = _vk("ctrl")
            vk_v    = _vk("v")
            _send_key(vk_ctrl)
            time.sleep(0.03)
            _send_key(vk_v)
            time.sleep(0.05)
            _send_key(vk_v, KEYEVENTF_KEYUP)
            _send_key(vk_ctrl, KEYEVENTF_KEYUP)
        except Exception:
            pass
        time.sleep(0.1)
        self.press_key("enter", hold_sec=0.05)
