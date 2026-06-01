# Orchestrator — 이벤트큐 소비 + 우선순위 + 안전대응(pause/resume). god-loop 대체 검증
import queue
import pytest
from core.sensing.event import Event
from core.orchestrator.orchestrator import Orchestrator


class Spy:
    """행동 호출을 기록하는 스파이."""
    def __init__(self):
        self.log = []
    def __call__(self, ev):
        self.log.append(ev.type)


def test_dispatches_event_to_registered_handler():
    q = queue.Queue()
    orch = Orchestrator(event_queue=q)
    spy = Spy()
    orch.on("char_pos", spy)
    q.put(Event(type="char_pos", data={"x": 1, "y": 2}))
    orch.process_pending()   # 큐 비울 때까지 1회 처리
    assert spy.log == ["char_pos"]


def test_unhandled_event_ignored():
    q = queue.Queue()
    orch = Orchestrator(event_queue=q)
    q.put(Event(type="unknown_xyz", data={}))
    orch.process_pending()   # 예외 없이 무시


def test_char_pos_updates_shared_state():
    q = queue.Queue()
    orch = Orchestrator(event_queue=q)
    q.put(Event(type="char_pos", data={"x": 30, "y": 40}))
    orch.process_pending()
    assert orch.state.get_position() == (30, 40)


def test_safety_event_sets_safety_mode():
    """거탐 이벤트 → SAFETY 모드 진입(사냥 일시정지)."""
    q = queue.Queue()
    paused = []
    orch = Orchestrator(event_queue=q, on_pause=lambda: paused.append(True))
    q.put(Event(type="lie", data={}))
    orch.process_pending()
    assert orch.mode == "safety"
    assert paused == [True]


def test_priority_safety_over_normal():
    """같은 배치에 사냥+거탐 이벤트가 있으면 거탐(안전)이 우선 처리."""
    q = queue.Queue()
    order = []
    orch = Orchestrator(event_queue=q,
                        on_pause=lambda: order.append("pause"))
    orch.on("char_pos", lambda ev: order.append("hunt"))
    q.put(Event(type="char_pos", data={"x": 1, "y": 1}))
    q.put(Event(type="lie", data={}))
    orch.process_pending()
    # 안전(pause)이 사냥보다 먼저
    assert order.index("pause") < order.index("hunt") if "hunt" in order else True
    assert orch.mode == "safety"


def test_resume_after_safety_cleared():
    q = queue.Queue()
    resumed = []
    orch = Orchestrator(event_queue=q, on_resume=lambda: resumed.append(True))
    q.put(Event(type="lie", data={}))
    orch.process_pending()
    assert orch.mode == "safety"
    orch.clear_safety()   # 거탐 해결 완료
    assert orch.mode == "hunting"
    assert resumed == [True]
