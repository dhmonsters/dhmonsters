# tests/test_route_attack.py
# 루트 모드에서 사냥 구간(pass 아님)일 때만 이미지 탐지→공격이 일어나는지 검증
from core.navigation.block import Block
from core import runtime as rt_mod


def _make_runtime():
    rt = rt_mod.BotRuntime.__new__(rt_mod.BotRuntime)
    rt._route_hunt_active = False
    return rt


def test_segment_enter_sets_flag_for_hunt_and_pass():
    rt = _make_runtime()
    rt._on_route_segment_enter(Block(type="move", start_x=10, end_x=50, mode="infinite"))
    assert rt._route_hunt_active is True
    rt._on_route_segment_enter(Block(type="move", start_x=10, end_x=50, mode="count"))
    assert rt._route_hunt_active is True
    rt._on_route_segment_enter(Block(type="move", start_x=10, end_x=50, mode="pass"))
    assert rt._route_hunt_active is False
    rt._on_route_segment_enter(Block(type="ladder", ladder_x=30, y_top=50, y_bot=100))
    assert rt._route_hunt_active is False


def test_segment_exit_always_clears_flag():
    rt = _make_runtime()
    rt._route_hunt_active = True
    rt._on_route_segment_exit(Block(type="move", start_x=10, end_x=50, mode="infinite"))
    assert rt._route_hunt_active is False


def test_hunting_tick_attacks_only_in_hunt_segment(monkeypatch):
    rt = _make_runtime()
    class _FHR: pass
    rt.floor_hunt_runner = _FHR()
    calls = {"attack": 0}

    class _Combat:
        def attack(self, *a, **k): calls["attack"] += 1
    class _Tick:
        def tick(self, now): pass
    class _Orch:
        mode = "hunting"
    class _Cfg:
        attack_key = "ctrl"
        attack_interval = 0.0   # 테스트: 쿨다운 없이 매 호출 발동
        hits_to_kill = 1
        skill_cast_sec = 0.08
    rt.combat = _Combat(); rt.buffs = _Tick(); rt.pet = _Tick(); rt.pickup = _Tick()
    rt.orchestrator = _Orch(); rt._cfg = _Cfg()
    monkeypatch.setattr(rt, "_monster_in_range", lambda: True)

    rt._route_hunt_active = False          # 통과(회수) 구간
    rt.hunting_tick(now=0.0)
    assert calls["attack"] == 0

    rt._route_hunt_active = True           # 사냥 구간 + 몬스터 감지
    rt.hunting_tick(now=0.0)
    assert calls["attack"] == 1
