# planet_solver_noauth 방식의 live preview와 마우스 이동 어댑터를 검증한다.
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from core.puzzle.live_temporal_selector import LiveTemporalDecision, LiveTemporalSelector
from core.puzzle.models import FramePacket, IdentityDecision, RoiSpec
from core.puzzle.planet_live import PlanetLiveSolver, PlanetMouseController, render_planet_cctv_preview
from core.puzzle.planet_noauth import PlanetNoAuthDetector


class PlanetMouseControllerTest(unittest.TestCase):
    def test_move_to_det_point_uses_noauth_client_roi_click(self) -> None:
        clicked: list[tuple[int, int]] = []
        controller = PlanetMouseController(
            background_clicker=lambda x, y: clicked.append((x, y)),
            client_origin_getter=lambda: (1000, 500),
        )
        detect_roi = RoiSpec("detect", "window_client", 100, 200, 300, 250)

        result = controller.move_to_det_point(
            detect_roi=detect_roi,
            point=(50.0, 60.0),
            det_frame=None,
            enabled=True,
        )

        self.assertTrue(result.moved)
        self.assertEqual(clicked, [(150, 260)])
        self.assertEqual(result.client_point, (150, 260))
        self.assertEqual(result.abs_point, (1150, 760))
        self.assertEqual(result.offset, (0.0, 0.0))
        self.assertEqual(result.reason, "bg_click")

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


class PlanetLiveSolverTemporalSelectorTest(unittest.TestCase):
    def test_live_temporal_selector_defaults_to_fast_family_pool(self) -> None:
        selector = LiveTemporalSelector()

        self.assertFalse(selector.family_pool.enable_bg_mht)
        self.assertFalse(selector.family_pool.enable_raw_mht)
        self.assertFalse(selector.family_pool.enable_phase_mht)

    def test_analyze_uses_temporal_selector_point_for_mouse_target(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [(10.0, 20.0, 0.8, 12.0, 14.0)]

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "TRACK_CONFIDENT",
                    (999.0, 999.0),
                    "wrong",
                    0.1,
                    "fake_wrong_identity",
                    0,
                    {},
                )

        class _FakeTemporalSelector:
            def __init__(self) -> None:
                self.calls = []

            def update(self, **kwargs):
                self.calls.append(kwargs)
                return LiveTemporalDecision(
                    point=(60.0, 70.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="good_family",
                )

        temporal_selector = _FakeTemporalSelector()
        solver = PlanetLiveSolver(
            detector=_FakeDetector(),
            identity_tracker=_FakeIdentityTracker(),
            temporal_selector=temporal_selector,
            mouse=PlanetMouseController(
                background_clicker=lambda x, y: clicked.append((x, y)),
                client_origin_getter=lambda: (0, 0),
            ),
        )
        roi = {
            "name": "detect",
            "x": 10,
            "y": 20,
            "w": 120,
            "h": 120,
        }
        frame = np.zeros((180, 180, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=7,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:140, 10:130],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)

        self.assertEqual(clicked, [(70, 90)])
        self.assertEqual(result.mouse_move.det_point, (60.0, 70.0))
        self.assertEqual(result.temporal_decision.family, "good_family")
        self.assertEqual(temporal_selector.calls[0]["primary_point"], (999.0, 999.0))


if __name__ == "__main__":
    unittest.main()
