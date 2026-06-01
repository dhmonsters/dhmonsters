# 미니맵↔캔버스 좌표 변환 + 화면px→미니맵px 범위 환산 + 캐릭터 추적 상태 (순수 함수)
from __future__ import annotations


def minimap_to_canvas(cx: int, cy: int, zoom: float,
                      pan: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """미니맵 픽셀(cx,cy)을 줌·팬 적용한 캔버스 픽셀로 변환."""
    return (round(cx * zoom + pan[0]), round(cy * zoom + pan[1]))


def screen_px_to_minimap_px(screen_px: float, minimap_w: int,
                            screen_w: int, camera_w_ratio: float) -> float:
    """게임 화면에서의 픽셀 거리를 미니맵 이미지에서의 픽셀 거리로 환산한다.

    공격/사냥 범위는 게임 화면(메인 뷰) 기준 픽셀로 설정돼 있지만, 캔버스는 미니맵
    이미지를 그리므로 같은 물리 거리를 미니맵 축척으로 바꿔야 노란 점 주변에 올바른
    크기로 그려진다. 미니맵 폭 중 카메라가 실제로 비추는 가시 폭이
    camera_w_ratio*minimap_w 이고, 그 가시 폭이 게임 화면 폭(screen_w)에 대응하므로
    `screen_px : screen_w = ? : camera_w_ratio*minimap_w` 비례로 환산한다.

    Args:
        screen_px: 게임 화면에서의 픽셀 거리(예: 공격박스 반폭 atk_x_max).
        minimap_w: 현재 캡처된 미니맵 이미지의 폭(px).
        screen_w: 캡처한 전체 화면(주 모니터)의 폭(px).
        camera_w_ratio: 게임 화면 폭 대비 미니맵에 보이는 카메라 가시 영역의 비율
            (기본 0.5 — config attack.camera_w_ratio).

    Returns:
        미니맵 이미지 기준 픽셀 거리(float). screen_w<=0이면 0.0(0 나눗셈 방어).
    """
    if screen_w <= 0:
        return 0.0
    return screen_px * (camera_w_ratio * minimap_w) / screen_w


def char_track_state(elapsed_sec: float,
                     lost_after: float = 1.0,
                     stale_after: float = 3.0) -> str:
    """마지막 캐릭터 검출 이후 경과시간(초)으로 추적 상태를 판정한다.

    UI가 '상황 인지'를 주도록: 정상 추적/일시적 끊김/오래 끊김을 구분한다.

    Args:
        elapsed_sec: 마지막 성공 검출 이후 흐른 시간(초).
        lost_after: 이 시간(초) 이상 미검출이면 'lost'(점 깜빡임).
        stale_after: 이 시간(초) 이상 미검출이면 'stale'(점 숨김 + 배지).

    Returns:
        "tracking" | "lost" | "stale".
    """
    if elapsed_sec < lost_after:
        return "tracking"
    if elapsed_sec < stale_after:
        return "lost"
    return "stale"
