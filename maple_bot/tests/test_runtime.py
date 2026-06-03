# BotRuntime — 7모듈 결선이 한 틱 도는지 Fake(게임없이)로 검증
import numpy as np
import pytest
from core.runtime import BotRuntime, RuntimeConfig
from core.navigation.block import Block
from core.navigation.floor_judge import Floor
from core.minigame.sidecar import InMemoryChannel


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


def test_attack_releases_held_move_key():
    """제자리 공격 시 유지 중인 좌우 이동키를 뗀다(key 모드는 항상 공격)."""
    rt, backend = _make_runtime(lambda r=None: _yellow_at(50, 75))
    rt.pump_scanners_once()
    rt.orchestrator.process_pending()
    rt.humanizer.hold_dir("right")          # 이동 중(오른쪽 유지) 가정
    assert rt.humanizer.held_dir() == "right"
    rt.hunting_tick(now=1.0)                 # key 모드 → 공격
    assert "right" in backend.ups            # 이동키 떼짐
    assert rt.humanizer.held_dir() is None
    assert "a" in backend.presses            # 공격 입력


def test_potion_fires_when_hp_low():
    """통합 런타임: HP가 임계 미만이면 hunting_tick에서 물약 키 송출(통합 포팅 때 빠졌던 배선 복구)."""
    from core.acting.combat import PotionRule
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
        hp_rule=PotionRule(enabled=True, key="pgup", threshold=0.65, cooldown=0.0),
    )
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg, sidecar_channel=InMemoryChannel(),
                    hp_mp_reader=lambda: (0.30, 1.0))   # HP 30% < 65%
    rt.hunting_tick(now=1.0)
    assert "pgup" in backend.presses


def test_potion_no_fire_when_full():
    """HP/MP 가득이면 물약 키 안 나감."""
    from core.acting.combat import PotionRule
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
        hp_rule=PotionRule(enabled=True, key="pgup", threshold=0.65, cooldown=0.0),
    )
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg, sidecar_channel=InMemoryChannel(),
                    hp_mp_reader=lambda: (1.0, 1.0))
    rt.hunting_tick(now=1.0)
    assert "pgup" not in backend.presses


def test_route_mode_builds_floor_hunt_runner_and_gates():
    """route_mode면 FloorHuntRunner 생성 + 활성조건(_bot_running & hunting) 게이팅."""
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
        floors=[Floor("1층", 70, 80)],
        route=[Block(type="move", target_x=0, move_type="walk")],
        route_mode=True, attack_key="a",
    )
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg,
                    sidecar_channel=InMemoryChannel())
    assert rt.floor_hunt_runner is not None
    assert rt._route_can_run() is False          # 아직 정지 상태
    assert rt.floor_hunt_runner.run_once() is False
    rt.set_running(True)
    assert rt._route_can_run() is True            # 켜짐 + hunting
    assert rt.floor_hunt_runner.run_once() is True
    rt.orchestrator.mode = "safety"
    assert rt._route_can_run() is False           # 안전모드 → 루트 멈춤


def test_no_route_mode_keeps_tick_path():
    """route_mode 아니면 FloorHuntRunner 없음(기존 틱 경로 유지)."""
    rt, _ = _make_runtime(lambda r=None: _yellow_at(50, 75))
    assert rt.floor_hunt_runner is None


def test_pickup_timer_presses_key_on_interval():
    """픽업 타이머: 활성 시 hunting_tick에서 줍기 키 입력."""
    backend = RecordingBackend()
    cfg = RuntimeConfig(minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
                        pickup_key="z", pickup_interval=0.0)
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg, sidecar_channel=InMemoryChannel())
    rt.hunting_tick(now=1.0)
    assert "z" in backend.presses        # 줍기 키 송출


def test_transparent_disabled_skips_solver():
    """투명도형 자동풀이 꺼지면 safety_tick이 풀이 시도 안 함(일시정지 유지)."""
    rt, _ = _make_runtime(lambda r=None: _yellow_at(50, 75))
    rt._cfg.transparent_enabled = False
    from core.sensing.event import Event
    rt.orchestrator._q.put(Event(type="lie", data={}))
    rt.orchestrator.process_pending()
    assert rt.orchestrator.mode == "safety"

    called = {"n": 0}
    rt.registry.solve = lambda *a, **k: called.__setitem__("n", called["n"] + 1)
    rt.safety_tick(now=2.0)
    assert called["n"] == 0            # 풀이 안 함
    assert rt.orchestrator.mode == "safety"   # 계속 일시정지


def test_lie_alert_sends_telegram_when_enabled():
    """거탐 알림 켜짐 + 텔레그램 자격 있으면 거탐 시 텔레그램 전송."""
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
        lie_alert=True, tg_token="t", tg_chat_id="c",
    )
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg,
                    sidecar_channel=InMemoryChannel())
    sent = []
    rt.telegram.send = lambda msg: sent.append(msg)
    from core.sensing.event import Event
    rt.orchestrator._q.put(Event(type="lie", data={}))
    rt.orchestrator.process_pending()
    assert any("거탐" in m for m in sent)


def test_lie_alert_off_no_telegram():
    """거탐 알림 꺼지면 텔레그램 안 보냄."""
    backend = RecordingBackend()
    cfg = RuntimeConfig(minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
                        lie_alert=False, tg_token="t", tg_chat_id="c")
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg, sidecar_channel=InMemoryChannel())
    sent = []
    rt.telegram.send = lambda msg: sent.append(msg)
    from core.sensing.event import Event
    rt.orchestrator._q.put(Event(type="lie", data={}))
    rt.orchestrator.process_pending()
    assert sent == []


def test_safety_event_triggers_solver_then_resume():
    """거탐 이벤트 → safety 모드 → 거탐엔진 풀이 → 재개."""
    rt, backend = _make_runtime(lambda r=None: _yellow_at(50, 75))

    # 실엔진(느린 ncnn) 대신 즉시-성공 Fake 엔진으로 교체 (조율 로직만 검증)
    from core.minigame.solver import MinigameSolver, SolveResult
    from core.minigame.registry import SolverRegistry

    class FastEngine(MinigameSolver):
        def can_handle(self, t): return t == "planet"
        def solve(self, screenshot, ctx=None):
            return SolveResult(success=True, note="solved")
    rt.registry = SolverRegistry()
    rt.registry.register(FastEngine())

    from core.sensing.event import Event
    rt.orchestrator._q.put(Event(type="lie", data={}))
    rt.orchestrator.process_pending()
    assert rt.orchestrator.mode == "safety"

    rt.safety_tick(now=2.0)
    assert rt.orchestrator.mode == "hunting"


def test_runtime_builds_recovery_graph_and_injects():
    """floors+route(사다리)면 BlockRunner에 복귀 그래프가 주입된다."""
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
        floors=[Floor("2층", 100, 149), Floor("1층", 150, 199)],
        route=[Block(type="ladder", ladder_x=40, y_bot=170, y_top=120)],
    )
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg, sidecar_channel=InMemoryChannel())
    assert rt.block_runner._judge is not None
    g = rt.block_runner._graph
    assert g is not None and "1층" in g and "2층" in g
    assert any(e["to"] == "2층" for e in g["1층"])   # 사다리 간선
