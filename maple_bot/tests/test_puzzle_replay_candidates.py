# puzzle.py replay 후보 로그 자동 연결을 검증합니다.
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from puzzle import (
    _candidate_rows_from_replay_companion,
    _companion_candidate_jsonl_path,
)


class PuzzleReplayCandidatesTests(unittest.TestCase):
    def test_companion_jsonl_path_uses_png_suffix_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay_dir = root / "sample_png"
            replay_dir.mkdir()
            companion = root / "sample.jsonl"
            companion.write_text("{}\n", encoding="utf-8")

            self.assertEqual(_companion_candidate_jsonl_path(replay_dir), companion)

    def test_candidate_rows_from_companion_jsonl_returns_rows_by_frame_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay_dir = root / "sample_png"
            replay_dir.mkdir()
            companion = root / "sample.jsonl"
            companion.write_text(
                "".join(
                    json.dumps({"cands": rows}) + "\n"
                    for rows in (
                        [[1, 2, 0.9]],
                        [[3, 4, 0.8], [5, 6, 0.7]],
                    )
                ),
                encoding="utf-8",
            )

            provider = _candidate_rows_from_replay_companion(replay_dir)

            self.assertEqual(provider(SimpleNamespace(frame_index=1)), [[3, 4, 0.8], [5, 6, 0.7]])
            self.assertEqual(provider(SimpleNamespace(frame_index=99)), [])

    def test_candidate_rows_from_missing_companion_returns_empty_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            replay_dir = Path(tmp) / "missing_png"
            replay_dir.mkdir()

            provider = _candidate_rows_from_replay_companion(replay_dir)

            self.assertEqual(provider(SimpleNamespace(frame_index=0)), [])


if __name__ == "__main__":
    unittest.main()
