# Studio batch 검증 preview를 회차별 리뷰 이미지로 묶습니다.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VisualBatchReviewResult:
    review_dir: Path
    report_path: Path
    contact_sheets: list[Path]


def build_visual_batch_review(
    session_dir: str | Path,
    *,
    runs: int,
    frames_per_run: int,
    samples_per_run: int = 12,
    thumb_width: int = 320,
) -> VisualBatchReviewResult:
    if runs <= 0:
        raise ValueError("runs must be positive")
    if frames_per_run <= 0:
        raise ValueError("frames_per_run must be positive")
    if samples_per_run <= 0:
        raise ValueError("samples_per_run must be positive")
    if thumb_width <= 0:
        raise ValueError("thumb_width must be positive")

    root = Path(session_dir)
    snapshots = sorted((root / "snapshots").glob("live_preview_*.png"))
    review_dir = root / "visual_batch_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    contact_sheets: list[Path] = []
    for run_index in range(runs):
        start = run_index * frames_per_run
        end = min(start + frames_per_run, len(snapshots))
        run_paths = snapshots[start:end]
        if not run_paths:
            continue
        selected = _sample_paths(run_paths, samples_per_run)
        sheet = _make_contact_sheet(selected, thumb_width=thumb_width)
        out_path = review_dir / f"run_{run_index + 1:02d}_contact_sheet.png"
        ok = _cv2().imwrite(str(out_path), sheet)
        if not ok:
            raise ValueError(f"cannot write contact sheet: {out_path}")
        contact_sheets.append(out_path)

    report_path = root / "visual_batch_review.md"
    report_path.write_text(
        _render_report(
            runs=runs,
            frames_per_run=frames_per_run,
            snapshots=len(snapshots),
            contact_sheets=contact_sheets,
        ),
        encoding="utf-8",
    )
    return VisualBatchReviewResult(review_dir=review_dir, report_path=report_path, contact_sheets=contact_sheets)


def _sample_paths(paths: list[Path], count: int) -> list[Path]:
    if len(paths) <= count:
        return paths
    if count == 1:
        return [paths[len(paths) // 2]]
    last = len(paths) - 1
    indexes = [round(i * last / float(count - 1)) for i in range(count)]
    return [paths[int(index)] for index in indexes]


def _make_contact_sheet(paths: list[Path], *, thumb_width: int) -> Any:
    cv2 = _cv2()
    frames = []
    for index, path in enumerate(paths):
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        thumb = _resize_to_width(frame, thumb_width=thumb_width)
        cv2.putText(
            thumb,
            path.stem.replace("live_preview_", "f"),
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 80),
            2,
            cv2.LINE_AA,
        )
        frames.append(thumb)
    if not frames:
        raise ValueError("no readable preview frames")

    import numpy as np

    cols = min(4, len(frames))
    rows = (len(frames) + cols - 1) // cols
    cell_h = max(frame.shape[0] for frame in frames)
    cell_w = max(frame.shape[1] for frame in frames)
    sheet = np.zeros((rows * cell_h, cols * cell_w, 3), dtype=np.uint8)
    for index, frame in enumerate(frames):
        row = index // cols
        col = index % cols
        y = row * cell_h
        x = col * cell_w
        sheet[y : y + frame.shape[0], x : x + frame.shape[1]] = frame
    return sheet


def _resize_to_width(frame: Any, *, thumb_width: int) -> Any:
    height, width = frame.shape[:2]
    if width <= 0:
        raise ValueError("frame width must be positive")
    scale = float(thumb_width) / float(width)
    thumb_height = max(1, int(round(height * scale)))
    return _cv2().resize(frame, (int(thumb_width), thumb_height))


def _render_report(
    *,
    runs: int,
    frames_per_run: int,
    snapshots: int,
    contact_sheets: list[Path],
) -> str:
    lines = [
        "# Studio Visual Batch Review",
        "",
        f"- runs: {runs}",
        f"- frames_per_run: {frames_per_run}",
        f"- snapshots: {snapshots}",
        f"- contact_sheets: {len(contact_sheets)}",
        "",
        "## Sheets",
        "",
    ]
    if not contact_sheets:
        lines.append("- none")
    else:
        lines.extend(f"- {path}" for path in contact_sheets)
    return "\n".join(lines) + "\n"


def _cv2() -> Any:
    import cv2

    return cv2
