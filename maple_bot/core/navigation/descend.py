# 자동 하강 위치 선택 — 층 x구간 안에서 밧줄구간을 제외하고 몬스터가 가장 밀집한 x를 고른다.
# 층별 반복 사냥에서 하강 지점을 명시하지 않았을 때 사용(B/C엔 없는 우리 신규 로직).
from __future__ import annotations


def _in_any_zone(x: int, zones: list[tuple[int, int]]) -> bool:
    """x가 (lo,hi) 구간들 중 하나에 속하면 True (밧줄 구간 제외용)."""
    return any(lo <= x <= hi for lo, hi in zones)


def pick_descend_x(floor_x_min: int, floor_x_max: int,
                   ladder_zones: list[tuple[int, int]],
                   monster_xs: list[int],
                   bucket_w: int = 24) -> int | None:
    """하강할 X를 고른다.

    floor_x_min~floor_x_max : 현재 층의 좌우 이동 구간
    ladder_zones            : 제외할 밧줄 X 구간 [(lo,hi), ...] (밧줄 위에선 안 내림)
    monster_xs              : 아래쪽에서 감지된 몬스터들의 X 목록
    bucket_w                : 밀집도 집계 버킷 폭(px)

    층 구간 안 + 밧줄 구간 밖의 몬스터들을 bucket_w 단위로 묶어 가장 많이 모인
    구간의 몬스터 평균 X를 반환. 후보가 없으면 None(호출측이 폴백 처리).
    """
    if floor_x_max < floor_x_min:
        floor_x_min, floor_x_max = floor_x_max, floor_x_min

    # 1) 층 구간 안 + 밧줄 구간 밖만 후보로
    cands = [x for x in monster_xs
             if floor_x_min <= x <= floor_x_max and not _in_any_zone(x, ladder_zones)]
    if not cands:
        return None

    # 2) 버킷별 집계 → 가장 몬스터 많은 버킷
    buckets: dict[int, list[int]] = {}
    for x in cands:
        buckets.setdefault((x - floor_x_min) // bucket_w, []).append(x)
    best = max(buckets.values(), key=len)   # 동률이면 먼저 채워진(왼쪽) 버킷

    # 3) 그 버킷 몬스터 평균 X (밧줄 구간이면 안전하게 후보 중앙값으로 한 번 더 거름)
    cx = round(sum(best) / len(best))
    if _in_any_zone(cx, ladder_zones):
        cx = sorted(best)[len(best) // 2]
    return cx
