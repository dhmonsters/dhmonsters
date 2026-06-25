# 라이브 투명 퍼즐 selector shadow 기록기를 검증합니다.
import json
import unittest

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
