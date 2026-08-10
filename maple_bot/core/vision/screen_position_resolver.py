# 미니맵 좌표 → 실제 게임 화면 좌표 변환기
"""
좌표계 설명.

    미니맵 좌표 (mx, my)    — 미니맵 이미지 내부 픽셀 (0 ~ minimap_w/h)
    오버레이 화면 좌표 (sx, sy) — game_region (0,0)이 원점인 픽셀 좌표

변환 원리.

    MapleStory는 카메라가 캐릭터를 따라가므로,
    현재 화면이 보여주는 미니맵 구간 = [cam_left, cam_left + cam_w]
    여기서 cam_left = clamp(mx - cam_w/2, 0, minimap_w - cam_w)

    화면 X = (mx - cam_left) / cam_w × game_width
    화면 Y = 층 프로파일 OR game_height × char_y_ratio

    cam_w (camera_width_on_minimap) 계산.
        게임 화면 1픽셀 ≙ 미니맵 (minimap_w / map_tile_w) 픽셀
        현실적으로는 camera_w_ratio로 조정.
        예) camera_w_ratio=0.5 → 화면이 미니맵 폭의 절반을 보여줌
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FloorProfile:
    """층 하나의 미니맵 Y ↔ 오버레이 화면 Y 매핑.

    Args:
        minimap_y: 이 층 중앙의 미니맵 Y 좌표.
        screen_y:  이 층 캐릭터의 오버레이 기준 화면 Y 좌표.
        name:      층 이름 (디버그 표시용). 선택.
    """
    minimap_y: int
    screen_y:  int
    name:      str = ""


class ScreenPositionResolver:
    """미니맵 좌표 → 오버레이 기준 실제 화면 좌표 변환기.

    Args:
        minimap_w:      미니맵 너비 (픽셀).
        minimap_h:      미니맵 높이 (픽셀).
        game_w:         게임 화면 너비 (픽셀) = overlay 너비.
        game_h:         게임 화면 높이 (픽셀) = overlay 높이.
        camera_w_ratio: game_w 대비 미니맵 카메라 폭 비율 (0.0 < r ≤ 1.0).
                        예: 0.5 → 미니맵 폭의 절반이 한 화면.
        char_y_ratio:   층 프로파일 없을 때 화면 Y 비율 (기본 0.6).
        char_offset_x:  화면 X 미세 보정 픽셀.
        char_offset_y:  화면 Y 미세 보정 픽셀.
        floors:         층별 Y 매핑 목록. 없으면 char_y_ratio 사용.
    """

    def __init__(
        self,
        minimap_w:      int,
        minimap_h:      int,
        game_w:         int,
        game_h:         int,
        camera_w_ratio: float = 0.5,
        char_y_ratio:   float = 0.6,
        char_offset_x:  int   = 0,
        char_offset_y:  int   = 0,
        floors:         list[FloorProfile] | None = None,
    ) -> None:
        self._mm_w  = max(minimap_w, 1)
        self._mm_h  = max(minimap_h, 1)
        self._gw    = max(game_w, 1)
        self._gh    = max(game_h, 1)
        self._cam_w = max(1, int(self._mm_w * max(0.01, min(1.0, camera_w_ratio))))
        self._y_ratio   = max(0.0, min(1.0, char_y_ratio))
        self._offset_x  = char_offset_x
        self._offset_y  = char_offset_y
        self._floors    = sorted(floors or [], key=lambda f: f.minimap_y)

    # ── 공개 API ──────────────────────────────────────────────────────────

    def resolve(
        self,
        minimap_pos: tuple[int, int],
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """미니맵 좌표 → (오버레이 화면 좌표, 카메라 미니맵 범위 (left, right)).

        Returns:
            (screen_pos, camera_range)
            screen_pos:    (sx, sy) — 오버레이 기준 캐릭터 화면 좌표.
            camera_range:  (cam_left, cam_right) — 미니맵 기준 현재 화면 구간.
        """
        mx, my = minimap_pos
        cam_left, cam_right = self._camera_range(mx)
        sx = self._resolve_x(mx, cam_left) + self._offset_x
        sy = self._resolve_y(my) + self._offset_y
        return (sx, sy), (cam_left, cam_right)

    def camera_range(self, minimap_x: int) -> tuple[int, int]:
        """미니맵 X 좌표 기준 현재 화면 카메라 구간 (left, right)."""
        return self._camera_range(minimap_x)

    @property
    def camera_width(self) -> int:
        """카메라가 보여주는 미니맵 폭 (픽셀)."""
        return self._cam_w

    @staticmethod
    def make_local_minimap_window(
        mx: int,
        my: int,
        mm_w: int,
        mm_h: int,
        window_size: int = 80,
    ) -> dict:
        """캐릭터 위치 중심 정사각형 크롭 범위를 반환한다.

        Args:
            mx, my:      미니맵 내 캐릭터 픽셀 좌표.
            mm_w, mm_h:  미니맵 전체 너비/높이.
            window_size: 크롭할 정사각형 한 변 크기 (미니맵 픽셀).

        Returns:
            {left, top, right, bottom, cx, cy, size}
        """
        half = window_size // 2
        # 미니맵 경계 안으로 클램프
        left = max(0, min(mx - half, mm_w - window_size))
        top  = max(0, min(my - half, mm_h - window_size))
        return {
            "left":   left,
            "top":    top,
            "right":  left + window_size,
            "bottom": top  + window_size,
            "cx":     mx,
            "cy":     my,
            "size":   window_size,
        }

    @staticmethod
    def make_local_minimap_window(
        mx: int,
        my: int,
        mm_w: int,
        mm_h: int,
        window_size: int = 80,
    ) -> dict:
        """캐릭터 위치 중심 정사각형 크롭 범위를 반환한다.

        Args:
            mx, my:      미니맵 내 캐릭터 픽셀 좌표.
            mm_w, mm_h:  미니맵 전체 너비/높이.
            window_size: 크롭할 정사각형 한 변 크기 (미니맵 픽셀).

        Returns:
            {left, top, right, bottom, cx, cy, size}
        """
        half = window_size // 2
        # 미니맵 경계 안으로 클램프
        left = max(0, min(mx - half, mm_w - window_size))
        top  = max(0, min(my - half, mm_h - window_size))
        return {
            "left":   left,
            "top":    top,
            "right":  left + window_size,
            "bottom": top  + window_size,
            "cx":     mx,
            "cy":     my,
            "size":   window_size,
        }

    # ── 내부 계산 ─────────────────────────────────────────────────────────

    def _camera_range(self, mx: int) -> tuple[int, int]:
        """미니맵 X를 기준으로 카메라 가시 범위 계산 (맵 끝에서 클램프)."""
        half     = self._cam_w / 2
        cam_left = mx - half
        cam_left = max(0.0, min(cam_left, self._mm_w - self._cam_w))
        cam_right = cam_left + self._cam_w
        return int(cam_left), int(cam_right)

    def _resolve_x(self, mx: int, cam_left: int) -> int:
        """카메라 구간 안에서 캐릭터의 상대 비율 → 화면 X."""
        ratio = (mx - cam_left) / self._cam_w
        ratio = max(0.0, min(1.0, ratio))
        return int(ratio * self._gw)

    def _resolve_y(self, my: int) -> int:
        """미니맵 Y → 화면 Y. 층 프로파일 우선, 없으면 비율 계산."""
        if self._floors:
            nearest = min(self._floors, key=lambda f: abs(f.minimap_y - my))
            return nearest.screen_y
        return int(self._gh * self._y_ratio)


# ── 팩토리 함수 ──────────────────────────────────────────────────────────────

def resolver_from_config(config) -> ScreenPositionResolver | None:
    """ConfigManager에서 파라미터를 읽어 ScreenPositionResolver를 생성한다.

    game_region 또는 minimap 설정이 없으면 None 반환.
    """
    try:
        region = config.get("settings1", "game_region")
        if not region or len(region) != 4:
            return None
        gw = int(region[2])
        gh = int(region[3])
        if gw <= 0 or gh <= 0:
            return None

        mm = config.get("minimap") or {}
        mm_w = int(mm.get("width",  200))
        mm_h = int(mm.get("height", 120))
        if mm_w <= 0 or mm_h <= 0:
            return None

        atk = config.get("attack") or {}
        camera_w_ratio = float(atk.get("camera_w_ratio", 0.5))
        char_y_ratio   = float(atk.get("char_y_ratio",   0.6))
        offset_x       = int(atk.get("char_offset_x",    0))
        offset_y       = int(atk.get("char_offset_y",    0))

        # 층별 프로파일 (선택 — config의 floor_profiles 목록)
        raw_floors = config.get("attack", "floor_profiles") or []
        floors = [
            FloorProfile(
                minimap_y=int(fp["minimap_y"]),
                screen_y=int(fp["screen_y"]),
                name=str(fp.get("name", "")),
            )
            for fp in raw_floors
            if "minimap_y" in fp and "screen_y" in fp
        ]

        return ScreenPositionResolver(
            minimap_w=mm_w, minimap_h=mm_h,
            game_w=gw,      game_h=gh,
            camera_w_ratio=camera_w_ratio,
            char_y_ratio=char_y_ratio,
            char_offset_x=offset_x,
            char_offset_y=offset_y,
            floors=floors,
        )
    except Exception:
        return None



