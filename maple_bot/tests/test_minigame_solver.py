# MinigameSolver 계약 + SolveResult 테스트
import pytest
from core.minigame.solver import MinigameSolver, SolveResult


class DummyEngine(MinigameSolver):
    def __init__(self, types): self._types = types
    def can_handle(self, minigame_type): return minigame_type in self._types
    def solve(self, screenshot, ctx=None):
        return SolveResult(success=True, elapsed=1.2, note="dummy")


def test_solve_result_fields():
    r = SolveResult(success=True, elapsed=2.5, note="ok")
    assert r.success is True
    assert r.elapsed == 2.5
    assert r.note == "ok"


def test_solve_result_defaults():
    r = SolveResult(success=False)
    assert r.elapsed == 0.0
    assert r.note == ""


def test_engine_can_handle():
    e = DummyEngine({"planet", "lona"})
    assert e.can_handle("planet") is True
    assert e.can_handle("violeta") is False


def test_engine_solve_returns_result():
    e = DummyEngine({"planet"})
    r = e.solve(screenshot=None)
    assert isinstance(r, SolveResult)
    assert r.success is True
