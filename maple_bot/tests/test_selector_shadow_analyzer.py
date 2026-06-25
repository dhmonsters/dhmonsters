# selector_shadow JSONL 분석기의 요약 지표를 검증합니다.
import json
import tempfile
import unittest
from pathlib import Path

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

    def test_write_markdown_report_mentions_no_shadow_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.md"

            write_markdown_report([], out)

            text = out.read_text(encoding="utf-8")

        self.assertIn("selector_shadow 로그가 있는 파일이 없습니다", text)


if __name__ == "__main__":
    unittest.main()
