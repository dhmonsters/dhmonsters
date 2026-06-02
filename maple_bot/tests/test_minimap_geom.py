# 미니맵↔캔버스 좌표 변환 + 범위 환산 + 추적 상태 순수 함수 검증
from core_ui.minimap_geom import (
    minimap_to_canvas, screen_px_to_minimap_px, char_track_state,
)


def test_minimap_to_canvas_zoom_and_pan():
    assert minimap_to_canvas(10, 20, 1.0) == (10, 20)
    assert minimap_to_canvas(10, 20, 2.0) == (20, 40)
    assert minimap_to_canvas(10, 20, 2.0, pan=(5, -3)) == (25, 37)


def test_screen_px_to_minimap_px_proportional():
    # factor = camera_w_ratio*minimap_w/screen_w = 0.5*200/1000 = 0.1
    assert screen_px_to_minimap_px(35, 200, 1000, 0.5) == 3.5
    assert screen_px_to_minimap_px(70, 200, 1000, 0.5) == 7.0   # 2배 입력→2배 출력


def test_screen_px_to_minimap_px_guards_zero_screen():
    assert screen_px_to_minimap_px(35, 200, 0, 0.5) == 0.0


def test_char_track_state_thresholds():
    # 미검출 경과시간(초) → 추적 상태
    assert char_track_state(0.0) == "tracking"
    assert char_track_state(0.9) == "tracking"
    assert char_track_state(1.0) == "lost"      # 경계: lost_after 이상
    assert char_track_state(2.5) == "lost"
    assert char_track_state(3.0) == "stale"     # 경계: stale_after 이상
    assert char_track_state(10.0) == "stale"


def test_char_track_state_custom_thresholds():
    assert char_track_state(0.4, lost_after=0.5, stale_after=2.0) == "tracking"
    assert char_track_state(1.0, lost_after=0.5, stale_after=2.0) == "lost"
    assert char_track_state(2.0, lost_after=0.5, stale_after=2.0) == "stale"


def test_canvas_to_minimap_roundtrip():
    from core_ui.minimap_geom import minimap_to_canvas, canvas_to_minimap
    cx, cy = minimap_to_canvas(37, 21, 2.0, pan=(5, -3))
    assert canvas_to_minimap(cx, cy, 2.0, pan=(5, -3)) == (37, 21)


def test_block_color_move_vs_teleport():
    from core_ui.minimap_geom import block_color, BLOCK_COLORS
    assert block_color({"type": "move"}) == BLOCK_COLORS["move"]
    assert block_color({"type": "move", "move_type": "teleport"}) == BLOCK_COLORS["teleport"]
    assert block_color({"type": "attack"}) == BLOCK_COLORS["attack"]


def test_block_anchor_by_type_and_unplaced():
    from core_ui.minimap_geom import block_anchor
    assert block_anchor({"type": "attack", "pos_x": 30, "pos_y": 40}) == (30, 40)
    assert block_anchor({"type": "attack", "pos_x": -1, "pos_y": -1}) is None
    assert block_anchor({"type": "ladder", "ladder_x": 450, "y_bot": 180}) == (450, 180)
    assert block_anchor({"type": "ladder", "ladder_x": 0, "y_bot": 0}) is None


def test_hit_test_nearest_and_skips_unplaced():
    from core_ui.minimap_geom import hit_test
    blocks = [
        {"type": "attack", "pos_x": 100, "pos_y": 100},
        {"type": "attack", "pos_x": -1, "pos_y": -1},      # 미배치 → 제외
        {"type": "attack", "pos_x": 105, "pos_y": 102},
    ]
    assert hit_test(blocks, 104, 101, radius=10) == 2       # 가장 가까운 것
    assert hit_test(blocks, 300, 300, radius=10) is None    # 반경 밖


def test_seed_block_at_seeds_type_fields():
    from core_ui.minimap_geom import seed_block_at
    m = seed_block_at("move", 70, 40)
    assert m["type"] == "move" and m["pos_x"] == 70 and m["pos_y"] == 40
    assert m["start_x"] == 70 and m["end_x"] == 70
    la = seed_block_at("ladder", 55, 88)
    assert la["type"] == "ladder" and la["ladder_x"] == 55 and la["y_bot"] == 88
    tp = seed_block_at("teleport", 12, 13)
    assert tp["type"] == "move" and tp["move_type"] == "teleport" and tp["pos_x"] == 12


def test_translate_block_moves_pos_and_type_fields_immutable():
    from core_ui.minimap_geom import translate_block
    src = {"type": "move", "pos_x": 10, "pos_y": 20, "start_x": 10, "end_x": 90}
    out = translate_block(src, 5, 3)
    assert out["pos_x"] == 15 and out["pos_y"] == 23
    assert out["start_x"] == 15 and out["end_x"] == 95
    assert src["pos_x"] == 10                                # 원본 불변
    lad = translate_block({"type": "ladder", "pos_x": -1, "pos_y": -1,
                           "ladder_x": 100, "y_top": 10, "y_bot": 50}, 5, 3)
    assert lad["ladder_x"] == 105 and lad["y_top"] == 13 and lad["y_bot"] == 53
    assert lad["pos_x"] == -1                                # 미배치 pos는 그대로
