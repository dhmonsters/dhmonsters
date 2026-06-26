# 여러 JSONL 후보 로그의 selector_shadow backfill 요약을 검증합니다.
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _selector_shadow_batch_report import (
    analyze_record_path_fast,
    main,
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
                    "merge_context": {
                        "frames": 0,
                        "max_size": 122.0,
                        "max_ratio": 1.1,
                    },
                },
            },
            {
                "i": 20,
                "selector_shadow": {
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "point": [4, 5],
                    "rescue_point": [4.0, 5.0],
                    "rescue_allowed": True,
                    "merge_context": {
                        "frames": 2,
                        "max_size": 181.5,
                        "max_ratio": 1.34,
                    },
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
        self.assertEqual(summary["merge_context_frames"], 2)
        self.assertEqual(summary["merge_context_max_size"], 181.5)
        self.assertEqual(summary["merge_context_max_ratio"], 1.34)
        self.assertEqual(summary["families"]["bg_split_viterbi_center_mild_state_mild"], 1)
        self.assertEqual(summary["events"][0]["frame"], 20)
        self.assertEqual(summary["events"][0]["merge_context"]["max_size"], 181.5)

    def test_first_rescue_allowed_frame_ignores_blocked_bg_split(self):
        rows = [
            {
                "i": 10,
                "selector_shadow": {
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "point": [1, 2],
                    "rescue_point": [1.0, 2.0],
                    "rescue_allowed": False,
                    "merge_context": {
                        "frames": 0,
                        "max_size": 128.0,
                        "max_ratio": 1.099,
                    },
                },
            },
            {
                "i": 20,
                "selector_shadow": {
                    "family": "balanced_viterbi_center_mild_state_mild",
                    "point": [4, 5],
                    "rescue_point": [4.0, 5.0],
                    "rescue_allowed": True,
                    "merge_context": {
                        "frames": 1,
                        "max_size": 180.0,
                        "max_ratio": 1.31,
                    },
                },
            },
        ]

        summary = summarize_backfilled_rows("clip.jsonl", rows)

        self.assertEqual(summary["first_bg_split_frame"], 10)
        self.assertEqual(summary["first_rescue_allowed_frame"], 20)
        self.assertEqual(summary["events"][0]["merge_context"]["frames"], 0)

    def test_write_markdown_report_includes_merge_context_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"

            write_markdown_report([
                {
                    "name": "clip.jsonl",
                    "frames": 3,
                    "shadow_frames": 2,
                    "bg_split_frames": 1,
                    "rescue_allowed_frames": 1,
                    "first_bg_split_frame": 20,
                    "first_rescue_allowed_frame": 20,
                    "merge_context_frames": 2,
                    "merge_context_max_size": 181.5,
                    "merge_context_max_ratio": 1.34,
                    "families": {
                        "bg_split_viterbi_center_mild_state_mild": 1,
                    },
                    "events": [],
                    "elapsed_ms": 12,
                },
            ], out)

            text = out.read_text(encoding="utf-8")

        self.assertIn("merge_frames", text)
        self.assertIn("181.5", text)
        self.assertIn("1.34", text)

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

    def test_analyze_record_path_fast_forwards_merge_gate_options(self):
        captured = []

        def fake_backfill(rows, **kwargs):
            captured.append(kwargs)
            return [dict(rows[0])]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.jsonl").write_text(
                json.dumps({
                    "i": 0,
                    "track": [1.0, 2.0],
                    "cands": [[1.0, 2.0, 0.9, 20.0, 20.0]],
                }) + "\n",
                encoding="utf-8",
            )

            with patch("_selector_shadow_batch_report.backfill_selector_shadow_rows", fake_backfill):
                analyze_record_path_fast(
                    root,
                    runtime=FakeRuntime(),
                    max_files=1,
                    limit=1,
                    min_frames=1,
                    shadow_min_frames=1,
                    emit_every=1,
                    include_local_box=False,
                    merge_context_frames=4,
                    merge_min_size=201.0,
                    merge_size_ratio=1.45,
                )

        self.assertEqual(captured[0]["merge_context_frames"], 4)
        self.assertEqual(captured[0]["merge_min_size"], 201.0)
        self.assertEqual(captured[0]["merge_size_ratio"], 1.45)

    def test_main_accepts_merge_gate_cli_options(self):
        captured = {}

        def fake_analyze(path, **kwargs):
            captured.update(kwargs)
            return []

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"
            with patch("_selector_shadow_batch_report.analyze_record_path_fast", fake_analyze):
                with patch("_selector_shadow_batch_report.write_markdown_report", return_value=out):
                    result = main([
                        "_record_debug",
                        "--out", str(out),
                        "--files", "1",
                        "--merge-context-frames", "4",
                        "--merge-min-size", "201",
                        "--merge-size-ratio", "1.45",
                    ])

        self.assertEqual(result, 0)
        self.assertEqual(captured["merge_context_frames"], 4)
        self.assertEqual(captured["merge_min_size"], 201.0)
        self.assertEqual(captured["merge_size_ratio"], 1.45)

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
