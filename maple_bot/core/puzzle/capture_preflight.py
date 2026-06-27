# 투명도형 퍼즐 라이브 화면 캡처 사전점검 산출물을 생성한다.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.puzzle.defaults import fixed_puzzle_rois, roi_to_payload
from core.puzzle.live_recording import grab_screen_bgr


FrameGrabber = Callable[[], Any]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CaptureCheckResult:
    ok: bool
    output_dir: Path
    report_path: Path
    image_path: Path | None
    width: int = 0
    height: int = 0
    error: str = ""


def run_capture_check(
    *,
    output_root: str | Path | None = None,
    frame_grabber: FrameGrabber | None = None,
    clock: Clock | None = None,
) -> CaptureCheckResult:
    output_dir = _create_output_dir(output_root=output_root, clock=clock)
    report_path = output_dir / "capture_check.md"
    grabber = frame_grabber or grab_screen_bgr

    try:
        frame = grabber()
        frame_h, frame_w = frame.shape[:2]
        image_path = output_dir / "capture_check.png"
        _write_png(image_path, frame)
        detect_roi, board_roi = fixed_puzzle_rois(frame_w=frame_w, frame_h=frame_h)
        result = CaptureCheckResult(
            ok=True,
            output_dir=output_dir,
            report_path=report_path,
            image_path=image_path,
            width=frame_w,
            height=frame_h,
        )
        report_path.write_text(
            _format_success_report(result, detect_roi=detect_roi, board_roi=board_roi),
            encoding="utf-8",
        )
        return result
    except Exception as exc:
        result = CaptureCheckResult(
            ok=False,
            output_dir=output_dir,
            report_path=report_path,
            image_path=None,
            error=str(exc),
        )
        report_path.write_text(_format_failure_report(result), encoding="utf-8")
        return result


def _write_png(path: Path, frame: Any) -> None:
    import cv2

    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"failed to write {path.name}")


def _create_output_dir(
    *,
    output_root: str | Path | None,
    clock: Clock | None,
) -> Path:
    root = Path(output_root) if output_root is not None else _default_output_root()
    now = (clock or datetime.now)()
    date_key = now.strftime("%Y-%m-%d")
    second_key = now.strftime("%Y%m%d_%H%M%S")
    base_dir = root / f"{date_key}_capture_checks"
    base_dir.mkdir(parents=True, exist_ok=True)

    counter = 1
    while True:
        output_dir = base_dir / f"{second_key}_{counter:03d}"
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
            return output_dir
        counter += 1


def _default_output_root() -> Path:
    return Path(__file__).resolve().parents[2] / "03_output"


def _format_success_report(result: CaptureCheckResult, *, detect_roi: Any, board_roi: Any) -> str:
    return "\n".join(
        [
            "# Live Capture Check",
            "",
            "- status: ok",
            f"- frame: {result.width}x{result.height}",
            f"- image: {result.image_path.name if result.image_path is not None else '-'}",
            f"- detect_roi: {roi_to_payload(detect_roi)}",
            f"- board_roi: {roi_to_payload(board_roi)}",
            "",
        ]
    )


def _format_failure_report(result: CaptureCheckResult) -> str:
    return "\n".join(
        [
            "# Live Capture Check",
            "",
            "- status: failed",
            f"- error: {result.error}",
            "",
        ]
    )
