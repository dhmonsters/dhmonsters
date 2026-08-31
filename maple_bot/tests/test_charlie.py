# 찰리중사 이빨 교환 입력 순서와 반복 횟수를 검증합니다.
from core.acting.charlie import CharlieExchange


class RecordingBackend:
    def __init__(self):
        self.presses = []

    def press(self, key, hold_sec=0.05):
        self.presses.append((key, hold_sec))


def make_exchange():
    backend = RecordingBackend()
    return CharlieExchange(backend, npc_key="u", sleep_fn=lambda _seconds: None), backend


def test_repeat_count_from_tooth_amount():
    assert CharlieExchange.repeat_count(1000) == 5
    assert CharlieExchange.repeat_count(450) == 2
    assert CharlieExchange.repeat_count(199) == 0


def test_one_routine_sequence():
    exchange, backend = make_exchange()

    exchange.run_one_routine()

    keys = [key for key, _hold in backend.presses]
    assert keys == ["u", "u", *("down" for _ in range(15)), "u", "left", "u", "u"]


def test_run_exchanges_repeats_by_amount():
    exchange, backend = make_exchange()

    exchange.run(600)

    assert sum(key == "down" for key, _hold in backend.presses) == 45


def test_no_run_when_insufficient():
    exchange, backend = make_exchange()

    exchange.run(150)

    assert backend.presses == []
