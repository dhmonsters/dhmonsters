# 라이브 투명 퍼즐 selector shadow 기록기를 검증합니다.
import json
import unittest
from unittest.mock import patch

from core.vision.transparent_selector_shadow import TransparentSelectorShadow


class FakeRuntime:
    def __init__(self, selected_family=None, selected_point=None):
        self.available = True
        self.load_error = ""
        self.selected_family = selected_family
        self.selected_point = selected_point
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
        if self.selected_point is not None:
            row["point"] = list(self.selected_point)
            row["rescue_point"] = list(self.selected_point)
        return {clip: row}, [row]


class TransparentSelectorShadowTests(unittest.TestCase):
    def test_shadow_median_handles_even_value_count(self):
        self.assertEqual(TransparentSelectorShadow._median([10.0, 30.0]), 20.0)

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

    def test_shadow_uses_runtime_point_for_augmented_family(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at2_state_mild",
            selected_point=(120.25, 100.75),
        )
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
                "raw_candidate_cont2_box_rel_p1_p05_state_mild": (10.0, 10.0),
                "raw_candidate_cont2_box_rel_n05_z0_state_mild": (100.0, 100.0),
            },
        )
        result = shadow.update(
            1,
            candidates=[(20.0, 10.0, 0.9, 20.0, 20.0)],
            anchors={
                "raw_candidate_cont2_box_rel_p1_p05_state_mild": (20.0, 10.0),
                "raw_candidate_cont2_box_rel_n05_z0_state_mild": (120.25, 100.75),
            },
        )

        self.assertEqual(result["point"], [120, 101])
        self.assertEqual(result["rescue_point"], [120.25, 100.75])

    def test_shadow_holds_cont12_after_cont2_switch_then_blocks_cont2_return(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at10_state_mild", (100.0, 100.0)),
                    ("raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at11_state_mild", (110.0, 110.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (200.0, 200.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (210.0, 210.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (220.0, 220.0)),
                    ("raw_candidate_cont2_box_rel_p05_z0_state_mild", (999.0, 999.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=8,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        for frame in range(6):
            result = shadow.update(
                frame,
                candidates=[(10.0 + frame, 10.0, 0.9, 20.0, 20.0)],
                anchors={
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (200.0 + frame * 10.0, 200.0 + frame * 10.0),
                    "raw_candidate_cont2_box_rel_p05_z0_state_mild": (900.0 + frame, 900.0 + frame),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont12_box_rel_p05_z0_state_mild")
        self.assertEqual(result["point"], [250, 250])
        self.assertEqual(result["rescue_point"], [250.0, 250.0])

    def test_shadow_does_not_hold_stale_cont12_without_prior_cont2_switch(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (200.0, 200.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (210.0, 210.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (220.0, 220.0)),
                    ("raw_candidate_cont2_box_rel_p05_z0_state_mild", (999.0, 999.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=8,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        for frame in range(4):
            result = shadow.update(
                frame,
                candidates=[(10.0 + frame, 10.0, 0.9, 20.0, 20.0)],
                anchors={
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (200.0 + frame * 10.0, 200.0 + frame * 10.0),
                    "raw_candidate_cont2_box_rel_p05_z0_state_mild": (900.0 + frame, 900.0 + frame),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont2_box_rel_p05_z0_state_mild")
        self.assertEqual(result["point"], [999, 999])

    def test_shadow_rescues_far_cont2_to_tight_cont11_cluster(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state",
            selected_point=(500.0, 500.0),
        )
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
            candidates=[(200.0, 200.0, 0.9, 100.0, 100.0)],
            anchors={
                "raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state": (500.0, 500.0),
                "raw_candidate_cont11_center_mild_state_mild": (200.0, 200.0),
                "raw_candidate_cont11_box_projected_state_mild": (202.0, 198.0),
                "raw_candidate_cont11_box_rel_n05_z0_state_mild": (184.0, 201.0),
                "raw_candidate_cont11_box_rel_p05_z0_state_mild": (216.0, 199.0),
                "raw_candidate_cont11_box_rel_z0_p05_state_mild": (201.0, 222.0),
            },
        )

        self.assertEqual(result["family"], "raw_candidate_cont11_center_mild_state_mild")
        self.assertEqual(result["point"], [200, 200])
        self.assertEqual(result["rescue_point"], [200.0, 200.0])

    def test_shadow_keeps_selected_family_when_cont11_cluster_is_not_far(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont0_center_mild_state_mild",
            selected_point=(220.0, 210.0),
        )
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
            candidates=[(200.0, 200.0, 0.9, 100.0, 100.0)],
            anchors={
                "raw_candidate_cont0_center_mild_state_mild": (220.0, 210.0),
                "raw_candidate_cont11_center_mild_state_mild": (200.0, 200.0),
                "raw_candidate_cont11_box_projected_state_mild": (202.0, 198.0),
                "raw_candidate_cont11_box_rel_n05_z0_state_mild": (184.0, 201.0),
                "raw_candidate_cont11_box_rel_p05_z0_state_mild": (216.0, 199.0),
            },
        )

        self.assertEqual(result["family"], "raw_candidate_cont0_center_mild_state_mild")
        self.assertEqual(result["point"], [220, 210])

    def test_shadow_does_not_rescue_far_cont0_without_prior_cont11_identity(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont0_center_mild_state_mild",
            selected_point=(500.0, 500.0),
        )
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
            candidates=[(200.0, 200.0, 0.9, 100.0, 100.0)],
            anchors={
                "raw_candidate_cont0_center_mild_state_mild": (500.0, 500.0),
                "raw_candidate_cont11_center_mild_state_mild": (200.0, 200.0),
                "raw_candidate_cont11_box_projected_state_mild": (202.0, 198.0),
                "raw_candidate_cont11_box_rel_n05_z0_state_mild": (184.0, 201.0),
                "raw_candidate_cont11_box_rel_p05_z0_state_mild": (216.0, 199.0),
            },
        )

        self.assertEqual(result["family"], "raw_candidate_cont0_center_mild_state_mild")
        self.assertEqual(result["point"], [500, 500])

    def test_shadow_does_not_rescue_cont2_switch_to_cont11_cluster(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at4212_state_mild",
            selected_point=(500.0, 500.0),
        )
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
            candidates=[(200.0, 200.0, 0.9, 100.0, 100.0)],
            anchors={
                "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at4212_state_mild": (500.0, 500.0),
                "raw_candidate_cont11_center_mild_state_mild": (200.0, 200.0),
                "raw_candidate_cont11_box_projected_state_mild": (202.0, 198.0),
                "raw_candidate_cont11_box_rel_n05_z0_state_mild": (184.0, 201.0),
                "raw_candidate_cont11_box_rel_p05_z0_state_mild": (216.0, 199.0),
            },
        )

        self.assertEqual(result["family"], "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at4212_state_mild")
        self.assertEqual(result["point"], [500, 500])

    def test_shadow_does_not_restart_cont11_rescue_after_motion_release(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_motion_release", (450.0, 420.0)),
                    ("raw_candidate_motion_release", (470.0, 418.0)),
                    ("raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state", (595.0, 439.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=6,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        for frame in range(3):
            result = shadow.update(
                frame,
                candidates=[(595.0, 439.0, 0.8, 120.0, 100.0)],
                anchors={
                    "raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state": (595.0, 439.0),
                    "raw_candidate_cont11_center_mild_state_mild": (262.0, 426.0),
                    "raw_candidate_cont11_box_projected_state_mild": (260.0, 424.0),
                    "raw_candidate_cont11_box_rel_n05_z0_state_mild": (246.0, 426.0),
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild": (278.0, 426.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state")
        self.assertEqual(result["point"], [595, 439])

    def test_shadow_rescues_cont11_to_balanced_when_strict_agrees(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont11_center_mild_state_mild",
            selected_point=(450.0, 430.0),
        )
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
            candidates=[(420.0, 300.0, 0.8, 100.0, 100.0)],
            anchors={
                "raw_candidate_cont11_center_mild_state_mild": (450.0, 430.0),
                "balanced_viterbi_center_mild_state_mild": (420.0, 300.0),
                "strict_transition_viterbi_center_mild_state_mild": (423.0, 304.0),
            },
        )

        self.assertEqual(result["family"], "balanced_viterbi_center_mild_state_mild")
        self.assertEqual(result["point"], [420, 300])
        self.assertEqual(result["rescue_point"], [420.0, 300.0])

    def test_shadow_does_not_rescue_cont11_to_balanced_when_strict_stays_with_cont11(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont11_center_mild_state_mild",
            selected_point=(200.0, 220.0),
        )
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
            candidates=[(300.0, 320.0, 0.8, 100.0, 100.0)],
            anchors={
                "raw_candidate_cont11_center_mild_state_mild": (200.0, 220.0),
                "balanced_viterbi_center_mild_state_mild": (300.0, 320.0),
                "strict_transition_viterbi_center_mild_state_mild": (202.0, 218.0),
            },
        )

        self.assertEqual(result["family"], "raw_candidate_cont11_center_mild_state_mild")
        self.assertEqual(result["point"], [200, 220])

    def test_shadow_continues_balanced_rescue_when_motion_stays_consistent(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_center_mild_state_mild", (450.0, 430.0)),
                    ("raw_candidate_cont11_center_mild_state_mild", (440.0, 432.0)),
                    ("raw_candidate_cont11_center_mild_state_mild", (430.0, 431.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=6,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        balanced_points = [(420.0, 300.0), (435.0, 304.0), (451.0, 307.0)]
        strict_points = [(421.0, 301.0), (510.0, 420.0), (515.0, 424.0)]
        for frame in range(3):
            result = shadow.update(
                frame,
                candidates=[(*balanced_points[frame], 0.8, 100.0, 100.0)],
                anchors={
                    "raw_candidate_cont11_center_mild_state_mild": (450.0 - frame * 10.0, 430.0),
                    "balanced_viterbi_center_mild_state_mild": balanced_points[frame],
                    "strict_transition_viterbi_center_mild_state_mild": strict_points[frame],
                },
            )

        self.assertEqual(result["family"], "balanced_viterbi_center_mild_state_mild")
        self.assertEqual(result["point"], [451, 307])
        self.assertEqual(result["rescue_point"], [451.0, 307.0])

    def test_shadow_keeps_balanced_identity_when_runtime_switches_to_cont0(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_center_mild_state_mild", (450.0, 430.0)),
                    ("raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at7719_state_mild", (259.0, 196.0)),
                    ("raw_candidate_cont0_center_mild_state_mild", (124.0, 174.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=6,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        balanced_points = [(423.0, 307.0), (436.0, 308.0), (448.0, 301.0)]
        strict_points = [(423.0, 307.0), (259.0, 196.0), (239.0, 188.0)]
        for frame in range(3):
            result = shadow.update(
                frame,
                candidates=[(*balanced_points[frame], 0.8, 100.0, 100.0)],
                anchors={
                    "raw_candidate_cont11_center_mild_state_mild": (450.0 - frame * 10.0, 430.0),
                    "balanced_viterbi_center_mild_state_mild": balanced_points[frame],
                    "strict_transition_viterbi_center_mild_state_mild": strict_points[frame],
                },
            )

        self.assertEqual(result["family"], "balanced_viterbi_center_mild_state_mild")
        self.assertEqual(result["point"], [448, 301])
        self.assertEqual(result["rescue_point"], [448.0, 301.0])

    def test_shadow_keeps_cont11_identity_when_runtime_switches_to_cont12(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (238.0, 334.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (567.0, 430.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (549.0, 431.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=6,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        cont11_centers = [(207.0, 334.0), (192.0, 386.0), (191.0, 389.0)]
        for frame in range(3):
            center = cont11_centers[frame]
            result = shadow.update(
                frame,
                candidates=[(*center, 0.8, 120.0, 118.0)],
                anchors={
                    "raw_candidate_cont11_center_mild_state_mild": center,
                    "raw_candidate_cont11_box_projected_state_mild": (center[0] + 2.0, center[1] + 2.0),
                    "raw_candidate_cont11_box_rel_n05_z0_state_mild": (center[0] - 12.0, center[1]),
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild": (center[0] + 14.0, center[1]),
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (567.0 - frame * 18.0, 430.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont11_center_mild_state_mild")
        self.assertEqual(result["point"], [191, 389])
        self.assertEqual(result["rescue_point"], [191.0, 389.0])

    def test_shadow_does_not_block_cont12_after_cont2_switch(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at4212_state_mild", (301.0, 245.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (273.0, 362.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=4,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        for frame in range(2):
            result = shadow.update(
                frame,
                candidates=[(273.0, 362.0, 0.8, 120.0, 118.0)],
                anchors={
                    "raw_candidate_cont11_center_mild_state_mild": (120.0, 120.0),
                    "raw_candidate_cont11_box_projected_state_mild": (122.0, 121.0),
                    "raw_candidate_cont11_box_rel_n05_z0_state_mild": (108.0, 120.0),
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild": (134.0, 120.0),
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (273.0, 362.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont12_box_rel_p05_z0_state_mild")
        self.assertEqual(result["point"], [273, 362])

    def test_shadow_prefers_motion_release_over_cont11_hold_for_right_split(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (397.0, 417.0)),
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (392.0, 424.0)),
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (377.0, 424.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (382.0, 230.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=8,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        cont11_points = [(397.0, 417.0), (392.0, 424.0), (377.0, 424.0), (300.0, 300.0)]
        for frame in range(4):
            center = cont11_points[frame]
            result = shadow.update(
                frame,
                candidates=[
                    (447.0, 418.0, 0.9, 100.0, 100.0),
                    (382.0, 230.0, 0.8, 100.0, 100.0),
                ],
                anchors={
                    "raw_candidate_cont11_center_mild_state_mild": center,
                    "raw_candidate_cont11_box_projected_state_mild": (center[0] + 2.0, center[1]),
                    "raw_candidate_cont11_box_rel_n05_z0_state_mild": (center[0] - 12.0, center[1]),
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild": (center[0] + 14.0, center[1]),
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (382.0, 230.0),
                    "balanced_viterbi_center_mild_state_mild": (447.0, 418.0),
                    "strict_transition_viterbi_center_mild_state_mild": (447.0, 418.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_motion_release")
        self.assertEqual(result["point"], [447, 418])
        self.assertEqual(result["rescue_point"], [447.0, 418.0])

    def test_shadow_rescues_to_raw_cont_center_when_strict_agrees(self):
        runtime = FakeRuntime(
            selected_family="raw_candidate_cont0_center_mild_state_mild",
            selected_point=(363.0, 221.0),
        )
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
            candidates=[(217.0, 133.0, 0.8, 120.0, 118.0)],
            anchors={
                "raw_candidate_cont10_center_mild_state_mild": (217.0, 133.0),
                "raw_candidate_cont10_box_projected_state_mild": (219.0, 134.0),
                "raw_candidate_cont10_box_rel_n05_z0_state_mild": (205.0, 133.0),
                "raw_candidate_cont10_box_rel_p05_z0_state_mild": (245.0, 133.0),
                "strict_transition_viterbi_center_mild_state_mild": (217.0, 133.0),
            },
        )

        self.assertEqual(result["family"], "raw_candidate_cont10_center_mild_state_mild")
        self.assertEqual(result["point"], [217, 133])

    def test_shadow_continues_raw_cont_center_when_strict_drifts(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont0_center_mild_state_mild", (363.0, 221.0)),
                    ("raw_candidate_cont0_center_mild_state_mild", (358.0, 209.0)),
                    ("raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at17033_state_mild", (406.0, 108.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=6,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        centers = [(217.0, 133.0), (208.0, 127.0), (198.0, 123.0)]
        strict_points = [(217.0, 133.0), (208.0, 127.0), (248.0, 38.0)]
        result = None
        for frame in range(3):
            center = centers[frame]
            result = shadow.update(
                frame,
                candidates=[(*center, 0.8, 120.0, 118.0)],
                anchors={
                    "raw_candidate_cont10_center_mild_state_mild": center,
                    "raw_candidate_cont10_box_projected_state_mild": (center[0] + 2.0, center[1]),
                    "raw_candidate_cont10_box_rel_n05_z0_state_mild": (center[0] - 12.0, center[1]),
                    "raw_candidate_cont10_box_rel_p05_z0_state_mild": (center[0] + 28.0, center[1]),
                    "strict_transition_viterbi_center_mild_state_mild": strict_points[frame],
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont10_center_mild_state_mild")
        self.assertEqual(result["point"], [198, 123])

    def test_shadow_does_not_start_raw_cont_center_over_cont11_identity(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_center_mild_state_mild", (203.0, 412.0)),
                    ("raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at17033_state_mild", (406.0, 108.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=4,
            min_frames=1,
            emit_every=1,
            include_local_box=False,
        )
        result = None
        for frame in range(2):
            result = shadow.update(
                frame,
                candidates=[(139.0, 340.0, 0.8, 120.0, 118.0)],
                anchors={
                    "raw_candidate_cont10_center_mild_state_mild": (139.0, 340.0),
                    "raw_candidate_cont10_box_projected_state_mild": (141.0, 340.0),
                    "raw_candidate_cont10_box_rel_n05_z0_state_mild": (127.0, 340.0),
                    "raw_candidate_cont10_box_rel_p05_z0_state_mild": (167.0, 340.0),
                    "raw_candidate_cont11_center_mild_state_mild": (203.0, 412.0),
                    "raw_candidate_cont11_box_projected_state_mild": (205.0, 412.0),
                    "raw_candidate_cont11_box_rel_n05_z0_state_mild": (191.0, 412.0),
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild": (231.0, 412.0),
                    "strict_transition_viterbi_center_mild_state_mild": (139.0, 340.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_cont11_center_mild_state_mild")
        self.assertEqual(result["point"], [203, 412])

    def test_shadow_releases_cont12_jump_to_motion_near_raw_candidate(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (397.0, 417.0)),
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (392.0, 424.0)),
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (377.0, 424.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (382.0, 230.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=8,
            min_frames=1,
            emit_every=1,
            max_candidates=1,
            include_local_box=False,
        )
        result = None
        for frame in range(4):
            candidates = [(320.0, 230.0, 0.9, 120.0, 120.0)]
            if frame == 3:
                candidates.extend([
                    (342.0, 426.0, 0.7, 110.0, 100.0),
                    (447.0, 418.0, 0.4, 110.0, 100.0),
                ])
            result = shadow.update(
                frame,
                candidates=candidates,
                anchors={
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state": (397.0 - frame * 10.0, 417.0 + frame * 3.0),
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (320.0, 230.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_motion_release")
        self.assertEqual(result["point"], [447, 418])
        self.assertEqual(result["rescue_point"], [447.0, 418.0])

    def test_shadow_coasts_motion_release_when_cont12_reappears_without_near_raw_candidate(self):
        class _SequenceRuntime:
            available = True
            load_error = ""

            def __init__(self):
                self.rows = [
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (397.0, 417.0)),
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (392.0, 424.0)),
                    ("raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state", (377.0, 424.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (382.0, 230.0)),
                    ("raw_candidate_cont12_box_rel_p05_z0_state_mild", (378.0, 224.0)),
                ]
                self.index = 0

            def select_from_path_pool(self, clip, _paths, _frames, **_kwargs):
                family, point = self.rows[min(self.index, len(self.rows) - 1)]
                self.index += 1
                row = {
                    "clip": clip,
                    "family": family,
                    "point": list(point),
                    "rescue_point": list(point),
                    "rank_center": 0.0,
                    "rank_rough": 0.0,
                }
                return {clip: row}, [row]

        shadow = TransparentSelectorShadow(
            _SequenceRuntime(),
            clip_id="live",
            window=8,
            min_frames=1,
            emit_every=1,
            max_candidates=1,
            include_local_box=False,
        )
        result = None
        for frame in range(5):
            candidates = [(320.0, 230.0, 0.9, 120.0, 120.0)]
            if frame == 3:
                candidates.extend([
                    (342.0, 426.0, 0.7, 110.0, 100.0),
                    (447.0, 418.0, 0.4, 110.0, 100.0),
                ])
            if frame == 4:
                candidates.append((482.0, 320.0, 0.8, 110.0, 100.0))
            result = shadow.update(
                frame,
                candidates=candidates,
                anchors={
                    "raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state": (397.0 - frame * 10.0, 417.0 + frame * 3.0),
                    "raw_candidate_cont12_box_rel_p05_z0_state_mild": (320.0, 230.0),
                },
            )

        self.assertEqual(result["family"], "raw_candidate_motion_release")
        self.assertEqual(result["point"], [464, 418])
        self.assertAlmostEqual(result["rescue_point"][0], 463.6666666666667)
        self.assertAlmostEqual(result["rescue_point"][1], 418.3333333333333)

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
