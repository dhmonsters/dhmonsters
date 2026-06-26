# 투명 도형 퍼즐 추적 엔진의 상태 전환과 후보 선택 규칙을 검증합니다.
import unittest
from unittest.mock import patch

import _transparent_engine_replay_score as replay
from core.vision.transparent_puzzle_engine import (
    BackgroundCatalog,
    EngineConfig,
    PuzzleCandidate,
    PuzzleEngineInput,
    TransparentPuzzleEngine,
    candidate_from_live_row,
    internal_points,
)


class TransparentPuzzleEngineTests(unittest.TestCase):
    def test_white_anchor_wins_during_prep(self):
        engine = TransparentPuzzleEngine()

        out = engine.update(PuzzleEngineInput(
            frame_index=0,
            candidates=[PuzzleCandidate(100.0, 100.0, 0.8, 40.0, 40.0)],
            white_anchor=(220.0, 180.0),
        ))

        self.assertEqual((out.x, out.y), (220.0, 180.0))
        self.assertEqual(out.state, "white_anchor")
        self.assertIsNone(out.candidate_index)

    def test_period_is_measured_from_candidate_repetition(self):
        catalog = BackgroundCatalog()
        for frame in range(8):
            x = float((frame % 5) * 10)
            catalog.add_frame(frame, [PuzzleCandidate(x, 0.0, 1.0, 20.0, 20.0)])

        period, score = catalog.estimate_period(prep_end=6, min_lag=3, max_lag=6)

        self.assertEqual(period, 5)
        self.assertLess(score, 1.0)

    def test_engine_prefers_continuous_candidate(self):
        engine = TransparentPuzzleEngine()
        engine.update(PuzzleEngineInput(0, [], white_anchor=(100.0, 100.0)))

        out = engine.update(PuzzleEngineInput(1, [
            PuzzleCandidate(108.0, 100.0, 0.4, 30.0, 30.0),
            PuzzleCandidate(220.0, 100.0, 0.99, 30.0, 30.0),
        ]))

        self.assertEqual(out.candidate_index, 0)
        self.assertEqual(out.state, "candidate")

    def test_engine_removes_periodic_background_candidate(self):
        engine = TransparentPuzzleEngine(EngineConfig(
            max_candidate_jump=120.0,
            use_background_catalog=True,
        ))
        prep_background = [
            110.0,
            150.0,
            190.0,
            230.0,
            270.0,
            110.0,
        ]
        for frame, bg_x in enumerate(prep_background):
            engine.update(PuzzleEngineInput(
                frame,
                [PuzzleCandidate(bg_x, 0.0, 0.9, 20.0, 20.0)],
                white_anchor=(100.0, 0.0),
            ))

        out = engine.update(PuzzleEngineInput(6, [
            PuzzleCandidate(150.0, 0.0, 0.95, 20.0, 20.0),
            PuzzleCandidate(40.0, 0.0, 0.80, 20.0, 20.0),
        ]))

        self.assertEqual(out.candidate_index, 1)
        self.assertEqual((out.x, out.y), (40.0, 0.0))

    def test_engine_coasts_when_candidates_jump_too_far(self):
        engine = TransparentPuzzleEngine(EngineConfig(max_candidate_jump=50.0, coast_frames=3))
        engine.update(PuzzleEngineInput(0, [], white_anchor=(100.0, 100.0)))
        engine.update(PuzzleEngineInput(1, [
            PuzzleCandidate(110.0, 100.0, 0.8, 30.0, 30.0),
        ]))

        out = engine.update(PuzzleEngineInput(2, [
            PuzzleCandidate(300.0, 300.0, 0.99, 30.0, 30.0),
        ]))

        self.assertEqual(out.state, "coast")
        self.assertAlmostEqual(out.x, 120.0, delta=1.0)

    def test_internal_points_include_center_and_box_offsets(self):
        pts = internal_points(
            PuzzleCandidate(100.0, 100.0, 0.8, 40.0, 20.0),
            grid_size=3,
            shrink=0.5,
        )

        self.assertIn((100.0, 100.0), pts)
        self.assertIn((90.0, 95.0), pts)
        self.assertIn((110.0, 105.0), pts)

    def test_merged_candidate_uses_predicted_internal_point(self):
        engine = TransparentPuzzleEngine(EngineConfig(max_candidate_jump=100.0))
        engine.update(PuzzleEngineInput(0, [], white_anchor=(100.0, 100.0)))
        engine.update(PuzzleEngineInput(1, [
            PuzzleCandidate(110.0, 100.0, 0.8, 60.0, 60.0),
        ]))

        out = engine.update(PuzzleEngineInput(2, [
            PuzzleCandidate(160.0, 100.0, 0.8, 120.0, 60.0),
        ]))

        self.assertEqual(out.state, "merged_internal")
        self.assertLess(abs(out.x - 120.0), abs(out.x - 160.0))

    def test_replay_adapter_converts_candidate_tuple(self):
        candidate = replay.candidate_from_tuple((10.0, 20.0, 0.7, 30.0, 40.0))

        self.assertEqual(candidate.cx, 10.0)
        self.assertEqual(candidate.cy, 20.0)
        self.assertEqual(candidate.score, 0.7)
        self.assertEqual(candidate.w, 30.0)
        self.assertEqual(candidate.h, 40.0)

    def test_replay_inputs_use_white_anchor_only_before_prep_end(self):
        with patch.object(replay.phase_catalog, "load_frames", return_value=[object(), object(), object()]):
            with patch.object(replay.phase_catalog, "load_rows", return_value=[{}, {}, {}]):
                with patch.object(replay.phase_catalog, "load_wrows", return_value=None):
                    with patch.object(
                        replay.phase_catalog,
                        "detect_prep",
                        return_value=(2, {0: (1.0, 1.0), 1: (2.0, 2.0), 2: (3.0, 3.0)}),
                    ):
                        with patch.object(
                            replay.phase_catalog,
                            "candidate_sets",
                            return_value=[[], [], []],
                        ):
                            inputs = replay.load_engine_inputs("dummy")

        self.assertEqual(inputs[0].white_anchor, (1.0, 1.0))
        self.assertEqual(inputs[1].white_anchor, (2.0, 2.0))
        self.assertIsNone(inputs[2].white_anchor)

    def test_live_candidate_adapter_uses_yolo_order(self):
        candidate = candidate_from_live_row((10.0, 20.0, 0.7, 30.0, 40.0))

        self.assertEqual(candidate.cx, 10.0)
        self.assertEqual(candidate.cy, 20.0)
        self.assertEqual(candidate.score, 0.7)
        self.assertEqual(candidate.w, 30.0)
        self.assertEqual(candidate.h, 40.0)

    def test_replay_output_permission_failure_is_nonfatal(self):
        with patch("pathlib.Path.write_text", side_effect=PermissionError("blocked")):
            result = replay.write_outputs([])

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
