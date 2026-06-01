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
            # 구간 왕복 모드: start_x < end_x 이고 sweeps>=1
            if block.end_x > block.start_x and block.sweeps >= 1:
                return self.run_sweep(block.start_x, block.end_x, block.sweeps,
                                      block.move_type, max_steps=max_steps)
            return self._exec_move(block, max_steps)
        # attack/ladder/jump 는 후속 태스크에서 — 지금은 move 만
        return True

    def run_sweep(self, start_x: int, end_x: int, sweeps: int,
                  move_type: str = "walk", max_steps: int = 200,
                  step_fn=None) -> bool:
        """start_x ~ end_x 사이를 sweeps회 왕복. 한 sweep = 끝→시작 1회.

        step_fn: 테스트용 위치 강제 콜백(실기에선 None=실제 이동).
        """
        targets = []
        for _ in range(sweeps):
            targets += [end_x, start_x]   # 끝으로 갔다 시작으로 = 1왕복
        for tx in targets:
            blk = Block(type="move", target_x=tx, move_type=move_type)
            if step_fn is not None:
                step_fn(tx)               # 테스트: 즉시 도달
            elif not self._exec_move(blk, max_steps):
                return False
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

            # 좌우 이동키는 '한 번 누르고 계속 유지'(C _walk_to_x). 방향이 바뀌면
            # hold_dir가 기존 키를 떼고 새 키를 누른다. 도착 전까진 떼지 않는다.
            self._h.hold_dir(direction)
            if use_tele:
                # 방향 유지한 채 텔포 키 (C _teleport_to_x)
                self._h.perform(Intent(action="key", key=self._tele_key, base_hold_sec=0.05))
        return False
