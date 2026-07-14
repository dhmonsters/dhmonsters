# 전역 노드 경로를 기존 이동기와 등록된 제한 액션으로 실행하는 조정기
import time

from core.humanize.intent import Intent
from core.navigation.block import Block
from core.navigation.world_graph import shortest_edge_path


class ActionExecutor:
    def __init__(self, humanizer, sleep_fn=time.sleep):
        self._humanizer = humanizer
        self._sleep = sleep_fn

    def execute(self, spec) -> None:
        for index in range(spec.repeat):
            self._humanizer.perform(Intent(
                action="key",
                key=spec.key,
                base_hold_sec=spec.hold_sec,
            ))
            if index + 1 < spec.repeat and spec.repeat_interval_sec > 0:
                self._sleep(spec.repeat_interval_sec)
        if spec.wait_after_sec > 0:
            self._sleep(spec.wait_after_sec)


class WorldRouteRunner:
    def __init__(self, model, block_runner, action_executor):
        self._model = model
        self._blocks = block_runner
        self._actions = action_executor

    def _run_edge(self, edge, target) -> bool:
        if edge.traversal in {"walk", "teleport"}:
            block = Block(
                type="move",
                target_x=int(target.x),
                move_type=edge.traversal,
            )
        else:
            data = dict(edge.ladder or {})
            block = Block(
                type="ladder",
                ladder_x=int(data["x"]),
                y_top=int(data["y_top"]),
                y_bot=int(data["y_bot"]),
                ladder_dir=data["direction"],
                exit_side=data["exit_side"],
                grab_side=data["grab_side"],
                jump_offset=int(data["jump_offset"]),
            )
        return self._blocks.run_block(
            block,
            arrival_tolerance=target.arrival_radius,
        )

    def run_node_path(self, node_ids) -> bool:
        for left, right in zip(node_ids, node_ids[1:]):
            edges = shortest_edge_path(self._model.edges, left, right)
            if edges is None:
                return False
            for edge in edges:
                target = self._model.nodes.get(edge.to_id)
                if target is None or not self._run_edge(edge, target):
                    return False
                if target.kind == "action":
                    self._actions.execute(target.action)
        return True

    def navigate_to(self, start_id: str, goal_id: str) -> bool:
        if start_id not in self._model.nodes or goal_id not in self._model.nodes:
            return False
        path = shortest_edge_path(self._model.edges, start_id, goal_id)
        if path is None:
            return False
        return self.run_node_path([start_id] + [edge.to_id for edge in path])
