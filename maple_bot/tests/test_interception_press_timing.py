# Interception 키 홀드가 하한 없이 하향 5% 랜덤을 한 번만 적용하는지 검증한다.
from core import interception_backend


def test_press_randomizes_hold_once_without_twenty_ms_floor(monkeypatch):
    sleeps = []
    events = []
    randomized = []

    def fake_down_5(value):
        randomized.append(value)
        return 0.0097

    monkeypatch.setattr(interception_backend, "down_5", fake_down_5, raising=False)
    monkeypatch.setattr(interception_backend.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        interception_backend,
        "key_down",
        lambda key: events.append(("down", key)),
    )
    monkeypatch.setattr(
        interception_backend,
        "key_up",
        lambda key: events.append(("up", key)),
    )

    interception_backend.press("x", 0.01)

    assert randomized == [0.01]
    assert sleeps == [0.0097]
    assert events == [("down", "x"), ("up", "x")]
