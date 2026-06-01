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


# ── 이동키 유지/해제 (좌우 이동은 항상 키다운, 전환·공격때만 뗌) ──────────
def test_hold_dir_presses_once_and_maintains(rec):
    """같은 방향 hold_dir 여러 번 → key_down 1회뿐, 유지(중간 key_up/press 없음)."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    for _ in range(5):
        h.hold_dir("right")
    assert rec.downs == ["right"]   # 딱 한 번만 누름
    assert rec.ups == []            # 유지 중엔 안 뗌
    assert rec.presses == []        # 톡톡 탭 아님
    assert h.held_dir() == "right"


def test_hold_dir_flip_releases_old_presses_new(rec):
    """방향 전환 → 기존 키 떼고(key_up) 새 키 누름(key_down)."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    h.hold_dir("right")
    h.hold_dir("left")
    assert rec.downs == ["right", "left"]
    assert rec.ups == ["right"]     # 전환 때 기존 방향만 뗌
    assert h.held_dir() == "left"


def test_release_dir_releases_held(rec):
    """release_dir → 유지 키 뗌. 다시 호출해도 추가 key_up 없음(멱등)."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    h.hold_dir("right")
    h.release_dir()
    assert rec.ups == ["right"]
    assert h.held_dir() is None
    h.release_dir()                 # 이미 뗀 상태
    assert rec.ups == ["right"]     # 변화 없음


def test_jitter_sec_within_spread_and_varies(rec):
    """고정 타이밍 → ±0.05 범위, 소수점 둘째자리, 매번 다름(고정 아님)."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    vals = [h.jitter_sec(0.5) for _ in range(60)]
    assert all(0.45 <= v <= 0.55 for v in vals)   # ±0.05 범위
    assert len(set(vals)) >= 5                     # 고정값 아님
    assert all(abs(v * 100 - round(v * 100)) < 1e-9 for v in vals)  # 둘째자리


def test_jitter_sec_no_negative(rec):
    """작은 base여도 음수로 안 감."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    assert all(h.jitter_sec(0.02) >= 0.0 for _ in range(60))


def test_jitter_sec_small_value_fine_grained(rec):
    """폴링처럼 작은 값(0.05)은 ±0.005 넷째자리 랜덤 — 0이나 2배로 튀지 않음."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    vals = [h.jitter_sec(0.05) for _ in range(80)]
    assert all(0.045 <= v <= 0.055 for v in vals)   # ±0.005 (둘째단위 값 → 넷째자리 범위)
    assert len(set(vals)) >= 5                        # 고정 아님
    assert all(abs(v * 10000 - round(v * 10000)) < 1e-6 for v in vals)  # 넷째자리


def test_random_side_returns_left_or_right(rec):
    """밧줄 좌우 랜덤 — left/right 중 하나, 양쪽 다 나옴."""
    h = Humanizer(backend=rec, sleep_fn=lambda s: None)
    sides = {h.random_side() for _ in range(40)}
    assert sides <= {"left", "right"}
    assert len(sides) == 2     # 양쪽 모두 등장
