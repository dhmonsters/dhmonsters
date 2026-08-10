# 이동 러너가 허용 시간을 넘긴 캐릭터 좌표를 재사용하지 않는지 검증한다.
import time

from core.navigation.block_runner import BlockRunner


def test_block_runner_refresh_rejects_stale_character_position():
    observed_at = time.monotonic() - 1.0
    runner = BlockRunner(
        input_backend=object(),
        pos_fn=lambda: (14, 62),
        position_sample_fn=lambda: ((14, 62), observed_at),
        ladder_profile={"position_max_age_sec": 0.15},
    )

    position, age = runner.refresh_position()

    assert position is None
    assert age is not None and age >= 1.0


def test_block_runner_refresh_accepts_recent_character_position():
    observed_at = time.monotonic()
    runner = BlockRunner(
        input_backend=object(),
        pos_fn=lambda: (41, 62),
        position_sample_fn=lambda: ((41, 62), observed_at),
        ladder_profile={"position_max_age_sec": 0.15},
    )

    position, age = runner.refresh_position()

    assert position == (41, 62)
    assert age is not None and 0.0 <= age <= 0.15
