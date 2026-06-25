# GT 없이 family 후보를 고르는 학습 selector입니다.
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Sequence

from _final_candidate_selector import (
    LinearSelectorModel,
    load_feature_rows_cache,
    select_linear_feature_rows,
)
from _offline_16gt_solver import DEFAULT_CACHE_PATH, fit_offline_16gt_model, prepare_offline_16gt_rows


def fit_gt_free_selector(rows: Sequence[dict]) -> LinearSelectorModel:
    model, _prepared = fit_offline_16gt_model(rows)
    return model


def prepare_gt_free_runtime_rows(rows: Sequence[dict]) -> list[dict]:
    prepared, _feature_names = prepare_offline_16gt_rows(rows)
    return prepared


def select_gt_free_family_rows(
    rows: Sequence[dict],
    selector: LinearSelectorModel,
) -> Dict[object, dict]:
    prepared = prepare_gt_free_runtime_rows(rows)
    return select_linear_feature_rows(prepared, selector)


def fit_cached_gt_free_selector(
    cache_path: str | Path = DEFAULT_CACHE_PATH,
) -> LinearSelectorModel:
    return fit_gt_free_selector(load_feature_rows_cache(cache_path))


def save_gt_free_selector_model(path: str | Path, model: LinearSelectorModel) -> Path:
    model_path = Path(path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_names": list(model.feature_names),
        "weights": list(model.weights),
        "mean": list(model.mean),
        "scale": list(model.scale),
    }
    model_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return model_path


def load_gt_free_selector_model(path: str | Path) -> LinearSelectorModel:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return LinearSelectorModel(
        feature_names=tuple(str(value) for value in payload["feature_names"]),
        weights=tuple(float(value) for value in payload["weights"]),
        mean=tuple(float(value) for value in payload["mean"]),
        scale=tuple(float(value) for value in payload["scale"]),
    )


def select_cached_rows_without_gt(
    cache_path: str | Path = DEFAULT_CACHE_PATH,
) -> Dict[object, dict]:
    rows = load_feature_rows_cache(cache_path)
    selector = fit_gt_free_selector(rows)
    runtime_rows = [
        {
            key: value
            for key, value in row.items()
            if key not in {"success", "mean", "max", "coverage"}
        }
        for row in rows
    ]
    return select_gt_free_family_rows(runtime_rows, selector)
