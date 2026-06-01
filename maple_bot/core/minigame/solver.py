# MinigameSolver — 거탐(미니게임) 해결 엔진의 공통 계약. 구현체는 인터페이스 뒤 격리
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SolveResult:
    """거탐 해결 결과."""
    success: bool
    elapsed: float = 0.0
    note: str = ""


class MinigameSolver(ABC):
    """거탐 엔진 계약 (도면 5-4).

    본체(Orchestrator)는 어느 엔진인지 모른 채 can_handle/solve 만 호출한다.
    새 미니게임(비올레타 등)은 이 인터페이스 구현체 1개 추가로 꽂는다(도면 5-5).
    """

    @abstractmethod
    def can_handle(self, minigame_type: str) -> bool:
        """이 엔진이 해당 미니게임 종류("planet"|"lona"|"violeta")를 처리할 수 있는가."""
        ...

    @abstractmethod
    def solve(self, screenshot, ctx: dict | None = None) -> SolveResult:
        """미니게임을 해결한다."""
        ...
