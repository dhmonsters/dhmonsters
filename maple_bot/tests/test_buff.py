# 버프 입력의 실행 조건과 다중 버프 간격을 검증합니다.
from core.acting.buff import Buff, BuffManager


class RecordingBackend:
    def __init__(self):
        self.presses = []

    def press(self, key, hold_sec=0.05):
        self.presses.append((key, hold_sec))


def test_buff_fires_when_interval_elapsed(monkeypatch):
    monkeypatch.setattr("core.acting.buff.randomize_interval", lambda value: value)
    backend = RecordingBackend()
    manager = BuffManager(backend, [Buff(key="1", interval=60)])

    manager.tick(100.0)

    assert backend.presses == [("1", 0.8)]


def test_buff_respects_interval(monkeypatch):
    monkeypatch.setattr("core.acting.buff.randomize_interval", lambda value: value)
    backend = RecordingBackend()
    manager = BuffManager(backend, [Buff(key="1", interval=60)])

    manager.tick(100.0)
    manager.tick(130.0)
    manager.tick(161.0)

    assert backend.presses == [("1", 0.8), ("1", 0.8)]


def test_empty_buff_key_is_skipped(monkeypatch):
    monkeypatch.setattr("core.acting.buff.randomize_interval", lambda value: value)
    backend = RecordingBackend()
    manager = BuffManager(backend, [Buff(key="", interval=60)])

    manager.tick(100.0)

    assert backend.presses == []


def test_multiple_buffs_are_staggered(monkeypatch):
    monkeypatch.setattr("core.acting.buff.randomize_interval", lambda value: value)
    backend = RecordingBackend()
    manager = BuffManager(
        backend,
        [Buff(key="1", interval=60), Buff(key="2", interval=120)],
        gap=1.2,
    )

    manager.tick(100.0)
    manager.tick(100.5)
    manager.tick(101.5)

    assert backend.presses == [("1", 0.8), ("2", 0.8)]
