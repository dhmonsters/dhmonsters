# final selector가 평가할 family 후보 shortlist를 만드는 유틸리티입니다.
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Any, Dict, Iterable, Sequence, Tuple

import numpy as np


Point = Tuple[float, float]

PATTERN_SOURCES = (
    "balanced_viterbi",
    "panel_default",
    "merge_context",
    "strict_transition_viterbi",
    "phase_catalog",
    "bg_split",
)

PATTERN_PARTS = (
    "state_mild_lb_free",
    "state_mild_lb_loose",
    "state_mild_lb_smooth",
    "center_mild_lb_free",
    "center_mild_lb_loose",
    "center_mild_lb_smooth",
    "center_mild_state_mild",
    "center_mild_offset_mild",
    "center_mild_state_medium",
    "center_mild_offset_medium",
    "center_mild_state_aggressive",
    "center_mild_offset_aggressive",
)


def is_pattern_candidate_family(family: str) -> bool:
    name = family.lower()
    return any(name.startswith(source) for source in PATTERN_SOURCES) and any(
        part in name for part in PATTERN_PARTS
    )


def pattern_candidate_families(
    paths: Dict[str, Dict[int, Point]],
) -> Dict[str, Dict[int, Point]]:
    return {
        family: path
        for family, path in paths.items()
        if is_pattern_candidate_family(family)
    }


def family_name_features(family: str, *, source: str | None = None) -> Dict[str, float]:
    name = family.lower()
    source_name = str(source or family).lower()
    return {
        "source_balanced_viterbi": float(source_name.startswith("balanced_viterbi")),
        "source_bg_split": float(source_name.startswith("bg_split")),
        "source_strict_transition": float(source_name.startswith("strict_transition")),
        "source_panel_default": float(source_name.startswith("panel_default")),
        "source_merge_context": float(source_name.startswith("merge_context")),
        "source_phase_catalog": float(source_name.startswith("phase_catalog")),
        "variant_free": float(name.endswith("_lb_free")),
        "variant_loose": float(name.endswith("_lb_loose")),
        "variant_smooth": float(name.endswith("_lb_smooth")),
        "center_mild": float("center_mild" in name),
        "center_medium": float("center_medium" in name),
        "center_aggressive": float("center_aggressive" in name),
        "state_mild": float("state_mild" in name),
        "state_medium": float("state_medium" in name),
        "state_aggressive": float("state_aggressive" in name),
        "offset_mild": float("offset_mild" in name),
        "offset_medium": float("offset_medium" in name),
        "offset_aggressive": float("offset_aggressive" in name),
    }


def _rank_values(values: Sequence[tuple[float, int]]) -> Dict[int, float]:
    if not values:
        return {}
    ordered = sorted(values)
    denom = max(1, len(ordered) - 1)
    return {
        row_index: float(rank) / float(denom)
        for rank, (_value, row_index) in enumerate(ordered)
    }


def rank_normalized_feature_rows(
    rows: Sequence[dict],
    *,
    lower_is_better: Iterable[str] = (),
    higher_is_better: Iterable[str] = (),
    clip_key: str = "clip",
) -> list[dict]:
    out = [dict(row) for row in rows]
    by_clip: dict[object, list[int]] = defaultdict(list)
    for index, row in enumerate(out):
        by_clip[row.get(clip_key)].append(index)

    for indices in by_clip.values():
        for feature in lower_is_better:
            ranks = _rank_values([
                (float(out[index].get(feature, 0.0) or 0.0), index)
                for index in indices
            ])
            for index, rank in ranks.items():
                out[index][f"rank_{feature}"] = rank

        for feature in higher_is_better:
            ranks = _rank_values([
                (-float(out[index].get(feature, 0.0) or 0.0), index)
                for index in indices
            ])
            for index, rank in ranks.items():
                out[index][f"rank_high_{feature}"] = rank

    return out


def select_weighted_feature_rows(
    rows: Sequence[dict],
    weights: Dict[str, float],
    *,
    clip_key: str = "clip",
    family_key: str = "family",
) -> Dict[object, dict]:
    selected: Dict[object, tuple[float, str, dict]] = {}
    for row in rows:
        clip = row.get(clip_key)
        family = str(row.get(family_key, ""))
        cost = sum(
            float(weight) * float(row.get(feature, 0.0) or 0.0)
            for feature, weight in weights.items()
        )
        item = (cost, family, dict(row))
        if clip not in selected or item < selected[clip]:
            selected[clip] = item
    return {
        clip: row
        for clip, (_cost, _family, row) in selected.items()
    }


@dataclass(frozen=True)
class FeatureTable:
    rows: tuple[dict, ...]
    feature_names: tuple[str, ...]
    matrix: np.ndarray
    clip_indices: Dict[object, tuple[int, ...]]


