# 독립 심판 합의의 시간 지속성과 현재 순증거 조건을 검증합니다.
from __future__ import annotations

import importlib
import unittest

from core.puzzle.models import Candidate, CandidateEvidence


class PersistentEvidenceQuorumTest(unittest.TestCase):
    def test_pairwise_margins_keep_correlated_motion_as_one_group(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        incumbent = _candidate("incumbent", 0.9)
        challenger = _candidate("challenger", 0.8)

        margins = module.pairwise_persistent_margins(
            incumbent_candidate=incumbent,
            challenger_candidate=challenger,
            incumbent_evidence=CandidateEvidence(
                candidate_id="incumbent",
                motion_divergence=0.1,
                rigid_violation=0.1,
            ),
            challenger_evidence=CandidateEvidence(
                candidate_id="challenger",
                motion_divergence=0.9,
                rigid_violation=0.9,
            ),
            candidate_pool=(incumbent, challenger, _candidate("weak", 0.2)),
        )

        self.assertAlmostEqual(margins["background_motion"], 0.8)
        self.assertEqual(margins["yolo_penalty"], 0.0)

    def test_anchor_shape_identity_rejects_small_distorted_challenger(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        incumbent = _candidate("incumbent", 0.64, width=72.0, height=71.0)
        challenger = _candidate("challenger", 0.16, width=37.0, height=26.0)

        margins = module.pairwise_persistent_margins(
            incumbent_candidate=incumbent,
            challenger_candidate=challenger,
            incumbent_evidence=CandidateEvidence(candidate_id="incumbent"),
            challenger_evidence=CandidateEvidence(candidate_id="challenger"),
            candidate_pool=(incumbent, challenger),
            anchor_shape=(98.0 * 97.0, 98.0 / 97.0),
        )

        self.assertLess(margins["anchor_shape_identity"], -1.0)

    def test_anchor_shape_identity_abstains_for_boundary_clipped_candidate(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        incumbent = Candidate(
            candidate_id="incumbent",
            frame_index=80,
            bbox=(-0.5, 14.5, 22.5, 105.5),
            center=(11.0, 60.0),
            score=0.7,
            source="raw",
        )
        challenger = Candidate(
            candidate_id="challenger",
            frame_index=80,
            bbox=(9.5, 64.5, 90.5, 145.5),
            center=(50.0, 105.0),
            score=0.7,
            source="raw",
        )

        margins = module.pairwise_persistent_margins(
            incumbent_candidate=incumbent,
            challenger_candidate=challenger,
            incumbent_evidence=CandidateEvidence(
                candidate_id="incumbent",
                motion_divergence=0.1,
                rigid_violation=0.1,
                local_rigid_residual=0.1,
                texture_bg_score=0.8,
            ),
            challenger_evidence=CandidateEvidence(
                candidate_id="challenger",
                motion_divergence=0.9,
                rigid_violation=0.9,
                local_rigid_residual=0.9,
                texture_bg_score=0.1,
            ),
            candidate_pool=(incumbent, challenger),
            anchor_shape=(81.0 * 81.0, 1.0),
            frame_shape=(538, 460),
        )

        self.assertIsNone(margins["background_motion"])
        self.assertIsNone(margins["local_rigid"])
        self.assertIsNone(margins["texture_background"])
        self.assertIsNone(margins["anchor_shape_identity"])

    def test_same_frame_quorum_waits_for_second_path_observation(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(required_groups=2, required_observations=2)

        first, first_debug = quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(70.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "texture_background": 0.2},
        )
        second, second_debug = quorum.update(
            incumbent_point=(18.0, 10.0),
            challenger_point=(78.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"local_rigid": 0.5},
        )

        self.assertEqual(first, (10.0, 10.0))
        self.assertEqual(first_debug["reason"], "persistence_pending")
        self.assertEqual(second, (78.0, 10.0))
        self.assertEqual(second_debug["reason"], "persistent_quorum_confirmed")

    def test_negative_current_net_margin_blocks_two_positive_votes(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(required_groups=2, required_observations=2)
        quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(70.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"local_rigid": 0.03, "texture_background": 0.04},
        )

        selected, debug = quorum.update(
            incumbent_point=(18.0, 10.0),
            challenger_point=(78.0, 10.0),
            stable_scale_px=20.0,
            group_margins={
                "background_motion": -0.67,
                "local_rigid": 0.03,
                "texture_background": 0.04,
            },
        )

        self.assertEqual(selected, (18.0, 10.0))
        self.assertEqual(debug["reason"], "current_evidence_rejected")
        self.assertLess(debug["current_net_margin"], 0.0)

    def test_repeated_one_judge_still_cannot_form_quorum(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(required_groups=2, required_observations=2)

        for index, challenger_x in enumerate((70.0, 78.0, 86.0)):
            selected, debug = quorum.update(
                incumbent_point=(10.0 + index * 8.0, 10.0),
                challenger_point=(challenger_x, 10.0),
                stable_scale_px=20.0,
                group_margins={"background_motion": 0.8},
            )

        self.assertEqual(selected, (26.0, 10.0))
        self.assertEqual(debug["reason"], "quorum_pending")
        self.assertEqual(debug["positive_groups"], ("background_motion",))

    def test_protected_incumbent_resets_persistent_challenge(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(required_groups=2, required_observations=2)
        quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(70.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
        )

        selected, debug = quorum.update(
            incumbent_point=(18.0, 10.0),
            challenger_point=(78.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
            protect_incumbent=True,
        )

        self.assertEqual(selected, (18.0, 10.0))
        self.assertEqual(debug["reason"], "protected_incumbent")
        self.assertEqual(debug["observation_count"], 0)

    def test_default_quorum_needs_third_observation_to_validate_velocity(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(
            required_groups=2,
            required_positive_groups=(),
        )

        first, _ = quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(70.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
        )
        second, second_debug = quorum.update(
            incumbent_point=(18.0, 10.0),
            challenger_point=(78.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
        )
        third, third_debug = quorum.update(
            incumbent_point=(26.0, 10.0),
            challenger_point=(86.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
        )

        self.assertEqual(first, (10.0, 10.0))
        self.assertEqual(second, (18.0, 10.0))
        self.assertEqual(second_debug["reason"], "persistence_pending")
        self.assertEqual(third, (86.0, 10.0))
        self.assertEqual(third_debug["reason"], "persistent_quorum_confirmed")

    def test_frames_without_support_do_not_count_as_path_observations(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(required_groups=2, required_observations=3)

        for challenger_x in (70.0, 78.0, 86.0):
            quorum.update(
                incumbent_point=(10.0, 10.0),
                challenger_point=(challenger_x, 10.0),
                stable_scale_px=20.0,
                group_margins={
                    "background_motion": None,
                    "local_rigid": None,
                    "texture_background": None,
                    "anchor_shape_identity": None,
                    "yolo_penalty": 0.0,
                },
            )

        selected, debug = quorum.update(
            incumbent_point=(18.0, 10.0),
            challenger_point=(94.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
        )

        self.assertEqual(selected, (18.0, 10.0))
        self.assertEqual(debug["reason"], "persistence_pending")
        self.assertEqual(debug["observation_count"], 1)

    def test_default_quorum_requires_majority_of_support_groups(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(required_observations=3)

        for challenger_x in (70.0, 78.0, 86.0):
            selected, debug = quorum.update(
                incumbent_point=(10.0, 10.0),
                challenger_point=(challenger_x, 10.0),
                stable_scale_px=20.0,
                group_margins={"background_motion": 0.7, "anchor_shape_identity": 0.3},
            )

        self.assertEqual(selected, (10.0, 10.0))
        self.assertEqual(debug["reason"], "quorum_pending")

        selected, debug = quorum.update(
            incumbent_point=(18.0, 10.0),
            challenger_point=(94.0, 10.0),
            stable_scale_px=20.0,
            group_margins={
                "background_motion": 0.7,
                "local_rigid": 0.2,
                "anchor_shape_identity": 0.3,
            },
        )

        self.assertEqual(selected, (94.0, 10.0))
        self.assertEqual(debug["reason"], "persistent_quorum_confirmed")

    def test_required_local_rigid_support_vetoes_static_majority(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(
            required_groups=3,
            required_observations=3,
            required_positive_groups=("local_rigid",),
        )

        for challenger_x in (70.0, 78.0, 86.0):
            selected, debug = quorum.update(
                incumbent_point=(10.0, 10.0),
                challenger_point=(challenger_x, 10.0),
                stable_scale_px=20.0,
                group_margins={
                    "background_motion": 0.3,
                    "local_rigid": -0.2,
                    "texture_background": 0.02,
                    "anchor_shape_identity": 0.8,
                },
            )

        self.assertEqual(selected, (10.0, 10.0))
        self.assertEqual(debug["reason"], "required_support_rejected")

    def test_custom_merge_groups_confirm_persistent_relative_identity(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(
            support_groups=(
                "background_relative_identity",
                "background_motion",
                "anchor_shape_identity",
            ),
            required_groups=2,
            required_observations=2,
            required_positive_groups=("background_relative_identity",),
        )

        first, first_debug = quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(14.0, 10.0),
            stable_scale_px=20.0,
            group_margins={
                "background_relative_identity": 2.4,
                "background_motion": 0.3,
            },
        )
        second, second_debug = quorum.update(
            incumbent_point=(11.0, 10.0),
            challenger_point=(15.0, 10.0),
            stable_scale_px=20.0,
            group_margins={
                "background_relative_identity": 2.1,
                "background_motion": 0.2,
            },
        )

        self.assertEqual(first, (10.0, 10.0))
        self.assertEqual(first_debug["reason"], "persistence_pending")
        self.assertEqual(second, (15.0, 10.0))
        self.assertEqual(second_debug["reason"], "persistent_quorum_confirmed")

    def test_custom_groups_ignore_unlisted_stock_support(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(
            support_groups=("background_relative_identity", "background_motion"),
            required_groups=2,
            required_observations=2,
        )

        selected, debug = quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(14.0, 10.0),
            stable_scale_px=20.0,
            group_margins={"local_rigid": 1.0},
        )

        self.assertEqual(selected, (10.0, 10.0))
        self.assertEqual(debug["reason"], "support_missing")

    def test_required_custom_group_vetoes_other_positive_votes(self) -> None:
        module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
        quorum = module.PersistentEvidenceQuorum(
            support_groups=(
                "background_relative_identity",
                "background_motion",
                "anchor_shape_identity",
            ),
            required_groups=2,
            required_observations=1,
            required_positive_groups=("background_relative_identity",),
        )

        selected, debug = quorum.update(
            incumbent_point=(10.0, 10.0),
            challenger_point=(14.0, 10.0),
            stable_scale_px=20.0,
            group_margins={
                "background_relative_identity": -0.1,
                "background_motion": 0.8,
                "anchor_shape_identity": 0.8,
            },
        )

        self.assertEqual(selected, (10.0, 10.0))
        self.assertEqual(debug["reason"], "required_support_rejected")


def _candidate(
    candidate_id: str,
    score: float,
    *,
    width: float = 20.0,
    height: float = 20.0,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        frame_index=1,
        bbox=(0.0, 0.0, width, height),
        center=(width / 2.0, height / 2.0),
        score=score,
        source="raw",
    )


if __name__ == "__main__":
    unittest.main()
