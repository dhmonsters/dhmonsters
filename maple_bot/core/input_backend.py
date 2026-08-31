# Interception 기반 키보드·마우스 입력 백엔드를 선택합니다.
from __future__ import annotations

from abc import ABC, abstractmethod


class InputBackend(ABC):
    name: str = "abstract"

    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def press(self, key: str, hold_sec: float = 0.05) -> None: ...

    @abstractmethod
    def click(self, x: int, y: int) -> None: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    def begin_priority(self) -> None:
        pass

    def end_priority(self) -> None:
        pass


class InterceptionBackend(InputBackend):
    name = "interception"

    def __init__(self):
        from core import interception_backend

        self._driver = interception_backend
        self._enabled = False

    def is_available(self) -> bool:
        if not self._enabled:
            self._enabled = self._driver.enable()
        return self._driver.is_active()

    def key_down(self, key: str) -> None:
        self._driver.key_down(key)

    def key_up(self, key: str) -> None:
        self._driver.key_up(key)

    def press(self, key: str, hold_sec: float = 0.05) -> None:
        self._driver.press(key, hold_sec)

    def click(self, x: int, y: int) -> None:
        self._driver.click(int(x), int(y))

    def begin_priority(self) -> None:
        self._driver.begin_priority()

    def end_priority(self) -> None:
        self._driver.end_priority()


def select_backend(candidates: list[InputBackend] | None = None) -> InputBackend:
    """사용 가능한 Interception 입력 백엔드를 반환합니다."""
    candidates = candidates or [InterceptionBackend()]
    last_error: Exception | None = None
    for backend in candidates:
        try:
            if backend.is_available():
                return backend
        except Exception as exc:
            last_error = exc
    detail = f" ({last_error})" if last_error else ""
    raise RuntimeError(
        "Interception 입력 백엔드 활성화에 실패했습니다. "
        "드라이버 설치와 관리자 권한 실행을 확인해 주세요." + detail
    )
