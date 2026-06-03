# PotionManager — 임계 미만 시 키 입력 + 실측 비율 진단 로그 throttle 검증
from core.potion_manager import PotionManager


class _Detector:
    def __init__(self, hp=1.0, mp=1.0):
        self.hp, self.mp = hp, mp

    def hp_ratio(self):
        return self.hp

    def mp_ratio(self):
        return self.mp


class _Input:
    def __init__(self):
        self.presses = []

    def press_key(self, key, hold_sec=0.05):
        self.presses.append(key)


def _mgr(hp=1.0, mp=1.0, msgs=None):
    inp = _Input()
    pm = PotionManager(inp, _Detector(hp, mp), on_status=(msgs.append if msgs is not None else None))
    pm.set_config(
        {"enabled": True, "threshold": 65, "key": "pgup", "cooldown_sec": 1.0},
        {"enabled": True, "threshold": 50, "key": "pgdn", "cooldown_sec": 1.0},
    )
    return pm, inp


def test_fires_when_below_threshold():
    pm, inp = _mgr(hp=0.40, mp=1.0)   # HP 40% < 65% → 발동, MP 100% → 미발동
    pm.check_and_use()
    assert inp.presses == ["pgup"]


def test_no_fire_when_full():
    pm, inp = _mgr(hp=1.0, mp=1.0)
    pm.check_and_use()
    assert inp.presses == []


def test_disabled_does_nothing():
    inp = _Input()
    pm = PotionManager(inp, _Detector(0.1, 0.1))
    pm.set_config({"enabled": False}, {"enabled": False})
    pm.check_and_use()
    assert inp.presses == []


def test_diagnostic_logs_measured_ratio():
    msgs = []
    pm, _ = _mgr(hp=1.0, mp=1.0, msgs=msgs)
    pm.check_and_use()
    # 포션은 안 나가도 실측 비율 진단 로그는 떠야 한다(왜 안 나가는지 가시화)
    assert any("HP 100%" in m for m in msgs)
    assert any("MP 100%" in m for m in msgs)


def test_diagnostic_is_throttled():
    msgs = []
    pm, _ = _mgr(hp=1.0, mp=1.0, msgs=msgs)
    pm.check_and_use()
    pm.check_and_use()          # 곧바로 다시 호출 → throttle 로 추가 로그 없음
    hp_logs = [m for m in msgs if "HP 100%" in m]
    assert len(hp_logs) == 1
