# BlockRunner — Block 시퀀스를 실행해 목표 X로 이동. C CoordScriptRunner 방식 + Humanizer 경유
# 모든 입력은 Humanizer(M1)를 통과한다(헌법). runner는 백엔드를 직접 들지 않는다.
from __future__ import annotations

import time
from typing import Callable

from core.navigation.block import Block
from core.humanize.intent import Intent

# C CoordScriptRunner/routine_runner 검증 상수
TOLERANCE = 3           # 도착 판정 픽셀 (이 이내면 도달)
MOVE_STUCK_POLLS = 30   # 이 횟수(≈1.5s) 동안 목표에 한 번도 가까워지지 않으면 포기(벽 판정)
TELEPORT_MIN_DIST = 15  # 이 거리 초과면 teleport, 이하면 walk 폴백
LADDER_X_TOL = 4        # 사다리 X 도달 판정 픽셀
JUMP_GRAB_OFFSET = 8    # 사다리에서 이만큼 떨어진 '접근점'에서 사다리 쪽으로 점프(A/B/C jump_offset)
MAX_GRAB_RETRY = 3      # 사다리 못 잡으면 재접근·재점프 재시도 횟수(A/B/C 재시도)
CLIMB_STUCK_POLLS = 16  # 등반 중 이 횟수(≈0.8s) y가 안 올라가면 '못 잡음'으로 보고 재시도
Y_ARRIVE_TOL = 2        # 사다리 등반/하강 도착 판정 Y (C: y <= y_top+2)
SAME_LEVEL_TOL = 2      # |char_y - y_bot| ≤ 이 값이면 사다리 밑 같은 층 (C _do_ladder)
LADDER_HANG_SEC = 0.5   # 점프 후 ↑로 사다리 매달리는 안정화 시간 (C 0.5)
LADDER_TOP_SETTLE_SEC = 0.45  # 정점(y_top) 도달 후 ↑ 추가 유지 — 로프에서 발판으로 올라서기(dismount)
CONFIRM_MOVE_POLLS = 8   # 발판 확인: 좌우로 이 횟수(≈0.4s)까지 밀어보며 x 변화 관찰
CONFIRM_MOVE_PX = 3      # x가 사다리에서 이만큼 벗어나면 '발판 위(좌우 이동됨)' = 등반 완료
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
                 dwell_fn: Callable[[], bool] | None = None,
                 poll_sec: float = 0.05,
                 floor_judge=None, recovery_graph=None, max_recover: int = 3,
                 on_segment_enter: Callable[[Block], None] | None = None,
                 on_segment_exit: Callable[[Block], None] | None = None,
                 log_fn: Callable[[str], None] | None = None):
        self._h = humanizer
        self._pos = pos_fn
        self._jump_key = jump_key
        self._tele_key = teleport_key
        self._sleep = sleep_fn or time.sleep
        self._stop = stop_fn or (lambda: False)
        # True면 이동 중 그 자리에 정지(park) — 밀집 사냥(DWELL) 동안 메인 틱이 공격하게 양보
        self._dwell = dwell_fn or (lambda: False)
        self._poll = poll_sec
        self._judge = floor_judge
        self._graph = recovery_graph
        self._max_recover = max_recover
        self._on_seg_enter = on_segment_enter   # callable(Block) | None — 블록 진입 통지
        self._on_seg_exit = on_segment_exit     # callable(Block) | None — 블록 이탈 통지(finally)
        self._log = log_fn or (lambda m: None)  # UI 로그 콜백(동작 가시화)
        self._last_log = None                   # 직전 로그(연속 중복 억제)

    def release_inputs(self) -> None:
        """유지 중인 모든 입력키 해제(정지/이탈 시 키 눌림 방지)."""
        self._h.release_all()

    def _log_once(self, msg: str) -> None:
        """직전과 같은 메시지는 생략(루트 반복 중 로그 폭주 방지)."""
        if msg != self._last_log:
            self._last_log = msg
            self._log(msg)

    @staticmethod
    def _desc(block: Block) -> str:
        """블록을 사람이 읽는 한국어 한 줄로."""
        t = block.type
        if t == "move":
            if block.end_x > block.start_x:
                mode = {"count": f"왕복{block.sweeps}", "infinite": "무한왕복",
                        "pass": "통과"}.get(block.mode, block.mode)
                return f"이동 {block.start_x}~{block.end_x} ({mode})"
            return f"이동 →{block.target_x}"
        if t == "ladder":
            return f"사다리 {'등반' if block.ladder_dir == 'up' else '하강'} x={block.ladder_x}"
        if t == "jump":
            return "점프"
        if t == "attack":
            return f"공격 {block.skill_key}"
        return t

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
            self._log_once(f"⤴ 층 이탈 감지(현재 {cur.name}≠목표 {want}, y={y}) → 사다리로 복귀")
            self._do_ladder(Block.from_dict(path[0]), max_steps)

    def run_block(self, block: Block, max_steps: int = 200) -> bool:
        if self._on_seg_enter is not None:
            self._on_seg_enter(block)
        self._log_once(f"▶ {self._desc(block)}")
        try:
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
                                          infinite=infinite, margin=block.rand_margin)
                return self._exec_move(block, max_steps)
            if block.type == "ladder":
                return self._do_ladder(block, max_steps)
            if block.type == "jump":
                return self._do_jump(block)
            return True
        finally:
            if self._on_seg_exit is not None:
                self._on_seg_exit(block)

    def _sweep_targets(self, start_x: int, end_x: int, margin: int) -> tuple[float, float]:
        """이번 왕복의 (끝쪽 턴, 시작쪽 턴) 목표. margin>0이면 구간 안에서 매번 랜덤(소수점4자리):
        끝=[end-margin, end], 시작=[start, start+margin] — 설정 구간을 벗어나지 않음."""
        if margin <= 0:
            return float(end_x), float(start_x)
        m = min(margin, max(0, (end_x - start_x)))   # 마진이 구간보다 크면 구간으로 제한
        end_t = self._h.rand_in(end_x - m, end_x)
        start_t = self._h.rand_in(start_x, start_x + m)
        return end_t, start_t

    def run_sweep(self, start_x: int, end_x: int, sweeps: int,
                  move_type: str = "walk", max_steps: int = 200,
                  step_fn=None, infinite: bool = False, margin: int = 0) -> bool:
        """start_x ~ end_x 사이를 sweeps회 왕복. 한 sweep = 끝→시작 1회.

        infinite=True면 stop_fn()이 True가 될 때까지 무한 왕복.
        margin>0이면 매 왕복 끝점을 구간 안에서 랜덤화(소수점4자리, 매번 다른 지점에서 턴).
        step_fn: 테스트용 위치 강제 콜백(실기에선 None=실제 이동).
        """
        def one_sweep() -> bool:
            end_t, start_t = self._sweep_targets(start_x, end_x, margin)
            for tx in (end_t, start_t):   # 끝으로 갔다 시작으로 = 1왕복(매번 랜덤 끝점)
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
        """target_x 까지 walk/teleport 로 접근. TOLERANCE 이내 도달 시 True.

        '진척 기반' 끼임 판정: 목표까지 거리가 한 번이라도 줄면 리셋. MOVE_STUCK_POLLS회
        (≈1.5초) 동안 한 번도 가까워지지 않으면 포기 — 거친 미니맵에서 캐릭터가 느리게
        움직여 x가 잠깐 안 변해도 거짓 '멈춤'이 안 되게 한다(벽일 때만 포기)."""
        best = None
        no_progress = 0
        for _ in range(max_steps):
            # 밀집 사냥(DWELL) 중엔 이동키 떼고 제자리 정지 — 메인 틱이 공격. 해제되면 이동 재개.
            while self._dwell() and not self._stop():
                self._h.release_dir()
                self._jsleep(self._poll)
            if self._stop():
                self._h.release_dir()
                return False
            x, _y = self._pos()
            dist = block.target_x - x
            if abs(dist) <= TOLERANCE:
                self._h.release_dir()   # 도착 시 이동키 떼기 → 목표 지나침(overshoot) 방지·정지
                return True   # 도착 (폐루프 종료)

            if best is None or abs(dist) < best:
                best = abs(dist)          # 목표에 조금이라도 가까워짐 → 진척
                no_progress = 0
            else:
                no_progress += 1
                if no_progress >= MOVE_STUCK_POLLS:
                    self._h.release_dir()   # 포기 시 이동키 떼기(눌림 방지)
                    self._log_once(
                        f"⚠ 이동 멈춤: x={x}→목표 {block.target_x} 진척 없음(벽/좌표 확인)")
                    return False

            direction = "right" if dist > 0 else "left"
            use_tele = (block.move_type == "teleport" and abs(dist) > TELEPORT_MIN_DIST)

            # 좌우 이동키는 '한 번 누르고 계속 유지'(C _walk_to_x). 방향이 바뀌면
            # hold_dir가 기존 키를 떼고 새 키를 누른다. 도착 전까진 떼지 않는다.
            self._h.hold_dir(direction)
            if use_tele:
                # 방향 유지한 채 텔포 키 (C _teleport_to_x)
                self._h.perform(Intent(action="key", key=self._tele_key, base_hold_sec=0.05))
            # 다음 위치 갱신을 기다린다 — 안 쉬면 스캐너(≈0.05s)보다 빨리 읽어
            # 위치가 안 변한 것처럼 보여 거짓 '멈춤'이 된다(시작 시 좌표 미수신 포함).
            self._jsleep(self._poll)
        return False

    # ── 사다리 (A/B/C map_navigator 방식 포팅: 접근점 점프 + 재시도 + 등반 진척감지) ──
    def _do_ladder(self, block: Block, max_steps: int) -> bool:
        """up: 접근점에서 사다리 쪽으로 점프+↑ 잡기(못 잡으면 재시도). down: 사다리 X에서 뛰어내림."""
        x, y = self._pos()
        if x is None or y is None:
            self._h.release_all()
            return False   # 좌표 인식 실패 — 스킵
        if block.ladder_dir == "down":
            self._exec_move(Block(type="move", target_x=block.ladder_x, move_type="walk"),
                            max_steps)   # 하강은 사다리 X에 서서 뛰어내림
            return self._descend_ladder(block.exit_side, block.y_bot, max_steps)
        return self._climb_with_retry(block, max_steps)

    def _climb_with_retry(self, block: Block, max_steps: int) -> bool:
        """등반 시도 → 못 잡으면(y가 안 올라감) 재접근·재점프 재시도(A/B/C 재시도).
        매 시도 현재 위치로 방향을 재계산 → 사다리를 지나쳤으면 반대로 돌아 '쳐다보고' 점프."""
        for attempt in range(1, MAX_GRAB_RETRY + 1):
            if self._stop():
                self._h.release_all(); return False
            # 등반 도중 몬스터에 맞아 다른 층으로 떨어졌을 수 있음 → 매 시도 현재 층 확인,
            # 사다리 바닥층이 아니면 그래프로 먼저 복귀(엉뚱한 사다리 헛잡기 방지).
            self._recover_if_needed(block, max_steps)
            x, y = self._pos()
            if x is None or y is None:
                self._h.release_all(); return False
            side = self._grab_side(block, x)   # 잡기·발판확인에 쓸 한 방향
            if abs(y - block.y_bot) <= SAME_LEVEL_TOL:
                # 같은 층(사다리 밑): 사다리 X로 가서 ↑만
                self._log_once(f"사다리 등반(같은층) x={block.ladder_x}, y {y}→{block.y_top}")
                self._exec_move(Block(type="move", target_x=block.ladder_x, move_type="walk"),
                                max_steps)
                ok = self._climb_hold_until(block.ladder_x, block.y_top, max_steps, side)
            else:
                self._log_once(
                    f"사다리 점프잡기 x={block.ladder_x} ({side}) 시도 {attempt}/{MAX_GRAB_RETRY}, "
                    f"y {y}→{block.y_top}")
                ok = self._jump_grab(block.ladder_x, side, block.y_top, max_steps,
                                     getattr(block, "jump_offset", JUMP_GRAB_OFFSET))
            if ok:
                self._log_once("✓ 사다리 등반 완료")
                return True
            self._h.release_all()
            self._log_once(f"↻ 사다리 못 잡음 → 재시도 {attempt}/{MAX_GRAB_RETRY}")
            self._jsleep(0.2)
        self._log_once(
            f"⚠ 사다리 등반 실패(재시도 {MAX_GRAB_RETRY}회 소진) — 사다리 X/Y·접근 확인")
        return False

    def _grab_side(self, block: Block, char_x: int) -> str:
        """밧줄 잡을 때 누를 좌우 방향. auto=가까운쪽(C방식)/left/right/random=좌우랜덤."""
        gs = getattr(block, "grab_side", "auto")
        if gs in ("left", "right"):
            return gs
        if gs == "random":
            return self._h.random_side()
        return "left" if block.ladder_x < char_x else "right"   # auto

    def _climb_loop(self, y_top: int, max_steps: int) -> bool:
        """↑가 눌린 상태에서 y_top까지 등반. 도달 시 True. y가 CLIMB_STUCK_POLLS 동안
        한 번도 안 줄면(로프 못 잡음/미끄러짐) False → 호출부가 재시도한다."""
        best = None
        no_prog = 0
        start_y = None
        for _ in range(max_steps):
            if self._stop():
                return False
            _x, y = self._pos()
            if y is None:
                return False
            if start_y is None:
                start_y = y
                # 시작 시점에 이미 목표(y_top) 이하 = 오를 거리가 없음(잘못된 사다리 Y/이미 위층).
                # 등반이 아니므로 '도착'으로 보지 않는다 — 한 칸도 안 올라갔는데 허위 '등반 완료'가
                # 떠서 같은 층에서 좌우만 하던 버그 방지(사용자 보고: y 안 바뀌었는데 층이동 표기).
                if start_y <= y_top + Y_ARRIVE_TOL:
                    return False
            if y <= y_top + Y_ARRIVE_TOL:
                return True   # 층 도착
            if best is None or y < best:
                best = y       # 조금이라도 올라감 → 진척
                no_prog = 0
            else:
                no_prog += 1
                if no_prog >= CLIMB_STUCK_POLLS:
                    return False   # y 안 줄어듦 = 못 잡음 → 재시도
            self._jsleep(self._poll)
        return False

    def _confirm_on_platform(self, ladder_x: int, confirm_dir: str, max_steps: int) -> bool:
        """발판 확인 = 등반 완료 판정의 핵심: confirm_dir 한 방향으로만 밀어 x가 사다리에서
        벗어나면(=발판 위) True. 로프 매달림이면 x 안 변함 → False(재시도).
        한 방향만 써서 좌우 왔다갔다(이상한 움직임) 없음. (사용자 정의: 그 층 y에서 좌/우 이동돼야 완료)"""
        self._h.release("up")            # 로프에서 ↑ 떼야 좌우 이동 가능
        self._h.hold_dir(confirm_dir)
        try:
            for _ in range(CONFIRM_MOVE_POLLS):
                if self._stop():
                    return False
                self._jsleep(self._poll)
                x, _y = self._pos()
                if x is not None and abs(x - ladder_x) >= CONFIRM_MOVE_PX:
                    return True           # 한 방향으로 이동됨 = 발판 위 = 등반 완료
            return False                  # 안 움직임 = 아직 로프 → 미완료(재시도)
        finally:
            self._h.release_dir()

    def _finish_climb(self, ladder_x: int, y_top: int, max_steps: int, confirm_dir: str) -> bool:
        """↑ 등반 → 정점 후 ↑ 더(dismount) → confirm_dir 한 방향 이동으로 발판 확인 → 완료(True)."""
        self._h.hold("up")
        try:
            if not self._climb_loop(y_top, max_steps):
                return False
            self._jsleep(LADDER_TOP_SETTLE_SEC)   # 발판으로 올라서기
            return self._confirm_on_platform(ladder_x, confirm_dir, max_steps)
        finally:
            self._h.release("up")

    def _climb_hold_until(self, ladder_x: int, y_top: int, max_steps: int,
                          confirm_dir: str) -> bool:
        """같은 층(사다리 밑)에서 ↑만으로 등반 + 발판 확인(한 방향)."""
        return self._finish_climb(ladder_x, y_top, max_steps, confirm_dir)

    def _grab_offset(self, base: int) -> float:
        """점프 접근 거리: 설정 base에서 ±10% 랜덤(소수점4자리). base<=0이면 0(사다리 X에서 점프)."""
        if base <= 0:
            return 0.0
        return self._h.rand_in(base * 0.9, base * 1.1, 4)

    def _jump_grab(self, ladder_x: int, side: str, y_top: int, max_steps: int,
                   jump_offset: int = JUMP_GRAB_OFFSET) -> bool:
        """접근점(사다리에서 side 반대쪽으로 jump_offset±10% 떨어진 곳)으로 가서, 거기서
        사다리 쪽으로 점프+↑ 잡기 → y_top까지 등반 (A/B/C jump_offset 접근 점프, 거리 랜덤)."""
        # 접근점: side=right면 사다리 왼쪽(ladder_x-offset)에서 오른쪽으로 점프해 잡음. 거리 ±10% 랜덤
        offset = self._grab_offset(jump_offset)
        approach_x = (ladder_x - offset if side == "right"
                      else ladder_x + offset)
        self._h.hold_dir(side)
        reached = False
        for _ in range(max_steps):
            if self._stop():
                self._h.release_all(); return False
            x, _y = self._pos()
            if x is not None and ((side == "right" and x >= approach_x) or
                                  (side == "left" and x <= approach_x)):
                reached = True
                break
            self._jsleep(self._poll)
        if not reached:
            self._h.release_all()
            return False
        # 사다리 쪽으로 점프(방향 유지=모멘텀) → ↑ 매달림 → 방향키 해제
        self._h.perform(Intent(action="key", key=self._jump_key, base_hold_sec=0.05))
        self._jsleep(0.05)
        self._h.hold("up")
        self._jsleep(LADDER_HANG_SEC)
        self._h.release_dir()
        self._h.release("up")           # 점프잡기 안정화 ↑ 해제 후 _finish_climb이 다시 등반
        # y_top까지 등반 + 발판 확인(side 한 방향 이동돼야 완료). 미확인이면 False로 재시도 유도
        return self._finish_climb(ladder_x, y_top, max_steps, side)

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
        """단순 점프 — 방향 키(있으면) 유지한 채 점프키 1회(C _do_jump). 점프 후 키 정리."""
        if block.direction in ("left", "right"):
            self._h.hold_dir(block.direction)
        elif block.direction == "down":
            self._h.hold("down")
        self._h.perform(Intent(action="key", key=self._jump_key, base_hold_sec=0.05))
        if block.direction == "down":
            self._h.release("down")
        elif block.direction in ("left", "right"):
            self._h.release_dir()   # 점프 후 방향키 떼기(잔류 이동 방지)
        return True
