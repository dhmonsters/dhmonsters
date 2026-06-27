# planet_solver_noauth 방식의 live preview와 마우스 이동 어댑터를 검증한다.
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from core.puzzle.models import RoiSpec
from core.puzzle.planet_live import PlanetMouseController, render_planet_cctv_preview
from core.puzzle.planet_noauth import PlanetNoAuthDetector


class PlanetMouseControllerTest(unittest.TestCase):
    def test_move_to_det_point_uses_cursor_offset_learning(self) -> None:
        moved: list[tuple[int, int]] = []
        controller = PlanetMouseController(
            cursor_setter=lambda x, y: moved.append((x, y)),
            cursor_detector=lambda _frame: (20.0, 30.0),
        )
        detect_roi = RoiSpec("detect", "window_client", 100, 200, 300, 250)
        det_frame = np.zeros((250, 300, 3), dtype=np.uint8)

        result = controller.move_to_det_point(
            detect_roi=detect_roi,
            point=(50.0, 60.0),
            det_frame=det_frame,
            enabled=True,
        )

        self.assertTrue(result.moved)
        self.assertEqual(moved, [(165, 275)])
        self.assertEqual(result.abs_point, (165, 275))
        self.assertEqual(result.offset, (15.0, 15.0))

    def test_move_to_det_point_skips_when_disabled(self) -> None:
        moved: list[tuple[int, int]] = []
        controller = PlanetMouseController(cursor_setter=lambda x, y: moved.append((x, y)))
        detect_roi = RoiSpec("detect", "window_client", 100, 200, 300, 250)

        result = controller.move_to_det_point(
            detect_roi=detect_roi,
            point=(50.0, 60.0),
            det_frame=None,
            enabled=False,
        )

        self.assertFalse(result.moved)
        self.assertEqual(moved, [])


class PlanetCctvPreviewTest(unittest.TestCase):
    def test_render_preview_crops_popup_area_and_draws_roi_guides(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        preview = render_planet_cctv_preview(
            frame,
            popup_score=0.72,
            candidates=[(30.0, 40.0, 0.9, 10.0, 12.0)],
            track_pos=(30.0, 40.0),
        )

        self.assertEqual(preview.shape[:2], (717, 948))
        self.assertTrue(np.any(preview[:, :, 1] > 200))
        self.assertTrue(np.any(preview[:, :, 2] > 200))


class PlanetNoAuthDetectorTest(unittest.TestCase):
    def test_detect_all_uses_planet_solver_m1_signature(self) -> None:
        calls = []

        class _FakeM1:
            def detect(self, board, imgsz, score):
                calls.append((board.shape[:2], imgsz, score))
                return np.array([[10, 20, 50, 80, 0.81, 0]], dtype=np.float32)

        fake_module = types.ModuleType("planet_live_solver")
        fake_module.load_models = lambda use_gpu=False: (_FakeM1(), object())

        with patch.dict(sys.modules, {"planet_live_solver": fake_module}):
            detector = PlanetNoAuthDetector()
            rows = detector.detect_all(np.zeros((120, 200, 3), dtype=np.uint8))

        self.assertEqual(calls, [((120, 200), 192, 0.2)])
        self.assertEqual(rows, [(30, 50, 0.8100000023841858, 40, 60)])


if __name__ == "__main__":
    unittest.main()
