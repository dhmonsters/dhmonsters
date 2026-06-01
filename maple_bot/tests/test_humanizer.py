# Humanizer의 타이밍 변형이 '사람같은' 분포를 만드는지 통계적으로 검증
import statistics
import pytest

from core.humanize.intent import Intent, RiskProfile
from core.humanize.humanizer import Humanizer


class RecordingBackend:
    """송출된 (key, hold_sec) 와 sleep 호출을 기록하는 가짜 백엔드."""
    name = "recording"

    def __init__(self):
        self.presses = []
        self.downs = []
        self.ups = []

    def key_down(self, key): self.downs.append(key)
    def key_up(self, key): self.ups.append(key)
    def press(self, key, hold_sec=0.05): self.presses.append((key, hold_sec))
    def is_available(self): return True


@pytest.fixture
def rec():
    return RecordingBackend()


def test_perform_key_routes_to_backend(rec):
    """key 의도 → 백엔드 press 호출."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    h.perform(Intent(action="key", key="ctrl", base_hold_sec=0.05))
    assert len(rec.presses) == 1
    assert rec.presses[0][0] == "ctrl"


def test_hold_sec_is_jittered_not_constant(rec):
    """동일 base_hold_sec 를 여러 번 입력해도 실제 hold 는 매번 달라야(비균일) 한다."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    for _ in range(30):
        h.perform(Intent(action="key", key="a", base_hold_sec=0.10))
    holds = [p[1] for p in rec.presses]
    # 30회 중 고유값이 충분히 많아야(=고정상수가 아님)
    assert len(set(holds)) >= 25
    # 평균은 base 근처지만 정확히 같지는 않음
    assert 0.06 < statistics.mean(holds) < 0.16


def test_jitter_stays_in_reasonable_bounds(rec):
    """지터가 폭주하지 않음 — base의 합리적 배수 안."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    for _ in range(50):
        h.perform(Intent(action="key", key="a", base_hold_sec=0.10))
    holds = [p[1] for p in rec.presses]
    assert all(0.03 <= x <= 0.30 for x in holds)


def test_careful_profile_slower_than_fast(rec):
    """careful 프로파일이 fast 보다 평균적으로 느림(딜레이 큼)."""
    sleeps = []
    h = Humanizer(backend=rec, sleep_fn=lambda s: sleeps.append(s))

    careful = [h.reaction_delay(RiskProfile.CAREFUL) for _ in range(200)]
    fast = [h.reaction_delay(RiskProfile.FAST) for _ in range(200)]
    assert statistics.mean(careful) > statistics.mean(fast)


def test_hold_intent_uses_key_down_up(rec):
    """hold 의도는 key_down 만(누른 상태 유지)."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    h.perform(Intent(action="hold", key="right"))
    assert rec.downs == ["right"]
