# planet_solver_noauth 방식의 live preview와 마우스 이동 어댑터를 검증한다.
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

import core.puzzle.planet_live as planet_live
from core.puzzle.live_temporal_selector import LiveTemporalDecision, LiveTemporalSelector
from core.puzzle.evidence import LiveEvidenceJudges
from core.puzzle.models import Candidate, CandidateEvidence, FramePacket, IdentityDecision, RoiSpec
from core.puzzle.defaults import fixed_detect_roi, fixed_popup_header_roi, fixed_popup_preview_roi
from core.puzzle.planet_live import (
    CCTV_OBSERVATION_BOTTOM_RIGHT,
    CCTV_OBSERVATION_BOTTOM_LEFT,
    CCTV_OBSERVATION_CONTRAST_CLIP_LIMIT,
    CCTV_OBSERVATION_LEFT_SIDE_TOP,
    CCTV_OBSERVATION_LEFT_SIDE_BOTTOM,
    CCTV_OBSERVATION_RIGHT_SIDE_SHADE,
    CCTV_OBSERVATION_RIGHT_SIDE_BOTTOM,
    CCTV_OBSERVATION_RIGHT_SIDE_TOP,
    CCTV_OBSERVATION_SCANLINE_ALPHA,
    CCTV_OBSERVATION_SIDE_STRIP_RATIO,
    CCTV_OBSERVATION_TOP_LEFT,
    CCTV_OBSERVATION_TOP_RIGHT,
    MouseMoveResult,
    PlanetLiveSolver,
    PlanetMouseController,
    _cctv_observation_transform_point,
    _refine_white_anchor_rows,
    render_planet_cctv_preview,
)
from core.puzzle.planet_noauth import PlanetNoAuthDetector


