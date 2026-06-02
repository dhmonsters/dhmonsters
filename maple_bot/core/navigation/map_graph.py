# 동선 사다리에서 층 인접그래프 구성 + 최단경로(복귀용). 순수 로직, 런타임 의존 없음
from __future__ import annotations

from collections import deque


def expected_floor(block: dict, judge) -> str | None:
    """블록이 실행돼야 하는 층 이름. ladder는 아래층(y_bot), 그 외는 pos_y로 판정.
    미배치(pos_y<0)나 층 밖이면 None. judge는 floor_at(y)->Floor|None."""
    if block.get("type") == "ladder":
        yb = int(block.get("y_bot", 0))
        f = judge.floor_at(yb) if yb > 0 else None
        return f.name if f is not None else None
    py = int(block.get("pos_y", -1))
    if py < 0:
        return None
    f = judge.floor_at(py)
    return f.name if f is not None else None


def build_graph(floors: list, route: list[dict], judge) -> dict[str, list[dict]]:
    """route의 ladder 블록마다 floor_at(y_bot)=아래층, floor_at(y_top)=위층을 찾아
    양방향 간선 추가. 간선 = {"to": 이웃층, "via": 방향보정된 ladder 블록}.
    층 밖(None)이거나 같은 층(자기루프)이면 건너뜀."""
    graph: dict[str, list[dict]] = {getattr(f, "name", str(f)): [] for f in floors}
    for b in route:
        if b.get("type") != "ladder":
            continue
        yb, yt = int(b.get("y_bot", 0)), int(b.get("y_top", 0))
        fa = judge.floor_at(yb) if yb > 0 else None   # 아래층
        fb = judge.floor_at(yt) if yt > 0 else None   # 위층
        if fa is None or fb is None or fa.name == fb.name:
            continue
        up = dict(b); up["ladder_dir"] = "up"          # 아래→위
        down = dict(b); down["ladder_dir"] = "down"    # 위→아래
        graph.setdefault(fa.name, []).append({"to": fb.name, "via": up})
        graph.setdefault(fb.name, []).append({"to": fa.name, "via": down})
    return graph


def shortest_path(graph: dict, start: str, goal: str) -> list[dict] | None:
    """start→goal 최단경로(간선 수)의 via(ladder 블록) 리스트. 같은 층이면 [],
    경로 없으면 None."""
    if start == goal:
        return []
    q = deque([(start, [])])
    seen = {start}
    while q:
        node, path = q.popleft()
        for edge in graph.get(node, []):
            nxt = edge["to"]
            if nxt in seen:
                continue
            npath = path + [edge["via"]]
            if nxt == goal:
                return npath
            seen.add(nxt)
            q.append((nxt, npath))
    return None
