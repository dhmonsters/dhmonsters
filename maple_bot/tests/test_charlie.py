# CharlieExchange — 찰리중사 이빨 교환 시퀀스(구매 제외). Humanizer 경유 + 반복횟수 계산
import pytest
from core.acting.charlie import CharlieExchange
from core.humanize.intent import Intent


class FakeHumanizer:
    def __init__(self): self.intents = []
    def perform(self, i): self.intents.append(i)


def test_repeat_count_from_tooth_amount():
    """반복 횟수 = 보유 이빨 // 200 (1루틴=200개 소비)."""
    assert CharlieExchange.repeat_count(tooth_amount=1000) == 5
    assert CharlieExchange.repeat_count(tooth_amount=450) == 2
    assert CharlieExchange.repeat_count(tooth_amount=199) == 0


def test_one_routine_sequence():
    """1루틴 시퀀스: NPC키→NPC키→아래15회→NPC키→왼쪽1회→NPC키→NPC키."""
    h = FakeHumanizer()
    ex = CharlieExchange(humanizer=h, npc_key="u")
    ex.run_one_routine()
    keys = [i.key for i in h.intents]
    # NPC키(u)가 여러 번, 아래(down) 15회, 왼쪽(left) 1회 포함
    assert keys.count("down") == 15
    assert keys.count("left") == 1
    assert keys.count("u") >= 4   # 대화 진행용 NPC키 다수


def test_run_exchanges_repeats_by_amount():
    """보유량에 따라 루틴 반복."""
    h = FakeHumanizer()
    ex = CharlieExchange(humanizer=h, npc_key="u")
    ex.run(tooth_amount=600)   # 3회
    # down 키가 15*3=45회
    assert sum(1 for i in h.intents if i.key == "down") == 45


def test_no_run_when_insufficient():
    """200개 미만이면 교환 안 함."""
    h = FakeHumanizer()
    ex = CharlieExchange(humanizer=h, npc_key="u")
    ex.run(tooth_amount=150)
    assert len(h.intents) == 0


def test_all_input_via_humanizer():
    """헌법: 모든 입력 Humanizer 경유."""
    h = FakeHumanizer()
    ex = CharlieExchange(humanizer=h, npc_key="u")
    ex.run_one_routine()
    assert all(isinstance(i, Intent) for i in h.intents)
