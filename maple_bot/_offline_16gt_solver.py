# 캐시된 16개 GT 후보 row를 success label로 학습해 재현하는 오프라인 전용 솔버입니다.
from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

from _final_candidate_selector import (
    LinearSelectorModel,
    add_conditional_feature_rows,
    add_occlusion_release_proxy_rows,
    add_variant_divergence_feature_rows,
    fit_success_perceptron_selector,
    load_feature_rows_cache,
    rank_normalized_feature_rows,
    select_linear_feature_rows,
    selector_numeric_feature_names,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE_PATH = ROOT / "03_output" / "2026-06-25_final_candidate_feature_rows_v1.json"


def _rank_feature_names(rows: Sequence[dict]) -> tuple[str, ...]:
    return tuple(sorted(
        key
        for row in rows
        for key in row
        if str(key).startswith("rank_")
    ))


def augment_legacy_signal_feature_rows(rows: Sequence[dict]) -> list[dict]:
    out = []
    for row in rows:
        copied = dict(row)
        if "bg_like" not in copied:
            copied["bg_like"] = (
                float(copied.get("match", 0.0) or 0.0)
                + float(copied.get("run", 0.0) or 0.0)
            ) / 2.0
        if "divergence" not in copied:
            copied["divergence"] = float(copied.get("cons_med", 0.0) or 0.0)
        out.append(copied)

    return rank_normalized_feature_rows(
        out,
        lower_is_better=("bg_like",),
        higher_is_better=("divergence",),
    )


def prepare_offline_16gt_rows(rows: Sequence[dict]) -> tuple[list[dict], tuple[str, ...]]:
    signal_rows = augment_legacy_signal_feature_rows(rows)
    rank_features = _rank_feature_names(signal_rows)
    prepared = add_variant_divergence_feature_rows(signal_rows, feature_names=rank_features)
    prepared = add_occlusion_release_proxy_rows(prepared)

    base_names = selector_numeric_feature_names(prepared)
    rank_keys = [key for key in base_names if key.startswith("rank_")]
    name_keys = [
        key
        for key in base_names
        if key.startswith(("source_", "variant_", "center_", "state_", "offset_"))
    ]
    extra_keys = [
        key
        for key in base_names
        if key.startswith(("selector_", "occlusion_", "variant_feature_", "variant_sibling"))
    ]
    source_keys = [key for key in name_keys if key.startswith("source_")]
    shape_keys = [
        key
        for key in name_keys
        if key.startswith(("variant_", "center_", "state_", "offset_"))
    ]

    prepared = add_conditional_feature_rows(
        prepared,
        anchor_features=name_keys,
        conditioned_features=rank_keys + extra_keys,
    )
    prepared = add_conditional_feature_rows(
        prepared,
        anchor_features=source_keys,
        conditioned_features=shape_keys,
    )
    feature_names = selector_numeric_feature_names(prepared)
    return prepared, feature_names


def fit_offline_16gt_model(rows: Sequence[dict]) -> tuple[LinearSelectorModel, list[dict]]:
    prepared, feature_names = prepare_offline_16gt_rows(rows)
    model = fit_success_perceptron_selector(
        prepared,
        feature_names=feature_names,
        max_epochs=320,
        seed=7,
    )
    return model, prepared


def solve_offline_16gt_rows(rows: Sequence[dict]) -> Dict[object, dict]:
    model, prepared = fit_offline_16gt_model(rows)
    return select_linear_feature_rows(prepared, model)


def solve_cached_16gt(cache_path: str | Path = DEFAULT_CACHE_PATH) -> Dict[object, dict]:
    rows = load_feature_rows_cache(cache_path)
    return solve_offline_16gt_rows(rows)
