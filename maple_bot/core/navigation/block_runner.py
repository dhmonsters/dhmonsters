# BlockRunner — Block 시퀀스를 실행해 목표 X로 이동. C CoordScriptRunner 방식 + Humanizer 경유
# 모든 입력은 Humanizer(M1)를 통과한다(헌법). runner는 백엔드를 직접 들지 않는다.
from __future__ import annotations

from typing import Callable

from core.navigation.block import Block
from core.humanize.intent import Intent

# C CoordScriptRunner 검증 상수
TOLERANCE = 3           # 도착 판정 픽셀 (이 이내면 도달)
TELEPORT_MIN_DIST = 15  # 이 거리 초과면 teleport, 이하면 walk 폴백


class BlockRunner:
    """Block 시퀀스를 순차 실행한다.

    pos_fn: callable() -> (x, y)  현재 캐릭터 위치(공유 위치상태, CharScanner가 갱신)
    humanizer: Intent 를 받아 사람같은 입력으로 송출 (M1)
    """

    def __init__(self, humanizer, pos_fn: Callable[[], tuple[int, int]],
                 jump_key: str = "alt", teleport_key: str = "space"):
        self._h = humanizer
        self._pos = pos_fn
        self._jump_key = jump_key
        self._tele_key = teleport_key

    def run_route(self, blocks: list[Block], max_steps: int = 200) -> bool:
        """블록 리스트를 순서대로 실행. 모두 성공하면 True."""
        for b in blocks:
            if not self.run_block(b, max_steps=max_steps):
                return False
        return True

    def run_block(self, block: Block, max_steps: int = 200) -> bool:
        if block.type == "move":
            return self._exec_move(block, max_steps)
        # attack/ladder/jump 는 후속 태스크에서 — 지금은 move 만
        return True

    # ── 이동 ──────────────────────────────────────────────────────────
    def _exec_move(self, block: Block, max_steps: int) -> bool:
        """target_x 까지 walk/teleport 로 접근. TOLERANCE 이내 도달 시 True."""
        last_x = None
        stuck = 0
        for _ in range(max_steps):
            x, _y = self._pos()
            dist = block.target_x - x
            if abs(dist) <= TOLERANCE:
                return True   # 도착 (폐루프 종료)

            # 끼임 감지: 위치가 안 변하면 카운트, 일정 횟수 넘으면 포기
            if last_x is not None and x == last_x:
                stuck += 1
                if stuck >= 5:
                    return False
            else:
                stuck = 0
            last_x = x

            direction = "right" if dist > 0 else "left"
            use_tele = (block.move_type == "teleport" and abs(dist) > TELEPORT_MIN_DIST)

            if use_tele:
                # 방향을 향한 뒤 텔포 키 (C _teleport_to_x)
                self._h.perform(Intent(action="move_dir", key=direction))
                self._h.perform(Intent(action="key", key=self._tele_key, base_hold_sec=0.05))
            else:
                # walk: 방향키 입력 (C _walk_to_x)
                self._h.perform(Intent(action="key", key=direction, base_hold_sec=0.08))
        return False
