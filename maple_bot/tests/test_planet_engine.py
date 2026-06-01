# PlanetV2Engine — 사이드카 채널로 거탐을 위임하는 엔진. 채널 왕복 로직 검증(실코어 없이)
import threading
import time
import pytest
from core.minigame.solver import SolveResult
from core.minigame.sidecar import InMemoryChannel, SolveRequest, SolveReply
from core.minigame.planet_engine import PlanetV2Engine


def test_can_handle_planet():
    eng = PlanetV2Engine(channel=InMemoryChannel())
    assert eng.can_handle("planet") is True
    assert eng.can_handle("lona") is False
    assert eng.can_handle("violeta") is False


def test_solve_sends_request_and_waits_reply():
    """solve()는 채널로 요청을 보내고, 사이드카(가짜)의 응답을 받아 SolveResult로 변환."""
    ch = InMemoryChannel()
    eng = PlanetV2Engine(channel=ch, timeout=1.0)

    # 가짜 사이드카 스레드: 요청 오면 성공 응답
    def fake_sidecar():
        for _ in range(100):
            req = ch.recv_request()
            if req is not None:
                ch.send_reply(SolveReply(frame_id=req.frame_id, success=True,
                                         elapsed=0.5, note="planet solved"))
                return
            time.sleep(0.01)
    t = threading.Thread(target=fake_sidecar, daemon=True); t.start()

    r = eng.solve(screenshot=None, ctx={"frame_id": 42})
    t.join(timeout=1.0)
    assert isinstance(r, SolveResult)
    assert r.success is True
    assert r.note == "planet solved"


def test_solve_timeout_returns_failure():
    """사이드카가 응답 안 하면 timeout 후 실패 결과(봇이 멈추지 않게)."""
    ch = InMemoryChannel()
    eng = PlanetV2Engine(channel=ch, timeout=0.1)
    r = eng.solve(screenshot=None, ctx={"frame_id": 1})
    assert r.success is False
    assert "timeout" in r.note.lower()
