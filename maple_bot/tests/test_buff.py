# BuffManager — 주기 버프(일반/토글) + 모션캔슬 대기. Humanizer 경유
import pytest
from core.acting.buff import BuffManager, Buff


class FakeHumanizer:
    def __init__(self): self.intents = []
    def perform(self, i): self.intents.append(i)


def test_buff_fires_when_interval_elapsed():
    h = FakeHumanizer()
    bm = BuffManager(humanizer=h, buffs=[Buff(key="1", interval=60)])
    bm.tick(now=100.0)  # 최초 발동
    assert any(i.key == "1" for i in h.intents)


def test_buff_respects_interval():
    h = FakeHumanizer()
    bm = BuffManager(humanizer=h, buffs=[Buff(key="1", interval=60)])
    bm.tick(now=100.0)
    n1 = len(h.intents)
    bm.tick(now=130.0)   # 아직 60초 안 지남
    assert len(h.intents) == n1
    bm.tick(now=161.0)   # 60초 경과
    assert len(h.intents) > n1


def test_disabled_buff_skipped():
    h = FakeHumanizer()
    bm = BuffManager(humanizer=h, buffs=[Buff(key="", interval=60)])  # 키 없음=비활성
    bm.tick(now=100.0)
    assert len(h.intents) == 0


def test_multiple_buffs_staggered():
    h = FakeHumanizer()
    bm = BuffManager(humanizer=h, buffs=[
        Buff(key="1", interval=60),
        Buff(key="2", interval=120),
    ], gap=1.2)
    # 동시 발동 방지: 한 틱에 하나씩, gap 간격으로 발동
    bm.tick(now=100.0)
    assert {i.key for i in h.intents} == {"1"}        # 버프1만
    bm.tick(now=100.5)                                # gap 전 → 추가 없음
    assert {i.key for i in h.intents} == {"1"}
    bm.tick(now=101.5)                                # gap 경과 → 버프2
    assert {i.key for i in h.intents} == {"1", "2"}
