# SidecarChannel — 본체(3.14)↔거탐 사이드카(3.13) IPC 추상. 인메모리 Fake로 프로토콜 검증
import pytest
from core.minigame.sidecar import SidecarChannel, InMemoryChannel, SolveRequest, SolveReply


def test_request_reply_dataclasses():
    req = SolveRequest(minigame_type="planet", frame_id=7, meta={"roi": [1, 2, 3, 4]})
    assert req.minigame_type == "planet"
    assert req.frame_id == 7
    rep = SolveReply(frame_id=7, success=True, elapsed=1.1, note="done")
    assert rep.success is True


def test_inmemory_channel_roundtrip():
    """본체가 보낸 요청을 사이드카측이 받고, 응답을 돌려준다."""
    ch = InMemoryChannel()
    # 본체 → 사이드카
    ch.send_request(SolveRequest(minigame_type="planet", frame_id=1))
    got = ch.recv_request()
    assert got.minigame_type == "planet" and got.frame_id == 1
    # 사이드카 → 본체
    ch.send_reply(SolveReply(frame_id=1, success=True))
    rep = ch.recv_reply()
    assert rep.frame_id == 1 and rep.success is True


def test_recv_empty_returns_none():
    ch = InMemoryChannel()
    assert ch.recv_request() is None
    assert ch.recv_reply() is None


def test_channel_is_abstract_contract():
    """SidecarChannel 은 추상 — 직접 인스턴스화 불가."""
    with pytest.raises(TypeError):
        SidecarChannel()
