# CharScanner의 HSV 위치 감지(순수 함수)를 합성 이미지로 검증 (C vision.py 방식)
import numpy as np
import pytest
import core.sensing.char_scanner as char_scanner_module
from core.sensing.char_scanner import CharScanner, find_char_by_template, find_char_in_hsv
from core.sensing.coordinate_history import CoordinateHistory
from core.runtime import RuntimeConfig


def _img_with_yellow_block(w=200, h=120, cx=50, cy=40, size=10):
    """배경(검정) 위에 노란색 블록 하나를 그린 BGR 이미지."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # 노란색 BGR = (0, 255, 255)
    img[cy - size // 2: cy + size // 2, cx - size // 2: cx + size // 2] = (0, 255, 255)
    return img


# C vision.py 기본 노란색 HSV 범위(20~40 H)
HSV_LO = (20, 100, 200)
HSV_HI = (40, 255, 255)


def test_finds_yellow_block_center():
    img = _img_with_yellow_block(cx=50, cy=40, size=10)
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=10, max_area=10000)
    assert pos is not None
    x, y = pos
    assert abs(x - 50) <= 2 and abs(y - 40) <= 2  # 무게중심 ≈ 블록 중심


def test_default_filter_accepts_deployed_round_marker_size():
    """배포 화면의 반지름 7 노란 마커를 기본 점 크기 범위가 탈락시키지 않는다."""
    import cv2

    image = np.zeros((39, 43, 3), dtype=np.uint8)
    cv2.circle(image, (29, 12), 7, (0, 225, 225), -1)
    config = RuntimeConfig(minimap_region={"left": 0, "top": 0, "width": 172, "height": 103})

    position = find_char_in_hsv(
        image,
        HSV_LO,
        HSV_HI,
        min_area=config.char_area_min,
        max_area=config.char_area_max,
    )

    assert position == (29, 12)


def test_even_width_marker_centroid_rounds_to_nearest_pixel():
    """X 중심이 28.5인 마커를 항상 왼쪽 28로 버리지 않는다."""
    yy, xx = np.ogrid[:39, :43]
    marker = (((xx - 28.5) / 6.5) ** 2 + ((yy - 12.0) / 6.0) ** 2) <= 1.0
    image = np.zeros((39, 43, 3), dtype=np.uint8)
    image[marker] = (0, 225, 225)

    position = find_char_in_hsv(image, HSV_LO, HSV_HI, min_area=3, max_area=160)

    assert position == (29, 12)


def test_hsv_diagnostics_report_selected_candidate_bbox():
    import cv2

    image = np.zeros((20, 30, 3), dtype=np.uint8)
    cv2.circle(image, (10, 10), 4, (0, 225, 225), -1)
    diagnostics = {}

    position = find_char_in_hsv(
        image,
        HSV_LO,
        HSV_HI,
        min_area=3,
        max_area=160,
        diagnostic_out=diagnostics,
    )

    assert position == (10, 10)
    assert diagnostics["candidate_bbox"] == (6, 6, 9, 9)


def test_template_diagnostics_report_selected_match_bbox():
    template = np.array([
        [[10, 20, 30], [30, 10, 20], [20, 30, 10]],
        [[40, 50, 60], [60, 40, 50], [50, 60, 40]],
        [[70, 80, 90], [90, 70, 80], [80, 90, 70]],
    ], dtype=np.uint8)
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    image[7:10, 11:14] = template
    diagnostics = {}

    position = find_char_by_template(
        image,
        [("y_p.png", template)],
        threshold=0.99,
        timing_out=diagnostics,
    )

    assert position == (12, 8)
    assert diagnostics["candidate_bbox"] == (11, 7, 3, 3)


def test_default_filter_still_rejects_larger_round_background_object():
    """캐릭터보다 큰 원형 배경 물체는 기본 최대 면적에서 제외한다."""
    import cv2

    image = np.zeros((39, 43, 3), dtype=np.uint8)
    cv2.circle(image, (29, 18), 10, (0, 225, 225), -1)
    config = RuntimeConfig(minimap_region={"left": 0, "top": 0, "width": 172, "height": 103})

    position = find_char_in_hsv(
        image,
        HSV_LO,
        HSV_HI,
        min_area=config.char_area_min,
        max_area=config.char_area_max,
    )

    assert position is None


def test_returns_none_when_no_yellow():
    img = np.zeros((120, 200, 3), dtype=np.uint8)  # 전부 검정
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=10, max_area=10000)
    assert pos is None


def test_area_filter_rejects_too_small():
    """min_area보다 작은 노이즈는 무시."""
    img = _img_with_yellow_block(size=2)  # 4px
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=50, max_area=10000)
    assert pos is None


def test_area_filter_rejects_too_big():
    """max_area보다 큰 덩어리는 무시(배경 오염 방지)."""
    img = _img_with_yellow_block(size=60)
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=10, max_area=100)
    assert pos is None


def test_char_scanner_uses_30ms_interval():
    assert CharScanner.interval == 0.03


def test_char_scanner_applies_position_offset_to_published_position(monkeypatch):
    monkeypatch.setattr(char_scanner_module, "_load_marker_templates", lambda: [("marker", np.ones((4, 4, 3), dtype=np.uint8))])
    monkeypatch.setattr(char_scanner_module, "find_char_by_template", lambda *_args, **_kwargs: (20, 30))
    published = []

    class PositionStore:
        def publish(self, x, y, observed_at):
            published.append((x, y, observed_at))

    scanner = CharScanner(
        lambda _region: np.zeros((80, 120, 3), dtype=np.uint8),
        {"width": 120, "height": 80},
        position_store=PositionStore(),
        position_offset=(5, -3),
    )

    event = scanner.scan_once()

    assert scanner.position() == (25, 27)
    assert event.data["x"] == 25
    assert event.data["y"] == 27
    assert published[-1][:2] == (25, 27)


def test_char_scanner_snapshot_keeps_frame_and_position_together(monkeypatch):
    marker = np.full((60, 90, 3), 17, dtype=np.uint8)
    monkeypatch.setattr(char_scanner_module, "_load_marker_templates", lambda: [("marker", np.ones((4, 4, 3), dtype=np.uint8))])
    monkeypatch.setattr(char_scanner_module, "find_char_by_template", lambda *_args, **_kwargs: (40, 25))
    scanner = CharScanner(lambda _region: marker, {"width": 90, "height": 60})

    scanner.scan_once()
    frame, position, observed_at = scanner.preview_snapshot()

    assert position == (40, 25)
    assert observed_at is not None
    assert np.array_equal(frame, marker)
    assert frame is not marker


@pytest.mark.parametrize("templates, expected_source", [([], "color"), ([('y_p.png', object())], "template")])
def test_success_log_reports_detection_source_and_raw_position(monkeypatch, templates, expected_source):
    logs = []
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    monkeypatch.setattr(char_scanner_module, "_load_marker_templates", lambda: templates)
    def fake_template(*_args, **kwargs):
        if templates:
            kwargs["timing_out"]["candidate_bbox"] = (1, 2, 3, 4)
            return 7, 8
        return None

    def fake_color(*_args, **kwargs):
        kwargs["diagnostic_out"]["candidate_bbox"] = (1, 2, 3, 4)
        return 7, 8

    monkeypatch.setattr(char_scanner_module, "find_char_by_template", fake_template)
    monkeypatch.setattr(char_scanner_module, "find_char_in_hsv", fake_color)
    scanner = CharScanner(
        lambda _region: image,
        {"left": 0, "top": 0, "width": 30, "height": 20},
        log_fn=logs.append,
    )

    scanner.scan_once()

    assert any(
        f"source={expected_source}" in message
        and "raw=(7,8)" in message
        and "candidate=(1,2,3,4)" in message
        for message in logs
    )


def test_coordinate_history_keeps_latest_ten_samples():
    history = CoordinateHistory(maxlen=10)
    for index in range(12):
        history.append((index, 40), observed_at=float(index), scan_duration_sec=0.01)
    samples = history.snapshot()
    assert len(samples) == 10
    assert samples[0].position == (2, 40)
    assert history.latest().position == (11, 40)
