# 입력 백엔드 — Interception(스텔스) 우선, SendInput 폴백. 공통 인터페이스 뒤로 격리
from __future__ import annotations

from abc import ABC, abstractmethod


class InputBackend(ABC):
    """입력 송출 백엔드 계약. 구현체는 교체 가능(콘센트)."""
    name: str = "abstract"

    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def press(self, key: str, hold_sec: float = 0.05) -> None: ...

    @abstractmethod
    def is_available(self) -> bool:
        """이 백엔드가 현재 환경에서 사용 가능한가."""
        ...


class InterceptionBackend(InputBackend):
    """커널 드라이버 기반 스텔스 입력 (core/interception_backend.py 래핑)."""
    name = "interception"

    def __init__(self):
        from core import interception_backend as _ic
        self._ic = _ic
        self._enabled = False

    def is_available(self) -> bool:
        if not self._enabled:
            # enable()은 드라이버 캡처를 1회 시도하고 성공 여부를 반환
            self._enabled = self._ic.enable()
        return self._ic.is_active()

    def key_down(self, key: str) -> None:
        self._ic.key_down(key)

    def key_up(self, key: str) -> None:
        self._ic.key_up(key)

    def press(self, key: str, hold_sec: float = 0.05) -> None:
        self._ic.press(key, hold_sec)


class SendInputBackend(InputBackend):
    """Win32 SendInput 폴백 (core/input_controller.py 프리미티브 재사용)."""
    name = "sendinput"

    def __init__(self):
        from core import input_controller as _src
        self._src = _src

    def is_available(self) -> bool:
        return True  # Win32는 항상 가용

    def key_down(self, key: str) -> None:
        vk = self._src._vk(key)
        if vk:
            self._src._send_key(vk, 0)

    def key_up(self, key: str) -> None:
        vk = self._src._vk(key)
        if vk:
            self._src._send_key(vk, self._src.KEYEVENTF_KEYUP)

    def press(self, key: str, hold_sec: float = 0.05) -> None:
        import time
        self.key_down(key)
        time.sleep(max(0.0, hold_sec))
        self.key_up(key)


def select_backend(candidates: list[InputBackend] | None = None) -> InputBackend:
    """후보 중 첫 번째로 가용한 백엔드를 선택. 없으면 RuntimeError.

    기본 우선순위: Interception → SendInput.
    """
    if candidates is None:
        candidates = [InterceptionBackend(), SendInputBackend()]
    for b in candidates:
        try:
            if b.is_available():
                return b
        except Exception:
            continue
    raise RuntimeError("사용 가능한 입력 백엔드가 없습니다.")
