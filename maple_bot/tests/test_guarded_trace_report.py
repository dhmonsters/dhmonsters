# guarded path의 worst frame trace 리포트를 검증합니다.
import unittest

from _guarded_trace_report import trace_guarded_worst_rows, write_markdown_report


class GuardedTraceReportTests(unittest.TestCase):
    def test_trace_guarded_worst_rows_includes_candidates_and_steps(self):
        rows = [
            {
                "i": 10,
                "cands": [
                    [0.0, 0.0, 0.9, 20.0, 20.0],
                    [50.0, 0.0, 0.7, 20.0, 20.0],
                ],
                "live_family": {
                    "points": {
                        "guarded_decal_identity_center_mild_state_mild": [0.0, 0.0],
                        "raw_candidate_cont0_center_mild_state_mild": [0.0, 0.0],
                    },
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "accepted",
                            "accepted": True,
                        }
                    },
                },
            },
            {
                "i": 11,
                "cands": [
                    [10.0, 0.0, 0.8, 20.0, 20.0],
                    [180.0, 0.0, 0.6, 20.0, 20.0],
                ],
                "live_family": {
                    "points": {
                        "guarded_decal_identity_center_mild_state_mild": [180.0, 0.0],
                        "raw_candidate_cont0_center_mild_state_mild": [10.0, 0.0],
                        "phase_catalog_live_center_mild_state_mild": [160.0, 0.0],
                    },
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "accepted",
                            "accepted": True,
                            "max_step": 180.0,
                        }
                    },
                },
            },
        ]
        gt = {0: (0.0, 0.0), 1: (10.0, 0.0)}

        trace = trace_guarded_worst_rows(rows, gt, max_items=1, candidates_per_frame=2)

        self.assertEqual(trace[0]["row_index"], 1)
        self.assertEqual(trace[0]["frame"], 11)
        self.assertEqual(trace[0]["error"], 170.0)
        self.assertEqual(trace[0]["step_from_previous"], 180.0)
        self.assertEqual(trace[0]["reason"], "accepted")
        self.assertEqual(trace[0]["nearest_candidates"][0]["point"], [180.0, 0.0])
        self.assertEqual(trace[0]["nearest_candidates"][0]["score_rank"], 1)
        self.assertEqual(trace[0]["nearest_candidates"][1]["dist_to_gt"], 0.0)
        self.assertEqual(trace[0]["gt_nearest_candidates"][0]["score_rank"], 0)
        self.assertTrue(trace[0]["gt_nearest_candidates"][0]["in_live_top8"])
        self.assertEqual(trace[0]["gt_nearest_candidates"][0]["point"], [10.0, 0.0])
        self.assertEqual(trace[0]["gt_nearest_candidates"][1]["dist_to_point"], 0.0)
        self.assertEqual(trace[0]["family_nearest_to_gt"][0]["family"], "raw_candidate_cont0_center_mild_state_mild")
        self.assertEqual(trace[0]["family_nearest_to_gt"][0]["dist_to_gt"], 0.0)
        self.assertEqual(trace[0]["family_nearest_to_selected"][0]["family"], "guarded_decal_identity_center_mild_state_mild")

    def test_write_markdown_report_includes_candidate_distances(self):
        text = write_markdown_report({
            "clip": "sample",
            "config": {
                "min_bg": 2,
                "match_px": 16.0,
                "shape_pct": 6.0,
                "max_step": 180.0,
            },
            "items": [
                {
                    "frame": 11,
                    "row_index": 1,
                    "error": 170.0,
                    "point": [180.0, 0.0],
                    "gt": [10.0, 0.0],
                    "reason": "accepted",
                    "step_from_previous": 180.0,
                    "nearest_candidates": [
                        {"point": [180.0, 0.0], "score": 0.6, "dist_to_point": 0.0, "dist_to_gt": 170.0},
                        {"point": [10.0, 0.0], "score": 0.8, "dist_to_point": 170.0, "dist_to_gt": 0.0, "score_rank": 0, "in_live_top8": True},
                    ],
                    "gt_nearest_candidates": [
                        {"point": [10.0, 0.0], "score": 0.8, "dist_to_point": 170.0, "dist_to_gt": 0.0, "score_rank": 0, "in_live_top8": True},
                    ],
                    "family_nearest_to_gt": [
                        {
                            "family": "raw_candidate_cont0_center_mild_state_mild",
                            "point": [10.0, 0.0],
                            "dist_to_point": 170.0,
                            "dist_to_gt": 0.0,
                        },
                    ],
                    "family_nearest_to_selected": [
                        {
                            "family": "guarded_decal_identity_center_mild_state_mild",
                            "point": [180.0, 0.0],
                            "dist_to_point": 0.0,
                            "dist_to_gt": 170.0,
                        },
                    ],
                }
            ],
        })

        self.assertIn("sample", text)
        self.assertIn("f11", text)
        self.assertIn("err=170.0", text)
        self.assertIn("cand0", text)
        self.assertIn("rank=0", text)
        self.assertIn("live8=True", text)
        self.assertIn("gt_cand0", text)
        self.assertIn("gt_family0 raw_candidate_cont0_center_mild_state_mild", text)
        self.assertIn("sel_family0 guarded_decal_identity_center_mild_state_mild", text)
        self.assertIn("d_gt=0.0", text)


if __name__ == "__main__":
    unittest.main()
