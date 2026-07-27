# 준비 구간의 지역 배경 흐름 프로필 계약을 검증합니다.
from __future__ import annotations

import math

import pytest

from core.puzzle.binary_merge_background import build_background_flow_profile
from core.puzzle.models import Candidate


def _candidate(
    candidate_id: str,
    frame_index: int,
    position_ratio: tuple[float, float],
    frame_shape: tuple[int, int],
) -> Candidate:
    height, width = frame_shape
    center = (position_ratio[0] * width, position_ratio[1] * height)
    half_size = min(width, height) * 0.02
    return Candidate(
        candidate_id=candidate_id,
        frame_index=frame_index,
        bbox=(
            center[0] - half_size,
            center[1] - half_size,
            center[0] + half_size,
            center[1] + half_size,
        ),
        center=center,
        score=0.8,
        source="test",
    )


def _translated_frames(
    frame_shape: tuple[int, int],
    *,
    frame_count: int,
    step: tuple[float, float],
) -> tuple[tuple[int, tuple[Candidate, ...]], ...]:
    origins = ((0.18, 0.27), (0.52, 0.61), (0.79, 0.36))
    return tuple(
        (
            frame_index,
            tuple(
                _candidate(
                    f"background-{candidate_index}",
                    frame_index,
                    (
                        origin[0] + step[0] * frame_index,
                        origin[1] + step[1] * frame_index,
                    ),
                    frame_shape,
                )
                for candidate_index, origin in enumerate(origins)
            ),
        )
        for frame_index in range(frame_count)
    )


@pytest.mark.parametrize("frame_shape", ((180, 320), (360, 640)))
def test_background_flow_profile_normalizes_uniform_translation_across_board_sizes(
    frame_shape: tuple[int, int],
) -> None:
    profile = build_background_flow_profile(
        _translated_frames(frame_shape, frame_count=3, step=(0.025, -0.015)),
        frame_shape=frame_shape,
    )

    assert profile.available
    assert profile.velocity_ratio == pytest.approx((0.025, -0.015))
    assert profile.dispersion == pytest.approx(0.0)


def test_background_flow_profile_median_ignores_independently_moving_outlier() -> None:
    frame_shape = (240, 400)
    previous = _translated_frames(frame_shape, frame_count=1, step=(0.0, 0.0))[0]
    current_candidates = tuple(
        _candidate(
            candidate.candidate_id,
            1,
            (
                candidate.center[0] / frame_shape[1] + 0.02,
                candidate.center[1] / frame_shape[0] + 0.01,
            ),
            frame_shape,
        )
        for candidate in previous[1]
    ) + (
        _candidate("outlier", 1, (0.92, 0.06), frame_shape),
    )
    previous_with_outlier = (
        previous[0],
        previous[1]
        + (_candidate("outlier", 0, (0.72, 0.24), frame_shape),),
    )

    profile = build_background_flow_profile(
        (previous_with_outlier, (1, current_candidates)),
        frame_shape=frame_shape,
    )

    assert profile.available
    assert profile.velocity_ratio == pytest.approx((0.02, 0.01))


def test_background_flow_profile_counts_empty_frames_as_missing_motion() -> None:
    frame_shape = (240, 400)
    profile = build_background_flow_profile(
        (
            (0, _translated_frames(frame_shape, frame_count=1, step=(0.0, 0.0))[0][1]),
            (1, ()),
            (2, ()),
        ),
        frame_shape=frame_shape,
    )

    assert not profile.available
    assert profile.velocity_ratio is None
    assert profile.valid_transitions == 0
    assert profile.missing_transitions == 2
    assert math.isinf(profile.dispersion)
    assert profile.reason == "insufficient_background_motion"


def test_background_flow_profile_is_available_for_nonperiodic_translation() -> None:
    frame_shape = (300, 500)
    profile = build_background_flow_profile(
        _translated_frames(frame_shape, frame_count=4, step=(0.013, 0.007)),
        frame_shape=frame_shape,
    )

    assert profile.available
    assert profile.valid_transitions == 3
    assert profile.velocity_ratio == pytest.approx((0.013, 0.007))


def test_background_flow_profile_is_available_for_slowly_rotating_local_flow() -> None:
    frame_shape = (300, 500)
    center = (0.50, 0.50)
    radii_and_angles = ((0.18, 0.15), (0.27, 1.10), (0.22, 2.35))
    frames = tuple(
        (
            frame_index,
            tuple(
                _candidate(
                    f"background-{candidate_index}",
                    frame_index,
                    (
                        center[0] + radius * math.cos(angle + 0.04 * frame_index),
                        center[1] + radius * math.sin(angle + 0.04 * frame_index),
                    ),
                    frame_shape,
                )
                for candidate_index, (radius, angle) in enumerate(radii_and_angles)
            ),
        )
        for frame_index in range(3)
    )

    profile = build_background_flow_profile(frames, frame_shape=frame_shape)

    assert profile.available
    assert profile.valid_transitions == 2
