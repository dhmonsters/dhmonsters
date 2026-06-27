# 기존 JSONL 후보 로그에서 selector_shadow를 재생 생성하는 backfill을 검증합니다.
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from _selector_shadow_backfill import (
    backfill_selector_shadow_rows,
    main,
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


class CountingRuntime(FakeRuntime):
    def __init__(self, selected_family):
        super().__init__(selected_family)
        self.calls = 0

    def select_from_path_pool(self, clip, paths, frames, **kwargs):
        self.calls += 1
        return super().select_from_path_pool(clip, paths, frames, **kwargs)


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
                "cands": [[10.0, 0.0, 0.95, 180.0, 120.0]],
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

    def test_emit_every_reduces_selector_runtime_calls(self):
        rows = [
            {
                "i": frame,
                "track": [float(frame), 0.0],
                "cands": [[float(frame), 0.0, 0.9, 20.0, 20.0]],
            }
            for frame in range(7)
        ]
        runtime = CountingRuntime("panel_default_center_mild_state_mild")

        out = backfill_selector_shadow_rows(
            rows,
            runtime=runtime,
            min_frames=1,
            shadow_min_frames=1,
            emit_every=3,
            include_local_box=False,
        )

        shadow_frames = [row["i"] for row in out if row.get("selector_shadow")]
        self.assertEqual(runtime.calls, 2)
        self.assertEqual(shadow_frames, [2, 5])

    def test_write_backfilled_jsonl_can_limit_loaded_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.jsonl"
            out_path = Path(tmp) / "output.jsonl"
            rows = [
                {
                    "i": frame,
                    "track": [float(frame), 0.0],
                    "cands": [[float(frame), 0.0, 0.9, 20.0, 20.0]],
                }
                for frame in range(5)
            ]
            in_path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            write_backfilled_jsonl(
                in_path,
                out_path,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                limit=2,
                include_local_box=False,
            )

            written = [
                json.loads(line)
                for line in out_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual([row["i"] for row in written], [0, 1])

    def test_write_backfilled_jsonl_uses_wjsonl_sidecar_widths(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.jsonl"
            sidecar_path = Path(tmp) / "input.wjsonl"
            out_path = Path(tmp) / "output.jsonl"
            in_path.write_text(
                json.dumps({
                    "i": 0,
                    "track": [10.0, 10.0],
                    "cands": [[10.0, 10.0, 0.9]],
                }) + "\n",
                encoding="utf-8",
            )
            sidecar_path.write_text(
                json.dumps([[10.2, 9.8, 180.0, 120.0, 0.8]]) + "\n",
                encoding="utf-8",
            )

            write_backfilled_jsonl(
                in_path,
                out_path,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                shadow_min_frames=1,
                include_local_box=False,
            )

            written = [
                json.loads(line)
                for line in out_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(written[0]["cands"][0], [10.0, 10.0, 0.9, 180.0, 120.0])
        self.assertEqual(written[0]["selector_shadow"]["merge_context"]["frames"], 1)

    def test_merge_gate_options_change_rescue_allowed_decision(self):
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
                "cands": [[10.0, 0.0, 0.95, 180.0, 120.0]],
            },
        ]

        allowed = backfill_selector_shadow_rows(
            rows,
            runtime=FakeRuntime("bg_split_viterbi_center_mild_state_mild"),
            clip_id="sample",
            window=5,
            min_frames=2,
            shadow_min_frames=1,
            max_candidates=4,
            include_local_box=False,
            merge_min_size=175.0,
            merge_size_ratio=10.0,
        )
        blocked = backfill_selector_shadow_rows(
            rows,
            runtime=FakeRuntime("bg_split_viterbi_center_mild_state_mild"),
            clip_id="sample",
            window=5,
            min_frames=2,
            shadow_min_frames=1,
            max_candidates=4,
            include_local_box=False,
            merge_min_size=200.0,
            merge_size_ratio=10.0,
        )

        self.assertTrue(allowed[2]["selector_shadow"]["rescue_allowed"])
        self.assertFalse(blocked[2]["selector_shadow"]["rescue_allowed"])
        self.assertEqual(blocked[2]["selector_shadow"]["merge_context"]["frames"], 0)

    def test_main_accepts_fast_cli_options(self):
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

            result = main([
                str(in_path),
                "--out", str(out_path),
                "--limit", "1",
                "--emit-every", "2",
                "--no-local-box",
            ])

        self.assertEqual(result, 0)

    def test_live_max_candidates_limits_live_family_input(self):
        instances = []

        class FakeLivePool:
            def __init__(self, **kwargs):
                self.lengths = []
                instances.append(self)

            def update(self, frame_index, *, candidates, gray_frame=None, white_anchor=None):
                self.lengths.append(len(candidates))
                return SimpleNamespace(points={})

        rows = [
            {
                "i": frame,
                "track": [float(frame), 0.0],
                "cands": [
                    [float(frame + cand), 0.0, float(100 - cand), 20.0, 20.0]
                    for cand in range(10)
                ],
            }
            for frame in range(3)
        ]

        with patch("_selector_shadow_backfill.TransparentLiveFamilyPool", FakeLivePool):
            backfill_selector_shadow_rows(
                rows,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                live_max_candidates=3,
                include_local_box=False,
            )

        self.assertEqual(instances[0].lengths, [0, 3, 3])

    def test_backfill_can_enable_guarded_decal_identity_pool(self):
        instances = []

        class FakeLivePool:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                instances.append(self)

            def update(self, frame_index, *, candidates, gray_frame=None, white_anchor=None):
                return SimpleNamespace(points={})

        rows = [
            {
                "i": 0,
                "track": [0.0, 0.0],
                "cands": [[0.0, 0.0, 0.9, 20.0, 20.0]],
            }
        ]

        with patch("_selector_shadow_backfill.TransparentLiveFamilyPool", FakeLivePool):
            backfill_selector_shadow_rows(
                rows,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                enable_guarded_decal_identity=True,
                include_local_box=False,
            )

        self.assertTrue(instances[0].kwargs["enable_guarded_decal_identity"])

    def test_backfill_forwards_guarded_decal_tuning_options(self):
        instances = []

        class FakeLivePool:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                instances.append(self)

            def update(self, frame_index, *, candidates, gray_frame=None, white_anchor=None):
                return SimpleNamespace(points={})

        rows = [
            {
                "i": 0,
                "track": [0.0, 0.0],
                "cands": [[0.0, 0.0, 0.9, 20.0, 20.0]],
            }
        ]

        with patch("_selector_shadow_backfill.TransparentLiveFamilyPool", FakeLivePool):
            backfill_selector_shadow_rows(
                rows,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                include_local_box=False,
                enable_guarded_decal_identity=True,
                guarded_decal_min_background_frames=2,
                guarded_decal_match_distance_px=16.0,
                guarded_decal_shape_pct=12.0,
                guarded_decal_max_step_px=180.0,
            )

        self.assertEqual(instances[0].kwargs["guarded_decal_min_background_frames"], 2)
        self.assertEqual(instances[0].kwargs["guarded_decal_match_distance_px"], 16.0)
        self.assertEqual(instances[0].kwargs["guarded_decal_shape_pct"], 12.0)
        self.assertEqual(instances[0].kwargs["guarded_decal_max_step_px"], 180.0)

    def test_backfill_can_keep_live_family_points_and_debug(self):
        class FakeLivePool:
            def __init__(self, **kwargs):
                pass

            def update(self, frame_index, *, candidates, gray_frame=None, white_anchor=None):
                return SimpleNamespace(
                    points={
                        "guarded_decal_identity_center_mild_state_mild": (10.0, 20.0),
                    },
                    debug={
                        "guarded_decal_identity": {
                            "accepted": True,
                            "background_ratio": 0.0,
                        },
                    },
                )

        rows = [
            {
                "i": 0,
                "track": [0.0, 0.0],
                "cands": [[0.0, 0.0, 0.9, 20.0, 20.0]],
            }
        ]

        with patch("_selector_shadow_backfill.TransparentLiveFamilyPool", FakeLivePool):
            out = backfill_selector_shadow_rows(
                rows,
                runtime=FakeRuntime("panel_default_center_mild_state_mild"),
                min_frames=1,
                include_local_box=False,
                include_live_family=True,
            )

        self.assertEqual(
            out[0]["live_family"]["points"]["guarded_decal_identity_center_mild_state_mild"],
            [10, 20],
        )
        self.assertTrue(out[0]["live_family"]["debug"]["guarded_decal_identity"]["accepted"])


if __name__ == "__main__":
    unittest.main()
