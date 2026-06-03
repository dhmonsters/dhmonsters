# FloorHuntRunner — 층별 반복 사냥 루트를 별도 스레드에서 반복 실행(C RoutineRunner._run 방식).
# 블로킹 run_route를 메인루프와 분리 → 사다리 등반(수초) 중에도 메인루프가 이벤트 선점 가능.
# 루트 도중 중단은 BlockRunner.stop_fn(=사냥모드 아님)이 폴링 루프마다 처리한다.
from __future__ import annotations

import threading
import time
from typing import Callable


class FloorHuntRunner:
    """route(Block 리스트)를 반복 실행. is_active()가 True일 때만 돈다.

    block_runner : run_route(blocks)를 가진 BlockRunner (stop_fn으로 중단 처리)
    get_blocks   : () -> list[Block]  실행할 루트(설정 변경 즉시 반영)
    is_active    : () -> bool  사냥 모드이고 봇이 켜져 있는가
    """

    def __init__(self, block_runner, get_blocks: Callable[[], list],
                 is_active: Callable[[], bool],
                 idle_sleep: float = 0.05,
                 sleep_fn: Callable[[float], None] | None = None):
        self._br = block_runner
        self._get_blocks = get_blocks
        self._is_active = is_active
        self._idle = idle_sleep
        self._sleep = sleep_fn or time.sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="FloorHuntRoute")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def run_once(self) -> bool:
        """활성 상태면 루트를 1회 실행하고 True. 비활성/빈 루트면 False(테스트·수동용)."""
        if self._stop.is_set() or not self._is_active():
            return False
        blocks = self._get_blocks()
        if not blocks:
            return False
        self._br.run_route(blocks)
        return True

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                if not self.run_once():
                    self._sleep(self._idle)   # 비활성/빈 루트면 잠깐 쉬고 재확인
        finally:
            self._br.release_inputs()   # 스레드 종료 시 눌린 이동키 해제(키 눌림 방지)
