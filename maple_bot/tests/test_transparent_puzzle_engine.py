# 투명 도형 퍼즐 추적 엔진의 상태 전환과 후보 선택 규칙을 검증합니다.
import unittest

from core.vision.transparent_puzzle_engine import (
    BackgroundCatalog,
    EngineConfig,
    PuzzleCandidate,
    PuzzleEngineInput,
    TransparentPuzzleEngine,
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


if __name__ == "__main__":
    unittest.main()
