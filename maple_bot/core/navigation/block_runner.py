# BlockRunner — Block 시퀀스를 실행해 목표 X로 이동. C CoordScriptRunner 방식 + Humanizer 경유
# 모든 입력은 Humanizer(M1)를 통과한다(헌법). runner는 백엔드를 직접 들지 않는다.
from __future__ import annotations

import time
from typing import Callable

from core.navigation.block import Block
from core.humanize.intent import Intent

# C CoordScriptRunner/routine_runner 검증 상수
TOLERANCE = 3           # 도착 판정 픽셀 (이 이내면 도달)
TELEPORT_MIN_DIST = 15  # 이 거리 초과면 teleport, 이하면 walk 폴백
LADDER_X_TOL = 4        # 사다리 X ±이 값 진입 시 점프 잡기 (C _jump_grab_ladder)
Y_ARRIVE_TOL = 2        # 사다리 등반/하강 도착 판정 Y (C: y <= y_top+2)
SAME_LEVEL_TOL = 2      # |char_y - y_bot| ≤ 이 값이면 사다리 밑 같은 층 (C _do_ladder)
LADDER_HANG_SEC = 0.5   # 점프 후 ↑로 사다리 매달리는 안정화 시간 (C 0.5)
DESCEND_DOWN_SEC = 1.0  # 하강 시 ↓ 선홀드 시간 (C _descend_ladder_jump 1초)


