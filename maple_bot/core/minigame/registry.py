# SolverRegistry — 등록된 거탐 엔진 중 can_handle 매칭으로 위임. 새 엔진 = register 1줄(콘센트)
from __future__ import annotations

from core.minigame.solver import MinigameSolver, SolveResult


class SolverRegistry:
    """거탐 엔진 레지스트리.

    본체는 solve(type, ...) 만 호출하고 어느 엔진이 처리하는지 모른다(격리).
    엔진 추가는 register() 한 번 — 기존 라우팅 코드는 바뀌지 않는다(도면 5-5).
    """

    def __init__(self):
        self._engines: list[MinigameSolver] = []

    def register(self, engine: MinigameSolver) -> None:
        self._engines.append(engine)

    def find(self, minigame_type: str) -> MinigameSolver | None:
        """해당 타입을 처리할 첫 엔진(등록 순 우선). 없으면 None."""
        for e in self._engines:
            if e.can_handle(minigame_type):
                return e
        return None

    def solve(self, minigame_type: str, screenshot, ctx: dict | None = None) -> SolveResult | None:
        """타입에 맞는 엔진으로 위임. 처리 가능한 엔진이 없으면 None."""
        engine = self.find(minigame_type)
        if engine is None:
            return None
        return engine.solve(screenshot, ctx)
