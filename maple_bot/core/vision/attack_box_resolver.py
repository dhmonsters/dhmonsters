# 캐릭터 화면 위치 기준으로 방향별 공격 범위 박스(left/right)를 계산한다
from __future__ import annotations


class AttackBoxResolver:
    """캐릭터 화면 좌표(character_screen_pos) → 왼쪽/오른쪽 공격 범위 박스 변환.

    config의 attack 섹션에서 range_px, box_h 값을 읽는다.
    박스 형식: (left, top, right, bottom) — 오버레이 기준 픽셀 좌표.
    """

    def resolve(
        self,
        char_screen_pos: tuple[int, int],
        config,
    ) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        """(left_box, right_box) 반환.

        Args:
            char_screen_pos: 오버레이 기준 캐릭터 화면 좌표 (cx, cy).
            config:          ConfigManager 인스턴스.

        Returns:
            left_box, right_box 각각 (left, top, right, bottom).
        """
        cx, cy = char_screen_pos
        atk    = config.get("attack") or {}
        rng    = int(atk.get("range_px", 150))
        box_h  = int(atk.get("box_h",   120))
        half_h = box_h // 2

        left_box  = (cx - rng, cy - half_h, cx,       cy + half_h)
        right_box = (cx,       cy - half_h, cx + rng,  cy + half_h)
        return left_box, right_box


