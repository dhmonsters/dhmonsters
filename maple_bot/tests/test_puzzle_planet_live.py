# planet_solver_noauth 방식의 live preview와 마우스 이동 어댑터를 검증한다.
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from core.puzzle.live_temporal_selector import LiveTemporalDecision, LiveTemporalSelector
from core.puzzle.evidence import LiveEvidenceJudges
from core.puzzle.models import FramePacket, IdentityDecision, RoiSpec
from core.puzzle.defaults import fixed_detect_roi, fixed_popup_header_roi, fixed_popup_preview_roi
from core.puzzle.planet_live import MouseMoveResult, PlanetLiveSolver, PlanetMouseController, render_planet_cctv_preview
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

    def test_move_to_det_point_defaults_to_visible_cursor_move(self) -> None:
        moved: list[tuple[int, int]] = []
        controller = PlanetMouseController(
            cursor_setter=lambda x, y: moved.append((x, y)),
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
        self.assertEqual(moved, [(1150, 760)])
        self.assertEqual(result.client_point, (150, 260))
        self.assertEqual(result.abs_point, (1150, 760))
        self.assertEqual(result.reason, "fg_move")

    def test_move_to_det_point_learns_visible_cursor_offset(self) -> None:
        moved: list[tuple[int, int]] = []
        controller = PlanetMouseController(
            cursor_setter=lambda x, y: moved.append((x, y)),
            cursor_detector=lambda _frame: (70.0, 80.0),
            client_origin_getter=lambda: (1000, 500),
            offset_alpha=0.5,
        )
        detect_roi = RoiSpec("detect", "window_client", 100, 200, 300, 250)

        result = controller.move_to_det_point(
            detect_roi=detect_roi,
            point=(50.0, 60.0),
            det_frame=np.zeros((250, 300, 3), dtype=np.uint8),
            enabled=True,
        )

        self.assertTrue(result.moved)
        self.assertEqual(moved, [(1140, 750)])
        self.assertEqual(result.client_point, (140, 250))
        self.assertEqual(result.abs_point, (1140, 750))
        self.assertEqual(result.offset, (-10.0, -10.0))
        self.assertEqual(result.reason, "fg_move")

    def test_move_to_det_point_can_freeze_visible_cursor_offset(self) -> None:
        moved: list[tuple[int, int]] = []
        controller = PlanetMouseController(
            cursor_setter=lambda x, y: moved.append((x, y)),
            cursor_detector=lambda _frame: (80.0, 80.0),
            client_origin_getter=lambda: (0, 0),
            offset_alpha=1.0,
        )
        detect_roi = RoiSpec("detect", "window_client", 0, 0, 300, 250)
        frame = np.zeros((250, 300, 3), dtype=np.uint8)

        learned = controller.move_to_det_point(
            detect_roi=detect_roi,
            point=(50.0, 50.0),
            det_frame=frame,
            enabled=True,
            learn_offset=True,
        )
        frozen = controller.move_to_det_point(
            detect_roi=detect_roi,
            point=(100.0, 100.0),
            det_frame=frame,
            enabled=True,
            learn_offset=False,
        )

        self.assertEqual(learned.offset, (-30.0, -30.0))
        self.assertEqual(frozen.offset, (-30.0, -30.0))
        self.assertEqual(moved, [(20, 20), (70, 70)])

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
    def test_detect_all_prefers_shape_yolo_weak_candidates(self) -> None:
        shape_calls = []
        m1_calls = []

        class _FakeShapeYolo:
            enabled = True

            def detect_all(self, frame, score_thr=0.2):
                shape_calls.append((frame.shape[:2], score_thr))
                return [(20, 30, 0.18, 40, 50)]

        class _FakeM1:
            def detect(self, board, imgsz, score):
                m1_calls.append((board.shape[:2], imgsz, score))
                return np.array([[1, 2, 3, 4, 0.99, 0]], dtype=np.float32)

        fake_module = types.ModuleType("planet_live_solver")
        fake_module.load_models = lambda use_gpu=False: (_FakeM1(), object())

        with patch.dict(sys.modules, {"planet_live_solver": fake_module}):
            detector = PlanetNoAuthDetector(shape_detector=_FakeShapeYolo(), shape_score=0.10)
            rows = detector.detect_all(np.zeros((120, 200, 3), dtype=np.uint8))

        self.assertEqual(rows, [(20, 30, 0.18, 40, 50)])
        self.assertEqual(shape_calls, [((120, 200), 0.10)])
        self.assertEqual(m1_calls, [])
        self.assertEqual(detector.load_source, "shape_yolo")

    def test_detect_all_retries_shape_yolo_after_live_solver_prepares_runtime(self) -> None:
        class _FakeShapeYolo:
            calls = 0

            def __init__(self) -> None:
                type(self).calls += 1
                self.enabled = type(self).calls >= 2

            def detect_all(self, _frame, score_thr=0.2):
                if not self.enabled:
                    return []
                return [(70, 80, 0.44, 18, 20)]

        class _FakeM1:
            def detect(self, _board, _imgsz, _score):
                return []

        shape_module = types.ModuleType("core.shape_yolo")
        shape_module.ShapeYolo = _FakeShapeYolo
        live_solver = types.ModuleType("planet_live_solver")
        live_solver.load_models = lambda use_gpu=False: (_FakeM1(), object())

        with patch.dict(sys.modules, {"core.shape_yolo": shape_module, "planet_live_solver": live_solver}):
            detector = PlanetNoAuthDetector(shape_score=0.10)
            rows = detector.detect_all(np.zeros((120, 200, 3), dtype=np.uint8))

        self.assertEqual(rows, [(70, 80, 0.44, 18, 20)])
        self.assertEqual(_FakeShapeYolo.calls, 2)
        self.assertEqual(detector.load_source, "shape_yolo")

    def test_detect_all_inpaints_pink_cursor_before_shape_yolo(self) -> None:
        shape_frames = []

        class _FakeShapeYolo:
            enabled = True

            def detect_all(self, frame, score_thr=0.2):
                shape_frames.append(frame.copy())
                return [(55, 65, 0.24, 30, 32)]

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[55:66, 75:86] = np.array([255, 0, 255], dtype=np.uint8)
        detector = PlanetNoAuthDetector(shape_detector=_FakeShapeYolo(), shape_score=0.10)

        rows = detector.detect_all(frame)

        self.assertEqual(rows, [(55, 65, 0.24, 30, 32)])
        self.assertEqual(len(shape_frames), 1)
        self.assertFalse(np.array_equal(shape_frames[0][60, 80], frame[60, 80]))
        self.assertLess(int(shape_frames[0][60, 80].max()), 80)

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

    def test_detect_all_retries_m1_with_weak_score_when_primary_is_empty(self) -> None:
        calls = []

        class _FakeM1:
            def detect(self, board, imgsz, score):
                calls.append((board.shape[:2], imgsz, score))
                if score > 0.1:
                    return np.zeros((0, 6), dtype=np.float32)
                return np.array([[10, 20, 50, 80, 0.09, 0]], dtype=np.float32)

        fake_module = types.ModuleType("planet_live_solver")
        fake_module.load_models = lambda use_gpu=False: (_FakeM1(), object())

        with patch.dict(sys.modules, {"planet_live_solver": fake_module}):
            detector = PlanetNoAuthDetector(weak_scores=(0.08,))
            rows = detector.detect_all(np.zeros((120, 200, 3), dtype=np.uint8))

        self.assertEqual(calls, [((120, 200), 192, 0.2), ((120, 200), 192, 0.08)])
        self.assertEqual(rows, [(30, 50, 0.09000000357627869, 40, 60)])
        self.assertEqual(detector.m1_score_used, 0.08)
        self.assertEqual(detector.m1_attempts, [0.2, 0.08])

    def test_detect_all_falls_back_to_yolo_verify_when_live_solver_import_fails(self) -> None:
        calls = []

        class _FakeM1:
            def detect(self, board, imgsz, score):
                calls.append((board.shape[:2], imgsz, score))
                return np.array([[11, 21, 51, 81, 0.75, 0]], dtype=np.float32)

        live_solver = types.ModuleType("planet_live_solver")

        def fail_load_models(use_gpu=False):
            raise ModuleNotFoundError("No module named 'mss'")

        live_solver.load_models = fail_load_models
        yolo_verify = types.ModuleType("planet_yolo_verify")
        yolo_verify.load_models = lambda use_gpu=False: (_FakeM1(), object())

        with patch.dict(sys.modules, {"planet_live_solver": live_solver, "planet_yolo_verify": yolo_verify}):
            detector = PlanetNoAuthDetector()
            rows = detector.detect_all(np.zeros((120, 200, 3), dtype=np.uint8))

        self.assertEqual(calls, [((120, 200), 192, 0.2)])
        self.assertFalse(detector._load_failed)
        self.assertEqual(detector.load_source, "planet_yolo_verify")
        self.assertEqual(rows, [(31, 51, 0.75, 40, 60)])

    def test_detect_all_records_load_error_when_all_model_loaders_fail(self) -> None:
        live_solver = types.ModuleType("planet_live_solver")
        live_solver.load_models = lambda use_gpu=False: (_ for _ in ()).throw(RuntimeError("live failed"))
        yolo_verify = types.ModuleType("planet_yolo_verify")
        yolo_verify.load_models = lambda use_gpu=False: (_ for _ in ()).throw(RuntimeError("verify failed"))

        with patch.dict(sys.modules, {"planet_live_solver": live_solver, "planet_yolo_verify": yolo_verify}):
            detector = PlanetNoAuthDetector()
            rows = detector.detect_all(np.zeros((120, 200, 3), dtype=np.uint8))

        self.assertEqual(rows, [])
        self.assertTrue(detector._load_failed)
        self.assertIn("live failed", detector.last_error)
        self.assertIn("verify failed", detector.last_error)


class PlanetLiveSolverTemporalSelectorTest(unittest.TestCase):
    def test_planet_live_solver_default_path_uses_scoreboard_backed_selector(self) -> None:
        solver = PlanetLiveSolver()

        selector = solver.temporal_selector
        self.assertIsInstance(selector, LiveTemporalSelector)
        self.assertTrue(selector.runtime.use_judge_scoreboard)
        self.assertIs(selector.selector_shadow.runtime, selector.runtime)
        self.assertEqual(selector.selector_shadow.emit_every, 1)

    def test_planet_live_solver_uses_live_evidence_judges_by_default(self) -> None:
        solver = PlanetLiveSolver()

        self.assertIsInstance(solver.evidence_judges, LiveEvidenceJudges)

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

    def test_analyze_prefers_confident_identity_when_selector_jumps_far(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [(100.0, 100.0, 0.8, 20.0, 20.0)]

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "TRACK_CONFIDENT",
                    (100.0, 100.0),
                    "identity",
                    0.8,
                    "candidate_continuity",
                    0,
                    {},
                )

        class _FakeTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(180.0, 100.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="jump_family",
                )

        solver = PlanetLiveSolver(
            detector=_FakeDetector(),
            identity_tracker=_FakeIdentityTracker(),
            temporal_selector=_FakeTemporalSelector(),
            mouse=PlanetMouseController(
                background_clicker=lambda x, y: clicked.append((x, y)),
                client_origin_getter=lambda: (0, 0),
            ),
        )
        roi = {
            "name": "detect",
            "x": 10,
            "y": 20,
            "w": 240,
            "h": 200,
        }
        frame = np.zeros((260, 260, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=56,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:220, 10:250],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)

        self.assertEqual(clicked, [(110, 120)])
        self.assertEqual(result.mouse_move.det_point, (100.0, 100.0))
        self.assertEqual(result.temporal_decision.family, "jump_family")

    def test_analyze_rejects_far_selector_even_when_identity_confidence_is_low(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [(100.0, 100.0, 0.2, 20.0, 20.0)]

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "TRACK_CONFIDENT",
                    (100.0, 100.0),
                    "identity",
                    0.45,
                    "candidate_continuity",
                    0,
                    {},
                )

        class _FakeTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(520.0, 180.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="far_jump_family",
                )

        solver = PlanetLiveSolver(
            detector=_FakeDetector(),
            identity_tracker=_FakeIdentityTracker(),
            temporal_selector=_FakeTemporalSelector(),
            mouse=PlanetMouseController(
                background_clicker=lambda x, y: clicked.append((x, y)),
                client_origin_getter=lambda: (0, 0),
            ),
        )
        roi = {
            "name": "detect",
            "x": 10,
            "y": 20,
            "w": 620,
            "h": 260,
        }
        frame = np.zeros((320, 700, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=55,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:280, 10:630],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)

        self.assertEqual(clicked, [(110, 120)])
        self.assertEqual(result.mouse_move.det_point, (100.0, 100.0))

    def test_analyze_keeps_hold_identity_when_selector_jumps_far(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [(100.0, 100.0, 0.2, 20.0, 20.0)]

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "IDENTITY_HOLD",
                    (100.0, 100.0),
                    "identity",
                    0.25,
                    "hold_ambiguous_candidate",
                    3,
                    {},
                )

        class _FakeTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(520.0, 180.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="far_jump_family",
                )

        solver = PlanetLiveSolver(
            detector=_FakeDetector(),
            identity_tracker=_FakeIdentityTracker(),
            temporal_selector=_FakeTemporalSelector(),
            mouse=PlanetMouseController(
                background_clicker=lambda x, y: clicked.append((x, y)),
                client_origin_getter=lambda: (0, 0),
            ),
        )
        roi = {
            "name": "detect",
            "x": 10,
            "y": 20,
            "w": 620,
            "h": 260,
        }
        frame = np.zeros((320, 700, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=56,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:280, 10:630],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)

        self.assertEqual(clicked, [(110, 120)])
        self.assertEqual(result.mouse_move.det_point, (100.0, 100.0))

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

    def test_analyze_records_detector_debug_when_detector_disabled(self) -> None:
        class _DisabledDetector:
            enabled = False
            load_source = ""
            last_error = "planet_live_solver: ModuleNotFoundError: No module named 'mss'"

        solver = PlanetLiveSolver(
            detector=_DisabledDetector(),
            mouse=PlanetMouseController(
                background_clicker=lambda _x, _y: None,
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
        candidate_event = next(event for event in result.trace_events if event[0] == "CANDIDATES")

        self.assertEqual(candidate_event[1]["count"], 0)
        self.assertEqual(candidate_event[1]["debug"]["detector_enabled"], False)
        self.assertIn("No module named 'mss'", candidate_event[1]["debug"]["detector_error"])

    def test_analyze_records_m1_retry_debug(self) -> None:
        class _RetryDetector:
            enabled = True
            load_source = "planet_live_solver"
            last_error = ""
            m1_score_used = 0.08
            m1_attempts = [0.2, 0.08]
            max_rows = 24

            def detect_all(self, _frame):
                return [(10.0, 20.0, 0.09, 12.0, 14.0)]

        solver = PlanetLiveSolver(
            detector=_RetryDetector(),
            mouse=PlanetMouseController(
                background_clicker=lambda _x, _y: None,
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
        candidate_event = next(event for event in result.trace_events if event[0] == "CANDIDATES")

        self.assertEqual(candidate_event[1]["debug"]["m1_score_used"], 0.08)
        self.assertEqual(candidate_event[1]["debug"]["m1_attempts"], [0.2, 0.08])
        self.assertEqual(candidate_event[1]["debug"]["detector_max_rows"], 24)

    def test_analyze_adds_white_anchor_candidate_when_detector_returns_zero(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _EmptyDetector:
            enabled = True

            def detect_all(self, _frame):
                return []

        class _FakeTemporalSelector:
            def __init__(self) -> None:
                self.calls = []

            def update(self, **kwargs):
                self.calls.append(kwargs)
                first = kwargs["candidates"][0]
                return LiveTemporalDecision(
                    point=(first[0], first[1]),
                    source="white_anchor",
                    reason="visible_start",
                    family="white_anchor",
                )

        temporal_selector = _FakeTemporalSelector()
        solver = PlanetLiveSolver(
            detector=_EmptyDetector(),
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
        frame[60:91, 50:86] = 255
        packet = FramePacket(
            session_id="s",
            frame_index=0,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:140, 10:130],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)
        candidate_event = next(event for event in result.trace_events if event[0] == "CANDIDATES")

        self.assertEqual(candidate_event[1]["count"], 1)
        self.assertEqual(candidate_event[1]["candidates"][0]["source"], "white_anchor")
        self.assertEqual(candidate_event[1]["debug"]["raw_count"], 0)
        self.assertEqual(candidate_event[1]["debug"]["white_anchor_count"], 1)
        self.assertAlmostEqual(temporal_selector.calls[0]["candidates"][0][0], 57.5)
        self.assertAlmostEqual(temporal_selector.calls[0]["candidates"][0][1], 55.0)
        self.assertEqual(clicked, [(67, 75)])

    def test_visible_lock_overrides_selector_after_stable_white_anchor(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _EmptyDetector:
            enabled = True

            def detect_all(self, _frame):
                return []

        class _WrongTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(100.0, 100.0),
                    source="selector_shadow",
                    reason="wrong_selector_point",
                    family="wrong_family",
                )

        solver = PlanetLiveSolver(
            detector=_EmptyDetector(),
            temporal_selector=_WrongTemporalSelector(),
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

        def _packet(frame_index: int) -> FramePacket:
            frame = np.zeros((180, 180, 3), dtype=np.uint8)
            frame[60:91, 50:86] = 255
            return FramePacket(
                session_id="s",
                frame_index=frame_index,
                timestamp_ms=0,
                source_frame=frame,
                board_frame=frame[20:140, 10:130],
                source_kind="test",
                roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
            )

        solver.analyze(_packet(0), solver_running=True)
        clicked.clear()
        result = solver.analyze(_packet(1), solver_running=True)
        candidate_event = next(event for event in result.trace_events if event[0] == "CANDIDATES")

        self.assertTrue(candidate_event[1]["debug"]["visible_lock"])
        self.assertEqual(candidate_event[1]["debug"]["visible_lock_stable"], 2)
        self.assertEqual(result.mouse_move.det_point, (57.5, 55.0))
        self.assertEqual(clicked, [(67, 75)])

    def test_analyze_learns_offset_only_after_visible_lock_is_stable(self) -> None:
        mouse_calls: list[dict[str, object]] = []

        class _EmptyDetector:
            enabled = True

            def detect_all(self, _frame):
                return []

        class _PrimaryTemporalSelector:
            def update(self, **kwargs):
                anchor = kwargs.get("white_anchor")
                return LiveTemporalDecision(
                    point=anchor,
                    source="primary",
                    reason="white_anchor",
                    family=None,
                )

        class _RecordingMouse:
            def move_to_det_point(self, **kwargs):
                mouse_calls.append(kwargs)
                return MouseMoveResult(
                    bool(kwargs.get("enabled")),
                    None,
                    None,
                    kwargs.get("point"),
                    (0.0, 0.0),
                    "recorded",
                )

        solver = PlanetLiveSolver(
            detector=_EmptyDetector(),
            temporal_selector=_PrimaryTemporalSelector(),
            mouse=_RecordingMouse(),
        )
        roi = {
            "name": "detect",
            "x": 10,
            "y": 20,
            "w": 120,
            "h": 120,
        }

        def _packet(frame_index: int) -> FramePacket:
            frame = np.zeros((180, 180, 3), dtype=np.uint8)
            frame[60:91, 50:86] = 255
            return FramePacket(
                session_id="s",
                frame_index=frame_index,
                timestamp_ms=0,
                source_frame=frame,
                board_frame=frame[20:140, 10:130],
                source_kind="test",
                roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
            )

        white_anchor_row = {
            "cx": 57.5,
            "cy": 55.0,
            "score": 0.99,
            "w": 36.0,
            "h": 31.0,
            "source": "white_anchor",
            "class_name": "white_anchor",
        }
        with patch("core.puzzle.planet_live._detect_white_anchor_rows", return_value=[white_anchor_row]):
            solver.analyze(_packet(0), solver_running=True)
            solver.analyze(_packet(1), solver_running=True)

        self.assertEqual(mouse_calls[0]["learn_offset"], False)
        self.assertEqual(mouse_calls[1]["learn_offset"], True)

    def test_motion_coast_candidate_keeps_selector_alive_after_white_fades(self) -> None:
        class _EmptyDetector:
            enabled = True

            def detect_all(self, _frame):
                return []

        class _FakeTemporalSelector:
            def __init__(self) -> None:
                self.calls = []

            def update(self, **kwargs):
                self.calls.append(kwargs)
                if not kwargs["candidates"]:
                    return LiveTemporalDecision(point=None, source="none", reason="no_points")
                first = kwargs["candidates"][0]
                return LiveTemporalDecision(
                    point=(first[0], first[1]),
                    source="selector_shadow",
                    reason="selected_family",
                    family="motion_test",
                )

        temporal_selector = _FakeTemporalSelector()
        solver = PlanetLiveSolver(
            detector=_EmptyDetector(),
            temporal_selector=temporal_selector,
            mouse=PlanetMouseController(client_origin_getter=lambda: (0, 0)),
            mouse_enabled=False,
        )
        roi = {
            "name": "detect",
            "x": 10,
            "y": 20,
            "w": 120,
            "h": 120,
        }

        def _packet(frame_index: int, shift_x: int | None) -> FramePacket:
            frame = np.zeros((180, 180, 3), dtype=np.uint8)
            if shift_x is not None:
                frame[60:91, 50 + shift_x : 86 + shift_x] = 255
            return FramePacket(
                session_id="s",
                frame_index=frame_index,
                timestamp_ms=0,
                source_frame=frame,
                board_frame=frame[20:140, 10:130],
                source_kind="test",
                roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
            )

        solver.analyze(_packet(0, 0), solver_running=True)
        solver.analyze(_packet(1, 4), solver_running=True)
        solver.analyze(_packet(2, 8), solver_running=True)
        result = solver.analyze(_packet(3, None), solver_running=True)
        candidate_event = next(event for event in result.trace_events if event[0] == "CANDIDATES")

        self.assertEqual(candidate_event[1]["count"], 1)
        self.assertEqual(candidate_event[1]["candidates"][0]["source"], "motion_coast")
        self.assertEqual(candidate_event[1]["debug"]["motion_coast_count"], 1)
        self.assertGreater(candidate_event[1]["debug"]["motion_coast_age"], 0)
        self.assertEqual(temporal_selector.calls[-1]["candidates"][0][2], 0.55)
        self.assertIsNotNone(result.temporal_decision.point)


if __name__ == "__main__":
    unittest.main()
