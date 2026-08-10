# 등록된 전역 이동 간선만 사용해 노드 사이 최단 경로를 계산하는 그래프
from collections import deque
from dataclasses import replace


def _reverse_edge(edge):
    ladder = dict(edge.ladder) if edge.ladder else None
    if ladder and "direction" in ladder:
        ladder["direction"] = "down" if ladder["direction"] == "up" else "up"
    return replace(
        edge,
        from_id=edge.to_id,
        to_id=edge.from_id,
        ladder=ladder,
    )


def shortest_edge_path(edges, start_id: str, goal_id: str):
    if start_id == goal_id:
        return []
    graph = {}
    for edge in edges:
        graph.setdefault(edge.from_id, []).append(edge)
        if edge.bidirectional:
            graph.setdefault(edge.to_id, []).append(_reverse_edge(edge))
    queue = deque([(start_id, [])])
    seen = {start_id}
    while queue:
        node_id, path = queue.popleft()
        for edge in graph.get(node_id, []):
            if edge.to_id in seen:
                continue
            next_path = path + [edge]
            if edge.to_id == goal_id:
                return next_path
            seen.add(edge.to_id)
            queue.append((edge.to_id, next_path))
    return None
