# Block 데이터클래스 — 동선 1스텝 데이터 (C routine_runner 스키마)
import pytest
from core.navigation.block import Block


def test_move_block():
    b = Block(type="move", target_x=35, move_type="teleport", direction="left")
    assert b.type == "move"
    assert b.target_x == 35
    assert b.move_type == "teleport"


def test_move_default_walk():
    b = Block(type="move", target_x=10)
    assert b.move_type == "walk"  # 기본


def test_attack_block():
    b = Block(type="attack", skill_key="a", attack_mode="count", attack_value=5, direction="right")
    assert b.skill_key == "a"
    assert b.attack_mode == "count"
    assert b.attack_value == 5


def test_ladder_block():
    b = Block(type="ladder", ladder_x=120, y_top=66, y_bot=83, exit_side="left")
    assert b.ladder_x == 120
    assert b.y_top == 66
    assert b.exit_side == "left"


def test_invalid_type_rejected():
    with pytest.raises(ValueError):
        Block(type="hack_warp")


def test_invalid_move_type_rejected():
    with pytest.raises(ValueError):
        Block(type="move", target_x=10, move_type="fly")


def test_from_dict_roundtrip():
    """config 직렬화 호환 — dict ↔ Block."""
    d = {"type": "move", "target_x": 50, "move_type": "teleport", "direction": "right"}
    b = Block.from_dict(d)
    assert b.target_x == 50
    assert b.to_dict()["move_type"] == "teleport"


def test_block_has_canvas_anchor_default_unplaced():
    from core.navigation.block import Block
    b = Block(type="attack")
    assert b.pos_x == -1 and b.pos_y == -1        # 기본 미배치


def test_block_from_dict_preserves_pos():
    from core.navigation.block import Block
    b = Block.from_dict({"type": "attack", "pos_x": 30, "pos_y": 40})
    assert (b.pos_x, b.pos_y) == (30, 40)
