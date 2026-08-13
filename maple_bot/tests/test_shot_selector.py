# 스크린샷 기반 영역 선택기의 좌표 환산과 실제 드래그 완료 동작을 검증합니다.
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog

from core_ui.shot_selector import ScreenshotRegionSelector, display_to_source_rect


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_no_scaling_identity():
    """표시배율 1.0 + 오프셋(0,0) → 그대로."""
    r = display_to_source_rect(10, 20, 100, 50, scale=1.0, src_origin=(0, 0))
    assert r == (10, 20, 100, 50)


def test_scaled_down_display():
    """스크린샷을 50%로 축소표시 → 표시좌표 ×2 가 원본."""
    r = display_to_source_rect(50, 30, 100, 40, scale=0.5, src_origin=(0, 0))
    assert r == (100, 60, 200, 80)


def test_with_source_origin_offset():
    """게임창이 화면 (200,100)에 있으면 원본좌표에 오프셋 더함."""
    r = display_to_source_rect(10, 10, 50, 50, scale=1.0, src_origin=(200, 100))
    assert r == (210, 110, 50, 50)


def test_combined_scale_and_origin():
    r = display_to_source_rect(25, 25, 50, 50, scale=0.5, src_origin=(200, 100))
    # 표시좌표/0.5 = 원본상대 → +origin
    assert r == (200 + 50, 100 + 50, 100, 100)


def test_normalizes_negative_drag():
    """드래그를 우하단→좌상단으로 해도 정규화(음수 w/h 방지)."""
    # 끝점이 시작점보다 작게 들어와도 정상 사각형
    r = display_to_source_rect(60, 60, -40, -30, scale=1.0, src_origin=(0, 0))
    assert r == (20, 30, 40, 30)


def test_region_selector_uses_release_position_without_move_event(app):
    """이동 이벤트가 없어도 실제 버튼 해제 위치로 선택을 완료한다."""
    selector = ScreenshotRegionSelector(
        np.zeros((100, 100, 3), dtype=np.uint8),
        max_display=100,
    )
    selected = []
    selector.region_selected.connect(lambda *rect: selected.append(rect))

    QTest.mousePress(
        selector._canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(10, 10),
    )
    QTest.mouseRelease(
        selector._canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(30, 25),
    )

    assert selected == [(10, 10, 21, 16)]
    assert selector.result() == QDialog.DialogCode.Accepted


def test_region_selector_keeps_last_drag_point_when_release_returns_to_start(app):
    """DPI 환경에서 해제 좌표가 시작점으로 돌아와도 보이던 드래그 영역을 확정한다."""
    selector = ScreenshotRegionSelector(
        np.zeros((100, 100, 3), dtype=np.uint8),
        max_display=100,
    )
    selected = []
    selector.region_selected.connect(lambda *rect: selected.append(rect))

    QTest.mousePress(
        selector._canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(10, 10),
    )
    QTest.mouseMove(selector._canvas, QPoint(30, 25))
    QTest.mouseRelease(
        selector._canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(10, 10),
    )

    assert selected == [(10, 10, 21, 16)]
    assert selector.result() == QDialog.DialogCode.Accepted
