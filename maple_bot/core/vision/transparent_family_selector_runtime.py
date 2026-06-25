# 저장된 GT-free family selector 모델을 라이브 런타임에서 사용합니다.
from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Sequence

from _gt_free_family_selector import (
    load_gt_free_selector_model,
    select_gt_free_family_rows,
)
from core.vision.transparent_feature_rows import build_transparent_feature_rows


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "models" / "transparent" / "gt_free_family_selector_v1.json"
GT_SCORE_LABELS = frozenset({"success", "mean", "max", "coverage"})


def strip_gt_score_labels(row: Mapping[str, object]) -> dict:
    return {
        str(key): value
        for key, value in row.items()
        if str(key) not in GT_SCORE_LABELS
    }


class TransparentFamilySelectorRuntime:
    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH):
        self.model_path = Path(model_path)
        self._model = None
        self._load_error = ""
        self._load()

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str:
        return self._load_error

    def select(self, rows: Sequence[Mapping[str, object]]) -> Dict[object, dict]:
        if self._model is None:
            return {}
        runtime_rows = [strip_gt_score_labels(row) for row in rows]
        return select_gt_free_family_rows(runtime_rows, self._model)

    def select_from_path_pool(
        self,
        clip: str,
        paths,
        frames,
        **kwargs,
    ) -> tuple[Dict[object, dict], list[dict]]:
        rows = build_transparent_feature_rows(
            clip,
            paths,
            frames,
            **kwargs,
        )
        return self.select(rows), rows

    def _load(self) -> None:
        try:
            if not self.model_path.exists():
                self._load_error = f"missing model: {self.model_path}"
                return
            self._model = load_gt_free_selector_model(self.model_path)
            self._load_error = ""
        except Exception as exc:
            self._model = None
            self._load_error = str(exc)
