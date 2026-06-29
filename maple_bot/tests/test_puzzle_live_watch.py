# 퍼즐 라이브 감시 게이트의 활성 감지를 검증한다.
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from core.puzzle.defaults import (
    DEFAULT_BOARD_ROI_RATIOS,
    DEFAULT_DETECT_ROI_RATIOS,
    DEFAULT_POPUP_HEADER_ROI_RATIOS,
    DEFAULT_POPUP_PREVIEW_ROI_RATIOS,
)
from core.puzzle.live_recording import LiveRecordingRuntime
from core.puzzle.live_watch import LivePuzzleActivationDetector, WatchStartResult
from core.puzzle.models import RoiSpec


class LivePuzzleActivationDetectorTest(unittest.TestCase):
    def test_dark_frame_does_not_activate_recording(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.full((100, 100, 3), 255, dtype=np.uint8)

        result = detector.detect(frame)

        self.assertFalse(result.active)
        self.assertEqual(result.reason, "popup_not_detected")

    def test_default_detector_does_not_activate_on_bright_game_background(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.full((100, 100, 3), 255, dtype=np.uint8)
        frame[30:90, 20:95] = 255

        result = detector.detect(frame)

        self.assertFalse(result.active)
        self.assertEqual(result.reason, "popup_not_detected")

    def test_dark_header_ratio_activates_with_planet_noauth_rois(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.full((1080, 1920, 3), 220, dtype=np.uint8)
        hx1 = int(1920 * DEFAULT_POPUP_HEADER_ROI_RATIOS["x_ratio"])
        hy1 = int(1080 * DEFAULT_POPUP_HEADER_ROI_RATIOS["y_ratio"])
        hx2 = hx1 + int(1920 * DEFAULT_POPUP_HEADER_ROI_RATIOS["w_ratio"])
        hy2 = hy1 + int(1080 * DEFAULT_POPUP_HEADER_ROI_RATIOS["h_ratio"])
        frame[hy1:hy2, hx1:hx2] = 30

        result = detector.detect(frame)

        self.assertTrue(result.active)
        self.assertEqual(result.reason, "popup_board")
        self.assertGreaterEqual(result.score, 0.50)
        self.assertIsNotNone(result.board_roi)
        self.assertIsNotNone(result.detect_roi)
        self.assertAlmostEqual(result.board_roi.x_ratio, DEFAULT_BOARD_ROI_RATIOS["x_ratio"])
        self.assertAlmostEqual(result.board_roi.y_ratio, DEFAULT_BOARD_ROI_RATIOS["y_ratio"])
        self.assertAlmostEqual(result.detect_roi.x_ratio, DEFAULT_DETECT_ROI_RATIOS["x_ratio"])
        self.assertAlmostEqual(result.detect_roi.y_ratio, DEFAULT_DETECT_ROI_RATIOS["y_ratio"])

    def test_default_rois_match_planet_solver_noauth_ratios(self) -> None:
        self.assertEqual(DEFAULT_POPUP_HEADER_ROI_RATIOS["x_ratio"], 0.320)
        self.assertEqual(DEFAULT_POPUP_HEADER_ROI_RATIOS["y_ratio"], 0.202)
        self.assertEqual(DEFAULT_POPUP_HEADER_ROI_RATIOS["w_ratio"], 0.678 - 0.320)
        self.assertEqual(DEFAULT_POPUP_HEADER_ROI_RATIOS["h_ratio"], 0.263 - 0.202)
        self.assertEqual(DEFAULT_BOARD_ROI_RATIOS["x_ratio"], 0.318)
        self.assertEqual(DEFAULT_BOARD_ROI_RATIOS["y_ratio"], 0.188)
        self.assertEqual(DEFAULT_BOARD_ROI_RATIOS["w_ratio"], 0.680 - 0.318)
        self.assertEqual(DEFAULT_BOARD_ROI_RATIOS["h_ratio"], 0.775 - 0.188)
        self.assertEqual(DEFAULT_DETECT_ROI_RATIOS["x_ratio"], 0.320)
        self.assertEqual(DEFAULT_DETECT_ROI_RATIOS["y_ratio"], 0.265)
        self.assertEqual(DEFAULT_DETECT_ROI_RATIOS["w_ratio"], 0.678 - 0.320)
        self.assertEqual(DEFAULT_DETECT_ROI_RATIOS["h_ratio"], 0.728 - 0.265)
        self.assertEqual(DEFAULT_POPUP_PREVIEW_ROI_RATIOS["x_ratio"], 0.318)
        self.assertEqual(DEFAULT_POPUP_PREVIEW_ROI_RATIOS["y_ratio"], 0.188)
        self.assertEqual(DEFAULT_POPUP_PREVIEW_ROI_RATIOS["w_ratio"], 0.680 - 0.318)
        self.assertEqual(DEFAULT_POPUP_PREVIEW_ROI_RATIOS["h_ratio"], 0.775 - 0.188)

    def test_white_shape_fallback_only_activates_when_enabled(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False, allow_white_fallback=True)
        frame = np.full((100, 100, 3), 120, dtype=np.uint8)
        frame[30:52, 36:58] = 255

        result = detector.detect(frame)

        self.assertTrue(result.active)
        self.assertEqual(result.reason, "white_shape")


class WatchPreviewFrameTest(unittest.TestCase):
    def test_watch_start_result_can_carry_memory_preview_without_path(self) -> None:
        preview_frame = np.full((8, 12, 3), 90, dtype=np.uint8)

        result = WatchStartResult("armed", preview_frame=preview_frame)

        self.assertIsNone(result.preview_path)
        self.assertIs(result.preview_frame, preview_frame)

    def test_build_watch_preview_frame_does_not_write_png(self) -> None:
        import puzzle

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        with TemporaryDirectory() as tmp:
            preview = puzzle._build_watch_preview_frame(frame, popup_score=0.14)

            self.assertEqual(list(Path(tmp).rglob("*.png")), [])
            self.assertEqual(preview.shape[:2], (634, 695))


class LiveRecordingActivationFrameTest(unittest.TestCase):
    def test_start_uses_activation_frame_without_extra_grab(self) -> None:
        grabbed = {"count": 0}

        def grab():
            grabbed["count"] += 1
            return np.full((6, 8, 3), 88, dtype=np.uint8)

        activation_frame = np.full((6, 8, 3), 77, dtype=np.uint8)
        with TemporaryDirectory() as tmp:
            runtime = LiveRecordingRuntime(
                output_root=tmp,
                frame_grabber=grab,
                fps=10.0,
                sleeper=lambda _seconds: None,
            )
            detect_roi = RoiSpec("detect", "window_client", 1, 1, 3, 3)
            board_roi = RoiSpec("board", "window_client", 2, 2, 4, 3)

            session = runtime.start(
                initial_frame=activation_frame,
                detect_roi=detect_roi,
                board_roi=board_roi,
            )

            self.assertTrue(session.output_dir.exists())
            self.assertEqual(session.detect_roi, detect_roi)
            self.assertEqual(session.board_roi, board_roi)
            self.assertEqual(runtime.frame_count, 1)
            self.assertEqual(grabbed["count"], 0)
            self.assertIsNotNone(runtime.latest_preview_path)
            self.assertTrue(runtime.latest_preview_path.exists())
            self.assertTrue(runtime.stop_recording(reason="test_cleanup"))
            self.assertTrue(runtime.finish(reason="test_cleanup").exists())


if __name__ == "__main__":
    unittest.main()
