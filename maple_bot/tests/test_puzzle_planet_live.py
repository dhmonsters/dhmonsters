# planet_solver_noauth 방식의 live preview와 마우스 이동 어댑터를 검증한다.
from __future__ import annotations

import unittest

import numpy as np

from core.puzzle.models import RoiSpec
from core.puzzle.planet_live import PlanetMouseController, render_planet_cctv_preview


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

        self.assertEqual(preview.shape[:2], (619, 695))
        self.assertTrue(np.any(preview[:, :, 1] > 200))
        self.assertTrue(np.any(preview[:, :, 2] > 200))


if __name__ == "__main__":
    unittest.main()