class BlockRunner:
    """Block 시퀀스를 순차 실행한다.

    pos_fn: callable() -> (x, y)  현재 캐릭터 위치(공유 위치상태, CharScanner가 갱신)
    humanizer: Intent 를 받아 사람같은 입력으로 송출 (M1)
    stop_fn:  callable() -> bool  True면 무한왕복/등반 루프 중단(정지/안전)
    """

    def __init__(self, humanizer, pos_fn: Callable[[], tuple[int, int]],
                 jump_key: str = "alt", teleport_key: str = "space",
                 sleep_fn: Callable[[float], None] | None = None,
                 stop_fn: Callable[[], bool] | None = None,
                 poll_sec: float = 0.05,
                 floor_judge=None, recovery_graph=None, max_recover: int = 3):
        self._h = humanizer
        self._pos = pos_fn
        self._jump_key = jump_key
        self._tele_key = teleport_key
        self._sleep = sleep_fn or time.sleep
        self._stop = stop_fn or (lambda: False)
        self._poll = poll_sec
        self._judge = floor_judge
        self._graph = recovery_graph
        self._max_recover = max_recover

    def _jsleep(self, base: float) -> None:
        """고정 타이밍을 Humanizer로 ±0.05 지터해 대기(어떤 고정 수치도 매번 다르게)."""
        self._sleep(self._h.jitter_sec(base))

    def run_route(self, blocks: list[Block], max_steps: int = 200) -> bool:
        """블록 리스트를 순서대로 실행. 모두 성공하면 True."""
        for b in blocks:
            if self._stop():
                return False
            if not self.run_block(b, max_steps=max_steps):
                return False
        return True

    def _recover_if_needed(self, block: Block, max_steps: int) -> None:
        """현재 층이 블록의 기대 층과 다르면 그래프 최단경로의 사다리를 타고 복귀.
        judge/graph 미주입이거나 기대층 None이면 아무것도 안 함."""
        if self._judge is None or not self._graph:
            return
        from core.navigation.map_graph import expected_floor, shortest_path
        want = expected_floor(block.to_dict(), self._judge)
        if want is None:
            return
        for _ in range(self._max_recover):
            _x, y = self._pos()
            cur = self._judge.floor_at(y)
            if cur is None or cur.name == want:
                return
            path = shortest_path(self._graph, cur.name, want)
            if not path:
                return                       # 복구 불가 → 그냥 진행
            self._do_ladder(Block.from_dict(path[0]), max_steps)

    def run_block(self, block: Block, max_steps: int = 200) -> bool:
        self._recover_if_needed(block, max_steps)
        if block.type == "move":
            # 구간 모드: start_x < end_x 이면 mode(count/infinite/pass)에 따라 왕복/통과
            if block.end_x > block.start_x:
                if block.mode == "pass":
                    # 통과: 구간을 한 방향으로 1회만 지나감(end_x까지)
                    return self._exec_move(
                        Block(type="move", target_x=block.end_x, move_type=block.move_type),
                        max_steps)
                infinite = (block.mode == "infinite")
                sweeps = max(1, block.sweeps)
                return self.run_sweep(block.start_x, block.end_x, sweeps,
                                      block.move_type, max_steps=max_steps,
                                      infinite=infinite)
            return self._exec_move(block, max_steps)
        if block.type == "ladder":
            return self._do_ladder(block, max_steps)
        if block.type == "jump":
            return self._do_jump(block)
        return True

    def run_sweep(self, start_x: int, end_x: int, sweeps: int,
                  move_type: str = "walk", max_steps: int = 200,
                  step_fn=None, infinite: bool = False) -> bool:
        """start_x ~ end_x 사이를 sweeps회 왕복. 한 sweep = 끝→시작 1회.

        infinite=True면 stop_fn()이 True가 될 때까지 무한 왕복.
        step_fn: 테스트용 위치 강제 콜백(실기에선 None=실제 이동).
        """
        def one_sweep() -> bool:
            for tx in (end_x, start_x):   # 끝으로 갔다 시작으로 = 1왕복
                if self._stop():
                    return False
                blk = Block(type="move", target_x=tx, move_type=move_type)
                if step_fn is not None:
                    step_fn(tx)           # 테스트: 즉시 도달
                elif not self._exec_move(blk, max_steps):
                    return False
            return True

        if infinite:
            while not self._stop():
                if not one_sweep():
                    return False
            return True
        for _ in range(sweeps):
            if not one_sweep():
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

    # ── 사다리 (C routine_runner._do_ladder 방식, 비전 기반) ───────────
    def _do_ladder(self, block: Block, max_steps: int) -> bool:
        """ladder_dir=up이면 사다리 X로 가서 등반(같은층 ↑ / 그 외 점프잡기),
        down이면 지정 X에서 ↓+좌우+점프로 뛰어내림. y 좌표로 층 도착 확인."""
        # 1) 사다리 X로 먼저 이동 (C: _do_move {'x': ladder_x})
        self._exec_move(Block(type="move", target_x=block.ladder_x, move_type="walk"),
                        max_steps)
        x, y = self._pos()
        if x is None or y is None:
            self._h.release_all()
            return False   # 좌표 인식 실패 — 스킵

        if block.ladder_dir == "down":
            return self._descend_ladder(block.exit_side, block.y_bot, max_steps)

        # up: 같은 층(사다리 밑)이면 ↑만, 아니면 점프 잡기
        if abs(y - block.y_bot) <= SAME_LEVEL_TOL:
            return self._climb_up_until(block.y_top, max_steps)
        side = self._grab_side(block, x)
        return self._jump_grab(block.ladder_x, side, block.y_top, max_steps)

    def _grab_side(self, block: Block, char_x: int) -> str:
        """밧줄 잡을 때 누를 좌우 방향. auto=가까운쪽(C방식)/left/right/random=좌우랜덤."""
        gs = getattr(block, "grab_side", "auto")
        if gs in ("left", "right"):
            return gs
        if gs == "random":
            return self._h.random_side()
        return "left" if block.ladder_x < char_x else "right"   # auto

    def _climb_up_until(self, y_top: int, max_steps: int) -> bool:
        """↑ 키를 누른 채 유지 → y ≤ y_top+2 도달까지 등반(C _climb_ladder_up_until)."""
        self._h.hold("up")
        try:
            for _ in range(max_steps):
                if self._stop():
                    return False
                _x, y = self._pos()
                if y is not None and y <= y_top + Y_ARRIVE_TOL:
                    return True   # 층 도착 확인
                self._jsleep(self._poll)
            return False
        finally:
            self._h.release("up")

    def _jump_grab(self, ladder_x: int, side: str, y_top: int, max_steps: int) -> bool:
        """좌/우 누른 채 사다리 X로 접근 → ±4 진입 시 점프+↑ 잡기 → y_top까지 등반
        (C _jump_grab_ladder)."""
        # 1) side 홀드로 접근
        self._h.hold_dir(side)
        reached = False
        for _ in range(max_steps):
            if self._stop():
                self._h.release_all(); return False
            x, _y = self._pos()
            if x is not None and abs(x - ladder_x) <= LADDER_X_TOL:
                reached = True
                break
            self._jsleep(self._poll)
        if not reached:
            self._h.release_all()
            return False
        # 2) 점프 + ↑ 잡기 (C: press jump → 0.05 → keyDown up → 0.5 매달림 → keyUp side)
        self._h.perform(Intent(action="key", key=self._jump_key, base_hold_sec=0.05))
        self._jsleep(0.05)
        self._h.hold("up")
        self._jsleep(LADDER_HANG_SEC)
        self._h.release_dir()
        # 3) y_top 까지 등반 + 도착 확인
        try:
            for _ in range(max_steps):
                if self._stop():
                    return False
                _x, y = self._pos()
                if y is not None and y <= y_top + Y_ARRIVE_TOL:
                    return True
                self._jsleep(self._poll)
            return False
        finally:
            self._h.release("up")

    def _descend_ladder(self, exit_side: str, y_bot: int, max_steps: int) -> bool:
        """지정 X에서 ↓ 1초 + 좌/우 + 점프 → 사다리에서 뛰어내림(C _descend_ladder_jump).
        y가 y_bot 근처(아래 발판)로 내려오면 도착."""
        side = self._h.random_side() if exit_side not in ("left", "right") else exit_side
        self._h.hold("down")
        self._jsleep(DESCEND_DOWN_SEC)
        self._h.hold_dir(side)
        self._h.perform(Intent(action="key", key=self._jump_key, base_hold_sec=0.05))
        self._jsleep(0.1)
        self._h.release("down")
        self._h.release_dir()
        for _ in range(max_steps):
            if self._stop():
                return False
            _x, y = self._pos()
            if y is not None and abs(y - y_bot) <= Y_ARRIVE_TOL:
                return True   # 아래 발판 도착
            self._jsleep(self._poll)
        return True   # 하강은 도착 확인 약해도 완료 처리(C와 동일 성향)

    def _do_jump(self, block: Block) -> bool:
        """단순 점프 — 방향 키(있으면) 유지한 채 점프키 1회(C _do_jump)."""
        if block.direction in ("left", "right"):
            self._h.hold_dir(block.direction)
        elif block.direction == "down":
            self._h.hold("down")
        self._h.perform(Intent(action="key", key=self._jump_key, base_hold_sec=0.05))
        if block.direction == "down":
            self._h.release("down")
        return True
