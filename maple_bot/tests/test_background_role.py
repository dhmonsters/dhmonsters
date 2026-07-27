# 배경 심판 점수와 후보 역할 판정을 검증하는 테스트입니다.
import math
import unittest

from core.puzzle.background_role import (
    BackgroundJudgeVector,
    BackgroundRoleProfile,
    decide_background_role,
    residual_to_similarity,
)


def profile(**overrides):
    values = {
        "weights": {"texture": 1.0, "edge": 1.0},
        "saturation": {},
        "resolve_margin": 0.1,
        "physical_jump_limit": 0.5,
        "yolo_floor": 0.8,
        "yolo_uncertainty_weight": 0.2,
    }
    values.update(overrides)
    return BackgroundRoleProfile(**values)


def candidate(candidate_id, values, jump=0.0, quality=1.0):
    return BackgroundJudgeVector(candidate_id, values, jump, quality)


class ResidualToSimilarityTests(unittest.TestCase):
    def test_rejects_invalid_residuals_and_clamps_at_saturation(self):
        for residual in (None, True, False, -0.1, math.nan, math.inf, -math.inf):
            self.assertIsNone(residual_to_similarity(residual, 2.0))
        self.assertEqual(residual_to_similarity(0.0, 2.0), 1.0)
        self.assertAlmostEqual(residual_to_similarity(1.0, 2.0), 0.5)
        self.assertEqual(residual_to_similarity(2.0, 2.0), 0.0)
        self.assertEqual(residual_to_similarity(3.0, 2.0), 0.0)

    def test_rejects_non_positive_or_non_finite_saturation(self):
        for saturation in (0.0, -1.0, math.nan, math.inf):
            with self.assertRaises(ValueError):
                residual_to_similarity(0.0, saturation)


class BackgroundRoleDecisionTests(unittest.TestCase):
    def test_missing_judges_are_renormalized_and_contributions_use_common_judges(self):
        background = candidate("background", {"texture": 1.0, "edge": None})
        target = candidate("target", {"texture": 0.0, "edge": 1.0})

        decision = decide_background_role(background, target, profile())

        self.assertEqual(decision.status, "resolved")
        self.assertEqual(decision.background_candidate_id, "background")
        self.assertEqual(decision.target_candidate_id, "target")
        self.assertEqual(decision.available_weight, 1.0)
        self.assertEqual(decision.judge_contributions, {"texture": 1.0})

    def test_holds_when_background_scores_are_ambiguous(self):
        decision = decide_background_role(
            candidate("a", {"texture": 0.6}),
            candidate("b", {"texture": 0.5}),
            profile(weights={"texture": 1.0}),
        )

        self.assertEqual(decision.status, "hold")
        self.assertEqual(decision.reason, "hold_ambiguous_background")
        self.assertAlmostEqual(decision.margin, 0.1)

    def test_holds_when_candidates_have_no_common_available_judge(self):
        decision = decide_background_role(
            candidate("a", {"texture": 0.9, "edge": None}),
            candidate("b", {"texture": None, "edge": 0.8}),
            profile(),
        )

        self.assertEqual(decision.status, "hold")
        self.assertEqual(decision.reason, "hold_no_background_evidence")
        self.assertEqual(decision.margin, 0.0)
        self.assertEqual(decision.available_weight, 0.0)

    def test_physical_gate_excludes_one_candidate_from_target_role(self):
        decision = decide_background_role(
            candidate("a", {"texture": 0.9}, jump=0.8),
            candidate("b", {"texture": 0.2}, jump=0.1),
            profile(weights={"texture": 1.0}),
        )

        self.assertEqual(decision.status, "resolved")
        self.assertEqual(decision.background_candidate_id, "a")
        self.assertEqual(decision.target_candidate_id, "b")

    def test_physical_gate_can_resolve_even_when_score_margin_is_small(self):
        decision = decide_background_role(
            candidate("a", {"texture": 0.51}, jump=0.8),
            candidate("b", {"texture": 0.5}, jump=0.1),
            profile(weights={"texture": 1.0}),
        )

        self.assertEqual(decision.status, "resolved")
        self.assertEqual(decision.target_candidate_id, "b")
        self.assertEqual(decision.background_candidate_id, "a")

    def test_holds_when_both_candidates_fail_physical_gate(self):
        decision = decide_background_role(
            candidate("a", {"texture": 0.9}, jump=0.8),
            candidate("b", {"texture": 0.2}, jump=0.9),
            profile(weights={"texture": 1.0}),
        )

        self.assertEqual(decision.status, "hold")
        self.assertEqual(decision.reason, "hold_ambiguous_background")

    def test_yolo_quality_only_increases_required_margin_below_floor(self):
        clear = decide_background_role(
            candidate("a", {"texture": 0.65}, quality=1.0),
            candidate("b", {"texture": 0.5}, quality=1.0),
            profile(weights={"texture": 1.0}),
        )
        uncertain = decide_background_role(
            candidate("a", {"texture": 0.65}, quality=0.6),
            candidate("b", {"texture": 0.5}, quality=1.0),
            profile(weights={"texture": 1.0}),
        )

        self.assertEqual(clear.status, "resolved")
        self.assertEqual(uncertain.status, "hold")
        self.assertAlmostEqual(uncertain.margin, 0.15)

    def test_uses_only_judges_available_for_both_candidates(self):
        decision = decide_background_role(
            candidate("a", {"texture": 0.9, "edge": None}),
            candidate("b", {"texture": 0.2, "edge": 1.0}),
            profile(),
        )

        self.assertEqual(decision.status, "resolved")
        self.assertEqual(decision.available_weight, 1.0)
        self.assertEqual(decision.judge_contributions, {"texture": 1.0})

    def test_rejects_invalid_profile_and_candidate_values(self):
        with self.assertRaises(ValueError):
            decide_background_role(
                candidate("a", {"texture": 0.5}),
                candidate("a", {"texture": 0.4}),
                profile(weights={"texture": 1.0}),
            )
        with self.assertRaises(ValueError):
            decide_background_role(
                candidate("a", {"texture": 1.1}),
                candidate("b", {"texture": 0.4}),
                profile(weights={"texture": 1.0}),
            )
        with self.assertRaises(ValueError):
            decide_background_role(
                candidate("a", {"texture": 0.5}),
                candidate("b", {"texture": 0.4}),
                profile(weights={"texture": -1.0}),
            )


if __name__ == "__main__":
    unittest.main()
