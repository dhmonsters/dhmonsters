# 자동 하강 위치 선택 — 층구간 ∩ 밧줄제외 ∩ 몬스터 밀집 검증
from core.navigation.descend import pick_descend_x


def test_picks_densest_monster_cluster():
    """몬스터가 x≈300에 몰려 있으면 그 근처를 하강 지점으로."""
    xs = [298, 301, 305, 302, 80, 500]   # 300 부근 4마리 vs 산발
    x = pick_descend_x(0, 600, ladder_zones=[], monster_xs=xs, bucket_w=24)
    assert 296 <= x <= 306


def test_excludes_ladder_zone():
    """밧줄 구간(280~320)에 몬스터가 몰려도 그 구간은 하강 후보에서 제외."""
    xs = [300, 301, 299, 302, 150, 152, 148]   # 밧줄 위 4 vs 150부근 3
    x = pick_descend_x(0, 600, ladder_zones=[(280, 320)], monster_xs=xs, bucket_w=24)
    assert 145 <= x <= 155          # 밧줄 제외 → 150 군집 선택


def test_excludes_outside_floor_range():
    """층 구간 밖 몬스터는 무시."""
    xs = [700, 705, 710, 250, 255]  # 700대는 층 밖(층 0~400)
    x = pick_descend_x(0, 400, ladder_zones=[], monster_xs=xs, bucket_w=24)
    assert 248 <= x <= 257


def test_no_candidate_returns_none():
    """층 안·밧줄 밖 몬스터가 없으면 None(폴백은 호출측)."""
    xs = [300, 301]                 # 전부 밧줄 위
    assert pick_descend_x(0, 600, ladder_zones=[(280, 320)], monster_xs=xs) is None
    assert pick_descend_x(0, 600, ladder_zones=[], monster_xs=[]) is None


def test_swapped_floor_bounds_ok():
    """floor_min/max가 뒤집혀 들어와도 정상."""
    xs = [200, 202, 198]
    x = pick_descend_x(400, 0, ladder_zones=[], monster_xs=xs)
    assert 196 <= x <= 204