@dataclass(frozen=True)
class LinearSelectorModel:
    feature_names: tuple[str, ...]
    weights: tuple[float, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]


def build_feature_table(
    rows: Sequence[dict],
    feature_names: Sequence[str],
    *,
    clip_key: str = "clip",
) -> FeatureTable:
    copied_rows = tuple(dict(row) for row in rows)
    names = tuple(str(feature) for feature in feature_names)
    matrix = np.asarray(
        [
            [float(row.get(feature, 0.0) or 0.0) for feature in names]
            for row in copied_rows
        ],
        dtype=float,
    )
    grouped: dict[object, list[int]] = defaultdict(list)
    for index, row in enumerate(copied_rows):
        grouped[row.get(clip_key)].append(index)
    return FeatureTable(
        rows=copied_rows,
        feature_names=names,
        matrix=matrix,
        clip_indices={
            clip: tuple(indices)
            for clip, indices in grouped.items()
        },
    )


def select_weighted_feature_table(
    table: FeatureTable,
    weights: Dict[str, float],
    *,
    family_key: str = "family",
) -> Dict[object, dict]:
    weight_vector = np.asarray(
        [float(weights.get(feature, 0.0) or 0.0) for feature in table.feature_names],
        dtype=float,
    )
    costs = table.matrix @ weight_vector
    selected: Dict[object, dict] = {}
    for clip, indices in table.clip_indices.items():
        best = None
        for index in indices:
            item = (float(costs[index]), str(table.rows[index].get(family_key, "")), index)
            if best is None or item < best:
                best = item
        if best is not None:
            selected[clip] = dict(table.rows[best[2]])
    return selected


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def save_feature_rows_cache(path: str | Path, rows: Sequence[dict]) -> Path:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rows": [_json_ready(row) for row in rows],
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return cache_path


