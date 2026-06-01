# Scanner 추상 — 독립 스레드로 화면을 주기 감시, 감지 시 Event를 이벤트큐로 push
from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod

from core.sensing.event import Event


class Scanner(ABC):
    """감지 스캐너 기반 클래스.

    구현체는 scan_once() 만 정의한다.
      - scan_once() → Event 반환 시 큐에 push, None 반환 시 무시
    start(queue)/stop() 으로 스레드 생명주기 관리.
    scan_once 예외는 삼켜서 스레드가 죽지 않게 한다(견고성, C 패턴).
    """
    interval: float = 0.05   # 스캔 주기(초) — 구현체가 오버라이드

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._queue: queue.Queue | None = None

    @abstractmethod
    def scan_once(self) -> Event | None:
        """1회 감지. 이벤트가 있으면 Event, 없으면 None."""
        ...

    # ── 생명주기 ──────────────────────────────────────────────────────
    def start(self, event_queue: queue.Queue) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._queue = event_queue
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name=f"{type(self).__name__}"
        )
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── 내부 루프 ──────────────────────────────────────────────────────
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                ev = self.scan_once()
                if ev is not None and self._queue is not None:
                    self._queue.put(ev)
            except Exception:
                # 일시 오류로 스레드를 죽이지 않는다 — 다음 주기에 재시도
                pass
            self._stop.wait(self.interval)
