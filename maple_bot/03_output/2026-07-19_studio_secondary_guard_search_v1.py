# 기존 안전 규칙 밖에서 무회귀 보조 관측 규칙을 탐색합니다.
from __future__ import annotations

import argparse
import csv
import itertools
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Condition:
    feature: str
    operator: str
    threshold: float

    def accepts(self, row: dict[str, float]) -> bool:
        value = row[self.feature]
        return value <= self.threshold if self.operator == "le" else value >= self.threshold

    def label(self) -> str:
        symbol = "<=" if self.operator == "le" else ">="
        return f"{self.feature}{symbol}{self.threshold:g}"


@dataclass(frozen=True)
class Result:
    conditions: tuple[Condition, ...]
    delta: int
    improved: int
    regressed: int
    first_half_delta: int
    second_half_delta: int
    run_deltas: tuple[int, ...]


CONDITIONS = {
    "texture_delta": ("le", (-0.01, -0.02, -0.03, -0.04, -0.05)),
    "bg_delta": ("le", (-0.40, -0.30, -0.20, -0.10, 0.0, 0.10)),
    "phase_delta": ("le", (-0.40, -0.30, -0.20, -0.10, 0.0, 0.10)),
    "motion_delta": ("ge", (-0.20, -0.10, 0.0, 0.05, 0.10, 0.20, 0.30, 0.40)),
    "rigid_delta": ("ge", (-0.20, -0.10, 0.0, 0.05, 0.10, 0.20, 0.30, 0.40)),
    "yolo_delta": ("ge", (-0.20, -0.10, 0.0, 0.05, 0.10, 0.20)),
    "merge_delta_low": ("le", (-0.40, -0.20, -0.10, 0.0, 0.10, 0.20)),
    "merge_delta_high": ("ge", (-0.20, -0.10, 0.0, 0.10, 0.20, 0.40)),
    "shift": ("ge", (50.0, 75.0, 100.0, 125.0, 150.0, 200.0)),
}


def _load_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for raw in csv.DictReader(stream):
            merge_delta = float(raw["selected_merge"]) - float(raw["base_merge"])
            rows.append(
                {
                    "run_index": int(raw["run_index"]),
                    "final_ok": int(raw["final_ok"]),
                    "gated_ok": int(raw["gated_ok"]),
                    "gate_selected": int(raw["gate_selected"]),
                    "texture_delta": float(raw["selected_texture"]) - float(raw["base_texture"]),
                    "bg_delta": float(raw["selected_bg"]) - float(raw["base_bg"]),
                    "phase_delta": float(raw["selected_phase"]) - float(raw["base_phase"]),
                    "motion_delta": float(raw["selected_motion"]) - float(raw["base_motion"]),
                    "rigid_delta": float(raw["selected_rigid"]) - float(raw["base_rigid"]),
                    "yolo_delta": float(raw["selected_yolo"]) - float(raw["base_yolo"]),
                    "merge_delta_low": merge_delta,
                    "merge_delta_high": merge_delta,
                    "shift": float(raw["shift"]),
                }
            )
    return rows


def _current_guard(row: dict[str, float]) -> bool:
    return (
        bool(row["gate_selected"])
        and row["texture_delta"] <= -0.06
        and row["shift"] >= 50.0
    )


def _rules():
    features = tuple(CONDITIONS)
    for size in (1, 2, 3):
        for selected_features in itertools.combinations(features, size):
            if "merge_delta_low" in selected_features and "merge_delta_high" in selected_features:
                continue
            grids = [CONDITIONS[feature][1] for feature in selected_features]
            for thresholds in itertools.product(*grids):
                yield tuple(
                    Condition(feature, CONDITIONS[feature][0], threshold)
                    for feature, threshold in zip(selected_features, thresholds)
                )


def _score(rows: list[dict[str, float]], conditions: tuple[Condition, ...]) -> Result:
    baseline = {run_index: 0 for run_index in range(10)}
    scores = {run_index: 0 for run_index in range(10)}
    improved = 0
    regressed = 0
    for row in rows:
        run_index = int(row["run_index"])
        current_selected = _current_guard(row)
        current_ok = int(row["gated_ok"] if current_selected else row["final_ok"])
        secondary_selected = (
            bool(row["gate_selected"])
            and not current_selected
            and all(condition.accepts(row) for condition in conditions)
        )
        chosen_ok = int(row["gated_ok"] if secondary_selected else current_ok)
        baseline[run_index] += current_ok
        scores[run_index] += chosen_ok
        improved += int(chosen_ok and not current_ok)
        regressed += int(current_ok and not chosen_ok)
    run_deltas = tuple(scores[index] - baseline[index] for index in range(10))
    return Result(
        conditions=conditions,
        delta=sum(run_deltas),
        improved=improved,
        regressed=regressed,
        first_half_delta=sum(run_deltas[:5]),
        second_half_delta=sum(run_deltas[5:]),
        run_deltas=run_deltas,
    )


def run(input_path: Path, output_path: Path) -> None:
    rows = _load_rows(input_path)
    results = []
    for conditions in _rules():
        result = _score(rows, conditions)
        if (
            result.regressed == 0
            and result.first_half_delta > 0
            and result.second_half_delta > 0
        ):
            results.append(result)
    results.sort(
        key=lambda result: (
            min(result.first_half_delta, result.second_half_delta),
            result.delta,
            -len(result.conditions),
        ),
        reverse=True,
    )
    current_total = sum(
        int(row["gated_ok"] if _current_guard(row) else row["final_ok"])
        for row in rows
    )
    lines = [
        "# Studio secondary observation guard search",
        "",
        "- GT is used only for post-run scoring.",
        f"- current safe total: {current_total}/{len(rows)}",
        "- accepted rules have zero frame regressions and improve both five-run halves.",
        "",
        "|rule|delta|first half|second half|improved|run delta|",
        "|---|---:|---:|---:|---:|---|",
    ]
    for result in results[:30]:
        label = " & ".join(condition.label() for condition in result.conditions)
        run_delta = ",".join(f"{value:+d}" for value in result.run_deltas)
        lines.append(
            f"|{label}|{result.delta:+d}|{result.first_half_delta:+d}|"
            f"{result.second_half_delta:+d}|{result.improved}|{run_delta}|"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output_path)
    print(f"rows={len(rows)} current={current_total} robust={len(results)}")
    if results:
        best = results[0]
        print(" & ".join(condition.label() for condition in best.conditions))
        print(
            f"delta={best.delta:+d} first={best.first_half_delta:+d} "
            f"second={best.second_half_delta:+d} runs={best.run_deltas}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
