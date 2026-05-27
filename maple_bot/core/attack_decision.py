# 방향 판단 및 공격 범위 계산 — Decision Layer
from __future__ import annotations


class AttackDecision:
    """
    캐릭터 위치 + 몬스터 목록을 받아 이동 방향과 공격 가능 여부를 반환.

    방향 판단 우선순위:
    1. 공격 범위 내 몬스터가 있으면 direction=None (제자리 공격)
    2. 좌/우 몬스터 수 비교 → 많은 쪽
    3. 동수이면 캐릭터에 가까운 몬스터가 있는 쪽
    4. 같으면 None (현재 방향 유지)
    """

    def __init__(self, attack_range: dict) -> None:
        """
        attack_range: {
            "left": int,      # 캐릭터 중심 기준 왼쪽 픽셀
            "right": int,     # 캐릭터 중심 기준 오른쪽 픽셀
            "vertical": int,  # 상하 픽셀 (캐릭터 중심 기준 ±vertical)
            "y_offset": int,  # Y 중심 오프셋 (음수=위쪽)
        }
        """
        self._ar = attack_range

    def _attack_box(self, char_cx: int, char_cy: int) -> tuple[int, int, int, int]:
        """공격 범위 박스 (x1, y1, x2, y2)."""
        cy = char_cy + self._ar.get("y_offset", 0)
        v  = self._ar.get("vertical", 180)
        return (
            char_cx - self._ar.get("left",  300),
            cy - v,
            char_cx + self._ar.get("right", 300),
            cy + v,
        )

    @staticmethod
    def _monster_center(m: dict) -> tuple[int, int]:
        x1, y1, x2, y2 = m["box"]
        return (x1 + x2) // 2, (y1 + y2) // 2

    def calculate(
        self,
        character_center: tuple[int, int],
        monsters: list[dict],
    ) -> dict:
        """
        반환: {"direction": "left"|"right"|None, "can_attack": bool}
        """
        if not monsters:
            return {"direction": None, "can_attack": False}

        cx, cy = character_center
        ax1, ay1, ax2, ay2 = self._attack_box(cx, cy)

        # 공격 범위 내 몬스터 필터
        in_range = [
            m for m in monsters
            if ax1 <= self._monster_center(m)[0] <= ax2
            and ay1 <= self._monster_center(m)[1] <= ay2
        ]
        can_attack = len(in_range) > 0

        # 우선순위 1: 공격 범위 내 몬스터 있으면 제자리
        if can_attack:
            return {"direction": None, "can_attack": True}

        # 좌/우 분류
        left_monsters  = [m for m in monsters if self._monster_center(m)[0] < cx]
        right_monsters = [m for m in monsters if self._monster_center(m)[0] >= cx]

        # 우선순위 2: 수 비교
        if len(left_monsters) > len(right_monsters):
            return {"direction": "left", "can_attack": False}
        if len(right_monsters) > len(left_monsters):
            return {"direction": "right", "can_attack": False}

        # 우선순위 3: 동수 — 더 가까운 몬스터가 있는 쪽
        def _closest_dist(ms):
            if not ms:
                return float("inf")
            return min(abs(self._monster_center(m)[0] - cx) for m in ms)

        dl = _closest_dist(left_monsters)
        dr = _closest_dist(right_monsters)
        if dl < dr:
            return {"direction": "left",  "can_attack": False}
        if dr < dl:
            return {"direction": "right", "can_attack": False}

        # 우선순위 4: 완전 동일 → None
        return {"direction": None, "can_attack": False}
