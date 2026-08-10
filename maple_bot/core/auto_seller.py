# 자동판매 상태와 예약 실행 판단을 관리하는 작은 상태기계.
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class AutoSellerStatus:
    state: str = "idle"
    last_started_at: float = 0.0
    last_finished_at: float = 0.0
    next_run_at: float = 0.0
    last_error: str = ""


class AutoSeller:
    """기존 JunkSeller를 수동/예약 실행 상태로 감싸는 얇은 래퍼."""

    def __init__(self, seller):
        self.seller = seller
        self.status = AutoSellerStatus()

    @property
    def state(self) -> str:
        return self.status.state

    def text(self) -> str:
        if self.status.state == "selling":
            return "판매 중"
        if self.status.state == "stopping":
            return "중단 요청"
        if self.status.state == "failed":
            return f"오류: {self.status.last_error}"
        if self.status.next_run_at > 0:
            remain = max(0.0, self.status.next_run_at - time.time())
            return f"대기 중, 다음 판매까지 {remain:.0f}초"
        return "대기 중"

    def schedule_after_minutes(self, minutes: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.status.next_run_at = now + max(0.1, float(minutes)) * 60.0

    def should_run(self, enabled: bool, interval_min: float, now: float | None = None) -> bool:
        if not enabled or self.status.state in ("selling", "stopping"):
            return False
        now = time.time() if now is None else now
        if self.status.next_run_at <= 0:
            self.schedule_after_minutes(interval_min, now)
            return False
        return now >= self.status.next_run_at

    def request_stop(self) -> None:
        if self.status.state == "selling":
            self.status.state = "stopping"

    def run_once(self, status_cb, stop_event) -> None:
        self.status.state = "selling"
        self.status.last_started_at = time.time()
        self.status.last_error = ""
        try:
            self.seller.sell(status_cb=status_cb, stop_event=stop_event)
        except Exception as exc:
            self.status.state = "failed"
            self.status.last_error = str(exc)
            raise
        else:
            self.status.state = "completed"
        finally:
            self.status.last_finished_at = time.time()
