# 퍼즐 라이브 감시 게이트의 활성 감지를 검증한다.
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from core.puzzle.defaults import DEFAULT_BOARD_ROI_RATIOS, DEFAULT_DETECT_ROI_RATIOS
from core.puzzle.live_recording import LiveRecordingRuntime
from core.puzzle.live_watch import LivePuzzleActivationDetector, WatchStartResult
from core.puzzle.models import RoiSpec


def _write_popup_template(path) -> None:
    import cv2

    template = np.full((54, 120, 3), 64, dtype=np.uint8)
    template[8:18, 12:108] = 220
    template[26:42, 24:96] = 142
    template[:, 0:4] = 12
    template[:, -4:] = 12
    cv2.imwrite(str(path), template)


class LivePuzzleActivationDetectorTest(unittest.TestCase):
    def test_dark_frame_does_not_activate_recording(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        result = detector.detect(frame)

        self.assertFalse(result.active)
        self.assertEqual(result.reason, "popup_not_detected")

    def test_default_detector_does_not_activate_on_bright_game_background(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[30:90, 20:95] = 255

        result = detector.detect(frame)

        self.assertFalse(result.active)
        self.assertEqual(result.reason, "popup_not_detected")

    def test_popup_header_template_activates_with_planet_rois(self) -> None:
        with TemporaryDirectory() as tmp:
            template_path = f"{tmp}/popup_header.png"
            _write_popup_template(template_path)
            detector = LivePuzzleActivationDetector(use_yolo=False, template_dir=tmp)
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            hx = int(1920 * 0.320) + 20
            hy = int(1080 * 0.202) + 5

            import cv2

            template = cv2.imread(template_path)
            frame[hy : hy + template.shape[0], hx : hx + template.shape[1]] = template

            result = detector.detect(frame)

        self.assertTrue(result.active)
        self.assertEqual(result.reason, "popup_board")
        self.assertIsNotNone(result.board_roi)
        self.assertIsNotNone(result.detect_roi)
        self.assertAlmostEqual(result.board_roi.x_ratio, DEFAULT_BOARD_ROI_RATIOS["x_ratio"])
        self.assertAlmostEqual(result.board_roi.y_ratio, DEFAULT_BOARD_ROI_RATIOS["y_ratio"])
        self.assertAlmostEqual(result.detect_roi.w_ratio, DEFAULT_DETECT_ROI_RATIOS["w_ratio"])
        self.assertAlmostEqual(result.detect_roi.h_ratio, DEFAULT_DETECT_ROI_RATIOS["h_ratio"])

    def test_white_shape_fallback_only_activates_when_enabled(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False, allow_white_fallback=True)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
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
            self.assertEqual(preview.shape[:2], (619, 695))


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
