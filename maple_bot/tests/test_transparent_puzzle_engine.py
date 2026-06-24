# 투명 도형 퍼즐 추적 엔진의 상태 전환과 후보 선택 규칙을 검증합니다.
import unittest

from core.vision.transparent_puzzle_engine import (
    BackgroundCatalog,
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


if __name__ == "__main__":
    unittest.main()
