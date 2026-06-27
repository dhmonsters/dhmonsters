# 퍼즐 라이브 감시 게이트의 활성 감지를 검증한다.
from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

import numpy as np

from core.puzzle.live_recording import LiveRecordingRuntime
from core.puzzle.live_watch import LivePuzzleActivationDetector


class LivePuzzleActivationDetectorTest(unittest.TestCase):
    def test_dark_frame_does_not_activate_recording(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        result = detector.detect(frame)

        self.assertFalse(result.active)
        self.assertEqual(result.reason, "no_shape")

    def test_white_shape_inside_board_roi_activates_recording(self) -> None:
        detector = LivePuzzleActivationDetector(use_yolo=False)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[30:52, 36:58] = 255

        result = detector.detect(frame)

        self.assertTrue(result.active)
        self.assertEqual(result.reason, "white_shape")


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

            session = runtime.start(initial_frame=activation_frame)

            self.assertTrue(session.output_dir.exists())
            self.assertEqual(runtime.frame_count, 1)
            self.assertEqual(grabbed["count"], 0)
            self.assertTrue(runtime.stop_recording(reason="test_cleanup"))
            self.assertTrue(runtime.finish(reason="test_cleanup").exists())


if __name__ == "__main__":
    unittest.main()
