# 공격범위 드래그 → 캐릭(기준점) 상대 오프셋 환산 검증
from core_ui.shot_selector import rect_to_offsets, offsets_to_rect


def test_rect_to_offsets_centered():
    """기준점(앵커) 기준 박스 → 좌우/상하 오프셋."""
    # 앵커(300,200), 박스 left=265,top=130,w=70,h=140 → x_min=-35,x_max=35,y_min=-70,y_max=70
    o = rect_to_offsets(265, 130, 70, 140, anchor=(300, 200))
    assert o == (-35, 35, -70, 70)


def test_offsets_to_rect_roundtrip():
    """오프셋 → 박스 (역변환). 기존 범위 미리보기용."""
    r = offsets_to_rect(-35, 35, -70, 70, anchor=(300, 200))
    assert r == (265, 130, 70, 140)   # (left, top, w, h)


def test_roundtrip_consistency():
    anchor = (500, 400)
    o = rect_to_offsets(450, 320, 120, 200, anchor=anchor)
    r = offsets_to_rect(*o, anchor=anchor)
    assert r == (450, 320, 120, 200)
