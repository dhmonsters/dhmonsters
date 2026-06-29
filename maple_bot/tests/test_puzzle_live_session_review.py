# 투명도형 라이브 세션 리뷰 리포트 생성을 검증한다.
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core.puzzle.live_recording import LiveRecordingRuntime
from core.puzzle.live_session_review import LiveSessionReviewBuilder
from core.puzzle.planet_live import PlanetLiveResult


def _write_trace(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )


class LiveSessionReviewBuilderTest(unittest.TestCase):
    def test_live_session_review_summarizes_dry_run_mouse_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_path = tmp_path / "trace.jsonl"
            review_path = tmp_path / "live_session_review.md"
            events = [
                {
                    "type": "SESSION_START",
                    "frame_index": None,
                    "payload": {"mouse_enabled": False},
                },
                {
                    "type": "PUZZLE_ACTIVATED",
                    "frame_index": None,
                    "payload": {"reason": "popup_board", "score": 0.88},
                },
                {
                    "type": "FRAME_RECORDED",
                    "frame_index": 0,
                    "payload": {},
                },
                {
                    "type": "TEMPORAL_SELECTOR",
                    "frame_index": 0,
                    "payload": {
                        "source": "selector_shadow",
                        "family": "raw_candidate_cont11_center_mild_state_mild",
                    },
                },
                {
                    "type": "MOUSE_MOVE",
                    "frame_index": 0,
                    "payload": {"moved": False, "reason": "disabled"},
                },
            ]
            _write_trace(trace_path, events)

            summary = LiveSessionReviewBuilder().build(trace_path, review_path)

            text = review_path.read_text(encoding="utf-8")
            self.assertIs(summary.mouse_enabled, False)
            self.assertEqual(summary.frames, 1)
            self.assertEqual(summary.temporal_selector_events, 1)
            self.assertEqual(summary.mouse_moved, 0)
            self.assertEqual(summary.mouse_disabled, 1)
            self.assertIn("mouse_enabled: false", text)
            self.assertIn("mouse_moved: 0", text)
            self.assertIn("mouse_disabled: 1", text)
            self.assertIn("raw_candidate_cont11_center_mild_state_mild", text)

    def test_live_recording_finish_writes_live_session_review(self) -> None:
        class _NoopSolver:
            def analyze(self, _packet, *, solver_running: bool):
                return PlanetLiveResult(
                    trace_events=[
                        (
                            "TEMPORAL_SELECTOR",
                            {
                                "source": "selector_shadow",
                                "family": "raw_candidate_cont11_center_mild_state_mild",
                            },
                        ),
                        (
                            "MOUSE_MOVE",
                            {
                                "moved": False,
                                "reason": "disabled",
                            },
                        ),
                    ]
                )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame = np.full((6, 8, 3), 55, dtype=np.uint8)
            runtime = LiveRecordingRuntime(
                output_root=tmp_path,
                frame_grabber=lambda: frame,
                fps=10.0,
                sleeper=lambda _seconds: None,
                live_solver=_NoopSolver(),
                mouse_enabled=False,
            )

            session = runtime.start(initial_frame=frame)
            runtime.stop_recording(reason="test_done")
            runtime.finish(reason="test_done")

            review_path = session.output_dir / "live_session_review.md"
            self.assertTrue(review_path.exists())
            text = review_path.read_text(encoding="utf-8")
            self.assertIn("mouse_enabled: false", text)
            self.assertIn("mouse_disabled: 1", text)


if __name__ == "__main__":
    unittest.main()
