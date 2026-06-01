# SharedState — 스레드 안전 공유 상태(위치/HP/MP). 스캐너 쓰기 ↔ 행동 읽기
import threading
import pytest
from core.orchestrator.shared_state import SharedState


def test_position_set_get():
    s = SharedState()
    s.set_position(10, 20)
    assert s.get_position() == (10, 20)


def test_position_none_initially():
    s = SharedState()
    assert s.get_position() is None


def test_hp_mp_ratio():
    s = SharedState()
    s.set_hp_ratio(0.6)
    s.set_mp_ratio(0.4)
    assert s.get_hp_ratio() == 0.6
    assert s.get_mp_ratio() == 0.4


def test_thread_safe_concurrent_writes():
    """여러 스레드가 동시에 써도 깨지지 않음."""
    s = SharedState()
    def writer(v):
        for _ in range(1000):
            s.set_position(v, v)
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    # 마지막 값은 5개 중 하나의 일관된 튜플(찢어진 값 없음)
    x, y = s.get_position()
    assert x == y and 0 <= x < 5


def test_position_staleness():
    """위치 갱신 시각 추적 — 오래된 위치 감지용."""
    s = SharedState()
    s.set_position(1, 1, now=100.0)
    assert s.position_age(now=100.5) == pytest.approx(0.5)
