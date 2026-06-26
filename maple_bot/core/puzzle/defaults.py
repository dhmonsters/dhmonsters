# 투명도형 퍼즐 분석에서 공유하는 고정 ROI 기본값을 제공한다.
from __future__ import annotations

from core.puzzle.models import RoiSpec
from core.puzzle.roi import resolve_ratio_roi


DEFAULT_DETECT_REGION = (1126, 297, 296, 130)
DEFAULT_DETECT_BASE_SIZE = (2560, 1369)
DEFAULT_DETECT_ROI_RATIOS = {
    "x_ratio": DEFAULT_DETECT_REGION[0] / DEFAULT_DETECT_BASE_SIZE[0],
    "y_ratio": DEFAULT_DETECT_REGION[1] / DEFAULT_DETECT_BASE_SIZE[1],
    "w_ratio": DEFAULT_DETECT_REGION[2] / DEFAULT_DETECT_BASE_SIZE[0],
    "h_ratio": DEFAULT_DETECT_REGION[3] / DEFAULT_DETECT_BASE_SIZE[1],
}
DEFAULT_BOARD_ROI_RATIOS = {
    "x_ratio": 0.286,
    "y_ratio": 0.183,
    "w_ratio": 0.428,
    "h_ratio": 0.575,
}


def fixed_detect_roi(*, frame_w: int, frame_h: int, window_title: str = "") -> RoiSpec:
    return resolve_ratio_roi(
        DEFAULT_DETECT_ROI_RATIOS,
        frame_w=frame_w,
        frame_h=frame_h,
        name="detect",
        basis="window_client",
        window_title=window_title,
    )


def fixed_board_roi(*, frame_w: int, frame_h: int, window_title: str = "") -> RoiSpec:
    return resolve_ratio_roi(
        DEFAULT_BOARD_ROI_RATIOS,
        frame_w=frame_w,
        frame_h=frame_h,
        name="board",
        basis="window_client",
        window_title=window_title,
    )


def fixed_puzzle_rois(
    *,
    frame_w: int,
    frame_h: int,
    window_title: str = "",
) -> tuple[RoiSpec, RoiSpec]:
    return (
        fixed_detect_roi(frame_w=frame_w, frame_h=frame_h, window_title=window_title),
        fixed_board_roi(frame_w=frame_w, frame_h=frame_h, window_title=window_title),
    )


def roi_to_payload(roi: RoiSpec) -> dict[str, object]:
    return {
        "name": roi.name,
        "basis": roi.basis,
        "x": roi.x,
        "y": roi.y,
        "w": roi.w,
        "h": roi.h,
        "x_ratio": roi.x_ratio,
        "y_ratio": roi.y_ratio,
        "w_ratio": roi.w_ratio,
        "h_ratio": roi.h_ratio,
        "dpi_scale": roi.dpi_scale,
        "window_title": roi.window_title,
    }


def fixed_detect_roi_text() -> str:
    return (
        "detect: ratio "
        f"{DEFAULT_DETECT_ROI_RATIOS['x_ratio']:.3f},"
        f"{DEFAULT_DETECT_ROI_RATIOS['y_ratio']:.3f},"
        f"{DEFAULT_DETECT_ROI_RATIOS['w_ratio']:.3f},"
        f"{DEFAULT_DETECT_ROI_RATIOS['h_ratio']:.3f}"
    )


def fixed_board_roi_text() -> str:
    return (
        "board: ratio "
        f"{DEFAULT_BOARD_ROI_RATIOS['x_ratio']},"
        f"{DEFAULT_BOARD_ROI_RATIOS['y_ratio']},"
        f"{DEFAULT_BOARD_ROI_RATIOS['w_ratio']},"
        f"{DEFAULT_BOARD_ROI_RATIOS['h_ratio']}"
    )
