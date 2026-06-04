# HuntDirector — 몹 밀집도 기반 체류(DWELL)↔이동(MOVING) 상태기계 검증
from core.acting.hunt_director import HuntDirector


def _d():
    return HuntDirector(stay_threshold=3, leave_threshold=1, max_dwell_sec=8.0)


def test_enters_dwell_when_dense():
    d = _d()
    assert d.update(2, now=0.0) is False    # 2마리 < 진입3 → 이동 유지
    assert d.update(3, now=0.1) is True     # 3마리 → 멈춰 사냥
    assert d.is_dwelling() is True


def test_hysteresis_keeps_dwelling_until_leave():
    d = _d()
    d.update(3, now=0.0)                     # 진입
    assert d.update(2, now=0.5) is True      # 2마리: 이탈(≤1) 아님 → 계속 사냥
    assert d.update(1, now=1.0) is False     # 1마리 → 이탈, 이동


def test_max_dwell_timeout_forces_move():
    d = _d()
    d.update(5, now=0.0)                      # 진입(많음)
    assert d.update(5, now=7.9) is True       # 아직 8초 전 → 계속
    assert d.update(5, now=8.0) is False      # 8초 경과 → 많아도 강제 이동


def test_sparse_never_dwells():
    d = _d()
    for t in range(5):
        assert d.update(1, now=float(t)) is False
    assert d.is_dwelling() is False
