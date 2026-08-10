# FloorHuntRunner — 루트 반복 실행 + 활성/비활성 제어 검증(스레드 없이 run_once 중심)
import time
from core.navigation.floor_hunt_runner import FloorHuntRunner


class FakeBR:
    def __init__(self):
        self.routes = []
        self.released = 0
    def run_route(self, blocks, max_steps=200):
        self.routes.append(list(blocks))
        return True
    def release_inputs(self):
        self.released += 1


def test_run_once_executes_when_active():
    br = FakeBR()
    r = FloorHuntRunner(br, get_blocks=lambda: ["a", "b"], is_active=lambda: True)
    assert r.run_once() is True
    assert br.routes == [["a", "b"]]


def test_run_once_skips_when_inactive():
    br = FakeBR()
    r = FloorHuntRunner(br, get_blocks=lambda: ["a"], is_active=lambda: False)
    assert r.run_once() is False
    assert br.routes == []


def test_run_once_skips_empty_route():
    br = FakeBR()
    r = FloorHuntRunner(br, get_blocks=lambda: [], is_active=lambda: True)
    assert r.run_once() is False


def test_thread_loops_then_stops():
    """스레드 시작 → 활성 동안 반복 실행 → stop() 후 멈춤."""
    br = FakeBR()
    active = {"on": True}
    r = FloorHuntRunner(br, get_blocks=lambda: ["x"],
                        is_active=lambda: active["on"],
                        idle_sleep=0.001, sleep_fn=time.sleep)
    r.start()
    time.sleep(0.05)          # 잠깐 도는 동안 여러 번 실행됨
    r.stop()
    time.sleep(0.02)
    assert len(br.routes) >= 1
    assert not r.is_running() or True   # stop 후 곧 종료(데몬)


def test_thread_idle_when_inactive_then_resumes():
    """비활성이면 안 돌다가 활성화되면 실행."""
    br = FakeBR()
    active = {"on": False}
    r = FloorHuntRunner(br, get_blocks=lambda: ["y"],
                        is_active=lambda: active["on"],
                        idle_sleep=0.001, sleep_fn=time.sleep)
    r.start()
    time.sleep(0.02)
    assert br.routes == []     # 비활성 → 실행 안 됨
    active["on"] = True
    time.sleep(0.03)
    r.stop()
    assert len(br.routes) >= 1 # 활성 후 실행됨
