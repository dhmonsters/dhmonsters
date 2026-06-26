# selector_shadow JSONL 분석기의 요약 지표를 검증합니다.
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _selector_shadow_analyzer import (
    analyze_record_file,
    analyze_record_path,
    write_markdown_report,
)


def _write_jsonl(path: Path, frames):
    with path.open("w", encoding="utf-8") as fh:
        for frame in frames:
            fh.write(json.dumps(frame, ensure_ascii=False) + "\n")


class SelectorShadowAnalyzerTests(unittest.TestCase):
    def test_analyze_file_counts_divergence_and_recovery_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.jsonl"
            _write_jsonl(path, [
                {
                    "i": 1,
                    "track": [10, 10],
                    "selector_shadow": {
                        "available": True,
                        "family": "panel_default_center_mild_state_mild",
                        "point": [12, 10],
                    },
                },
                {
                    "i": 2,
                    "track": [100, 10],
                    "selector_shadow": {
                        "available": True,
                        "family": "balanced_viterbi_center_mild_state_mild",
                        "point": [20, 10],
                    },
                },
                {
                    "i": 3,
                    "track": None,
                    "selector_shadow": {
                        "available": True,
                        "family": "balanced_viterbi_center_mild_state_mild",
                        "point": [22, 10],
                    },
                },
            ])

            summary = analyze_record_file(path, divergence_px=30.0, jump_px=40.0)

        self.assertEqual(summary["frames"], 3)
        self.assertEqual(summary["shadow_frames"], 3)
        self.assertEqual(summary["divergence_count"], 1)
        self.assertEqual(summary["recovery_candidates"], 1)
        self.assertEqual(summary["shadow_less_jumpy"], 1)
        self.assertEqual(summary["families"]["balanced_viterbi_center_mild_state_mild"], 2)
        self.assertEqual(summary["events"][0]["frame"], 2)
        self.assertEqual(summary["events"][0]["kind"], "divergence")

    def test_analyze_path_skips_files_without_shadow_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_jsonl(root / "old.jsonl", [
                {"i": 1, "track": [1, 1], "cands": []},
            ])
            _write_jsonl(root / "new.jsonl", [
                {
                    "i": 1,
                    "track": [1, 1],
                    "selector_shadow": {
                        "available": True,
                        "family": "panel_default_center_mild_state_mild",
                        "point": [1, 1],
                    },
                },
            ])

            summaries = analyze_record_path(root)

        self.assertEqual([item["name"] for item in summaries], ["new.jsonl"])

    def test_analyze_file_counts_selector_rescue_gate_and_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rescue.jsonl"
            _write_jsonl(path, [
                {
                    "i": 1,
                    "track": [10, 10],
                    "rescue_source": None,
                    "health": {"source": "primary", "reason": "primary_healthy"},
                    "selector_shadow": {
                        "available": True,
                        "family": "panel_default_center_mild_state_mild",
                        "point": [10, 10],
                        "rescue_point": [10.0, 10.0],
                        "rescue_allowed": False,
                    },
                },
                {
                    "i": 2,
                    "track": [20, 10],
                    "rescue_source": "selector_shadow",
                    "health": {"source": "rescue", "reason": "primary_repeated_jump"},
                    "selector_shadow": {
                        "available": True,
                        "family": "bg_split_viterbi_center_mild_state_mild",
                        "point": [20, 10],
                        "rescue_point": [20.0, 10.0],
                        "rescue_allowed": True,
                    },
                },
                {
                    "i": 3,
                    "track": [30, 10],
                    "rescue_source": "engine",
                    "health": {"source": "primary", "reason": "primary_healthy"},
                    "selector_shadow": {
                        "available": True,
                        "family": "bg_split_viterbi_center_mild_state_mild",
                        "point": [30, 10],
                        "rescue_point": [30.0, 10.0],
                        "rescue_allowed": True,
                    },
                },
            ])

            summary = analyze_record_file(path)

        self.assertEqual(summary["rescue_allowed_frames"], 2)
        self.assertEqual(summary["rescue_blocked_frames"], 1)
        self.assertEqual(summary["bg_split_frames"], 2)
        self.assertEqual(summary["selector_rescue_used"], 1)
        self.assertEqual(summary["health_rescue_frames"], 1)
        self.assertTrue(any(
            event["kind"] == "selector_rescue_used"
            for event in summary["events"]
        ))

    def test_write_markdown_report_mentions_no_shadow_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"

            write_markdown_report([], out)

            text = out.read_text(encoding="utf-8")

        self.assertIn("selector_shadow 로그가 있는 파일이 없습니다.", text)

    def test_write_markdown_report_permission_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"

            with patch("pathlib.Path.write_text", side_effect=PermissionError("blocked")):
                result = write_markdown_report([], out)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
