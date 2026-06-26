# 여러 JSONL 후보 로그의 selector_shadow backfill 요약을 검증합니다.
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _selector_shadow_batch_report import (
    analyze_record_path_fast,
    summarize_backfilled_rows,
    write_markdown_report,
)


class FakeRuntime:
    available = True
    load_error = ""

    def __init__(self, family="panel_default_center_mild_state_mild"):
        self.family = family
        self.calls = 0

    def select_from_path_pool(self, clip, paths, frames, **kwargs):
        self.calls += 1
        family = self.family if self.family in paths else next(iter(paths), self.family)
        row = {
            "clip": clip,
            "family": family,
            "rank_center": 0.0,
            "rank_rough": 0.0,
        }
        return {clip: row}, [row]


class SelectorShadowBatchReportTests(unittest.TestCase):
    def test_summarize_backfilled_rows_counts_rescue_and_bg_split(self):
        rows = [
            {
                "i": 10,
                "selector_shadow": {
                    "family": "balanced_viterbi_center_mild_state_mild",
                    "point": [1, 2],
                    "rescue_point": [1.0, 2.0],
                    "rescue_allowed": False,
                },
            },
            {
                "i": 20,
                "selector_shadow": {
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "point": [4, 5],
                    "rescue_point": [4.0, 5.0],
                    "rescue_allowed": True,
                },
            },
            {"i": 30},
        ]

        summary = summarize_backfilled_rows("clip.jsonl", rows, elapsed_ms=12)

        self.assertEqual(summary["name"], "clip.jsonl")
        self.assertEqual(summary["frames"], 3)
        self.assertEqual(summary["shadow_frames"], 2)
        self.assertEqual(summary["bg_split_frames"], 1)
        self.assertEqual(summary["rescue_allowed_frames"], 1)
        self.assertEqual(summary["first_bg_split_frame"], 20)
        self.assertEqual(summary["first_rescue_allowed_frame"], 20)
        self.assertEqual(summary["families"]["bg_split_viterbi_center_mild_state_mild"], 1)
        self.assertEqual(summary["events"][0]["frame"], 20)

    def test_first_rescue_allowed_frame_ignores_blocked_bg_split(self):
        rows = [
            {
                "i": 10,
                "selector_shadow": {
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "point": [1, 2],
                    "rescue_point": [1.0, 2.0],
                    "rescue_allowed": False,
                },
            },
            {
                "i": 20,
                "selector_shadow": {
                    "family": "balanced_viterbi_center_mild_state_mild",
                    "point": [4, 5],
                    "rescue_point": [4.0, 5.0],
                    "rescue_allowed": True,
                },
            },
        ]

        summary = summarize_backfilled_rows("clip.jsonl", rows)

        self.assertEqual(summary["first_bg_split_frame"], 10)
        self.assertEqual(summary["first_rescue_allowed_frame"], 20)

    def test_analyze_record_path_fast_limits_files_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a.jsonl", "b.jsonl", "c.jsonl"):
                rows = [
                    {
                        "i": frame,
                        "track": [float(frame), 0.0],
                        "cands": [[float(frame), 0.0, 0.9, 20.0, 20.0]],
                    }
                    for frame in range(5)
                ]
                (root / name).write_text(
                    "\n".join(json.dumps(row) for row in rows) + "\n",
                    encoding="utf-8",
                )

            summaries = analyze_record_path_fast(
                root,
                runtime=FakeRuntime(),
                max_files=2,
                limit=2,
                min_frames=1,
                shadow_min_frames=1,
                emit_every=1,
                include_local_box=False,
            )

        self.assertEqual([item["name"] for item in summaries], ["a.jsonl", "b.jsonl"])
        self.assertEqual([item["frames"] for item in summaries], [2, 2])

    def test_write_markdown_report_returns_none_on_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            original_write_text = Path.write_text

            def blocked(self, *args, **kwargs):
                if self == out:
                    raise PermissionError("blocked")
                return original_write_text(self, *args, **kwargs)

            with patch("pathlib.Path.write_text", blocked):
                result = write_markdown_report([], out)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
