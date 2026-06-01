# BlockRunner — walk/teleport 거리폴백 + TOLERANCE 폐루프 + Humanizer 경유 검증
import pytest
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner, TOLERANCE, TELEPORT_MIN_DIST


class FakeHumanizer:
    """perform(Intent) 호출을 기록 — 모든 입력이 Humanizer 경유하는지 검증."""
    def __init__(self):
        self.intents = []
    def perform(self, intent):
        self.intents.append(intent)


class MovingChar:
    """step마다 목표 쪽으로 일정량 이동하는 모의 캐릭터(위치 콜백)."""
    def __init__(self, start_x, speed=10):
        self.x = start_x
        self.speed = speed
        self.target = None
    def pos(self):
        # 목표를 향해 한 스텝 이동(테스트용 물리)
        if self.target is not None:
            if abs(self.x - self.target) <= self.speed:
                self.x = self.target
            elif self.x < self.target:
                self.x += self.speed
            else:
                self.x -= self.speed
        return (self.x, 75)


def test_walk_to_near_target_uses_humanizer():
    """가까운 목표(≤15px)는 walk — Humanizer로 방향키 입력.
    speed보다 큰 거리로 시작해 최소 1회 이동(입력)이 일어나게 한다."""
    h = FakeHumanizer()
    char = MovingChar(start_x=18, speed=5); char.target = 30  # 거리 12 → walk, 여러스텝
    runner = BlockRunner(humanizer=h, pos_fn=char.pos)
    runner.run_block(Block(type="move", target_x=30), max_steps=50)
    # 도착했고, Humanizer를 통해 입력이 나갔다
    assert abs(char.x - 30) <= TOLERANCE
    assert len(h.intents) > 0
    # walk면 방향키(left/right) intent가 있어야
    assert any(i.key in ("left", "right") for i in h.intents)


def test_teleport_for_far_target():
    """먼 목표(>15px)는 teleport 키 사용."""
    h = FakeHumanizer()
    char = MovingChar(start_x=10, speed=20); char.target = 80  # 거리 70 → teleport
    runner = BlockRunner(humanizer=h, pos_fn=char.pos)
    runner.run_block(Block(type="move", target_x=80, move_type="teleport"), max_steps=50)
    # teleport 키(space 등)가 입력됐는지
    assert any(i.key == "space" for i in h.intents)


def test_arrives_within_tolerance():
    """TOLERANCE 이내 도달하면 멈춤(폐루프)."""
    h = FakeHumanizer()
    char = MovingChar(start_x=0); char.target = 50
    runner = BlockRunner(humanizer=h, pos_fn=char.pos)
    arrived = runner.run_block(Block(type="move", target_x=50), max_steps=100)
    assert arrived is True
    assert abs(char.x - 50) <= TOLERANCE


def test_gives_up_after_max_steps():
    """위치가 안 변하면(끼임) max_steps 후 포기(무한루프 방지)."""
    h = FakeHumanizer()
    class StuckChar:
        def pos(self): return (0, 75)  # 절대 안 움직임
    runner = BlockRunner(humanizer=h, pos_fn=StuckChar().pos)
    arrived = runner.run_block(Block(type="move", target_x=50), max_steps=10)
    assert arrived is False


def test_all_input_goes_through_humanizer():
    """헌법: 모든 입력은 Humanizer 경유 — runner는 직접 키 송출 안 함."""
    h = FakeHumanizer()
    char = MovingChar(start_x=20); char.target = 30
    runner = BlockRunner(humanizer=h, pos_fn=char.pos)
    runner.run_block(Block(type="move", target_x=30), max_steps=50)
    # runner가 backend를 직접 들고있지 않음(humanizer만)
    assert not hasattr(runner, "_backend")
