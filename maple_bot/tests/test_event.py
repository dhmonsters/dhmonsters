# Event 데이터클래스 — 감지부→오케스트레이터 통지 단위
import time
import pytest
from core.sensing.event import Event


def test_event_basic():
    e = Event(type="char_pos", data={"x": 10, "y": 20})
    assert e.type == "char_pos"
    assert e.data["x"] == 10
    assert e.ts > 0  # 자동 타임스탬프


def test_event_ts_auto_set():
    before = time.time()
    e = Event(type="lie", data={})
    after = time.time()
    assert before <= e.ts <= after


def test_event_type_required():
    with pytest.raises(ValueError):
        Event(type="", data={})


def test_event_data_defaults_empty():
    e = Event(type="user_gone")
    assert e.data == {}
