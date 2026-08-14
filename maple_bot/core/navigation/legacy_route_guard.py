# 구형 동선 설정의 자동 실행을 막고 신규 동선 재저장을 안내한다.
from __future__ import annotations


class LegacyRouteGuard:
    def __init__(self, log_fn=None) -> None:
        self._log = log_fn or (lambda _message: None)
        self._notified = False

    def start(self) -> None:
        if self._notified:
            return
        self._notified = True
        self._log("구형 동선 설정(route)은 실행하지 않습니다. 동선·이동 탭에서 현재 맵을 신규 동선(route_steps)으로 다시 저장해 주세요.")

    def stop(self) -> None:
        self._notified = False

    def is_running(self) -> bool:
        return False
