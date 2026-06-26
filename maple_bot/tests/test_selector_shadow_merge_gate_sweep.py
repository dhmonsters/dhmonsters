# selector shadow 병합 gate sweep 유틸리티를 검증합니다.
import tempfile
import unittest
from pathlib import Path

from _selector_shadow_merge_gate_sweep import (
    GateSpec,
    parse_gate,
    record_files,
    summarize_gate,
    sweep_backfilled_rows,
)


class SelectorShadowMergeGateSweepTests(unittest.TestCase):
    def test_parse_gate_reads_name_size_and_ratio(self):
        gate = parse_gate("strict:190:1.45")

        self.assertEqual(gate, GateSpec("strict", 190.0, 1.45))

    def test_summarize_gate_uses_cached_merge_max_without_rerunning_selector(self):
        rows = [
            {
                "i": 10,
                "selector_shadow": {
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "rescue_point": [1.0, 2.0],
                    "merge_context": {
                        "max_size": 180.0,
                        "max_ratio": 1.20,
                    },
                },
            },
            {
                "i": 20,
                "selector_shadow": {
                    "family": "panel_default_center_mild_state_mild",
                    "rescue_point": [3.0, 4.0],
                    "merge_context": {
                        "max_size": 220.0,
                        "max_ratio": 1.60,
                    },
                },
            },
        ]

        loose = summarize_gate("clip.jsonl", rows, GateSpec("loose", 175.0, 1.30))
        strict = summarize_gate("clip.jsonl", rows, GateSpec("strict", 190.0, 1.30))

        self.assertEqual(loose["bg_split_frames"], 1)
        self.assertEqual(loose["rescue_allowed_frames"], 1)
        self.assertEqual(loose["first_rescue_allowed_frame"], 10)
        self.assertEqual(strict["rescue_allowed_frames"], 0)
        self.assertEqual(strict["merge_context_max_size"], 220.0)
        self.assertEqual(strict["bg_split_max_size"], 180.0)
        self.assertEqual(strict["bg_split_max_ratio"], 1.2)

    def test_summarize_gate_treats_merge_context_family_as_rescue_family(self):
        rows = [
            {
                "i": 10,
                "selector_shadow": {
                    "family": "merge_context_center_mild_state_mild",
                    "rescue_point": [1.0, 2.0],
                    "merge_context": {
                        "max_size": 180.0,
                        "max_ratio": 1.20,
                    },
                },
            },
        ]

        summary = summarize_gate("clip.jsonl", rows, GateSpec("loose", 175.0, 1.30))

        self.assertEqual(summary["bg_split_frames"], 1)
        self.assertEqual(summary["rescue_allowed_frames"], 1)
        self.assertEqual(summary["first_rescue_allowed_frame"], 10)

    def test_sweep_backfilled_rows_returns_one_summary_per_gate(self):
        rows = [
            {
                "i": 1,
                "selector_shadow": {
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "rescue_point": [1.0, 2.0],
                    "merge_context": {
                        "max_size": 180.0,
                        "max_ratio": 1.20,
                    },
                },
            },
        ]

        summaries = sweep_backfilled_rows(
            "clip.jsonl",
            rows,
            [GateSpec("loose", 175.0, 1.30), GateSpec("strict", 190.0, 1.30)],
        )

        self.assertEqual([item["gate"] for item in summaries], ["loose", "strict"])
        self.assertEqual([item["rescue_allowed_frames"] for item in summaries], [1, 0])

    def test_record_files_can_filter_to_gt_clip_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = root / "records"
            gt = root / "gt"
            records.mkdir()
            gt.mkdir()
            (records / "a.jsonl").write_text("{}\n", encoding="utf-8")
            (records / "b.jsonl").write_text("{}\n", encoding="utf-8")
            (gt / "b").mkdir()

            files = record_files(records, gt_dir=gt)

        self.assertEqual([path.name for path in files], ["b.jsonl"])


if __name__ == "__main__":
    unittest.main()
