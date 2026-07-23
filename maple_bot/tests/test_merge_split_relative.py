# 병합 분리 판별기의 배경 상대 좌표와 신분 복원 동작을 검증합니다.
from __future__ import annotations

import importlib
import unittest

from core.puzzle.models import Candidate


def _candidate(
    candidate_id: str,
    bbox: tuple[float, float, float, float],
    *,
    frame_index: int = 0,
) -> Candidate:
    x1, y1, x2, y2 = bbox
    return Candidate(
        candidate_id=candidate_id,
        frame_index=frame_index,
        bbox=bbox,
        center=((x1 + x2) / 2.0, (y1 + y2) / 2.0),
        score=0.8,
        source="test",
    )


class RelativeCoordinateGeometryTest(unittest.TestCase):
    def test_similarity_transform_preserves_relative_coordinate(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        expected = module.relative_coordinate(
            (4.0, 3.0),
            (0.0, 0.0),
            (10.0, 0.0),
        )

        def transform(point: tuple[float, float]) -> tuple[float, float]:
            x, y = point
            return (100.0 - 2.5 * y, 40.0 + 2.5 * x)

        transformed = module.relative_coordinate(
            transform((4.0, 3.0)),
            transform((0.0, 0.0)),
            transform((10.0, 0.0)),
        )

        self.assertIsNotNone(expected)
        self.assertIsNotNone(transformed)
        self.assertAlmostEqual(transformed.u, expected.u)
        self.assertAlmostEqual(transformed.v, expected.v)

    def test_coincident_anchors_abstain(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")

        coordinate = module.relative_coordinate(
            (4.0, 3.0),
            (1.0, 1.0),
            (1.0, 1.0),
        )

        self.assertIsNone(coordinate)


class MergeSplitEventDetectorTest(unittest.TestCase):
    def test_partial_overlap_requires_repeated_observation(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        detector = module.MergeSplitEventDetector(confirm_observations=2)
        target = _candidate("target", (10.0, 10.0, 30.0, 30.0))
        background = _candidate("background", (24.0, 10.0, 44.0, 30.0))

        first = detector.update(
            target_candidate=target,
            candidates=(target, background),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )
        second = detector.update(
            target_candidate=target,
            candidates=(target, background),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )

        self.assertEqual(first.state, module.MergeState.SEPARATE)
        self.assertEqual(second.state, module.MergeState.PARTIAL_OVERLAP)
        self.assertGreater(second.overlap_ratio, 0.0)

    def test_unrelated_large_box_does_not_start_full_merge(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        detector = module.MergeSplitEventDetector(confirm_observations=2)
        unrelated = _candidate("large", (200.0, 200.0, 240.0, 240.0))

        for _ in range(3):
            event = detector.update(
                target_candidate=None,
                candidates=(unrelated,),
                stable_area=400.0,
                predicted_target_point=(20.0, 20.0),
            )

        self.assertEqual(event.state, module.MergeState.SEPARATE)

    def test_expanded_box_near_prediction_enters_full_merge(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        detector = module.MergeSplitEventDetector(confirm_observations=2)
        merged = _candidate("merged", (7.0, 7.0, 35.0, 35.0))

        detector.update(
            target_candidate=None,
            candidates=(merged,),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )
        event = detector.update(
            target_candidate=None,
            candidates=(merged,),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )

        self.assertEqual(event.state, module.MergeState.MERGED)
        self.assertGreater(event.area_ratio, 1.25)

    def test_partial_and_full_merge_both_enter_splitting(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        target = _candidate("target", (10.0, 10.0, 30.0, 30.0))
        background = _candidate("background", (24.0, 10.0, 44.0, 30.0))
        split_target = _candidate("split-target", (14.0, 10.0, 34.0, 30.0))
        split_background = _candidate("split-background", (38.0, 10.0, 58.0, 30.0))

        partial_detector = module.MergeSplitEventDetector(confirm_observations=1)
        partial_detector.update(
            target_candidate=target,
            candidates=(target, background),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )
        partial_split = partial_detector.update(
            target_candidate=split_target,
            candidates=(split_target, split_background),
            stable_area=400.0,
            predicted_target_point=(24.0, 20.0),
        )

        merged_detector = module.MergeSplitEventDetector(confirm_observations=1)
        merged_detector.update(
            target_candidate=None,
            candidates=(_candidate("merged", (7.0, 7.0, 35.0, 35.0)),),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )
        merged_split = merged_detector.update(
            target_candidate=split_target,
            candidates=(split_target, split_background),
            stable_area=400.0,
            predicted_target_point=(24.0, 20.0),
        )

        self.assertEqual(partial_split.state, module.MergeState.SPLITTING)
        self.assertEqual(merged_split.state, module.MergeState.SPLITTING)


if __name__ == "__main__":
    unittest.main()
