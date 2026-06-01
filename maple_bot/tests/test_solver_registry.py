# SolverRegistry — 등록 엔진 중 can_handle 매칭 위임. 콘센트 격리(새 엔진 무수정 추가) 검증
import pytest
from core.minigame.solver import MinigameSolver, SolveResult
from core.minigame.registry import SolverRegistry


class FakeEngine(MinigameSolver):
    def __init__(self, name, types):
        self.name = name
        self._types = types
        self.solve_called = False
    def can_handle(self, t): return t in self._types
    def solve(self, screenshot, ctx=None):
        self.solve_called = True
        return SolveResult(success=True, note=self.name)


def test_registry_routes_to_matching_engine():
    planet = FakeEngine("planet", {"planet"})
    lona = FakeEngine("lona", {"lona"})
    reg = SolverRegistry()
    reg.register(planet)
    reg.register(lona)

    r = reg.solve("lona", screenshot=None)
    assert r.note == "lona"
    assert lona.solve_called and not planet.solve_called


def test_registry_returns_none_when_no_engine():
    reg = SolverRegistry()
    reg.register(FakeEngine("planet", {"planet"}))
    r = reg.solve("violeta", screenshot=None)
    assert r is None  # 처리 가능한 엔진 없음


def test_registry_priority_first_registered_wins():
    """같은 타입을 둘이 처리 가능하면 먼저 등록된 것 우선."""
    e1 = FakeEngine("first", {"planet"})
    e2 = FakeEngine("second", {"planet"})
    reg = SolverRegistry()
    reg.register(e1); reg.register(e2)
    r = reg.solve("planet", screenshot=None)
    assert r.note == "first"


def test_consent_test_add_violeta_no_modification():
    """도면 5-5 콘센트테스트1: 비올레타 엔진 추가 = register 1줄, 기존 라우팅 무수정."""
    reg = SolverRegistry()
    reg.register(FakeEngine("planet", {"planet"}))
    reg.register(FakeEngine("lona", {"lona"}))
    # 기존: violeta 처리 불가
    assert reg.solve("violeta", screenshot=None) is None
    # 새 엔진 1줄 추가
    reg.register(FakeEngine("violeta", {"violeta"}))
    # 이제 처리됨 — 기존 planet/lona 라우팅 코드는 한 줄도 안 바뀜
    r = reg.solve("violeta", screenshot=None)
    assert r is not None and r.note == "violeta"
    # 기존 엔진들 여전히 동작
    assert reg.solve("planet", screenshot=None).note == "planet"
