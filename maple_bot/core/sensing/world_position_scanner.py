from __future__ import annotations
# 미니맵을 주기 캡처해 전역 캐릭터 위치와 추적 상태를 공유하는 스캐너

import threading

from core.navigation.world_map import WorldPoint


class WorldPositionScanner:
    def __init__(
        self,
        capture_fn,
        region_fn,
        local_position_fn,
        tracker,
        interval_sec: float = 0.08,
    ):
        self._capture = capture_fn
        self._region = region_fn
        self._local = local_position_fn
        self._tracker = tracker
        self._interval = interval_sec
        self._position = None
        self._state = "unavailable"
        self._stop = threading.Event()
        self._thread = None

    def scan_once(self):
        local = self._local()
        if local is None:
            if self._position is not None:
                self._state = "estimated"
            return None
        frame = self._capture(self._region())
        local_point = WorldPoint(*local)
        result = self._tracker.update(frame, local_point)
        point = self._tracker.character_world(local_point)
        self._position = (point.x, point.y)
        self._state = result.state
        return self._position

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="WorldPositionScanner",
        )
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception:
                self._state = "estimated"
            self._stop.wait(self._interval)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(0.2, self._interval * 3))

    def position(self):
        return self._position

    def state(self):
        return self._state

    def viewport(self):
        result = self._tracker.result
        if result is None:
            return None
        return (
            (result.origin.x, result.origin.y),
            self._tracker.viewport_size,
        )
