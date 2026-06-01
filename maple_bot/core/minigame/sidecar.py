# SidecarChannel — 본체(3.14)↔거탐 사이드카(3.13) IPC 추상
# 실제 구현은 mmap 공유메모리(C "LonaHunter_SharedData" 패턴). 여기선 계약+인메모리 Fake.
from __future__ import annotations

import queue
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SolveRequest:
    """본체 → 사이드카: 이 프레임의 미니게임을 풀어라."""
    minigame_type: str
    frame_id: int
    meta: dict = field(default_factory=dict)


@dataclass
class SolveReply:
    """사이드카 → 본체: 결과."""
    frame_id: int
    success: bool
    elapsed: float = 0.0
    note: str = ""


class SidecarChannel(ABC):
    """본체↔사이드카 양방향 채널 계약.

    구현:
      - InMemoryChannel: 같은 프로세스(테스트/단일런타임용)
      - MmapChannel(TODO): 실제 3.13 사이드카 프로세스와 mmap 공유메모리.
        C 검증 패턴(SHM_NAME, 헤더+페이로드 struct)을 따른다. 실기 환경에서 구현·검증.
    """

    @abstractmethod
    def send_request(self, req: SolveRequest) -> None: ...

    @abstractmethod
    def recv_request(self) -> SolveRequest | None: ...

    @abstractmethod
    def send_reply(self, rep: SolveReply) -> None: ...

    @abstractmethod
    def recv_reply(self) -> SolveReply | None: ...


class InMemoryChannel(SidecarChannel):
    """프로세스 내 큐 기반 채널 — 사이드카 분리 없이 동작/테스트할 때."""

    def __init__(self):
        self._req: queue.Queue[SolveRequest] = queue.Queue()
        self._rep: queue.Queue[SolveReply] = queue.Queue()

    def send_request(self, req: SolveRequest) -> None:
        self._req.put(req)

    def recv_request(self) -> SolveRequest | None:
        try:
            return self._req.get_nowait()
        except queue.Empty:
            return None

    def send_reply(self, rep: SolveReply) -> None:
        self._rep.put(rep)

    def recv_reply(self) -> SolveReply | None:
        try:
            return self._rep.get_nowait()
        except queue.Empty:
            return None
