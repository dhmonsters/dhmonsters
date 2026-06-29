# planet_solver_noauth 방식의 live preview와 마우스 이동 어댑터를 검증한다.
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from core.puzzle.live_temporal_selector import LiveTemporalDecision, LiveTemporalSelector
from core.puzzle.models import FramePacket, IdentityDecision, RoiSpec
from core.puzzle.defaults import fixed_detect_roi, fixed_popup_header_roi, fixed_popup_preview_roi
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

        self.assertEqual(preview.shape[:2], (634, 695))
        self.assertTrue(np.any(preview[:, :, 1] > 200))
        self.assertTrue(np.any(preview[:, :, 2] > 200))

    def test_render_preview_draws_header_at_actual_hdr_roi_offset(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        header_roi = fixed_popup_header_roi(frame_w=1920, frame_h=1080)
        preview_roi = fixed_popup_preview_roi(frame_w=1920, frame_h=1080)
        detect_roi = fixed_detect_roi(frame_w=1920, frame_h=1080)

        preview = render_planet_cctv_preview(frame, popup_score=0.72)

        hdr_top = header_roi.y - preview_roi.y
        hdr_bottom = hdr_top + header_roi.h - 1
        det_top = detect_roi.y - preview_roi.y
        self.assertGreater(hdr_top, 0)
        self.assertLessEqual(det_top - hdr_bottom, 4)
        self.assertTrue(np.array_equal(preview[hdr_top, 3], np.array([0, 230, 255], dtype=np.uint8)))
        self.assertTrue(np.array_equal(preview[hdr_bottom, 3], np.array([0, 230, 255], dtype=np.uint8)))
        self.assertTrue(np.array_equal(preview[det_top, 3], np.array([0, 140, 255], dtype=np.uint8)))


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
    def test_planet_live_solver_default_path_uses_scoreboard_backed_selector(self) -> None:
        solver = PlanetLiveSolver()

        selector = solver.temporal_selector
        self.assertIsInstance(selector, LiveTemporalSelector)
        self.assertTrue(selector.runtime.use_judge_scoreboard)
        self.assertIs(selector.selector_shadow.runtime, selector.runtime)
        self.assertEqual(selector.selector_shadow.emit_every, 1)

    def test_live_temporal_selector_defaults_to_fast_family_pool(self) -> None:
        selector = LiveTemporalSelector()

        self.assertFalse(selector.family_pool.enable_phase_catalog)
        self.assertFalse(selector.family_pool.enable_bg_mht)
        self.assertFalse(selector.family_pool.enable_raw_mht)
        self.assertFalse(selector.family_pool.enable_phase_mht)
        self.assertFalse(selector.family_pool.enable_guarded_decal_identity)
        self.assertEqual(selector.family_pool.raw_rank_families, 0)
        self.assertEqual(selector.family_pool.raw_continuity_families, 20)
        self.assertEqual(selector.family_pool.raw_beam_families, 0)
        self.assertEqual(selector.family_pool.raw_max_candidates_per_frame, 24)
        self.assertIn(("p1", "p05"), selector.family_pool.raw_box_rel_pairs)

    def test_live_temporal_selector_passes_expected_background_to_shadow(self) -> None:
        class _FakeFamilyPool:
            def __init__(self) -> None:
                self.frames = []

            def update(self, frame_index, **_kwargs):
                self.frames.append(frame_index)
                return types.SimpleNamespace(
                    points={"panel_default_center_mild_state_mild": (10.0, 20.0)},
                    debug={},
                )

            def expected_background_by_frame(self, frames):
                return {
                    int(frame): [(99, (100.0, 200.0, 0.8, 20.0, 20.0))]
                    for frame in frames
                }

        class _FakeShadow:
            def __init__(self) -> None:
                self.calls = []

            def reset(self, **_kwargs):
                pass

            def update(self, frame_index, **kwargs):
                self.calls.append((frame_index, kwargs))
                return {
                    "family": "panel_default_center_mild_state_mild",
                    "point": [10, 20],
                    "rescue_point": [10.0, 20.0],
                    "rescue_allowed": False,
                }

        shadow = _FakeShadow()
        selector = LiveTemporalSelector(
            family_pool=_FakeFamilyPool(),
            selector_shadow=shadow,
            use_expected_background=True,
        )

        selector.update(
            frame_index=5,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
        )

        expected = shadow.calls[-1][1]["expected_by_frame"]
        self.assertEqual(expected[5][0][0], 99)

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

    def test_analyze_dry_run_keeps_temporal_decision_without_mouse_click(self) -> None:
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
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(60.0, 70.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="good_family",
                )

        solver = PlanetLiveSolver(
            detector=_FakeDetector(),
            identity_tracker=_FakeIdentityTracker(),
            temporal_selector=_FakeTemporalSelector(),
            mouse=PlanetMouseController(
                background_clicker=lambda x, y: clicked.append((x, y)),
                client_origin_getter=lambda: (0, 0),
            ),
            mouse_enabled=False,
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

        self.assertEqual(clicked, [])
        self.assertFalse(result.mouse_move.moved)
        self.assertEqual(result.mouse_move.reason, "disabled")
        self.assertEqual(result.temporal_decision.family, "good_family")


if __name__ == "__main__":
    unittest.main()
