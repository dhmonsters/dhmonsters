# 투명도형 MHT solver의 박스 내부 상태 선택을 검증합니다.
import unittest

from core.vision.transparent_mht_solver import (
    MhtCandidate,
    MhtFrame,
    solve_mht,
)
import _transparent_mht_replay_score as replay_score


class TransparentMhtSolverTests(unittest.TestCase):
    def test_merged_candidate_uses_internal_point_near_prediction(self):
        frames = [
            MhtFrame(0, [], anchor=(0.0, 0.0)),
            MhtFrame(1, [MhtCandidate(40.0, 0.0, 1.0, 20.0, 20.0)]),
            MhtFrame(2, [
                MhtCandidate(
                    40.0,
                    0.0,
                    1.0,
                    100.0,
                    50.0,
                    bg_center=(40.0, 0.0),
                )
            ]),
        ]

        path = solve_mht(frames, grid_size=5, shrink=0.76)

        self.assertAlmostEqual(path[2][0], 78.0, delta=0.001)
        self.assertAlmostEqual(path[2][1], 0.0, delta=0.001)

    def test_background_repel_does_not_choose_far_decal_when_prediction_is_elsewhere(self):
        frames = [
            MhtFrame(0, [], anchor=(0.0, 0.0)),
            MhtFrame(1, [MhtCandidate(20.0, 0.0, 1.0, 20.0, 20.0)]),
            MhtFrame(2, [
                MhtCandidate(40.0, 0.0, 1.0, 20.0, 20.0),
                MhtCandidate(
                    80.0,
                    0.0,
                    1.0,
                    100.0,
                    50.0,
                    bg_center=(80.0, 0.0),
                ),
            ]),
        ]

        path = solve_mht(frames, grid_size=5, shrink=0.76)

        self.assertAlmostEqual(path[2][0], 40.0, delta=0.001)
        self.assertAlmostEqual(path[2][1], 0.0, delta=0.001)

    def test_replay_candidate_tuple_order_is_center_size_score(self):
        candidate = replay_score.candidate_from_tuple(
            (10.0, 20.0, 30.0, 40.0, 0.75),
            bg_center=(11.0, 21.0),
            motion_score=4.0,
            viol_score=5.0,
            bg_score=6.0,
        )

        self.assertEqual(candidate, MhtCandidate(
            10.0,
            20.0,
            0.75,
            30.0,
            40.0,
            bg_center=(11.0, 21.0),
            motion_score=4.0,
            viol_score=5.0,
            bg_score=6.0,
        ))

    def test_stable_prep_end_ignores_late_isolated_white_flash(self):
        prep_end = replay_score.stable_prep_end_from_big_frames(
            big_frames=list(range(58)) + [128],
            min_run=20,
            max_gap=2,
        )

        self.assertEqual(prep_end, 58)


if __name__ == "__main__":
    unittest.main()
