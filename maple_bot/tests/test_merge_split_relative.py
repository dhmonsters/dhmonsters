# 병합 분리 판별기의 배경 상대 좌표와 신분 복원 동작을 검증합니다.
from __future__ import annotations

import importlib
import unittest


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


if __name__ == "__main__":
    unittest.main()
