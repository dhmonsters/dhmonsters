# 몬스터 감지 — B 메커니즘(닉네임 위치→atk박스→박스내 몬스터). A matchTemplate 베이스
import numpy as np
import pytest
from core.sensing.monster_vision import (
    find_template_pos, monsters_in_box, attack_box,
)

_RNG = np.random.default_rng(11)


def _textured(seed, size=24):
    return np.random.default_rng(seed).integers(0, 256, (size, size, 3), dtype=np.uint8)


def _scene(patches, w=600, h=400):
    """patches: [(img, x, y), ...] 를 노이즈 배경에 심은 씬."""
    s = _RNG.integers(0, 50, (h, w, 3), dtype=np.uint8)
    for img, x, y in patches:
        ph, pw = img.shape[:2]
        s[y:y+ph, x:x+pw] = img
    return s


def test_find_template_pos_returns_center():
    name = _textured(1)
    scene = _scene([(name, 300, 200)])
    pos = find_template_pos(scene, name, threshold=0.9)
    assert pos is not None
    cx, cy = pos
    assert abs(cx - (300 + 12)) <= 2 and abs(cy - (200 + 12)) <= 2   # 중심


def test_find_template_pos_none_when_absent():
    name = _textured(1)
    scene = _RNG.integers(0, 50, (400, 600, 3), dtype=np.uint8)
    assert find_template_pos(scene, name, threshold=0.9) is None


def test_attack_box_from_name_and_offsets():
    """닉네임 위치(300,200) + B atk 오프셋(-35~35, -70~70) → 공격 박스."""
    box = attack_box((300, 200), x_min=-35, x_max=35, y_min=-70, y_max=70)
    assert box == (300 - 35, 200 - 70, 70, 140)   # (left, top, w, h)


def test_monsters_in_box_detects_inside():
    """박스 안 몬스터만 감지, 박스 밖은 무시."""
    mob = _textured(2)
    name = _textured(1)
    # 닉네임(300,200), 몬스터를 박스 안(290,180)에 + 박스 밖(550,50)에
    scene = _scene([(name, 300, 200), (mob, 285, 150), (mob, 550, 40)])
    box = attack_box((312, 212), x_min=-60, x_max=60, y_min=-90, y_max=90)
    found = monsters_in_box(scene, {"m": mob}, box, threshold=0.9)
    # 박스 안 몬스터는 잡히고(>=1), 박스 밖은 카운트 안 됨
    assert found >= 1


def test_monsters_in_box_none_outside():
    mob = _textured(2)
    scene = _scene([(mob, 550, 40)])         # 박스 밖에만
    box = (200, 150, 100, 100)               # (200~300, 150~250)
    found = monsters_in_box(scene, {"m": mob}, box, threshold=0.9)
    assert found == 0


def test_multi_template_any_matches():
    """B 다중 템플릿(monster1~9) — 여러 종류 중 하나라도 박스 안에 있으면."""
    m1, m2 = _textured(3), _textured(4)
    scene = _scene([(m2, 220, 170)])         # m2만 존재
    box = (200, 150, 120, 120)
    found = monsters_in_box(scene, {"m1": m1, "m2": m2}, box, threshold=0.9)
    assert found >= 1