def load_feature_rows_cache(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return [dict(row) for row in payload.get("rows", [])]


def summarize_selected_rows(selected: Dict[object, dict]) -> dict:
    rows = list(selected.values())
    total = len(rows)
    means = [float(row.get("mean", 0.0) or 0.0) for row in rows]
    return {
        "success": sum(1 for row in rows if bool(row.get("success", False))),
        "total": total,
        "mean": float(np.mean(means)) if means else float("nan"),
    }


def selector_bank_oracle(
    selector_picks: Dict[str, Dict[object, dict]],
    *,
    score_key: str = "mean",
) -> Dict[object, dict]:
    by_clip: dict[object, list[tuple[float, str, dict]]] = defaultdict(list)
    for selector_name, picks in selector_picks.items():
        for clip, row in picks.items():
            by_clip[clip].append((
                float(row.get(score_key, float("inf"))),
                str(selector_name),
                dict(row),
            ))

    selected: Dict[object, dict] = {}
    for clip, candidates in by_clip.items():
        _score, selector_name, row = min(candidates)
        row["selector_name"] = selector_name
        selected[clip] = row
    return selected


def add_interaction_feature_rows(
    rows: Sequence[dict],
    interactions: Sequence[tuple[str, str]],
) -> list[dict]:
    out = [dict(row) for row in rows]
    for row in out:
        for left, right in interactions:
            row[f"{left}*{right}"] = (
                float(row.get(left, 0.0) or 0.0)
                * float(row.get(right, 0.0) or 0.0)
            )
    return out


def add_selector_provenance_feature_rows(
    rows: Sequence[dict],
    selector_picks: Dict[str, Dict[object, dict]],
    *,
    selector_groups: Dict[str, str] | None = None,
    clip_key: str = "clip",
    family_key: str = "family",
) -> list[dict]:
    vote_counts: dict[tuple[object, str], int] = defaultdict(int)
    group_votes: dict[tuple[object, str], set[str]] = defaultdict(set)
    selector_totals: dict[object, int] = defaultdict(int)
    clip_groups: dict[object, set[str]] = defaultdict(set)

    for selector_name, picks in selector_picks.items():
        group = (
            str(selector_groups[selector_name])
            if selector_groups and selector_name in selector_groups
            else str(selector_name).split("_", 1)[0]
        )
        for clip, row in picks.items():
            family = str(row.get(family_key, ""))
            key = (clip, family)
            vote_counts[key] += 1
            group_votes[key].add(group)
            selector_totals[clip] += 1
            clip_groups[clip].add(group)

    out = [dict(row) for row in rows]
    for row in out:
        clip = row.get(clip_key)
        family = str(row.get(family_key, ""))
        key = (clip, family)
        vote_count = float(vote_counts.get(key, 0))
        group_count = float(len(group_votes.get(key, set())))
        selector_total = float(selector_totals.get(clip, 0))
        group_total = float(len(clip_groups.get(clip, set())))

        row["selector_vote_count"] = vote_count
        row["selector_vote_ratio"] = vote_count / selector_total if selector_total else 0.0
        row["selector_group_count"] = group_count
        row["selector_group_ratio"] = group_count / group_total if group_total else 0.0
    return out


def _local_box_variant_key(family: str) -> str:
    for suffix in ("_lb_free", "_lb_loose", "_lb_smooth"):
        if family.endswith(suffix):
            return family[: -len(suffix)]
    return family


def add_variant_divergence_feature_rows(
    rows: Sequence[dict],
    *,
    feature_names: Sequence[str],
    clip_key: str = "clip",
    family_key: str = "family",
) -> list[dict]:
    out = [dict(row) for row in rows]
    groups: dict[tuple[object, str], list[int]] = defaultdict(list)
    for index, row in enumerate(out):
        family = str(row.get(family_key, ""))
        groups[(row.get(clip_key), _local_box_variant_key(family))].append(index)

    for indices in groups.values():
        values_by_feature = {
            feature: np.asarray(
                [float(out[index].get(feature, 0.0) or 0.0) for index in indices],
                dtype=float,
            )
            for feature in feature_names
        }
        spreads = [
            float(np.max(values) - np.min(values))
            for values in values_by_feature.values()
            if values.size
        ]
        medians = {
            feature: float(np.median(values)) if values.size else 0.0
            for feature, values in values_by_feature.items()
        }
        spread_mean = float(np.mean(spreads)) if spreads else 0.0

        for index in indices:
            distances = [
                abs(float(out[index].get(feature, 0.0) or 0.0) - medians[feature])
                for feature in feature_names
            ]
            out[index]["variant_sibling_count"] = float(len(indices))
            out[index]["variant_feature_spread_mean"] = spread_mean
            out[index]["variant_feature_distance_mean"] = (
                float(np.mean(distances)) if distances else 0.0
            )
    return out


def add_occlusion_release_proxy_rows(
    rows: Sequence[dict],
    *,
    consensus_key: str = "rank_cons_med",
    roughness_key: str = "rank_rough",
    background_key: str = "rank_run",
) -> list[dict]:
    out = [dict(row) for row in rows]
    for row in out:
        consensus = float(row.get(consensus_key, 0.0) or 0.0)
        roughness = float(row.get(roughness_key, 0.0) or 0.0)
        background_escape = float(row.get(background_key, 0.0) or 0.0)
        smooth_outlier = max(0.0, consensus - roughness)
        row["occlusion_release_proxy"] = smooth_outlier * (
            0.5 + 0.5 * max(0.0, background_escape)
        )
    return out


def add_conditional_feature_rows(
    rows: Sequence[dict],
    *,
    anchor_features: Sequence[str],
    conditioned_features: Sequence[str],
) -> list[dict]:
    out = [dict(row) for row in rows]
    for row in out:
        for anchor in anchor_features:
            anchor_value = float(row.get(anchor, 0.0) or 0.0)
            for feature in conditioned_features:
                row[f"{anchor}*{feature}"] = anchor_value * float(
                    row.get(feature, 0.0) or 0.0
                )
    return out


def selector_numeric_feature_names(
    rows: Sequence[dict],
    *,
    exclude: Iterable[str] = ("mean", "max", "success", "coverage"),
) -> tuple[str, ...]:
    excluded = set(exclude)
    keys = sorted({key for row in rows for key in row})
    return tuple(
        key
        for key in keys
        if key not in excluded
        and any(isinstance(row.get(key), (int, float)) for row in rows)
    )


def _feature_matrix(rows: Sequence[dict], feature_names: Sequence[str]) -> np.ndarray:
    return np.asarray(
        [
            [float(row.get(feature, 0.0) or 0.0) for feature in feature_names]
            for row in rows
        ],
        dtype=float,
    )


def _standardized_feature_matrix(
    rows: Sequence[dict],
    feature_names: Sequence[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = _feature_matrix(rows, feature_names)
    mean = matrix.mean(axis=0) if matrix.size else np.zeros(len(feature_names))
    scale = matrix.std(axis=0) if matrix.size else np.ones(len(feature_names))
    scale = np.where(scale < 1e-9, 1.0, scale)
    return (matrix - mean) / scale, mean, scale


def select_linear_feature_rows(
    rows: Sequence[dict],
    model: LinearSelectorModel,
    *,
    clip_key: str = "clip",
    family_key: str = "family",
) -> Dict[object, dict]:
    matrix = _feature_matrix(rows, model.feature_names)
    mean = np.asarray(model.mean, dtype=float)
    scale = np.asarray(model.scale, dtype=float)
    weights = np.asarray(model.weights, dtype=float)
    scores = ((matrix - mean) / scale) @ weights

    selected: Dict[object, tuple[float, str, dict]] = {}
    for index, row in enumerate(rows):
        clip = row.get(clip_key)
        item = (float(scores[index]), str(row.get(family_key, "")), dict(row))
        if clip not in selected or item > selected[clip]:
            selected[clip] = item
    return {
        clip: row
        for clip, (_score, _family, row) in selected.items()
    }


def rank_linear_feature_rows(
    rows: Sequence[dict],
    model: LinearSelectorModel,
    *,
    clip_key: str = "clip",
    family_key: str = "family",
) -> Dict[object, list[dict]]:
    matrix = _feature_matrix(rows, model.feature_names)
    mean = np.asarray(model.mean, dtype=float)
    scale = np.asarray(model.scale, dtype=float)
    weights = np.asarray(model.weights, dtype=float)
    scores = ((matrix - mean) / scale) @ weights

    grouped: Dict[object, list[tuple[float, str, dict]]] = defaultdict(list)
    for index, row in enumerate(rows):
        copied = dict(row)
        copied["selector_score"] = float(scores[index])
        grouped[row.get(clip_key)].append((
            float(scores[index]),
            str(row.get(family_key, "")),
            copied,
        ))

    ranked: Dict[object, list[dict]] = {}
    for clip, items in grouped.items():
        ordered = sorted(items, key=lambda item: (item[0], item[1]), reverse=True)
        ranked_rows = []
        for rank, (_score, _family, row) in enumerate(ordered):
            copied = dict(row)
            copied["selector_rank"] = int(rank)
            ranked_rows.append(copied)
        ranked[clip] = ranked_rows
    return ranked


def fit_success_perceptron_selector(
    rows: Sequence[dict],
    *,
    feature_names: Sequence[str] | None = None,
    clip_key: str = "clip",
    family_key: str = "family",
    success_key: str = "success",
    score_key: str = "mean",
    learning_rate: float = 0.1,
    max_epochs: int = 320,
    seed: int = 7,
) -> LinearSelectorModel:
    names = tuple(feature_names or selector_numeric_feature_names(rows))
    copied_rows = tuple(dict(row) for row in rows)
    matrix, mean, scale = _standardized_feature_matrix(copied_rows, names)

    by_clip: dict[object, list[int]] = defaultdict(list)
    for index, row in enumerate(copied_rows):
        by_clip[row.get(clip_key)].append(index)
    for clip, indices in by_clip.items():
        if not any(bool(copied_rows[index].get(success_key, False)) for index in indices):
            raise ValueError(f"clip has no success candidate: {clip}")

    rng = random.Random(seed)
    weights = np.zeros(len(names), dtype=float)
    best_weights = weights.copy()
    best_metric = (-1, float("-inf"))

    def evaluate(current_weights: np.ndarray) -> tuple[int, float]:
        scores = matrix @ current_weights
        selected = []
        for indices in by_clip.values():
            selected.append(max(
                indices,
                key=lambda index: (
                    float(scores[index]),
                    str(copied_rows[index].get(family_key, "")),
                ),
            ))
        success_count = sum(
            1
            for index in selected
            if bool(copied_rows[index].get(success_key, False))
        )
        mean_score = float(np.mean([
            float(copied_rows[index].get(score_key, 0.0) or 0.0)
            for index in selected
        ]))
        return success_count, -mean_score

    clips = list(by_clip)
    for _epoch in range(max_epochs):
        rng.shuffle(clips)
        for clip in clips:
            scores = matrix @ weights
            indices = by_clip[clip]
            predicted = max(
                indices,
                key=lambda index: (
                    float(scores[index]),
                    str(copied_rows[index].get(family_key, "")),
                ),
            )
            if bool(copied_rows[predicted].get(success_key, False)):
                continue

            success_indices = [
                index
                for index in indices
                if bool(copied_rows[index].get(success_key, False))
            ]
            gold = max(
                success_indices,
                key=lambda index: (
                    float(scores[index])
                    - 0.002 * float(copied_rows[index].get(score_key, 0.0) or 0.0),
                    -float(copied_rows[index].get(score_key, 0.0) or 0.0),
                    str(copied_rows[index].get(family_key, "")),
                ),
            )
            weights += learning_rate * (matrix[gold] - matrix[predicted])

        metric = evaluate(weights)
        if metric > best_metric:
            best_metric = metric
            best_weights = weights.copy()

    return LinearSelectorModel(
        feature_names=names,
        weights=tuple(float(value) for value in best_weights),
        mean=tuple(float(value) for value in mean),
        scale=tuple(float(value) for value in scale),
    )
