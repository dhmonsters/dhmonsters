# 라이브 투명 퍼즐 selector shadow 기록기를 검증합니다.
import json
import unittest
from unittest.mock import patch

from core.vision.transparent_selector_shadow import TransparentSelectorShadow


class FakeRuntime:
    def __init__(self, selected_family=None):
        self.available = True
        self.load_error = ""
        self.selected_family = selected_family
        self.calls = []

    def select_from_path_pool(self, clip, paths, frames, **kwargs):
        self.calls.append({
            "clip": clip,
            "paths": paths,
            "frames": frames,
            "kwargs": kwargs,
        })
        family = self.selected_family or sorted(paths)[0]
        row = {
            "clip": clip,
            "family": family,
            "rank_center": 0.0,
            "rank_rough": 0.0,
        }
        return {clip: row}, [row]


class TransparentSelectorShadowTests(unittest.TestCase):
    def test_shadow_builds_local_box_path_pool_from_live_anchors(self):
        runtime = FakeRuntime()
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=4,
            min_frames=3,
            emit_every=1,
        )

        for frame in range(3):
            result = shadow.update(
                frame,
                candidates=[
                    (10.0 + frame, 20.0, 0.9, 30.0, 30.0),
                    (100.0, 100.0, 0.1, 20.0, 20.0),
                ],
                anchors={
                    "panel_default_center_mild_state_mild": (10.0 + frame, 20.0),
                },
            )

        call = runtime.calls[-1]
        self.assertIsNotNone(result)
        self.assertEqual(call["frames"], [0, 1, 2])
        self.assertIn("panel_default_center_mild_state_mild", call["paths"])
        self.assertTrue(any(name.endswith("_lb_free") for name in call["paths"]))
        self.assertEqual(call["kwargs"]["candidate_sets"][2][0][0], 12.0)
        self.assertEqual(result["clip"], "live")

    def test_shadow_forwards_expected_background_to_runtime(self):
        runtime = FakeRuntime()
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=3,
            min_frames=2,
            emit_every=1,
            include_local_box=False,
        )

        shadow.update(
            0,
            candidates=[(10.0, 20.0, 0.9, 30.0, 30.0)],
            anchors={
                "panel_default_center_mild_state_mild": (10.0, 20.0),
            },
            expected_by_frame={0: [(7, (100.0, 200.0, 0.8, 20.0, 20.0))]},
        )
        shadow.update(
            1,
            candidates=[(11.0, 20.0, 0.9, 30.0, 30.0)],
            anchors={
                "panel_default_center_mild_state_mild": (11.0, 20.0),
            },
            expected_by_frame={1: [(8, (101.0, 201.0, 0.8, 20.0, 20.0))]},
        )

        expected = runtime.calls[-1]["kwargs"]["expected_by_frame"]
        self.assertEqual(expected[0][0][0], 7)
        self.assertEqual(expected[1][0][0], 8)

    def test_shadow_converts_candidate_order_for_local_box_paths(self):
        runtime = FakeRuntime(selected_family="panel_default_center_mild_state_mild")
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
        )
        captured = {}

        def fake_augment(paths, candidate_sets, frames, **kwargs):
            captured["candidate"] = candidate_sets[0][0]
            return dict(paths)

        with patch(
            "core.vision.transparent_selector_shadow.local_box.augment_local_box_paths",
            side_effect=fake_augment,
        ):
            shadow.update(
                0,
                candidates=[(10.0, 20.0, 0.9, 30.0, 40.0)],
                anchors={
                    "panel_default_center_mild_state_mild": (10.0, 20.0),
                },
            )

        self.assertEqual(captured["candidate"], (10.0, 20.0, 30.0, 40.0, 0.9))

    def test_shadow_result_is_json_serializable_and_contains_selected_point(self):
        runtime = FakeRuntime(selected_family="panel_default_center_mild_state_mild")
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=4,
            min_frames=3,
            emit_every=1,
        )

        result = None
        for frame in range(3):
            result = shadow.update(
                frame,
                candidates=[(30.0 + frame, 40.0, 0.9, 30.0, 30.0)],
                anchors={
                    "panel_default_center_mild_state_mild": (30.0 + frame, 40.0),
                },
            )

        encoded = json.dumps(result, ensure_ascii=False)

        self.assertIn("panel_default_center_mild_state_mild", encoded)
        self.assertEqual(result["point"], [32, 40])
        self.assertEqual(result["rows"], 1)

    def test_shadow_result_exposes_float_rescue_point_for_live_health_selector(self):
        runtime = FakeRuntime(selected_family="panel_default_center_mild_state_mild")
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=3,
            min_frames=2,
            emit_every=1,
            include_local_box=False,
        )

        shadow.update(
            0,
            candidates=[(10.0, 10.0, 0.9, 20.0, 20.0)],
            anchors={
                "panel_default_center_mild_state_mild": (10.25, 10.75),
            },
        )
        result = shadow.update(
            1,
            candidates=[(11.0, 10.0, 0.9, 20.0, 20.0)],
            anchors={
                "panel_default_center_mild_state_mild": (11.25, 10.75),
            },
        )

        self.assertEqual(result["point"], [11, 11])
        self.assertEqual(result["rescue_point"], [11.25, 10.75])

    def test_shadow_rescue_requires_bg_split_family_and_merge_context(self):
        panel_runtime = FakeRuntime(selected_family="panel_default_center_mild_state_mild")
        split_runtime = FakeRuntime(selected_family="bg_split_viterbi_center_mild_state_mild")
        panel_shadow = TransparentSelectorShadow(
            panel_runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        split_shadow = TransparentSelectorShadow(
            split_runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )

        anchors = {
            "panel_default_center_mild_state_mild": (10.0, 10.0),
            "bg_split_viterbi_center_mild_state_mild": (12.0, 10.0),
        }
        normal_candidates = [(10.0, 10.0, 0.9, 20.0, 20.0)]
        merged_candidates = [
            (10.0, 10.0, 0.9, 20.0, 20.0),
            (12.0, 10.0, 0.8, 180.0, 120.0),
        ]

        panel_result = panel_shadow.update(0, candidates=merged_candidates, anchors=anchors)
        split_blocked = split_shadow.update(0, candidates=normal_candidates, anchors=anchors)
        split_allowed = split_shadow.update(1, candidates=merged_candidates, anchors=anchors)

        self.assertFalse(panel_result["rescue_allowed"])
        self.assertFalse(split_blocked["rescue_allowed"])
        self.assertEqual(split_blocked["merge_context"]["frames"], 0)
        self.assertTrue(split_allowed["rescue_allowed"])
        self.assertEqual(split_allowed["merge_context"]["frames"], 1)

    def test_shadow_rescue_allows_merge_context_family_only_when_merge_gate_is_open(self):
        runtime = FakeRuntime(selected_family="merge_context_center_mild_state_mild")
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        anchors = {
            "merge_context_center_mild_state_mild": (12.0, 10.0),
        }

        blocked = shadow.update(
            0,
            candidates=[(12.0, 10.0, 0.8, 70.0, 50.0)],
            anchors=anchors,
        )
        allowed = shadow.update(
            1,
            candidates=[(12.0, 10.0, 0.8, 180.0, 120.0)],
            anchors=anchors,
        )

        self.assertFalse(blocked["rescue_allowed"])
        self.assertEqual(blocked["merge_context"]["frames"], 0)
        self.assertTrue(allowed["rescue_allowed"])
        self.assertEqual(allowed["merge_context"]["frames"], 1)

    def test_shadow_rescue_allows_guarded_decal_identity_without_merge_gate(self):
        family = "guarded_decal_identity_center_mild_state_mild"
        runtime = FakeRuntime(selected_family=family)
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )

        result = shadow.update(
            0,
            candidates=[(40.0, 10.0, 0.8, 20.0, 20.0)],
            anchors={family: (40.0, 10.0)},
        )

        self.assertTrue(result["rescue_allowed"])
        self.assertEqual(result["family"], family)
        self.assertEqual(runtime.calls[-1]["kwargs"]["meta"][family]["source"], "guarded_decal_identity")

    def test_shadow_rescue_allows_guarded_decal_consensus_without_merge_gate(self):
        family = "guarded_decal_identity_consensus_center_mild_state_mild"
        runtime = FakeRuntime(selected_family=family)
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )

        result = shadow.update(
            0,
            candidates=[(40.0, 10.0, 0.8, 20.0, 20.0)],
            anchors={family: (40.0, 10.0)},
        )

        self.assertTrue(result["rescue_allowed"])
        self.assertEqual(result["family"], family)
        self.assertEqual(runtime.calls[-1]["kwargs"]["meta"][family]["source"], "guarded_decal_identity")

    def test_shadow_exposes_guarded_consensus_rescue_even_when_model_selects_raw(self):
        selected_family = "raw_candidate_beam10_center_mild_state_mild"
        consensus_family = "guarded_decal_identity_consensus_center_mild_state_mild"
        runtime = FakeRuntime(selected_family=selected_family)
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=2,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )

        result = shadow.update(
            0,
            candidates=[(200.0, 10.0, 0.8, 20.0, 20.0)],
            anchors={
                selected_family: (200.0, 10.0),
                consensus_family: (40.25, 10.75),
            },
        )

        self.assertEqual(result["family"], selected_family)
        self.assertFalse(result["rescue_allowed"])
        self.assertEqual(result["rescue_point"], [200.0, 10.0])
        self.assertTrue(result["consensus_rescue_allowed"])
        self.assertEqual(result["consensus_rescue_family"], consensus_family)
        self.assertEqual(result["consensus_rescue_point"], [40.25, 10.75])

    def test_default_merge_gate_uses_wjsonl_sized_thresholds(self):
        runtime = FakeRuntime(selected_family="bg_split_viterbi_center_mild_state_mild")
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=3,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        anchors = {
            "bg_split_viterbi_center_mild_state_mild": (12.0, 10.0),
        }

        blocked = shadow.update(
            0,
            candidates=[
                (10.0, 10.0, 0.9, 60.0, 60.0),
                (12.0, 10.0, 0.8, 70.0, 50.0),
            ],
            anchors=anchors,
        )
        allowed = shadow.update(
            1,
            candidates=[
                (10.0, 10.0, 0.9, 120.0, 120.0),
                (12.0, 10.0, 0.8, 180.0, 120.0),
            ],
            anchors=anchors,
        )

        self.assertFalse(blocked["rescue_allowed"])
        self.assertEqual(blocked["merge_context"]["frames"], 0)
        self.assertTrue(allowed["rescue_allowed"])
        self.assertEqual(allowed["merge_context"]["frames"], 1)

    def test_shadow_prunes_old_frames_to_window(self):
        runtime = FakeRuntime(selected_family="panel_default_center_mild_state_mild")
        shadow = TransparentSelectorShadow(
            runtime,
            clip_id="live",
            window=3,
            min_frames=2,
            emit_every=1,
            include_local_box=False,
        )

        for frame in range(5):
            shadow.update(
                frame,
                candidates=[(float(frame), 0.0, 0.9, 10.0, 10.0)],
                anchors={
                    "panel_default_center_mild_state_mild": (float(frame), 0.0),
                },
            )

        self.assertEqual(runtime.calls[-1]["frames"], [2, 3, 4])
        self.assertEqual(
            sorted(runtime.calls[-1]["paths"]["panel_default_center_mild_state_mild"]),
            [2, 3, 4],
        )


if __name__ == "__main__":
    unittest.main()
