import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase_catalog_score",
    ROOT / "_phase_catalog_score.py",
)
phase_catalog_score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(phase_catalog_score)


class PhaseCatalogSolverTests(unittest.TestCase):
    def test_stable_prep_end_ignores_late_isolated_big_white(self):
        prep_end = phase_catalog_score.stable_prep_end_from_big_frames(
            list(range(58)) + [128],
            min_run=20,
            max_gap=2,
        )

        self.assertEqual(prep_end, 58)

    def test_stable_prep_end_uses_initial_white_center_stability(self):
        centers = [(i, 100.0, 100.0) for i in range(20)]
        centers.extend((i, 100.0 + (i - 19) * 10.0, 100.0) for i in range(20, 30))

        prep_end = phase_catalog_score.stable_prep_end_from_white_centers(
            centers,
            run_end=40,
            center_tol=30.0,
            min_seed=20,
        )

        self.assertEqual(prep_end, 23)

    def test_estimate_period_lag_does_not_trust_prep_end(self):
        csets = [
            [(0.0, 0.0, 10.0, 10.0, 0.9), (100.0, 0.0, 10.0, 10.0, 0.9)],
            [(10.0, 0.0, 10.0, 10.0, 0.9), (110.0, 0.0, 10.0, 10.0, 0.9)],
            [(20.0, 0.0, 10.0, 10.0, 0.9), (120.0, 0.0, 10.0, 10.0, 0.9)],
            [(0.0, 0.0, 10.0, 10.0, 0.9), (100.0, 0.0, 10.0, 10.0, 0.9)],
            [(10.0, 0.0, 10.0, 10.0, 0.9), (110.0, 0.0, 10.0, 10.0, 0.9)],
            [(20.0, 0.0, 10.0, 10.0, 0.9), (120.0, 0.0, 10.0, 10.0, 0.9)],
        ]

        lag, score = phase_catalog_score.estimate_period_lag(
            csets,
            prep_end=5,
            min_lag=2,
            max_lag=5,
        )

        self.assertEqual(lag, 3)
        self.assertEqual(score, 0.0)

    def test_explain_background_leaves_unexplained_target_candidate(self):
        expected_background = [
            (10.0, 10.0, 20.0, 20.0, 0.9),
            (100.0, 100.0, 20.0, 20.0, 0.9),
        ]
        candidates = [
            (11.0, 10.0, 20.5, 20.0, 0.8),
            (99.0, 101.0, 19.8, 20.3, 0.8),
            (70.0, 55.0, 20.0, 20.0, 0.7),
        ]

        explained, unexplained = phase_catalog_score.explain_background(
            candidates,
            expected_background,
            pos_tol=6.0,
            area_tol_pct=8.0,
            aspect_tol_pct=8.0,
        )

        self.assertEqual(len(explained), 2)
        self.assertEqual(unexplained, [candidates[2]])


if __name__ == "__main__":
    unittest.main()
