# 병합 분리 판별기의 배경 상대 좌표와 신분 복원 동작을 검증합니다.
from __future__ import annotations

import importlib
import unittest

from core.puzzle.models import Candidate, CandidateEvidence


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


def _center_candidate(
    candidate_id: str,
    center: tuple[float, float],
    *,
    size: float = 2.0,
    frame_index: int = 0,
) -> Candidate:
    half = size / 2.0
    return _candidate(
        candidate_id,
        (
            center[0] - half,
            center[1] - half,
            center[0] + half,
            center[1] + half,
        ),
        frame_index=frame_index,
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

    def test_nearly_identical_duplicate_box_is_not_partial_overlap(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        detector = module.MergeSplitEventDetector(confirm_observations=1)
        target = _candidate("white-anchor", (0.0, 0.0, 100.0, 100.0))
        duplicate = _candidate("raw-duplicate", (5.0, 5.0, 95.0, 95.0))

        event = detector.update(
            target_candidate=target,
            candidates=(target, duplicate),
            stable_area=10000.0,
            predicted_target_point=(50.0, 50.0),
        )

        self.assertEqual(event.state, module.MergeState.SEPARATE)
        self.assertEqual(event.overlap_ratio, 0.0)

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

    def test_nearby_expanded_box_merges_despite_unrelated_candidates(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        detector = module.MergeSplitEventDetector(confirm_observations=1)
        merged = _candidate("merged", (7.0, 7.0, 35.0, 35.0))
        anchors = (
            _candidate("anchor-a", (80.0, 80.0, 84.0, 84.0)),
            _candidate("anchor-b", (100.0, 80.0, 104.0, 84.0)),
        )

        event = detector.update(
            target_candidate=None,
            candidates=(merged, *anchors),
            stable_area=400.0,
            predicted_target_point=(20.0, 20.0),
        )

        self.assertEqual(event.state, module.MergeState.MERGED)

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


class SplitChildAssignmentTest(unittest.TestCase):
    def test_non_background_incumbent_is_preserved_over_closer_prediction(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        anchors = (
            module.BackgroundAnchor("a", (0.0, 0.0), 8),
            module.BackgroundAnchor("b", (10.0, 0.0), 8),
        )
        fingerprint = module.RelationFingerprint.from_observations(
            background_point=(5.0, 4.0),
            anchors=anchors,
            jitter=0.1,
        )

        decision = module.assign_split_children(
            children=(
                _candidate("background", (4.0, 3.0, 6.0, 5.0)),
                _candidate("incumbent-target", (7.0, 3.0, 9.0, 5.0)),
                _candidate("prediction-distractor", (9.0, 3.0, 11.0, 5.0)),
            ),
            anchors=anchors,
            fingerprint=fingerprint,
            predicted_target_point=(10.0, 4.0),
            incumbent_candidate_id="incumbent-target",
        )

        self.assertEqual(decision.target_candidate_id, "incumbent-target")
        self.assertEqual(decision.reason, "background_relation_assigned")

    def test_relation_preserving_child_is_background(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        fingerprint = module.RelationFingerprint.from_observations(
            background_point=(5.0, 4.0),
            anchors=(
                module.BackgroundAnchor("a", (0.0, 0.0), 8),
                module.BackgroundAnchor("b", (10.0, 0.0), 8),
            ),
            jitter=0.02,
        )

        decision = module.assign_split_children(
            children=(
                _candidate("background-child", (4.0, 3.0, 6.0, 5.0)),
                _candidate("target-child", (7.0, 7.0, 9.0, 9.0)),
            ),
            anchors=(
                module.BackgroundAnchor("a", (0.0, 0.0), 9),
                module.BackgroundAnchor("b", (10.0, 0.0), 9),
            ),
            fingerprint=fingerprint,
            predicted_target_point=(8.0, 8.0),
        )

        self.assertEqual(decision.background_candidate_id, "background-child")
        self.assertEqual(decision.target_candidate_id, "target-child")
        self.assertGreater(decision.relative_margin, 0.0)

    def test_one_anchor_abstains_instead_of_guessing(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        fingerprint = module.RelationFingerprint.from_observations(
            background_point=(5.0, 4.0),
            anchors=(
                module.BackgroundAnchor("a", (0.0, 0.0), 8),
                module.BackgroundAnchor("b", (10.0, 0.0), 8),
            ),
            jitter=0.02,
        )

        decision = module.assign_split_children(
            children=(
                _candidate("child-a", (4.0, 3.0, 6.0, 5.0)),
                _candidate("child-b", (7.0, 7.0, 9.0, 9.0)),
            ),
            anchors=(module.BackgroundAnchor("a", (0.0, 0.0), 9),),
            fingerprint=fingerprint,
            predicted_target_point=(8.0, 8.0),
        )

        self.assertEqual(decision.reason, "insufficient_anchors")
        self.assertIsNone(decision.target_candidate_id)

    def test_clipped_anchor_abstains(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        fingerprint = module.RelationFingerprint.from_observations(
            background_point=(5.0, 4.0),
            anchors=(
                module.BackgroundAnchor("a", (0.0, 0.0), 8),
                module.BackgroundAnchor("b", (10.0, 0.0), 8),
            ),
            jitter=0.02,
        )

        decision = module.assign_split_children(
            children=(
                _candidate("child-a", (4.0, 3.0, 6.0, 5.0)),
                _candidate("child-b", (7.0, 7.0, 9.0, 9.0)),
            ),
            anchors=(
                module.BackgroundAnchor("a", (0.0, 0.0), 9, clipped=True),
                module.BackgroundAnchor("b", (10.0, 0.0), 9),
            ),
            fingerprint=fingerprint,
            predicted_target_point=(8.0, 8.0),
        )

        self.assertEqual(decision.reason, "insufficient_anchors")
        self.assertIsNone(decision.target_candidate_id)

    def test_nearly_equal_relations_abstain_as_ambiguous(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        anchors = (
            module.BackgroundAnchor("a", (0.0, 0.0), 8),
            module.BackgroundAnchor("b", (10.0, 0.0), 8),
        )
        fingerprint = module.RelationFingerprint.from_observations(
            background_point=(5.0, 4.0),
            anchors=anchors,
            jitter=0.1,
        )

        decision = module.assign_split_children(
            children=(
                _candidate("child-a", (4.0, 3.0, 6.0, 5.0)),
                _candidate("child-b", (4.2, 3.0, 6.2, 5.0)),
            ),
            anchors=anchors,
            fingerprint=fingerprint,
            predicted_target_point=(5.2, 4.0),
        )

        self.assertEqual(decision.reason, "ambiguous_relation")
        self.assertIsNone(decision.target_candidate_id)


class BackgroundAnchorManagerTest(unittest.TestCase):
    def test_nearby_anchor_selection_ignores_far_and_clipped_tracks(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        anchors = (
            module.BackgroundAnchor("far-a", (0.0, 0.0), 8),
            module.BackgroundAnchor("far-b", (100.0, 100.0), 8),
            module.BackgroundAnchor("clipped", (49.0, 50.0), 8, clipped=True),
            module.BackgroundAnchor("near-a", (45.0, 50.0), 8),
            module.BackgroundAnchor("near-b", (55.0, 50.0), 8),
            module.BackgroundAnchor("near-c", (50.0, 58.0), 8),
        )

        selected = module.nearest_background_anchors(
            background_point=(50.0, 50.0),
            anchors=anchors,
            limit=3,
        )

        self.assertEqual(
            tuple(anchor.track_id for anchor in selected),
            ("near-a", "near-b", "near-c"),
        )

    def test_excluded_merge_participant_cannot_take_over_anchor_track(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        manager = module.BackgroundAnchorManager(minimum_stable_observations=1)
        anchor = _center_candidate("anchor", (20.0, 20.0))

        first = manager.update(
            candidates=(anchor,),
            target_candidate=None,
            evidence={},
            frame_shape=(100, 100),
            stable_scale_px=10.0,
        )
        merge_participant = _center_candidate("merge-participant", (21.0, 20.0))
        second = manager.update(
            candidates=(merge_participant,),
            target_candidate=None,
            evidence={},
            frame_shape=(100, 100),
            stable_scale_px=10.0,
            excluded_candidate_ids=("merge-participant",),
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(second, ())

    def test_tracks_background_anchors_when_candidate_ids_change(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        manager = module.BackgroundAnchorManager(minimum_stable_observations=2)
        target = _candidate("target", (45.0, 45.0, 55.0, 55.0))
        first_candidates = (
            target,
            _candidate("frame-1-a", (8.0, 8.0, 12.0, 12.0)),
            _candidate("frame-1-b", (68.0, 8.0, 72.0, 12.0)),
        )
        second_candidates = (
            _candidate("target-new-id", (46.0, 45.0, 56.0, 55.0)),
            _candidate("frame-2-a", (9.0, 8.0, 13.0, 12.0)),
            _candidate("frame-2-b", (69.0, 8.0, 73.0, 12.0)),
        )
        evidence = {
            candidate.candidate_id: CandidateEvidence(
                candidate_id=candidate.candidate_id,
                bg_score=0.8,
            )
            for candidate in (*first_candidates, *second_candidates)
        }

        first = manager.update(
            candidates=first_candidates,
            target_candidate=target,
            evidence=evidence,
            frame_shape=(100, 100),
            stable_scale_px=10.0,
        )
        second = manager.update(
            candidates=second_candidates,
            target_candidate=second_candidates[0],
            evidence=evidence,
            frame_shape=(100, 100),
            stable_scale_px=10.0,
        )

        self.assertEqual(first, ())
        self.assertEqual(len(second), 2)
        self.assertTrue(all(anchor.track_id.startswith("anchor-") for anchor in second))
        self.assertTrue(all(anchor.stable_observations == 2 for anchor in second))

    def test_marks_border_anchor_as_clipped(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        manager = module.BackgroundAnchorManager(minimum_stable_observations=1)
        target = _candidate("target", (45.0, 45.0, 55.0, 55.0))
        border = _candidate("border", (0.0, 20.0, 4.0, 24.0))

        anchors = manager.update(
            candidates=(target, border),
            target_candidate=target,
            evidence={"border": CandidateEvidence(candidate_id="border", bg_score=0.8)},
            frame_shape=(100, 100),
            stable_scale_px=10.0,
        )

        self.assertEqual(len(anchors), 1)
        self.assertTrue(anchors[0].clipped)


class MergeSplitRelativeResolverTest(unittest.TestCase):
    def test_partial_overlap_refreshes_visible_background_fingerprint(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        resolver = module.MergeSplitRelativeResolver(
            event_confirm_observations=1,
            minimum_anchor_observations=1,
        )
        target = _center_candidate("target", (50.0, 50.0), size=10.0)
        background = _center_candidate("background", (55.0, 50.0), size=10.0)
        anchor_a = _center_candidate("anchor-a", (20.0, 20.0), size=4.0)
        anchor_b = _center_candidate("anchor-b", (80.0, 20.0), size=4.0)

        decision = resolver.update(
            incumbent_point=target.center,
            candidates=(target, background, anchor_a, anchor_b),
            evidence={},
            stable_area=100.0,
            frame_shape=(100, 100),
        )

        self.assertEqual(decision.state, module.MergeState.PARTIAL_OVERLAP)
        self.assertEqual(decision.debug["fingerprint_pair_count"], 1)

    def test_partial_overlap_keeps_visible_target_motion_current(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        resolver = module.MergeSplitRelativeResolver(
            event_confirm_observations=1,
            minimum_anchor_observations=1,
        )
        anchor_a = _center_candidate("anchor-a", (10.0, 10.0), size=2.0)
        anchor_b = _center_candidate("anchor-b", (90.0, 10.0), size=2.0)

        for x in (30.0, 32.0):
            target = _center_candidate(f"target-{x}", (x, 50.0), size=2.0)
            background = _center_candidate(f"background-{x}", (40.0, 50.0), size=2.0)
            resolver.update(
                incumbent_point=target.center,
                candidates=(target, background, anchor_a, anchor_b),
                evidence={},
                stable_area=4.0,
                frame_shape=(100, 100),
            )

        overlap_target = _center_candidate("overlap-target", (34.0, 50.0), size=2.0)
        overlapping_background = _center_candidate(
            "overlapping-background", (35.0, 50.0), size=2.0
        )
        resolver.update(
            incumbent_point=overlap_target.center,
            candidates=(overlap_target, overlapping_background, anchor_a, anchor_b),
            evidence={},
            stable_area=4.0,
            frame_shape=(100, 100),
        )

        self.assertEqual(resolver._predicted_target_point(None, ()), (36.0, 50.0))

    def test_distant_large_box_does_not_create_partial_overlap(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        resolver = module.MergeSplitRelativeResolver(
            event_confirm_observations=1,
            minimum_anchor_observations=1,
        )
        target = _center_candidate("target", (50.0, 50.0), size=10.0)
        nearest_background = _center_candidate("nearest-background", (65.0, 50.0), size=10.0)
        distant_large = _candidate("distant-large", (-100.0, -100.0, 55.0, 55.0))

        decision = resolver.update(
            incumbent_point=target.center,
            candidates=(target, nearest_background, distant_large),
            evidence={},
            stable_area=100.0,
            frame_shape=(200, 200),
        )

        self.assertEqual(decision.state, module.MergeState.SEPARATE)

    def test_partial_overlap_split_restores_non_background_child(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        resolver = module.MergeSplitRelativeResolver(
            event_confirm_observations=1,
            minimum_anchor_observations=2,
        )
        anchor_a = _center_candidate("anchor-a", (20.0, 20.0))
        anchor_b = _center_candidate("anchor-b", (40.0, 20.0))
        background = _center_candidate("background", (30.0, 28.0))
        target = _center_candidate("target", (34.0, 32.0))
        evidence = {
            candidate.candidate_id: CandidateEvidence(
                candidate_id=candidate.candidate_id,
                bg_score=0.8,
            )
            for candidate in (anchor_a, anchor_b, background, target)
        }

        for _ in range(2):
            resolver.update(
                incumbent_point=(34.0, 32.0),
                candidates=(target, background, anchor_a, anchor_b),
                evidence=evidence,
                stable_area=4.0,
                frame_shape=(100, 100),
            )

        overlap_target = _center_candidate("overlap-target", (31.0, 29.0))
        resolver.update(
            incumbent_point=(31.0, 29.0),
            candidates=(overlap_target, background, anchor_a, anchor_b),
            evidence=evidence,
            stable_area=4.0,
            frame_shape=(100, 100),
        )

        target_child = _center_candidate("target-child", (33.0, 31.0))
        background_child = _center_candidate("background-child", (30.0, 28.0))
        far_distractor = _center_candidate("far-distractor", (25.0, 28.0))
        decision = resolver.update(
            incumbent_point=(31.0, 29.0),
            candidates=(
                target_child,
                background_child,
                far_distractor,
                anchor_a,
                anchor_b,
            ),
            evidence=evidence,
            stable_area=4.0,
            frame_shape=(100, 100),
        )

        self.assertEqual(decision.state, module.MergeState.SPLITTING)
        self.assertEqual(decision.background_candidate_id, "background-child")
        self.assertEqual(decision.target_candidate_id, "target-child")
        self.assertEqual(decision.target_point, (33.0, 31.0))
        self.assertNotIn("far-distractor", decision.debug["local_child_ids"])
        self.assertIn("predicted_target_point", decision.debug)

    def test_split_assignment_remains_available_for_three_observations(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        resolver = module.MergeSplitRelativeResolver(
            event_confirm_observations=1,
            minimum_anchor_observations=2,
        )
        anchor_a = _center_candidate("anchor-a", (20.0, 20.0))
        anchor_b = _center_candidate("anchor-b", (40.0, 20.0))
        background = _center_candidate("background", (30.0, 28.0))
        target = _center_candidate("target", (34.0, 32.0))
        evidence: dict[str, CandidateEvidence] = {}

        for _ in range(2):
            resolver.update(
                incumbent_point=target.center,
                candidates=(target, background, anchor_a, anchor_b),
                evidence=evidence,
                stable_area=4.0,
                frame_shape=(100, 100),
            )
        overlap = _center_candidate("overlap", (31.0, 29.0))
        resolver.update(
            incumbent_point=overlap.center,
            candidates=(overlap, background, anchor_a, anchor_b),
            evidence=evidence,
            stable_area=4.0,
            frame_shape=(100, 100),
        )

        decisions = []
        for index in range(3):
            target_child = _center_candidate(f"target-{index}", (33.0, 31.0))
            background_child = _center_candidate(f"background-{index}", (30.0, 28.0))
            decisions.append(
                resolver.update(
                    incumbent_point=(30.0, 28.0),
                    candidates=(target_child, background_child, anchor_a, anchor_b),
                    evidence=evidence,
                    stable_area=4.0,
                    frame_shape=(100, 100),
                )
            )

        self.assertEqual(
            [decision.target_candidate_id for decision in decisions],
            ["target-0", "target-1", "target-2"],
        )


if __name__ == "__main__":
    unittest.main()
