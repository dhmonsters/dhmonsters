# 전역 노드 경로의 이동과 등록 액션 실행을 검증하는 테스트
from core.navigation.world_map import (
    ActionSpec,
    NavEdge,
    NavNode,
    WorldMapModel,
)
from core.navigation.world_runner import ActionExecutor, WorldRouteRunner


class FakeHumanizer:
    def __init__(self):
        self.intents = []

    def perform(self, intent):
        self.intents.append(intent)


class FakeBlockRunner:
    def __init__(self):
        self.calls = []

    def run_block(self, block, max_steps=200, arrival_tolerance=None):
        self.calls.append((block, arrival_tolerance))
        return True


class FakeActionExecutor:
    def __init__(self):
        self.specs = []

    def execute(self, spec):
        self.specs.append(spec)


def test_action_executor_repeats_through_humanizer():
    humanizer = FakeHumanizer()
    sleeps = []
    executor = ActionExecutor(humanizer, sleep_fn=sleeps.append)

    executor.execute(ActionSpec("up", 0.2, 2, 0.3, 1.0))

    assert [intent.key for intent in humanizer.intents] == ["up", "up"]
    assert sleeps == [0.3, 1.0]


def test_world_route_runs_registered_action_node_with_its_tolerance():
    action = ActionSpec("space", 0.1, 1, 0.0, 0.0)
    model = WorldMapModel(
        nodes={
            "a": NavNode("a", "waypoint", 10, 20),
            "b": NavNode("b", "action", 30, 20, 7, "", action),
        },
        edges=(NavEdge("e1", "a", "b", True, "walk"),),
    )
    blocks = FakeBlockRunner()
    actions = FakeActionExecutor()
    runner = WorldRouteRunner(model, blocks, actions)

    assert runner.navigate_to("a", "b") is True
    assert blocks.calls[0][1] == 7
    assert actions.specs == [action]


def test_world_route_rejects_unregistered_destination():
    model = WorldMapModel(nodes={"a": NavNode("a", "waypoint", 10, 20)})
    runner = WorldRouteRunner(model, FakeBlockRunner(), FakeActionExecutor())

    assert runner.navigate_to("a", "outside") is False
