# 다른 층으로 떨어졌을 때 그래프로 올바른 층에 복귀하는지 검증(엉뚱한 사다리 헛잡기 방지)
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner


class _Floor:
    def __init__(self, name): self.name = name


class _Judge:
    """y>=100 → 아래층(F0) / y<100 → 위층(F1)."""
    def floor_at(self, y):
        return _Floor("F0") if y is not None and y >= 100 else _Floor("F1")


def test_recover_uses_graph_ladder_when_on_wrong_floor():
    # 그래프: F0(아래)→F1(위)는 ladder_x=50 사다리로 연결
    via = {"type": "ladder", "ladder_x": 50, "y_top": 60, "y_bot": 110, "ladder_dir": "up"}
    graph = {"F0": [{"to": "F1", "via": via}], "F1": []}
    # 캐릭터는 y=110(F0, 아래층)에 떨어져 있음
    r = BlockRunner(humanizer=object(), pos_fn=lambda: (50, 110),
                    floor_judge=_Judge(), recovery_graph=graph)
    climbed = []
    r._do_ladder = lambda blk, ms: climbed.append(blk.ladder_x) or True

    # 블록: 위층(F1)에 있어야 하는 사다리(y_bot=60→F1). 캐릭은 F0 → 복귀 필요
    blk = Block(type="ladder", ladder_x=99, y_top=10, y_bot=60, ladder_dir="up")
    r._recover_if_needed(blk, max_steps=50)
    assert 50 in climbed   # 그래프의 복귀 사다리(ladder_x=50)를 타고 위층으로 복귀 시도


def test_no_recover_when_already_on_expected_floor():
    via = {"type": "ladder", "ladder_x": 50, "y_top": 60, "y_bot": 110, "ladder_dir": "up"}
    graph = {"F0": [{"to": "F1", "via": via}], "F1": []}
    r = BlockRunner(humanizer=object(), pos_fn=lambda: (50, 110),  # F0
                    floor_judge=_Judge(), recovery_graph=graph)
    climbed = []
    r._do_ladder = lambda blk, ms: climbed.append(blk.ladder_x) or True
    # 사다리 바닥이 F0(y_bot=110)인 블록 → 기대층=F0=현재층 → 복귀 안 함
    blk = Block(type="ladder", ladder_x=50, y_top=60, y_bot=110, ladder_dir="up")
    r._recover_if_needed(blk, max_steps=50)
    assert climbed == []
