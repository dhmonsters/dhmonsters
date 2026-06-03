# 루트 블록(move)의 Y를 근접 클러스터링해 층 밴드(Floor)를 자동 추출 — 복귀 그래프용
from __future__ import annotations

from core.navigation.floor_judge import Floor


def floors_from_route(route: list[dict], band: int = 12) -> list[Floor]:
    """move 블록의 pos_y(미니맵 px)를 band 간격으로 클러스터링해 Floor 리스트 생성.

    band: 같은 층으로 묶을 Y 허용 간격(px). 각 층은 [min-band, max+band] 범위로
    여유를 둬 사다리 끝점(y_top/y_bot)이 인접 층에 포함되도록 한다.
    미배치(pos_y<0)·비 move 블록은 무시. 빈 입력이면 []."""
    ys = sorted({int(b["pos_y"]) for b in route
                 if b.get("type") == "move" and int(b.get("pos_y", -1)) >= 0})
    if not ys:
        return []
    clusters: list[list[int]] = [[ys[0]]]
    for y in ys[1:]:
        if y - clusters[-1][-1] <= band:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    floors: list[Floor] = []
    for i, cl in enumerate(clusters):
        floors.append(Floor(name=f"F{i}", y_min=min(cl) - band, y_max=max(cl) + band))
    return floors
