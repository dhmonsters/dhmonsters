# 동선 상태기가 이동 방향과 액션 키의 소유권을 한곳에서 관리한다.
from __future__ import annotations


class RouteInputOwner:
    def __init__(self, input_backend) -> None:
        self._backend = input_backend
        self._direction: str | None = None
        self._actions: set[str] = set()

    @property
    def direction(self) -> str | None:
        return self._direction

    def hold_direction(self, direction: str) -> None:
        direction = str(direction)
        if self._direction == direction:
            return
        if self._direction:
            self._backend.key_up(self._direction)
        self._backend.key_down(direction)
        self._direction = direction

    def release_direction(self) -> None:
        if self._direction:
            self._backend.key_up(self._direction)
        self._direction = None

    def hold_action(self, key: str) -> None:
        if key and key not in self._actions:
            self._backend.key_down(key)
            self._actions.add(key)

    def release_action(self, key: str) -> None:
        if key:
            self._backend.key_up(key)
            self._actions.discard(key)

    def release_all(self) -> None:
        self.release_direction()
        for key in tuple(self._actions):
            self.release_action(key)

    def press_action(self, key: str, hold_sec: float = 0.05) -> None:
        if key:
            self._backend.press(key, hold_sec)
