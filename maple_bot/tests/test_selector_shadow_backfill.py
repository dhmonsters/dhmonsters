# 기존 JSONL 후보 로그에서 selector_shadow를 재생 생성하는 backfill을 검증합니다.
import json
import tempfile
import unittest
from pathlib import Path

from _selector_shadow_backfill import (
    backfill_selector_shadow_rows,
    write_backfilled_jsonl,
)


class FakeRuntime:
    available = True
    load_error = ""

    def __init__(self, selected_family):
        self.selected_family = selected_family

    def select_from_path_pool(self, clip, paths, frames, **kwargs):
        family = self.selected_family if self.selected_family in paths else next(iter(paths), self.selected_family)
        row = {
            "clip": clip,
            "family": family,
            "rank_center": 0.0,
            "rank_rough": 0.0,
        }
        return {clip: row}, [row]


class SelectorShadowBackfillTests(unittest.TestCase):
    def test_backfill_adds_bg_split_selector_shadow_from_live_family_pool(self):
        rows = [
            {
                "i": 0,
                "track": [0.0, 0.0],
                "cands": [[0.0, 0.0, 0.9, 20.0, 20.0]],
            },
            {
                "i": 1,
                "track": [20.0, 0.0],
                "cands": [[20.0, 0.0, 0.9, 20.0, 20.0]],
            },
            {
                "i": 2,
                "track": [10.0, 0.0],
                "cands": [[10.0, 0.0, 0.95, 100.0, 50.0]],
            },
            {
                "i": 3,
                "track": [10.0, 0.0],
                "cands": [
                    [60.0, 0.0, 0.7, 20.0, 20.0],
                    [10.0, 0.0, 0.95, 20.0, 20.0],
                ],
            },
        ]

        out = backfill_selector_shadow_rows(
            rows,
            runtime=FakeRuntime("bg_split_viterbi_center_mild_state_mild"),
            clip_id="sample",
            window=5,
            min_frames=2,
            shadow_min_frames=1,
            max_candidates=4,
            include_local_box=False,
        )

        self.assertIn("selector_shadow", out[2])
        self.assertEqual(
            out[2]["selector_shadow"]["family"],
            "bg_split_viterbi_center_mild_state_mild",
        )
        self.assertTrue(out[2]["selector_shadow"]["rescue_allowed"])
        self.assertEqual(out[2]["selector_shadow"]["rescue_point"], [40.0, 0.0])
        self.assertEqual(out[3]["selector_shadow"]["rescue_point"], [60.0, 0.0])

    def test_write_backfilled_jsonl_writes_augmented_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.jsonl"
            out_path = Path(tmp) / "output.jsonl"
            in_path.write_text(
                json.dumps({
                    "i": 0,
                    "track": [1.0, 2.0],
                    "cands": [[1.0, 2.0, 0.9, 20.0, 20.0]],
                }) + "\n",
                encoding="utf-8",
            )

            result = write_backfilled_jsonl(
                in_path,
                out_path,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                include_local_box=False,
            )

            written = [
                json.loads(line)
                for line in out_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(result, out_path)
        self.assertEqual(written[0]["selector_shadow"]["family"], "panel_default_center_mild_state_mild")


if __name__ == "__main__":
    unittest.main()
