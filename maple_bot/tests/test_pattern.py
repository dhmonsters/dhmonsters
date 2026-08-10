# 사냥 패턴 표시 문자열과 기본 역직렬화 값을 검증한다.
from core.pattern import HuntPattern, KeyPattern, Step


def test_step_labels_are_valid_korean_text():
    assert Step.make("move", direction="left", duration=1.5).label() == "이동 left 1.5초"
    assert Step.make("jump", direction="up").label() == "점프 위"
    assert Step.make("attack_if_monster", key="ctrl", repeat=3).label() == (
        "몬스터 감지 → 공격 ctrl × 3 [미설정]"
    )


def test_pattern_default_names_are_readable():
    assert HuntPattern.from_dict({}).name == "패턴"
    assert KeyPattern.from_dict({}).name == "키 패턴"
