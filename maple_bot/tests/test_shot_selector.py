# 스크린샷 기반 영역 선택기 — 표시좌표→원본화면좌표 환산 검증 (드래그 GUI는 환산 로직만)
import pytest
from core_ui.shot_selector import display_to_source_rect


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
