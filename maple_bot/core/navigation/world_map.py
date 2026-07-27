from __future__ import annotations
# 큰 지도 절대좌표와 보정·이동 노드 데이터를 정의하는 순수 모델
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorldPoint:
    x: float
    y: float


@dataclass(frozen=True)
class Calibration:
    scale: float
    offset_x: float
    offset_y: float

    def local_to_world(self, point: WorldPoint) -> WorldPoint:
        return WorldPoint(
            self.offset_x + point.x * self.scale,
            self.offset_y + point.y * self.scale,
        )

    def world_to_local(self, point: WorldPoint) -> WorldPoint:
        return WorldPoint(
            (point.x - self.offset_x) / self.scale,
            (point.y - self.offset_y) / self.scale,
        )


def calibrate_two_points(
    world_a: WorldPoint,
    world_b: WorldPoint,
    local_a: WorldPoint,
    local_b: WorldPoint,
    min_local_distance: float = 20.0,
    max_angle_deg: float = 3.0,
) -> Calibration:
    wdx, wdy = world_b.x - world_a.x, world_b.y - world_a.y
    ldx, ldy = local_b.x - local_a.x, local_b.y - local_a.y
    wd, ld = math.hypot(wdx, wdy), math.hypot(ldx, ldy)
    if ld < min_local_distance or wd <= 0:
        raise ValueError("기준점 거리가 너무 짧습니다")
    cos_angle = (wdx * ldx + wdy * ldy) / (wd * ld)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_angle))))
    if angle > max_angle_deg:
        raise ValueError("두 좌표계의 기준점 방향이 다릅니다")
    scale = wd / ld
    return Calibration(
        scale=scale,
        offset_x=world_a.x - local_a.x * scale,
        offset_y=world_a.y - local_a.y * scale,
    )


@dataclass(frozen=True)
class ActionSpec:
    key: str
    hold_sec: float
    repeat: int
    repeat_interval_sec: float
    wait_after_sec: float
    action_type: str = "key"
    click_x: int | None = None
    click_y: int | None = None

    def __post_init__(self) -> None:
        if self.action_type not in {"key", "click"}:
            raise ValueError("action_type은 key 또는 click이어야 합니다")
        if self.action_type == "click" and (self.click_x is None or self.click_y is None):
            raise ValueError("마우스 클릭 액션에는 화면 X/Y 좌표가 필요합니다")
        if self.action_type == "key" and not self.key.strip():
            raise ValueError("action key는 비어 있을 수 없습니다")
        if self.repeat < 1:
            raise ValueError("repeat는 1 이상이어야 합니다")
        if min(self.hold_sec, self.repeat_interval_sec, self.wait_after_sec) < 0:
            raise ValueError("action 시간은 음수일 수 없습니다")


@dataclass(frozen=True)
class NavNode:
    id: str
    kind: str
    x: float
    y: float
    arrival_radius: float = 4.0
    label: str = ""
    action: ActionSpec | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"waypoint", "action"}:
            raise ValueError("node kind는 waypoint 또는 action이어야 합니다")
        if self.kind == "action" and self.action is None:
            raise ValueError("action 노드에는 action 설정이 필요합니다")


        if self.kind != "action" and self.action is not None:
            raise ValueError("action 설정은 action 노드에만 사용할 수 있습니다")


@dataclass(frozen=True)
class NavEdge:
    id: str
    from_id: str
    to_id: str
    bidirectional: bool
    traversal: str
    ladder: dict | None = None

    def __post_init__(self) -> None:
        if self.traversal not in {"walk", "teleport", "ladder"}:
            raise ValueError("지원하지 않는 traversal입니다")
        if self.traversal == "ladder" and not self.ladder:
            raise ValueError("ladder 연결에는 ladder 설정이 필요합니다")


@dataclass(frozen=True)
class NavRoute:
    id: str
    name: str
    node_ids: tuple[str, ...]
    loop: bool = True


@dataclass
class WorldMapModel:
    enabled: bool = False
    image_path: str = ""
    image_width: int = 0
    image_height: int = 0
    tracking_policy: str = "continue_estimated"
    calibration: Calibration | None = None
    nodes: dict[str, NavNode] = field(default_factory=dict)
    edges: tuple[NavEdge, ...] = ()
    routes: dict[str, NavRoute] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "WorldMapModel":
        world = data.get("world_map", data)
        navigation = data.get("navigation", {})
        calibration_data = world.get("calibration")
        calibration = None
        if calibration_data:
            offset = calibration_data.get("offset", [0.0, 0.0])
            calibration = Calibration(
                float(calibration_data["scale"]),
                float(offset[0]),
                float(offset[1]),
            )
        nodes = {}
        for item in navigation.get("nodes", []):
            action_data = item.get("action")
            action = ActionSpec(**action_data) if action_data else None
            node = NavNode(
                id=item["id"],
                kind=item["kind"],
                x=float(item["x"]),
                y=float(item["y"]),
                arrival_radius=float(item.get("arrival_radius", 4.0)),
                label=item.get("label", ""),
                action=action,
            )
            nodes[node.id] = node
        edges = tuple(NavEdge(**item) for item in navigation.get("edges", []))
        routes = {}
        for item in navigation.get("routes", []):
            route = NavRoute(
                id=item["id"],
                name=item["name"],
                node_ids=tuple(item.get("node_ids", [])),
                loop=bool(item.get("loop", True)),
            )
            routes[route.id] = route
        return cls(
            enabled=bool(world.get("enabled", False)),
            image_path=world.get("image_path", ""),
            image_width=int(world.get("image_width", 0)),
            image_height=int(world.get("image_height", 0)),
            tracking_policy=world.get("tracking_policy", "continue_estimated"),
            calibration=calibration,
            nodes=nodes,
            edges=edges,
            routes=routes,
        )

    def to_dict(self) -> dict:
        calibration = None
        if self.calibration is not None:
            calibration = {
                "scale": self.calibration.scale,
                "offset": [self.calibration.offset_x, self.calibration.offset_y],
            }
        nodes = []
        for node in self.nodes.values():
            action = None
            if node.action is not None:
                action = {
                    "key": node.action.key,
                    "hold_sec": node.action.hold_sec,
                    "repeat": node.action.repeat,
                    "repeat_interval_sec": node.action.repeat_interval_sec,
                    "wait_after_sec": node.action.wait_after_sec,
                }
            nodes.append({
                "id": node.id,
                "kind": node.kind,
                "x": node.x,
                "y": node.y,
                "arrival_radius": node.arrival_radius,
                "label": node.label,
                "action": action,
            })
        edges = [{
            "id": edge.id,
            "from_id": edge.from_id,
            "to_id": edge.to_id,
            "bidirectional": edge.bidirectional,
            "traversal": edge.traversal,
            "ladder": edge.ladder,
        } for edge in self.edges]
        routes = [{
            "id": route.id,
            "name": route.name,
            "node_ids": list(route.node_ids),
            "loop": route.loop,
        } for route in self.routes.values()]
        return {
            "world_map": {
                "enabled": self.enabled,
                "image_path": self.image_path,
                "image_width": self.image_width,
                "image_height": self.image_height,
                "tracking_policy": self.tracking_policy,
                "calibration": calibration,
            },
            "navigation": {
                "nodes": nodes,
                "edges": edges,
                "routes": routes,
            },
        }
