# Intent 데이터클래스의 필드·기본값·검증을 테스트
import pytest
from core.humanize.intent import Intent, RiskProfile


def test_intent_minimal_key_press():
    """키 입력 의도 — 최소 필드."""
    it = Intent(action="key", key="ctrl")
    assert it.action == "key"
    assert it.key == "ctrl"
    assert it.risk_profile == RiskProfile.NORMAL  # 기본값


def test_intent_hold_with_base_timing():
    """홀드 의도 — base 타이밍은 '의도값'일 뿐, 실제 변형은 Humanizer가."""
    it = Intent(action="hold", key="right", base_hold_sec=0.5)
    assert it.base_hold_sec == 0.5
    assert it.base_delay == 0.0  # 기본


def test_intent_risk_profile_override():
    """위험 프로파일 지정."""
    it = Intent(action="key", key="a", risk_profile=RiskProfile.CAREFUL)
    assert it.risk_profile == RiskProfile.CAREFUL


def test_intent_invalid_action_rejected():
    """알 수 없는 action은 거부."""
    with pytest.raises(ValueError):
        Intent(action="teleport_hack", key="x")


def test_intent_key_required_for_key_action():
    """key/hold 액션엔 key 필수."""
    with pytest.raises(ValueError):
        Intent(action="key", key="")


def test_risk_profile_values():
    """3종 프로파일 존재."""
    assert {p.value for p in RiskProfile} == {"careful", "normal", "fast"}
