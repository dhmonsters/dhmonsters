# 투명도형 퍼즐 ROI 좌표 변환과 crop 동작을 검증한다.
import numpy as np

from core.puzzle.roi import crop_by_roi, resolve_ratio_roi


def test_resolve_ratio_roi_converts_board_roi_to_window_client_pixels():
    roi = resolve_ratio_roi(
        {
            "x_ratio": 0.286,
            "y_ratio": 0.183,
            "w_ratio": 0.428,
            "h_ratio": 0.575,
        },
        frame_w=1920,
        frame_h=1080,
        name="board",
    )

    assert roi.name == "board"
    assert roi.basis == "window_client"
    assert (roi.x, roi.y, roi.w, roi.h) == (549, 198, 822, 621)
    assert roi.x_ratio == 0.286
    assert roi.h_ratio == 0.575


def test_crop_by_roi_returns_exact_region_copy():
    frame = np.arange(10 * 12 * 3, dtype=np.uint8).reshape((10, 12, 3))
    roi = resolve_ratio_roi(
        {"x_ratio": 0.25, "y_ratio": 0.2, "w_ratio": 0.5, "h_ratio": 0.4},
        frame_w=12,
        frame_h=10,
        name="board",
    )

    crop = crop_by_roi(frame, roi)

    assert crop.shape == (4, 6, 3)
    np.testing.assert_array_equal(crop, frame[2:6, 3:9])
    crop[:, :, :] = 0
    assert frame[2, 3, 0] != 0


def test_resolve_ratio_roi_rejects_invalid_dimensions():
    try:
        resolve_ratio_roi(
            {"x_ratio": 0.0, "y_ratio": 0.0, "w_ratio": 0.0, "h_ratio": 0.5},
            frame_w=100,
            frame_h=100,
            name="bad",
        )
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("resolve_ratio_roi should reject zero width")