def _near_pixel(frame: np.ndarray, point: tuple[int, int], color: np.ndarray, radius: int = 3) -> bool:
    x, y = point
    patch = frame[max(0, y - radius):y + radius + 1, max(0, x - radius):x + radius + 1]
    return bool(np.any(np.all(patch == color, axis=2)))


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
    def test_cctv_observation_uses_thin_reference_like_3d_plate_geometry(self) -> None:
        front_top_width = CCTV_OBSERVATION_TOP_RIGHT[0] - CCTV_OBSERVATION_TOP_LEFT[0]
        front_bottom_width = CCTV_OBSERVATION_BOTTOM_RIGHT[0] - CCTV_OBSERVATION_BOTTOM_LEFT[0]
        front_left_height = CCTV_OBSERVATION_BOTTOM_LEFT[1] - CCTV_OBSERVATION_TOP_LEFT[1]
        front_right_height = CCTV_OBSERVATION_BOTTOM_RIGHT[1] - CCTV_OBSERVATION_TOP_RIGHT[1]
        right_top_depth = CCTV_OBSERVATION_RIGHT_SIDE_TOP[0] - CCTV_OBSERVATION_TOP_RIGHT[0]
        right_bottom_depth = CCTV_OBSERVATION_RIGHT_SIDE_BOTTOM[0] - CCTV_OBSERVATION_BOTTOM_RIGHT[0]
        left_top_depth = CCTV_OBSERVATION_TOP_LEFT[0] - CCTV_OBSERVATION_LEFT_SIDE_TOP[0]
        left_bottom_drop = CCTV_OBSERVATION_BOTTOM_LEFT[1] - CCTV_OBSERVATION_LEFT_SIDE_BOTTOM[1]
        right_bottom_drop = CCTV_OBSERVATION_RIGHT_SIDE_BOTTOM[1] - CCTV_OBSERVATION_BOTTOM_RIGHT[1]

        self.assertLess(CCTV_OBSERVATION_BOTTOM_RIGHT[0], CCTV_OBSERVATION_TOP_RIGHT[0])
        self.assertGreater(front_top_width, 0.72)
        self.assertGreater(front_bottom_width, 0.66)
        self.assertLessEqual(front_left_height, 0.54)
        self.assertLessEqual(front_right_height, 0.56)
        self.assertGreaterEqual(right_top_depth, 0.06)
        self.assertLessEqual(right_top_depth, 0.08)
        self.assertGreaterEqual(right_bottom_depth, 0.07)
        self.assertLessEqual(right_bottom_depth, 0.09)
        self.assertLessEqual(left_top_depth, 0.035)
        self.assertLessEqual(left_bottom_drop, 0.035)
        self.assertLessEqual(right_bottom_drop, 0.065)
        self.assertLessEqual(CCTV_OBSERVATION_SIDE_STRIP_RATIO, 0.09)
        self.assertGreaterEqual(CCTV_OBSERVATION_SCANLINE_ALPHA, 0.82)
        self.assertLessEqual(CCTV_OBSERVATION_RIGHT_SIDE_SHADE, 0.52)
        self.assertGreaterEqual(CCTV_OBSERVATION_CONTRAST_CLIP_LIMIT, 1.12)
        self.assertLessEqual(CCTV_OBSERVATION_CONTRAST_CLIP_LIMIT, 1.22)

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

    def test_render_preview_draws_large_target_marker(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        preview_roi = fixed_popup_preview_roi(frame_w=1920, frame_h=1080)
        detect_roi = fixed_detect_roi(frame_w=1920, frame_h=1080)
        marker_x = detect_roi.x - preview_roi.x + 120
        marker_y = detect_roi.y - preview_roi.y + 140

        preview = render_planet_cctv_preview(frame, track_pos=(120.0, 140.0))
        marker_x, marker_y = _cctv_observation_transform_point(
            preview.shape[1],
            preview.shape[0],
            marker_x,
            marker_y,
        )

        self.assertTrue(np.array_equal(preview[marker_y, marker_x], np.array([0, 255, 80], dtype=np.uint8)))
        self.assertTrue(np.array_equal(preview[marker_y, marker_x + 24], np.array([0, 255, 80], dtype=np.uint8)))

    def test_render_preview_draws_header_at_actual_hdr_roi_offset(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        header_roi = fixed_popup_header_roi(frame_w=1920, frame_h=1080)
        preview_roi = fixed_popup_preview_roi(frame_w=1920, frame_h=1080)
        detect_roi = fixed_detect_roi(frame_w=1920, frame_h=1080)

        preview = render_planet_cctv_preview(frame, popup_score=0.72)

        hdr_top = header_roi.y - preview_roi.y
        hdr_bottom = hdr_top + header_roi.h - 1
        det_top = detect_roi.y - preview_roi.y
        hdr_top_point = _cctv_observation_transform_point(preview.shape[1], preview.shape[0], 3, hdr_top)
        hdr_bottom_point = _cctv_observation_transform_point(preview.shape[1], preview.shape[0], 3, hdr_bottom)
        det_top_point = _cctv_observation_transform_point(preview.shape[1], preview.shape[0], 3, det_top)
        self.assertGreater(hdr_top, 0)
        self.assertLessEqual(det_top - hdr_bottom, 4)
        self.assertTrue(np.array_equal(preview[hdr_top_point[1], hdr_top_point[0]], np.array([0, 230, 255], dtype=np.uint8)))
        self.assertTrue(_near_pixel(preview, hdr_bottom_point, np.array([0, 140, 255], dtype=np.uint8)))
        self.assertTrue(_near_pixel(preview, det_top_point, np.array([0, 140, 255], dtype=np.uint8)))

    def test_render_preview_labels_candidates_with_stable_numbers(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        real_cv2 = planet_live._cv2()
        texts: list[str] = []

        class _SpyCv2:
            def __getattr__(self, name):
                return getattr(real_cv2, name)

            def putText(self, image, text, org, font_face, font_scale, color, thickness, line_type):
                texts.append(str(text))
                return real_cv2.putText(image, text, org, font_face, font_scale, color, thickness, line_type)

        with patch("core.puzzle.planet_live._cv2", return_value=_SpyCv2()):
            render_planet_cctv_preview(
                frame,
                candidates=[
                    (30.0, 40.0, 0.9, 10.0, 12.0),
                    (70.0, 80.0, 0.7, 14.0, 16.0),
                ],
            )

        self.assertTrue(any(text.startswith("#1") for text in texts))
        self.assertTrue(any(text.startswith("#2") for text in texts))

    def test_render_preview_marks_picked_and_dropped_candidates(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        real_cv2 = planet_live._cv2()
        texts: list[str] = []

        class _SpyCv2:
            def __getattr__(self, name):
                return getattr(real_cv2, name)

            def putText(self, image, text, org, font_face, font_scale, color, thickness, line_type):
                texts.append(str(text))
                return real_cv2.putText(image, text, org, font_face, font_scale, color, thickness, line_type)

        with patch("core.puzzle.planet_live._cv2", return_value=_SpyCv2()):
            render_planet_cctv_preview(
                frame,
                candidates=[
                    (30.0, 40.0, 0.9, 10.0, 12.0),
                    (170.0, 180.0, 0.7, 14.0, 16.0),
                ],
                track_pos=(30.0, 40.0),
            )

        self.assertIn("#1 PICK", texts)
        self.assertIn("#2 DROP", texts)

    def test_render_preview_draws_selected_target_history_polyline(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        real_cv2 = planet_live._cv2()
        polylines: list[tuple[bool, tuple[int, int, int], int]] = []

        class _SpyCv2:
            def __getattr__(self, name):
                return getattr(real_cv2, name)

            def polylines(self, image, pts, is_closed, color, thickness):
                polylines.append((bool(is_closed), tuple(color), int(thickness)))
                return real_cv2.polylines(image, pts, is_closed, color, thickness)

        with patch("core.puzzle.planet_live._cv2", return_value=_SpyCv2()):
            render_planet_cctv_preview(
                frame,
                track_pos=(80.0, 90.0),
                target_history=[(30.0, 40.0), (55.0, 65.0), (80.0, 90.0)],
            )

        self.assertIn((False, (0, 255, 80), 2), polylines)


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
    def test_white_anchor_fragment_uses_containing_yolo_box_center(self) -> None:
        white_rows = [
            {
                "cx": 295.0,
                "cy": 420.0,
                "score": 0.86,
                "w": 35.0,
                "h": 26.0,
                "source": "white_anchor",
                "class_name": "white_anchor",
            }
        ]
        raw_rows = [
            (335.0, 411.0, 0.52, 92.0, 94.0),
            (352.0, 434.0, 0.13, 73.0, 63.0),
        ]

        refined = _refine_white_anchor_rows(white_rows, raw_rows)

        self.assertEqual(len(refined), 1)
        self.assertEqual(refined[0]["cx"], 335.0)
        self.assertEqual(refined[0]["cy"], 411.0)
        self.assertEqual(refined[0]["w"], 92.0)
        self.assertEqual(refined[0]["h"], 94.0)
        self.assertEqual(refined[0]["source"], "white_anchor")

    def test_white_anchor_fragment_keeps_original_when_no_yolo_box_contains_it(self) -> None:
        white_rows = [
            {
                "cx": 295.0,
                "cy": 420.0,
                "score": 0.86,
                "w": 35.0,
                "h": 26.0,
                "source": "white_anchor",
                "class_name": "white_anchor",
            }
        ]

        refined = _refine_white_anchor_rows(white_rows, [(100.0, 100.0, 0.9, 40.0, 40.0)])

        self.assertEqual(refined, white_rows)

    def test_full_white_anchor_does_not_use_similar_sized_yolo_box(self) -> None:
        white_rows = [
            {
                "cx": 228.05,
                "cy": 293.56,
                "score": 0.99,
                "w": 104.0,
                "h": 105.0,
                "source": "white_anchor",
                "class_name": "white_anchor",
            }
        ]
        raw_rows = [(243.0, 255.0, 0.60, 104.0, 90.0)]

        refined = _refine_white_anchor_rows(white_rows, raw_rows)

        self.assertEqual(refined, white_rows)

    def test_reset_cascades_to_stateful_solver_components(self) -> None:
        class _ResetSpy:
            def __init__(self) -> None:
                self.reset_calls = 0

            def reset(self) -> None:
                self.reset_calls += 1

        detector = object()
        evidence = _ResetSpy()
        identity = _ResetSpy()
        temporal = _ResetSpy()
        solver = PlanetLiveSolver(
            detector=detector,
            evidence_judges=evidence,
            identity_tracker=identity,
            temporal_selector=temporal,
            mouse_enabled=False,
        )
        solver._last_detect_debug = {"candidate_count": 4}
        solver._target_history = [(10.0, 20.0)]
        solver._visible_white_lock._last_point = (10.0, 20.0)
        solver._motion_coast._history = [(1, (10.0, 20.0), (12.0, 12.0))]

        solver.reset()

        self.assertIs(solver.detector, detector)
        self.assertEqual(evidence.reset_calls, 1)
        self.assertEqual(identity.reset_calls, 1)
        self.assertEqual(temporal.reset_calls, 1)
        self.assertEqual(solver._last_detect_debug, {})
        self.assertEqual(solver._target_history, [])
        self.assertIsNone(solver._visible_white_lock._last_point)
        self.assertEqual(solver._motion_coast._history, [])

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

    def test_live_temporal_selector_disables_legacy_rescues_for_small_board(self) -> None:
        class _FakeFamilyPool:
            def update(self, _frame_index, **_kwargs):
                return types.SimpleNamespace(
                    points={"panel_default_center_mild_state_mild": (10.0, 20.0)},
                    debug={},
                )

        class _FakeShadow:
            def __init__(self) -> None:
                self.calls = []

            def reset(self, **_kwargs):
                pass

            def update(self, _frame_index, **kwargs):
                self.calls.append(kwargs)
                return None

        shadow = _FakeShadow()
        selector = LiveTemporalSelector(
            family_pool=_FakeFamilyPool(),
            selector_shadow=shadow,
        )

        selector.update(
            frame_index=1,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
            frame_shape=(538, 460),
        )
        selector.update(
            frame_index=2,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
            frame_shape=(618, 695),
        )

        self.assertFalse(shadow.calls[0]["allow_legacy_rescues"])
        self.assertTrue(shadow.calls[1]["allow_legacy_rescues"])

    def test_live_temporal_selector_adds_kinematic_shape_family_to_shadow(self) -> None:
        class _FakeFamilyPool:
            def update(self, _frame_index, **_kwargs):
                return types.SimpleNamespace(points={}, debug={})

        class _FakeShapeTracker:
            def __init__(self) -> None:
                self.calls = []
                self.reset_calls = 0

            def reset(self) -> None:
                self.reset_calls += 1

            def update(self, candidates, *, white_anchor=None):
                self.calls.append((candidates, white_anchor))
                return (30.0, 40.0)

        class _FakeShadow:
            def __init__(self) -> None:
                self.calls = []

            def reset(self, **_kwargs):
                pass

            def update(self, _frame_index, **kwargs):
                self.calls.append(kwargs)
                return None

        shape_tracker = _FakeShapeTracker()
        shadow = _FakeShadow()
        selector = LiveTemporalSelector(
            family_pool=_FakeFamilyPool(),
            selector_shadow=shadow,
            kinematic_shape_tracker=shape_tracker,
            enable_kinematic_shape=True,
        )

        selector.update(
            frame_index=1,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
            white_anchor=(10.0, 20.0),
        )
        selector.reset()

        self.assertEqual(
            shadow.calls[0]["anchors"]["kinematic_shape_center_mild_state_mild"],
            (30.0, 40.0),
        )
        self.assertEqual(shape_tracker.calls[0][1], (10.0, 20.0))
        self.assertEqual(shape_tracker.reset_calls, 1)

    def test_live_temporal_selector_keeps_kinematic_shape_out_of_default_shadow(self) -> None:
        class _FakeFamilyPool:
            def update(self, _frame_index, **_kwargs):
                return types.SimpleNamespace(points={}, debug={})

        class _FakeShapeTracker:
            def reset(self) -> None:
                pass

            def update(self, _candidates, *, white_anchor=None):
                return (30.0, 40.0)

        class _FakeShadow:
            def __init__(self) -> None:
                self.calls = []

            def reset(self, **_kwargs):
                pass

            def update(self, _frame_index, **kwargs):
                self.calls.append(kwargs)
                return None

        shadow = _FakeShadow()
        selector = LiveTemporalSelector(
            family_pool=_FakeFamilyPool(),
            selector_shadow=shadow,
            kinematic_shape_tracker=_FakeShapeTracker(),
        )

        decision = selector.update(
            frame_index=1,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
        )

        self.assertNotIn(
            "kinematic_shape_center_mild_state_mild",
            shadow.calls[0]["anchors"],
        )
        self.assertEqual(decision.debug["kinematic_shape_point"], (30.0, 40.0))

    def test_live_temporal_selector_exposes_and_resets_wide_beam_hypotheses(self) -> None:
        class _FakeFamilyPool:
            def update(self, _frame_index, **_kwargs):
                return types.SimpleNamespace(points={}, debug={})

        class _FakeTracker:
            def __init__(self, point, hypotheses=()) -> None:
                self.point = point
                self.hypothesis_points = hypotheses
                self.last_debug = {"state_count": len(hypotheses)}
                self.reset_calls = 0

            def reset(self) -> None:
                self.reset_calls += 1

            def update(self, _candidates, *, white_anchor=None):
                return self.point

        class _FakeShadow:
            def reset(self, **_kwargs):
                pass

            def update(self, _frame_index, **_kwargs):
                return None

        narrow = _FakeTracker((20.0, 30.0))
        wide = _FakeTracker((40.0, 50.0), ((40.0, 50.0), (80.0, 90.0)))
        selector = LiveTemporalSelector(
            family_pool=_FakeFamilyPool(),
            selector_shadow=_FakeShadow(),
            kinematic_beam_tracker=narrow,
            kinematic_wide_beam_tracker=wide,
        )

        decision = selector.update(
            frame_index=1,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
        )
        selector.reset()

        self.assertEqual(
            decision.debug["kinematic_wide_beam_points"],
            ((40.0, 50.0), (80.0, 90.0)),
        )
        self.assertEqual(decision.debug["kinematic_wide_beam_debug"]["state_count"], 2)
        self.assertEqual(wide.reset_calls, 1)

    def test_live_temporal_selector_seeds_only_wide_beam_from_immediate_white_anchor(self) -> None:
        class _FakeFamilyPool:
            def update(self, _frame_index, **_kwargs):
                return types.SimpleNamespace(points={}, debug={})

        class _FakeTracker:
            hypothesis_points = ()
            last_debug = {}

            def __init__(self) -> None:
                self.anchors = []

            def reset(self) -> None:
                pass

            def update(self, _candidates, *, white_anchor=None):
                self.anchors.append(white_anchor)
                return white_anchor

        class _FakeShadow:
            def reset(self, **_kwargs):
                pass

            def update(self, _frame_index, **_kwargs):
                return None

        narrow = _FakeTracker()
        wide = _FakeTracker()
        selector = LiveTemporalSelector(
            family_pool=_FakeFamilyPool(),
            selector_shadow=_FakeShadow(),
            kinematic_beam_tracker=narrow,
            kinematic_wide_beam_tracker=wide,
        )

        selector.update(
            frame_index=1,
            candidates=[(10.0, 20.0, 0.9, 20.0, 20.0)],
            primary_point=(10.0, 20.0),
            white_anchor=(10.0, 20.0),
            wide_white_anchor=(12.0, 22.0),
        )

        self.assertEqual(narrow.anchors, [(10.0, 20.0)])
        self.assertEqual(wide.anchors, [(12.0, 22.0)])

    def test_kinematic_texture_gate_accepts_shape_only_when_it_is_not_more_background_like(self) -> None:
        base = Candidate("base", 1, (5.0, 5.0, 15.0, 15.0), (10.0, 10.0), 0.8, "raw")
        shape = Candidate("shape", 1, (95.0, 95.0, 105.0, 105.0), (100.0, 100.0), 0.8, "raw")
        evidence = {
            "base": CandidateEvidence("base", texture_bg_score=0.70),
            "shape": CandidateEvidence("shape", texture_bg_score=0.60),
        }

        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=base.center,
            shape_point=shape.center,
            candidates=[base, shape],
            evidence=evidence,
        )

        self.assertEqual(point, shape.center)
        self.assertTrue(debug["selected"])
        self.assertEqual(debug["base_point"], base.center)
        self.assertEqual(debug["shape_point"], shape.center)
        self.assertEqual(debug["selected_point"], shape.center)

        evidence["shape"] = CandidateEvidence("shape", texture_bg_score=0.80)
        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=base.center,
            shape_point=shape.center,
            candidates=[base, shape],
            evidence=evidence,
        )

        self.assertEqual(point, base.center)
        self.assertFalse(debug["selected"])

        evidence["base"] = CandidateEvidence("base", texture_bg_score=0.99)
        evidence["shape"] = CandidateEvidence("shape", texture_bg_score=0.95)
        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=base.center,
            shape_point=shape.center,
            candidates=[base, shape],
            evidence=evidence,
        )

        self.assertEqual(point, base.center)
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "shape_too_background_like")

    def test_kinematic_texture_gate_preserves_confident_identity_without_clear_texture_gain(self) -> None:
        base = Candidate("base", 1, (5.0, 5.0, 15.0, 15.0), (10.0, 10.0), 0.8, "raw")
        shape = Candidate("shape", 1, (32.0, 5.0, 42.0, 15.0), (37.0, 10.0), 0.8, "raw")
        evidence = {
            "base": CandidateEvidence("base", texture_bg_score=0.959),
            "shape": CandidateEvidence("shape", texture_bg_score=0.937),
        }

        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=base.center,
            shape_point=shape.center,
            candidates=[base, shape],
            evidence=evidence,
            identity_state="TRACK_CONFIDENT",
        )

        self.assertEqual(point, base.center)
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "confident_texture_gain_too_weak")

        evidence["shape"] = CandidateEvidence("shape", texture_bg_score=0.899)
        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=base.center,
            shape_point=shape.center,
            candidates=[base, shape],
            evidence=evidence,
            identity_state="TRACK_CONFIDENT",
        )

        self.assertEqual(point, shape.center)
        self.assertTrue(debug["selected"])

    def test_kinematic_texture_gate_preserves_short_hold_shift_inside_same_candidate(self) -> None:
        candidate = Candidate("same", 1, (0.0, 0.0, 30.0, 20.0), (15.0, 10.0), 0.8, "raw")
        evidence = {"same": CandidateEvidence("same", texture_bg_score=0.90)}

        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=(3.0, 10.0),
            shape_point=candidate.center,
            candidates=[candidate],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, (3.0, 10.0))
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "hold_same_candidate_shift_too_small")

        point, debug = planet_live._choose_kinematic_texture_target(
            base_point=(-10.0, 10.0),
            shape_point=candidate.center,
            candidates=[candidate],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, candidate.center)
        self.assertTrue(debug["selected"])

    def test_kinematic_beam_gate_accepts_beam_when_appearance_is_not_worse(self) -> None:
        active = Candidate("active", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.8, "raw")
        beam = Candidate("beam", 1, (120.0, 90.0, 140.0, 110.0), (130.0, 100.0), 0.3, "raw")
        evidence = {
            "active": CandidateEvidence("active", color_residual=0.34),
            "beam": CandidateEvidence("beam", color_residual=0.345),
        }

        point, debug = planet_live._choose_kinematic_beam_target(
            base_point=active.center,
            beam_point=beam.center,
            candidates=[active, beam],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, beam.center)
        self.assertEqual(debug["reason"], "appearance_parity")

    def test_kinematic_beam_gate_preserves_base_when_beam_appearance_is_worse(self) -> None:
        active = Candidate("active", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.8, "raw")
        beam = Candidate("beam", 1, (120.0, 90.0, 140.0, 110.0), (130.0, 100.0), 0.3, "raw")
        evidence = {
            "active": CandidateEvidence("active", color_residual=0.34),
            "beam": CandidateEvidence("beam", color_residual=0.36),
        }

        point, debug = planet_live._choose_kinematic_beam_target(
            base_point=active.center,
            beam_point=beam.center,
            candidates=[active, beam],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, active.center)
        self.assertEqual(debug["reason"], "beam_appearance_worse")

    def test_kinematic_beam_gate_never_overrides_visible_anchor(self) -> None:
        active = Candidate("active", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.99, "raw")
        beam = Candidate("beam", 1, (120.0, 90.0, 140.0, 110.0), (130.0, 100.0), 0.3, "raw")
        evidence = {
            "active": CandidateEvidence("active", color_residual=0.34),
            "beam": CandidateEvidence("beam", color_residual=0.34),
        }

        point, debug = planet_live._choose_kinematic_beam_target(
            base_point=active.center,
            beam_point=beam.center,
            candidates=[active, beam],
            evidence=evidence,
            identity_state="INIT_VISIBLE",
        )

        self.assertEqual(point, active.center)
        self.assertEqual(debug["reason"], "visible_identity_locked")

    def test_kinematic_beam_gate_preserves_short_shift_inside_same_candidate(self) -> None:
        candidate = Candidate("same", 1, (0.0, 0.0, 120.0, 80.0), (60.0, 40.0), 0.3, "raw")
        evidence = {"same": CandidateEvidence("same", color_residual=0.34)}

        point, debug = planet_live._choose_kinematic_beam_target(
            base_point=(20.0, 40.0),
            beam_point=(80.0, 40.0),
            candidates=[candidate],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, (20.0, 40.0))
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "same_candidate_shift_too_small")

    def test_kinematic_beam_gate_allows_large_shift_inside_same_candidate(self) -> None:
        candidate = Candidate("same", 1, (0.0, 0.0, 180.0, 100.0), (90.0, 50.0), 0.3, "raw")
        evidence = {"same": CandidateEvidence("same", color_residual=0.34)}

        point, debug = planet_live._choose_kinematic_beam_target(
            base_point=(20.0, 50.0),
            beam_point=(130.0, 50.0),
            candidates=[candidate],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, (130.0, 50.0))
        self.assertTrue(debug["selected"])

    def test_kinematic_beam_gate_preserves_base_for_bottom_clipped_candidate(self) -> None:
        active = Candidate("active", 1, (80.0, 80.0, 120.0, 120.0), (100.0, 100.0), 0.3, "raw")
        beam = Candidate("beam", 1, (100.0, 160.0, 140.0, 199.0), (120.0, 179.5), 0.3, "raw")
        evidence = {
            "active": CandidateEvidence("active", color_residual=0.34),
            "beam": CandidateEvidence("beam", color_residual=0.34),
        }

        point, debug = planet_live._choose_kinematic_beam_target(
            base_point=active.center,
            beam_point=beam.center,
            candidates=[active, beam],
            evidence=evidence,
            identity_state="TRACK_CONFIDENT",
            frame_shape=(200, 300),
        )

        self.assertEqual(point, active.center)
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "beam_candidate_bottom_clipped")

    def test_wide_beam_gate_selects_lowest_texture_hypothesis_after_safe_separation(self) -> None:
        base = Candidate("base", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.8, "raw")
        weak = Candidate("weak", 1, (145.0, 90.0, 165.0, 110.0), (155.0, 100.0), 0.3, "raw")
        strong = Candidate("strong", 1, (190.0, 90.0, 210.0, 110.0), (200.0, 100.0), 0.3, "raw")
        evidence = {
            "base": CandidateEvidence("base", texture_bg_score=0.92, color_residual=0.34),
            "weak": CandidateEvidence("weak", texture_bg_score=0.88, color_residual=0.34),
            "strong": CandidateEvidence("strong", texture_bg_score=0.84, color_residual=0.34),
        }

        point, debug = planet_live._choose_kinematic_wide_beam_target(
            base_point=base.center,
            hypothesis_points=(weak.center, strong.center),
            candidates=[base, weak, strong],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
            frame_shape=(300, 300),
        )

        self.assertEqual(point, strong.center)
        self.assertTrue(debug["selected"])
        self.assertEqual(debug["wide_candidate_id"], "strong")

    def test_wide_beam_gate_preserves_base_when_texture_gain_is_below_guard(self) -> None:
        base = Candidate("base", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.8, "raw")
        wide = Candidate("wide", 1, (190.0, 90.0, 210.0, 110.0), (200.0, 100.0), 0.3, "raw")
        evidence = {
            "base": CandidateEvidence("base", texture_bg_score=0.92, color_residual=0.34),
            "wide": CandidateEvidence("wide", texture_bg_score=0.87, color_residual=0.34),
        }

        point, debug = planet_live._choose_kinematic_wide_beam_target(
            base_point=base.center,
            hypothesis_points=(wide.center,),
            candidates=[base, wide],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, base.center)
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "texture_gain_too_weak")

    def test_wide_beam_gate_preserves_base_when_paths_are_not_separated(self) -> None:
        base = Candidate("base", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.8, "raw")
        wide = Candidate("wide", 1, (129.0, 90.0, 149.0, 110.0), (139.0, 100.0), 0.3, "raw")
        evidence = {
            "base": CandidateEvidence("base", texture_bg_score=0.92, color_residual=0.34),
            "wide": CandidateEvidence("wide", texture_bg_score=0.80, color_residual=0.34),
        }

        point, debug = planet_live._choose_kinematic_wide_beam_target(
            base_point=base.center,
            hypothesis_points=(wide.center,),
            candidates=[base, wide],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, base.center)
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "paths_not_separated")

    def test_wide_beam_gate_accepts_observation_consensus_when_texture_gain_is_moderate(self) -> None:
        base = Candidate("base", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.70, "raw")
        wide = Candidate("wide", 1, (190.0, 90.0, 210.0, 110.0), (200.0, 100.0), 0.65, "raw")
        evidence = {
            "base": CandidateEvidence(
                "base",
                texture_bg_score=0.92,
                motion_divergence=0.20,
                merge_likelihood=0.40,
                color_residual=0.34,
            ),
            "wide": CandidateEvidence(
                "wide",
                texture_bg_score=0.87,
                motion_divergence=0.30,
                merge_likelihood=0.35,
                color_residual=0.34,
            ),
        }

        point, debug = planet_live._choose_kinematic_wide_beam_target(
            base_point=base.center,
            hypothesis_points=(wide.center,),
            candidates=[base, wide],
            evidence=evidence,
            identity_state="IDENTITY_HOLD",
        )

        self.assertEqual(point, wide.center)
        self.assertTrue(debug["selected"])
        self.assertEqual(debug["reason"], "wide_observation_consensus")

    def test_wide_beam_observation_consensus_requires_motion_yolo_and_merge_support(self) -> None:
        base = Candidate("base", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.70, "raw")
        cases = (
            ("motion", 0.19, 0.65, 0.35),
            ("yolo", 0.30, 0.59, 0.35),
            ("merge", 0.30, 0.65, 0.29),
        )
        for label, motion, score, merge in cases:
            with self.subTest(label=label):
                wide = Candidate("wide", 1, (190.0, 90.0, 210.0, 110.0), (200.0, 100.0), score, "raw")
                evidence = {
                    "base": CandidateEvidence(
                        "base",
                        texture_bg_score=0.92,
                        motion_divergence=0.20,
                        merge_likelihood=0.40,
                        color_residual=0.34,
                    ),
                    "wide": CandidateEvidence(
                        "wide",
                        texture_bg_score=0.87,
                        motion_divergence=motion,
                        merge_likelihood=merge,
                        color_residual=0.34,
                    ),
                }

                point, debug = planet_live._choose_kinematic_wide_beam_target(
                    base_point=base.center,
                    hypothesis_points=(wide.center,),
                    candidates=[base, wide],
                    evidence=evidence,
                    identity_state="IDENTITY_HOLD",
                )

                self.assertEqual(point, base.center)
                self.assertFalse(debug["selected"])
                self.assertEqual(debug["reason"], "texture_gain_too_weak")

    def test_local_rigid_gate_selects_independently_moving_retained_hypothesis(self) -> None:
        base = Candidate("base", 1, (90.0, 90.0, 110.0, 110.0), (100.0, 100.0), 0.8, "raw")
        target = Candidate("target", 1, (180.0, 90.0, 200.0, 110.0), (190.0, 100.0), 0.5, "raw")
        evidence = {
            "base": CandidateEvidence("base", local_rigid_residual=0.10),
            "target": CandidateEvidence("target", local_rigid_residual=0.35),
        }

        point, debug = planet_live._choose_kinematic_local_rigid_target(
            base_point=base.center,
            hypothesis_points=(base.center, target.center),
            candidates=[base, target],
            evidence=evidence,
            identity_state="TRACK_CONFIDENT",
        )

        self.assertEqual(point, target.center)
        self.assertTrue(debug["selected"])
        self.assertEqual(debug["reason"], "local_rigid_advantage")
        self.assertEqual(debug["selected_candidate_id"], "target")

    def test_local_rigid_gate_rejects_barely_over_old_advantage_margin(self) -> None:
        base = Candidate("base", 1, (369.0, 340.0, 389.0, 360.0), (379.0, 350.0), 0.8, "raw")
        target = Candidate("target", 1, (302.0, 331.0, 322.0, 351.0), (312.0, 341.0), 0.5, "raw")
        evidence = {
            "base": CandidateEvidence("base", local_rigid_residual=0.215856),
            "target": CandidateEvidence("target", local_rigid_residual=0.336808),
        }

        point, debug = planet_live._choose_kinematic_local_rigid_target(
            base_point=base.center,
            hypothesis_points=(base.center, target.center),
            candidates=[base, target],
            evidence=evidence,
            identity_state="TRACK_CONFIDENT",
        )

        self.assertEqual(point, base.center)
        self.assertFalse(debug["selected"])
        self.assertEqual(debug["reason"], "advantage_too_weak")

    def test_analyze_applies_local_rigid_gate_after_existing_target_gates(self) -> None:
        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [
                    (50.0, 50.0, 0.8, 20.0, 20.0),
                    (150.0, 50.0, 0.5, 20.0, 20.0),
                ]

        class _FakeEvidenceJudges:
            def score(self, candidates, _packet):
                return {
                    candidate.candidate_id: CandidateEvidence(
                        candidate.candidate_id,
                        motion_divergence=0.5 if candidate.center[0] < 100.0 else 0.0,
                        local_rigid_residual=0.10 if candidate.center[0] < 100.0 else 0.35,
                        texture_bg_score=0.80 if candidate.center[0] < 100.0 else 0.90,
                        color_residual=0.34,
                        merge_likelihood=0.5 if candidate.center[0] < 100.0 else 0.2,
                    )
                    for candidate in candidates
                }

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "TRACK_CONFIDENT",
                    (50.0, 50.0),
                    "base",
                    0.8,
                    "candidate_continuity",
                    0,
                    {},
                )

        class _FakeTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(50.0, 50.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="base_family",
                    debug={"kinematic_wide_beam_points": [(50.0, 50.0), (150.0, 50.0)]},
                )

        solver = PlanetLiveSolver(
            detector=_FakeDetector(),
            evidence_judges=_FakeEvidenceJudges(),
            identity_tracker=_FakeIdentityTracker(),
            temporal_selector=_FakeTemporalSelector(),
            mouse_enabled=False,
        )
        roi = {"name": "detect", "x": 0, "y": 0, "w": 220, "h": 120}
        frame = np.zeros((120, 220, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=7,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame,
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)
        target_payload = dict(next(payload for event, payload in result.trace_events if event == "TARGET_SELECTION"))

        self.assertEqual(result.mouse_move.det_point, (150.0, 50.0))
        self.assertEqual(target_payload["source"], "kinematic_local_rigid")
        self.assertTrue(target_payload["kinematic_local_rigid_gate"]["selected"])

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

    def test_analyze_keeps_temporal_during_overlap_reacquire_divergence(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [(323.0, 116.0, 0.88, 115.0, 78.0), (196.0, 117.0, 0.76, 90.0, 70.0)]

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "REACQUIRE",
                    (323.0, 116.0),
                    "right_reacquire",
                    0.87,
                    "reacquired",
                    0,
                    {"distance": 13.9, "color_weight": 0.7},
                )

        class _FakeTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(196.0, 117.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="raw_candidate_cont0_center_mild_state_mild",
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
            "w": 700,
            "h": 500,
        }
        frame = np.zeros((620, 760, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=49,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:520, 10:710],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)

        self.assertEqual(clicked, [(206, 137)])
        self.assertEqual(result.mouse_move.det_point, (196.0, 117.0))

    def test_analyze_rejects_far_temporal_while_identity_holds_occlusion(self) -> None:
        decision = IdentityDecision(
            "OCCLUSION_SUSPECTED",
            (226.0, 70.0),
            "f81_planet_live_22",
            0.35,
            "occlusion_suspected",
            1,
            {"distance": 55.0},
        )
        temporal = LiveTemporalDecision(
            point=(402.0, 169.0),
            source="selector_shadow",
            reason="selected_family",
            family="raw_candidate_cont10_box_rel_p05_z0_state_mild",
        )

        self.assertTrue(planet_live._should_prefer_identity_target(decision, temporal))

    def test_analyze_prefers_identity_for_midrange_occlusion_divergence(self) -> None:
        decision = IdentityDecision(
            "OCCLUSION_SUSPECTED",
            (177.0, 77.0),
            "f88_planet_live_16",
            0.35,
            "occlusion_suspected",
            1,
            {"distance": 55.0},
        )
        temporal = LiveTemporalDecision(
            point=(226.0, 85.0),
            source="selector_shadow",
            reason="selected_family",
            family="raw_candidate_cont10_box_rel_p05_z0_state_mild",
        )

        self.assertTrue(planet_live._should_prefer_identity_target(decision, temporal))

    def test_analyze_rejects_far_temporal_after_local_identity_reacquire(self) -> None:
        decision = IdentityDecision(
            "REACQUIRE",
            (191.0, 70.0),
            "f83_planet_live_20",
            0.797,
            "reacquired",
            0,
            {"distance": 30.0, "distance_to_last": 35.0, "color_weight": 0.0},
        )
        temporal = LiveTemporalDecision(
            point=(444.0, 54.0),
            source="selector_shadow",
            reason="selected_family",
            family="raw_candidate_cont11_box_rel_p05_z0_state_mild",
        )

        self.assertTrue(planet_live._should_prefer_identity_target(decision, temporal))

    def test_analyze_rejects_far_temporal_after_faded_broad_reacquire(self) -> None:
        decision = IdentityDecision(
            "REACQUIRE",
            (227.0, 96.0),
            "f98_planet_live_29",
            0.633,
            "reacquired",
            0,
            {"distance": 84.3, "distance_to_last": 84.1, "color_weight": 0.0},
        )
        temporal = LiveTemporalDecision(
            point=(44.0, 511.0),
            source="selector_shadow",
            reason="selected_family",
            family="raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at97_state_mild",
        )

        self.assertTrue(planet_live._should_prefer_identity_target(decision, temporal))

    def test_analyze_rejects_far_temporal_during_late_overlap_continuity(self) -> None:
        clicked: list[tuple[int, int]] = []

        class _FakeDetector:
            enabled = True

            def detect_all(self, _frame):
                return [(621.0, 201.0, 0.87, 109.0, 118.0), (196.0, 117.0, 0.76, 90.0, 70.0)]

        class _FakeIdentityTracker:
            def update(self, **_kwargs):
                return IdentityDecision(
                    "TRACK_CONFIDENT",
                    (621.0, 201.0),
                    "right_continuity",
                    0.81,
                    "candidate_continuity",
                    0,
                    {"distance": 8.6, "color_weight": 0.1},
                )

        class _FakeTemporalSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    point=(196.0, 117.0),
                    source="selector_shadow",
                    reason="selected_family",
                    family="raw_candidate_cont0_center_mild_state_mild",
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
            "w": 700,
            "h": 500,
        }
        frame = np.zeros((620, 760, 3), dtype=np.uint8)
        packet = FramePacket(
            session_id="s",
            frame_index=49,
            timestamp_ms=0,
            source_frame=frame,
            board_frame=frame[20:520, 10:710],
            source_kind="test",
            roi_snapshot={"detect": roi, "board": dict(roi, name="board")},
        )

        result = solver.analyze(packet, solver_running=True)

        self.assertEqual(clicked, [(631, 221)])
        self.assertEqual(result.mouse_move.det_point, (621.0, 201.0))

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
