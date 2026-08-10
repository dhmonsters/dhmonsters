# 실행 중 세션 갱신과 명시적 라이선스 차단을 감시하는 모듈
from __future__ import annotations

import threading
from collections.abc import Callable

from core.license_v2 import AuthoritativeDenial, HEARTBEAT_SECONDS, LicenseClient, LicenseV2Error


class LicenseRuntimeMonitor:
    def __init__(self, client: LicenseClient, hwid: str):
        self._client = client
        self._hwid = hwid
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._safe_stop: Callable[[str], None] | None = None

    def register_safe_stop(self, callback: Callable[[str], None] | None) -> None:
        self._safe_stop = callback

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="license-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                self._client.heartbeat(self._hwid)
            except AuthoritativeDenial as exc:
                if self._safe_stop is not None:
                    self._safe_stop(f"라이선스 {exc.code}: {exc}")
                self._stop.set()
            except LicenseV2Error:
                # 일시 장애와 남은 오프라인 유예는 다음 주기에 다시 확인한다.
                continue


_monitor: LicenseRuntimeMonitor | None = None


def configure_runtime(client: LicenseClient, hwid: str) -> LicenseRuntimeMonitor:
    global _monitor
    if _monitor is None:
        _monitor = LicenseRuntimeMonitor(client, hwid)
    _monitor.start()
    return _monitor


def register_safe_stop(callback: Callable[[str], None] | None) -> None:
    if _monitor is not None:
        _monitor.register_safe_stop(callback)

