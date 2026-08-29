# 빨코2 복귀 공격 텔레포트 타이밍 설정 병합을 검증한다.
from core.config_adapter import _merge_rednose2_timing_settings


def test_versioned_timing_preserves_first_two_recovery_attack_teleports():
    profile = _merge_rednose2_timing_settings({
        "timing_version": 2,
        "floor2_recovery_first_attack_hold_sec": 0.61,
        "floor2_recovery_first_teleport_hold_sec": 0.11,
        "floor2_recovery_first_interval_sec": 0.71,
        "floor2_recovery_second_attack_hold_sec": 0.62,
        "floor2_recovery_second_teleport_hold_sec": 0.12,
        "floor2_recovery_second_interval_sec": 0.72,
    })

    assert profile["floor2_recovery_first_attack_hold_sec"] == 0.61
    assert profile["floor2_recovery_first_teleport_hold_sec"] == 0.11
    assert profile["floor2_recovery_first_interval_sec"] == 0.71
    assert profile["floor2_recovery_second_attack_hold_sec"] == 0.62
    assert profile["floor2_recovery_second_teleport_hold_sec"] == 0.12
    assert profile["floor2_recovery_second_interval_sec"] == 0.72
