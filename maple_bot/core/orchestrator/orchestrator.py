# Orchestrator — 이벤트큐를 소비해 우선순위로 행동을 디스패치. god-loop를 대체하는 얇은 조율자
from __future__ import annotations

import queue
from typing import Callable

from core.sensing.event import Event
from core.orchestrator.shared_state import SharedState


# 이벤트 우선순위 — 숫자 작을수록 먼저 (안전 > 사냥)
_PRIORITY = {
    "lie": 0,          # 거탐 — 최우선
    "anti_mob": 0,     # 방지몹 — 최우선
    "user_detected": 1,
    "potion_low": 2,
    "char_pos": 5,     # 일반 사냥
}
_DEFAULT_PRIORITY = 9

# 안전 모드를 유발하는 이벤트 타입
_SAFETY_EVENTS = {"lie", "anti_mob"}


class Orchestrator:
    """감지 이벤트를 받아 우선순위 판단 후 행동으로 디스패치.

    god-loop 와 달리 로직을 직접 갖지 않는다 — 각 모듈(Nav/Acting/Solver)에 위임.
    이벤트 핸들러는 등록식: 새 이벤트 타입 = 핸들러 1개 추가(콘센트).
    """

    def __init__(self, event_queue: queue.Queue,
                 on_pause: Callable[[], None] | None = None,
                 on_resume: Callable[[], None] | None = None):
        self._q = event_queue
        self._handlers: dict[str, Callable[[Event], None]] = {}
        self._on_pause = on_pause or (lambda: None)
        self._on_resume = on_resume or (lambda: None)
        self.state = SharedState()
        self.mode = "hunting"   # "hunting" | "safety"

        # 내장 핸들러: 위치 갱신은 항상 공유상태로
        self.on("char_pos", self._handle_char_pos)

    def on(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """이벤트 타입에 핸들러 등록."""
        self._handlers[event_type] = handler

    def process_pending(self) -> None:
        """현재 큐에 쌓인 이벤트를 우선순위 순으로 1배치 처리."""
        batch: list[Event] = []
        while True:
            try:
                batch.append(self._q.get_nowait())
            except queue.Empty:
                break
        # 우선순위 정렬 (안전 이벤트 먼저)
        batch.sort(key=lambda e: _PRIORITY.get(e.type, _DEFAULT_PRIORITY))
        for ev in batch:
            self._dispatch(ev)

    def clear_safety(self) -> None:
        """안전 상황 해결 완료 → 사냥 재개."""
        if self.mode == "safety":
            self.mode = "hunting"
            self._on_resume()

    # ── 내부 ──────────────────────────────────────────────────────────
    def _dispatch(self, ev: Event) -> None:
        # 안전 이벤트면 모드 전환 + 행동 일괄 정지
        if ev.type in _SAFETY_EVENTS and self.mode != "safety":
            self.mode = "safety"
            self._on_pause()
        handler = self._handlers.get(ev.type)
        if handler is not None:
            handler(ev)

    def _handle_char_pos(self, ev: Event) -> None:
        self.state.set_position(ev.data["x"], ev.data["y"], now=ev.ts)
