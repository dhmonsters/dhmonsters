# 투명도형 퍼즐 검출 행을 표준 Candidate 객체로 변환한다.
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from core.puzzle.models import Candidate, FramePacket


CandidateSource = Literal["yolo", "raw", "live_family", "replay"]
ALLOWED_SOURCES = {"yolo", "raw", "live_family", "replay"}


class CandidateProvider:
    def __init__(
        self,
        row_provider: Callable[[FramePacket], Sequence[Any]],
        source: CandidateSource,
        min_score: float = 0.0,
        max_candidates: int | None = None,
    ) -> None:
        if source not in ALLOWED_SOURCES:
            raise ValueError(f"unsupported candidate source: {source}")
        if max_candidates is not None and max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        self.row_provider = row_provider
        self.source = source
        self.min_score = float(min_score)
        self.max_candidates = max_candidates
        self.last_debug: dict[str, object] = {
            "input_count": 0,
            "kept_count": 0,
            "dropped": [],
        }

    def detect(self, packet: FramePacket) -> list[Candidate]:
        rows = list(self.row_provider(packet))
        candidates: list[Candidate] = []
        dropped: list[dict[str, object]] = []

        for row_index, row in enumerate(rows):
            parsed = parse_candidate_row(row)
            if parsed["score"] < self.min_score:
                dropped.append(
                    {
                        "row_index": row_index,
                        "reason": "below_min_score",
                        "score": parsed["score"],
                    }
                )
                continue
            if self.max_candidates is not None and len(candidates) >= self.max_candidates:
                dropped.append(
                    {
                        "row_index": row_index,
                        "reason": "max_candidates",
                        "score": parsed["score"],
                    }
                )
                continue
            candidates.append(
                candidate_from_parsed_row(
                    parsed,
                    frame_index=packet.frame_index,
                    source=self.source,
                    row_index=row_index,
                )
            )

        self.last_debug = {
            "input_count": len(rows),
            "kept_count": len(candidates),
            "dropped": dropped,
        }
        return candidates


def candidate_from_row(
    row: Any,
    *,
    frame_index: int,
    source: CandidateSource,
    row_index: int,
    class_name: str = "",
) -> Candidate:
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"unsupported candidate source: {source}")
    parsed = parse_candidate_row(row)
    if class_name:
        parsed["class_name"] = class_name
    return candidate_from_parsed_row(
        parsed,
        frame_index=frame_index,
        source=source,
        row_index=row_index,
    )


def candidate_from_parsed_row(
    parsed: Mapping[str, Any],
    *,
    frame_index: int,
    source: str,
    row_index: int,
) -> Candidate:
    cx = float(parsed["cx"])
    cy = float(parsed["cy"])
    width = float(parsed["w"])
    height = float(parsed["h"])
    if width <= 0.0 or height <= 0.0:
        raise ValueError("candidate width and height must be positive")

    return Candidate(
        candidate_id=f"f{frame_index}_{source}_{row_index}",
        frame_index=frame_index,
        bbox=(
            cx - width / 2.0,
            cy - height / 2.0,
            cx + width / 2.0,
            cy + height / 2.0,
        ),
        center=(cx, cy),
        score=float(parsed["score"]),
        source=source,
        class_name=str(parsed.get("class_name", "")),
    )


def parse_candidate_row(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return _parse_mapping_row(row)
    if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
        return _parse_sequence_row(row)
    raise ValueError("candidate row must be a mapping or sequence")


def _parse_sequence_row(row: Sequence[Any]) -> dict[str, Any]:
    if len(row) < 5:
        raise ValueError("candidate row sequence must contain cx, cy, score, w, h")
    return {
        "cx": float(row[0]),
        "cy": float(row[1]),
        "score": float(row[2]),
        "w": float(row[3]),
        "h": float(row[4]),
        "class_name": str(row[5]) if len(row) > 5 else "",
    }


def _parse_mapping_row(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        cx = row["cx"]
        cy = row["cy"]
        score = row["score"]
        width = row["w"]
        height = row["h"]
    except KeyError as exc:
        raise ValueError(f"missing candidate row field: {exc.args[0]}") from exc
    return {
        "cx": float(cx),
        "cy": float(cy),
        "score": float(score),
        "w": float(width),
        "h": float(height),
        "class_name": str(row.get("class_name", "")),
    }
