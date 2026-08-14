# 전역 사다리 점프 프로필의 설정 변환을 검증한다.
from core.config_adapter import to_runtime_config


def test_ladder_profile_defaults():
    config = to_runtime_config({})
    assert config.ladder_launch_distance == 8.0
    assert config.ladder_up_delay_sec == 0.245
    assert config.ladder_stable_samples == 3


def test_ladder_profile_reads_user_values():
    config = to_runtime_config({"ladder_profile": {
        "launch_distance": 10.0,
        "jump_hold_sec": 0.12,
        "up_delay_sec": 0.04,
    }})
    assert config.ladder_launch_distance == 10.0
    assert config.ladder_jump_hold_sec == 0.12
    assert config.ladder_up_delay_sec == 0.04
