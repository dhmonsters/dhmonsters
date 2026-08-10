# 키 입력 종류와 기준 유지시간만 전달하는 입력 의도 모델
from __future__ import annotations

from dataclasses import dataclass


_VALID_ACTIONS = {"key", "hold", "move_dir"}


@dataclass
class Intent:
    action: str
    key: str = ""
    base_hold_sec: float = 0.05

    def __post_init__(self) -> None:
        if self.action not in _VALID_ACTIONS:
            raise ValueError(
                f"지원하지 않는 action: {self.action!r} (허용: {sorted(_VALID_ACTIONS)})"
            )
        if not self.key:
            raise ValueError(f"action={self.action!r}에는 key 값이 필요합니다")
