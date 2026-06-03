# Humanizer 스레드 안전(락) + rand_in 검증 — 이동(루트)과 공격(메인)이 동시 사용
import threading

from core.humanize.humanizer import Humanizer


class _Backend:
    def __init__(self):
        self.events = []
        self._lock = threading.Lock()
    def key_down(self, k):
        with self._lock: self.events.append(("down", k))
    def key_up(self, k):
        with self._lock: self.events.append(("up", k))
    def press(self, k, hold):
        with self._lock: self.events.append(("press", k))


def test_rand_in_4_decimals_within_range():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None)
    for _ in range(100):
        v = h.rand_in(9, 10)
        assert 9 <= v <= 10 and round(v, 4) == v
    assert h.rand_in(5, 5) == 5.0          # lo==hi → lo
    assert h.rand_in(10, 5) == 10.0        # hi<lo → lo


def test_concurrent_hold_attack_no_crash():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None)
    from core.humanize.intent import Intent
    stop = [False]

    def mover():
        while not stop[0]:
            h.hold_dir("right"); h.hold_dir("left"); h.release_dir()

    def attacker():
        while not stop[0]:
            h.perform(Intent(action="key", key="ctrl", base_hold_sec=0.01))

    ts = [threading.Thread(target=mover), threading.Thread(target=attacker)]
    for t in ts: t.start()
    threading.Event().wait(0.1)
    stop[0] = True
    for t in ts: t.join(timeout=1)
    assert all(not t.is_alive() for t in ts)   # 데드락/예외 없이 종료
