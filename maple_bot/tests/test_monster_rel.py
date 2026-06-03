# 사냥영역 몬스터 탐지 → 캐릭(닉네임) 기준 화면px 오프셋 변환 검증
import numpy as np

from core import runtime as rt_mod


def _make_runtime(monkeypatch, name_pos, boxes):
    """vision 함수를 가짜로 바꿔, detect_monsters_rel의 오프셋 계산만 검증."""
    rt = rt_mod.BotRuntime.__new__(rt_mod.BotRuntime)
    rt._name_tpl = np.zeros((2, 2, 3), np.uint8)
    rt._monster_tpls = {"m1": np.zeros((2, 2, 3), np.uint8)}
    rt._capture = lambda *a, **k: np.zeros((50, 50, 3), np.uint8)

    class _Cfg:
        hunt_area_region = {"left": 0, "top": 0, "width": 50, "height": 50}
        name_threshold = 0.7
        monster_accuracy = 0.9
        atk_x_min, atk_x_max, atk_y_min, atk_y_max = -30, 30, -40, 40
        coord_mode = "absolute"      # _resolve_region 통과(좌표 그대로)
        game_window_title = ""
        coord_anchor = None
    rt._cfg = _Cfg()

    monkeypatch.setattr(rt_mod.monster_vision, "find_template_pos",
                        lambda *a, **k: name_pos)
    monkeypatch.setattr(rt_mod.monster_vision, "attack_box",
                        lambda *a, **k: (0, 0, 50, 50))
    monkeypatch.setattr(rt_mod.monster_vision, "monster_boxes_in_box",
                        lambda *a, **k: boxes)
    return rt


def test_offset_is_monster_center_minus_name(monkeypatch):
    # 닉네임(캐릭) 중심 (20,20), 몬스터 박스 (30,10,10,10) → 중심(35,15) → 오프셋(15,-5)
    rt = _make_runtime(monkeypatch, name_pos=(20, 20), boxes=[(30, 10, 10, 10)])
    assert rt.detect_monsters_rel() == [(15, -5)]


def test_empty_when_no_name(monkeypatch):
    rt = _make_runtime(monkeypatch, name_pos=None, boxes=[(30, 10, 10, 10)])
    assert rt.detect_monsters_rel() == []


def test_empty_when_no_templates(monkeypatch):
    rt = _make_runtime(monkeypatch, name_pos=(20, 20), boxes=[])
    rt._monster_tpls = {}
    assert rt.detect_monsters_rel() == []
