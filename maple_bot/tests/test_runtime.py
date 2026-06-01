# BotRuntime — 7모듈 결선이 한 틱 도는지 Fake(게임없이)로 검증
import numpy as np
import pytest
from core.runtime import BotRuntime, RuntimeConfig
from core.navigation.block import Block
from core.navigation.floor_judge import Floor
from core.minigame.sidecar import InMemoryChannel, SolveReply


class RecordingBackend:
    name = "recording"
    def __init__(self): self.presses=[]; self.downs=[]; self.ups=[]
    def key_down(self,k): self.downs.append(k)
    def key_up(self,k): self.ups.append(k)
    def press(self,k,hold_sec=0.05): self.presses.append(k)
    def is_available(self): return True


def _yellow_at(x, y, w=200, h=120):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[max(0,y-4):y+4, max(0,x-4):x+4] = (0, 255, 255)
    return img


def _make_runtime(capture, channel=None):
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left":0,"top":0,"width":200,"height":120},
        floors=[Floor("1층", 70, 80)],
        route=[Block(type="move", target_x=120, move_type="walk")],
        attack_key="a",
    )
    rt = BotRuntime(screen_capture=capture, input_backend=backend, config=cfg,
                    sidecar_channel=channel or InMemoryChannel())
    return rt, backend


def test_assembles_all_modules():
    rt, _ = _make_runtime(lambda r=None: _yellow_at(50, 75))
    assert rt.humanizer is not None
    assert rt.orchestrator is not None
    assert rt.block_runner is not None
    assert rt.combat is not None
    assert rt.registry is not None


def test_char_pos_flows_to_shared_state():
    """스캐너 1회 → 이벤트큐 → 오케스트레이터 → 공유위치 갱신."""
    rt, _ = _make_runtime(lambda r=None: _yellow_at(60, 75))
    rt.pump_scanners_once()          # 스캐너 수동 1회(스레드 대신)
    rt.orchestrator.process_pending()
    pos = rt.orchestrator.state.get_position()
    assert pos is not None
    assert abs(pos[0] - 60) <= 3


def test_hunting_tick_moves_and_attacks():
    """정상 사냥 틱: 위치 갱신 후 이동/공격 입력이 나간다(Humanizer 경유)."""
    rt, backend = _make_runtime(lambda r=None: _yellow_at(50, 75))
    rt.pump_scanners_once()
    rt.orchestrator.process_pending()
    rt.hunting_tick(now=1.0)
    # 이동(방향키) 또는 공격(a)이 백엔드로 송출됨
    assert backend.presses or backend.downs


def test_safety_event_triggers_solver_then_resume():
    """거탐 이벤트 → safety 모드 → 사이드카 풀이 → 재개."""
    ch = InMemoryChannel()
    # runtime과 가짜 사이드카가 같은 채널을 공유하도록 주입
    rt, backend = _make_runtime(lambda r=None: _yellow_at(50, 75), channel=ch)

    from core.sensing.event import Event
    # 거탐 이벤트 주입 → safety 모드
    rt.orchestrator._q.put(Event(type="lie", data={}))
    rt.orchestrator.process_pending()
    assert rt.orchestrator.mode == "safety"

    # 가짜 사이드카가 성공 응답을 미리 적재 (frame_id=1: 첫 safety_tick)
    ch.send_reply(SolveReply(frame_id=1, success=True, note="solved"))
    rt.safety_tick(now=2.0)
    # 풀이 성공 → 사냥 재개
    assert rt.orchestrator.mode == "hunting"
