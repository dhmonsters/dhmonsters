# 검증 세션의 대용량 영상 파일 보존과 정리를 담당한다.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VIDEO_NAMES = frozenset({"raw_cctv.mkv", "board_crop.mkv", "overlay.mkv"})


@dataclass(frozen=True)
class RetentionItem:
    path: Path
    reason: str


@dataclass(frozen=True)
class RetentionPlan:
    root: Path
    keep_latest: int
    delete_candidates: list[RetentionItem]


@dataclass(frozen=True)
class RetentionResult:
    plan: RetentionPlan
    deleted_count: int
    deleted_bytes: int


def plan_video_retention(root: str | Path, *, keep_latest: int = 3) -> RetentionPlan:
    if keep_latest < 0:
        raise ValueError("keep_latest must be non-negative")
    session_root = Path(root)
    if not session_root.exists():
        return RetentionPlan(session_root, keep_latest, [])

    sessions = sorted([path for path in session_root.iterdir() if path.is_dir()], key=lambda path: path.name)
    protected = set(sessions[-keep_latest:]) if keep_latest else set()
    delete_candidates: list[RetentionItem] = []
    for session in sessions:
        if session in protected or (session / ".keep_videos").exists():
            continue
        for video_name in sorted(VIDEO_NAMES):
            path = session / video_name
            if path.is_file():
                delete_candidates.append(RetentionItem(path=path, reason="expired_session_video"))
    return RetentionPlan(session_root, keep_latest, delete_candidates)


def apply_video_retention(
    root: str | Path,
    *,
    keep_latest: int = 3,
    dry_run: bool = True,
) -> RetentionResult:
    plan = plan_video_retention(root, keep_latest=keep_latest)
    if dry_run:
        return RetentionResult(plan=plan, deleted_count=0, deleted_bytes=0)

    deleted_count = 0
    deleted_bytes = 0
    for item in plan.delete_candidates:
        if item.path.name not in VIDEO_NAMES or not item.path.is_file():
            continue
        deleted_bytes += item.path.stat().st_size
        item.path.unlink()
        deleted_count += 1
    return RetentionResult(plan=plan, deleted_count=deleted_count, deleted_bytes=deleted_bytes)


def remove_success_session_videos(
    session_dir: str | Path,
    *,
    passed: bool,
    apply: bool = False,
) -> RetentionResult:
    session = Path(session_dir)
    candidates: list[RetentionItem] = []
    if passed and session.is_dir() and not (session / ".keep_videos").exists():
        candidates = [
            RetentionItem(path=session / name, reason="successful_validation_video")
            for name in sorted(VIDEO_NAMES)
            if (session / name).is_file()
        ]
    plan = RetentionPlan(root=session, keep_latest=0, delete_candidates=candidates)
    if not apply:
        return RetentionResult(plan=plan, deleted_count=0, deleted_bytes=0)

    deleted_count = 0
    deleted_bytes = 0
    for item in candidates:
        if item.path.name not in VIDEO_NAMES or not item.path.is_file():
            continue
        deleted_bytes += item.path.stat().st_size
        item.path.unlink()
        deleted_count += 1
    return RetentionResult(plan=plan, deleted_count=deleted_count, deleted_bytes=deleted_bytes)


def remove_validation_session_videos(
    session_dir: str | Path,
    *,
    apply: bool = False,
) -> RetentionResult:
    session = Path(session_dir)
    candidates: list[RetentionItem] = []
    if session.is_dir() and not (session / ".keep_videos").exists():
        candidates = [
            RetentionItem(path=session / name, reason="completed_validation_video")
            for name in sorted(VIDEO_NAMES)
            if (session / name).is_file()
        ]
    plan = RetentionPlan(root=session, keep_latest=0, delete_candidates=candidates)
    if not apply:
        return RetentionResult(plan=plan, deleted_count=0, deleted_bytes=0)

    deleted_count = 0
    deleted_bytes = 0
    for item in candidates:
        if item.path.name not in VIDEO_NAMES or not item.path.is_file():
            continue
        deleted_bytes += item.path.stat().st_size
        item.path.unlink()
        deleted_count += 1
    return RetentionResult(plan=plan, deleted_count=deleted_count, deleted_bytes=deleted_bytes)
