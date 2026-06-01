# PlanetV2Engine — 검증된 Planet v2 거탐 코어를 3.13 사이드카로 위임하는 엔진
# 코어(__mypyc.cp313.pyd)는 본체(3.14)와 ABI 비호환 → 사이드카 프로세스 + 채널 IPC로 격리
from __future__ import annotations

import time

from core.minigame.solver import MinigameSolver, SolveResult
from core.minigame.sidecar import SidecarChannel, SolveRequest


class PlanetV2Engine(MinigameSolver):
    """Planet v2(플래닛맵 투명도형) 거탐 엔진.

    실제 풀이는 별도 3.13 사이드카 프로세스 안의 mypyc 코어가 수행한다.
    이 클래스는 본체측 프록시 — 채널로 요청을 보내고 결과를 기다린다.
    어느 코어인지 본체는 모른다(블랙박스 격리, 헌법).
    """
    MINIGAME_TYPE = "planet"

    def __init__(self, channel: SidecarChannel, timeout: float = 30.0,
                 poll_interval: float = 0.02):
        self._ch = channel
        self._timeout = timeout
        self._poll = poll_interval
        self._frame_seq = 0

    # TODO(실기): 사이드카 프로세스 기동.
    #   - 3.13 임베드 파이썬으로 sidecar_main.py 실행
    #   - sidecar 측이 Planet_solver __mypyc.cp313.pyd 를 import 해 toss 코어 호출
    #   - MmapChannel(SHM_NAME) 로 본체와 공유메모리 통신 (C LonaHunter_SharedData 패턴)
    #   현재 골격은 channel 주입식이라 사이드카 기동/연결은 Orchestrator(M6) 또는 런처가 담당.

    def can_handle(self, minigame_type: str) -> bool:
        return minigame_type == self.MINIGAME_TYPE

    def solve(self, screenshot, ctx: dict | None = None) -> SolveResult:
        ctx = ctx or {}
        self._frame_seq += 1
        frame_id = int(ctx.get("frame_id", self._frame_seq))

        # 사이드카에 풀이 요청 (screenshot은 실제 구현에서 공유메모리/핸들로 전달)
        self._ch.send_request(SolveRequest(
            minigame_type=self.MINIGAME_TYPE,
            frame_id=frame_id,
            meta={k: v for k, v in ctx.items() if k != "frame_id"},
        ))

        # 응답 대기 (timeout 내). 응답 없으면 실패로 — 봇이 멈추지 않게
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            rep = self._ch.recv_reply()
            if rep is not None and rep.frame_id == frame_id:
                return SolveResult(success=rep.success, elapsed=rep.elapsed, note=rep.note)
            time.sleep(self._poll)

        return SolveResult(success=False, elapsed=self._timeout,
                           note="timeout — 사이드카 응답 없음")
