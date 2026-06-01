# Scanner 추상 — 독립 스레드 생명주기 + 이벤트큐 push 를 테스트
import queue
import time
import pytest
from core.sensing.event import Event
from core.sensing.scanner import Scanner


class CountingScanner(Scanner):
    """테스트용 — scan_once가 호출될 때마다 Event 하나 push."""
    interval = 0.01

    def __init__(self):
        super().__init__()
        self.scan_count = 0

    def scan_once(self):
        self.scan_count += 1
        return Event(type="tick", data={"n": self.scan_count})


def test_scanner_pushes_events_to_queue():
    q = queue.Queue()
    s = CountingScanner()
    s.start(q)
    time.sleep(0.1)   # 여러 번 스캔되도록
    s.stop()
    # 큐에 이벤트가 쌓였는지
    assert not q.empty()
    e = q.get_nowait()
    assert e.type == "tick"


def test_scanner_stops_cleanly():
    q = queue.Queue()
    s = CountingScanner()
    s.start(q)
    time.sleep(0.05)
    s.stop()
    count_at_stop = s.scan_count
    time.sleep(0.05)
    # stop 후에는 더 이상 스캔되지 않음
    assert s.scan_count == count_at_stop
    assert not s.is_running()


def test_scan_once_returning_none_pushes_nothing():
    """scan_once가 None 반환(감지 없음)이면 큐에 push 안 함."""
    class SilentScanner(Scanner):
        interval = 0.01
        def scan_once(self): return None
    q = queue.Queue()
    s = SilentScanner()
    s.start(q)
    time.sleep(0.05)
    s.stop()
    assert q.empty()


def test_scanner_exception_does_not_kill_thread():
    """scan_once 예외가 나도 스레드가 죽지 않고 계속 돈다(견고성)."""
    class FlakyScanner(Scanner):
        interval = 0.01
        def __init__(self):
            super().__init__(); self.n = 0
        def scan_once(self):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("일시 오류")
            return Event(type="ok", data={})
    q = queue.Queue()
    s = FlakyScanner()
    s.start(q)
    time.sleep(0.1)
    s.stop()
    assert not q.empty()  # 첫 예외 후에도 이벤트 나옴
