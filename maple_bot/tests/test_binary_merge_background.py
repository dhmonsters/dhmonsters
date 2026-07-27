# 준비 구간의 지역 배경 흐름 프로필 계약을 검증합니다.
from __future__ import annotations

import math
from statistics import median

import pytest

from core.puzzle.binary_merge_background import (
    _minimum_cost_background_matches,
    build_background_flow_profile,
)
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
    radii_and_angles = ((0.22, 0.15), (0.22, 1.10), (0.22, 2.35))
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


def test_background_flow_profile_marks_a_single_far_jump_as_missing() -> None:
    frame_shape = (240, 400)
    profile = build_background_flow_profile(
        (
            (0, (_candidate("anchor", 0, (0.05, 0.50), frame_shape),)),
            (1, (_candidate("anchor", 1, (0.95, 0.50), frame_shape),)),
        ),
        frame_shape=frame_shape,
    )

    assert not profile.available
    assert profile.valid_transitions == 0
    assert profile.missing_transitions == 1
    assert profile.reason == "insufficient_background_motion"


def test_background_flow_profile_marks_one_normal_match_plus_one_outlier_as_missing() -> None:
    frame_shape = (240, 400)
    profile = build_background_flow_profile(
        (
            (
                0,
                (
                    _candidate("normal", 0, (0.20, 0.30), frame_shape),
                    _candidate("outlier", 0, (0.68, 0.70), frame_shape),
                ),
            ),
            (
                1,
                (
                    _candidate("normal", 1, (0.22, 0.31), frame_shape),
                    _candidate("outlier", 1, (0.95, 0.35), frame_shape),
                ),
            ),
        ),
        frame_shape=frame_shape,
    )

    assert not profile.available
    assert profile.valid_transitions == 0
    assert profile.missing_transitions == 1
    assert profile.reason == "insufficient_background_motion"


def test_background_flow_profile_marks_two_retained_matches_after_filtering_as_missing() -> None:
    frame_shape = (240, 400)
    profile = build_background_flow_profile(
        (
            (
                0,
                (
                    _candidate("anchor-a", 0, (0.16, 0.24), frame_shape),
                    _candidate("anchor-b", 0, (0.48, 0.65), frame_shape),
                    _candidate("outlier", 0, (0.78, 0.34), frame_shape),
                ),
            ),
            (
                1,
                (
                    _candidate("anchor-a", 1, (0.18, 0.25), frame_shape),
                    _candidate("anchor-b", 1, (0.50, 0.66), frame_shape),
                    _candidate("outlier", 1, (0.94, 0.06), frame_shape),
                ),
            ),
        ),
        frame_shape=frame_shape,
    )

    assert not profile.available
    assert profile.valid_transitions == 0
    assert profile.missing_transitions == 1
    assert profile.reason == "insufficient_background_motion"


def test_minimum_cost_background_matches_excludes_outlier_from_envelope() -> None:
    frame_shape = (240, 400)
    previous = tuple(
        _candidate(candidate_id, 0, position, frame_shape)
        for candidate_id, position in (
            ("anchor-a", (0.18, 0.27)),
            ("anchor-b", (0.52, 0.61)),
            ("anchor-c", (0.79, 0.36)),
            ("outlier", (0.72, 0.24)),
        )
    )
    current = tuple(
        _candidate(candidate_id, 1, position, frame_shape)
        for candidate_id, position in (
            ("anchor-a", (0.20, 0.28)),
            ("anchor-b", (0.54, 0.62)),
            ("anchor-c", (0.81, 0.37)),
            ("outlier", (0.92, 0.06)),
        )
    )

    matches = _minimum_cost_background_matches(previous, current, frame_shape)

    assert tuple((left.candidate_id, right.candidate_id) for left, right in matches) == (
        ("anchor-a", "anchor-a"),
        ("anchor-b", "anchor-b"),
        ("anchor-c", "anchor-c"),
    )


def test_minimum_cost_background_matches_collapses_duplicates_deterministically() -> None:
    frame_shape = (240, 400)
    previous = (
        _candidate("anchor-a", 0, (0.20, 0.30), frame_shape),
        _candidate("anchor-a-duplicate", 0, (0.201, 0.30), frame_shape),
        _candidate("anchor-b", 0, (0.70, 0.60), frame_shape),
        _candidate("anchor-c", 0, (0.45, 0.72), frame_shape),
    )
    current = (
        _candidate("anchor-a", 1, (0.22, 0.31), frame_shape),
        _candidate("anchor-a-duplicate", 1, (0.221, 0.31), frame_shape),
        _candidate("anchor-b", 1, (0.72, 0.61), frame_shape),
        _candidate("anchor-c", 1, (0.47, 0.73), frame_shape),
    )

    ordered = _minimum_cost_background_matches(previous, current, frame_shape)
    permuted = _minimum_cost_background_matches(
        tuple(reversed(previous)),
        (current[1], current[3], current[2], current[0]),
        frame_shape,
    )

    expected = (
        ("anchor-a", "anchor-a"),
        ("anchor-c", "anchor-c"),
        ("anchor-b", "anchor-b"),
    )
    assert tuple((left.candidate_id, right.candidate_id) for left, right in ordered) == expected
    assert tuple((left.candidate_id, right.candidate_id) for left, right in permuted) == expected


def test_minimum_cost_background_matches_uses_global_optimum_over_greedy_pairing() -> None:
    frame_shape = (1000, 1000)
    previous = (
        _candidate("left-a", 0, (0.20, 0.20), frame_shape),
        _candidate("left-b", 0, (0.40, 0.20), frame_shape),
        _candidate("left-c", 0, (0.65, 0.70), frame_shape),
    )
    current = (
        _candidate("right-x", 1, (0.30, 0.20), frame_shape),
        _candidate("right-y", 1, (0.20, 0.31), frame_shape),
        _candidate("right-z", 1, (0.67, 0.71), frame_shape),
    )

    matches = _minimum_cost_background_matches(previous, current, frame_shape)

    assert tuple((left.candidate_id, right.candidate_id) for left, right in matches) == (
        ("left-a", "right-y"),
        ("left-b", "right-x"),
        ("left-c", "right-z"),
    )


def test_background_flow_profile_reports_rotating_tangent_velocity_and_dispersion() -> None:
    frame_shape = (300, 500)
    center = (0.50, 0.50)
    radius = 0.20
    angles = (0.0, 2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0)
    rotation = 0.04
    frames = tuple(
        (
            frame_index,
            tuple(
                _candidate(
                    f"anchor-{candidate_index}",
                    frame_index,
                    (
                        center[0] + radius * math.cos(angle + rotation * frame_index),
                        center[1] + radius * math.sin(angle + rotation * frame_index),
                    ),
                    frame_shape,
                )
                for candidate_index, angle in enumerate(angles)
            ),
        )
        for frame_index in range(2)
    )
    dx_values = tuple(
        radius * (math.cos(angle + rotation) - math.cos(angle))
        for angle in angles
    )
    dy_values = tuple(
        radius * (math.sin(angle + rotation) - math.sin(angle))
        for angle in angles
    )
    expected_velocity = (median(dx_values), median(dy_values))
    expected_dispersion = median(
        math.hypot(dx - expected_velocity[0], dy - expected_velocity[1])
        for dx, dy in zip(dx_values, dy_values)
    )

    profile = build_background_flow_profile(frames, frame_shape=frame_shape)

    assert profile.available
    assert profile.velocity_ratio == pytest.approx(expected_velocity)
    assert profile.dispersion == pytest.approx(expected_dispersion)
