# BlockRunner - Block 시퀀스를 실행해 목표 X로 이동한다.
# 방향키는 RouteInputOwner가 유지하고 단발 입력은 입력 백엔드로 직접 전달한다.
from __future__ import annotations

import time
import random
from dataclasses import dataclass, replace
from typing import Callable

from core.navigation.block import Block
from core.navigation.route_input_owner import RouteInputOwner
from core.humanize.intent import Intent
from core.humanize.priority_input_executor import PriorityInputExecutor

# C CoordScriptRunner/routine_runner 검증 상수
TOLERANCE = 3           # 도착 판정 픽셀 (이 이내면 도달)
MOVE_STUCK_POLLS = 30   # 이 횟수(≈1.5s) 동안 목표에 한 번도 가까워지지 않으면 포기(벽 판정)
TELEPORT_MIN_DIST = 15  # 이 거리 초과면 teleport, 이하면 walk 폴백
LADDER_X_TOL = 4        # 사다리 X 도달 판정 픽셀
JUMP_GRAB_OFFSET = 1    # 사다리에서 이만큼만 뒤로 떨어진 '접근점'에서 사다리 쪽으로 점프(아주 가까이)
MAX_GRAB_RETRY = 5      # 사다리 못 잡으면 재접근·재점프 재시도 횟수
JUMP_TO_UP_SEC = 0.02   # 점프 후 ↑ 전환 지연(작을수록 빠르게 사다리 잡음)
CLIMB_STUCK_POLLS = 16  # 등반 중 이 횟수(≈0.8s) y가 안 올라가면 '못 잡음'으로 보고 재시도
Y_ARRIVE_TOL = 2        # 사다리 등반/하강 도착 판정 Y (C: y <= y_top+2)
SAME_LEVEL_TOL = 2      # |char_y - y_bot| ≤ 이 값이면 사다리 밑 같은 층 (C _do_ladder)
LADDER_HANG_SEC = 0.5   # 점프 후 ↑로 사다리 매달리는 안정화 시간 (C 0.5)
LADDER_TOP_SETTLE_SEC = 0.45  # 정점(y_top) 도달 후 ↑ 추가 유지 — 로프에서 발판으로 올라서기(dismount)
CONFIRM_MOVE_POLLS = 8   # 발판 확인: 좌우로 이 횟수(≈0.4s)까지 밀어보며 x 변화 관찰
CONFIRM_MOVE_PX = 3      # x가 사다리에서 이만큼 벗어나면 '발판 위(좌우 이동됨)' = 등반 완료


@dataclass(frozen=True)
class LadderProfile:
    launch_distance_right: float = 7.0
    launch_distance_left: float = 2.0
    jump_hold_sec: float = 0.10
    up_delay_sec: float = 0.125
    direction_hold_sec: float = 0.08
    stable_tolerance: int = 2
    stable_samples: int = 3
    position_max_age_sec: float = 0.15
    grab_confirm_sec: float = 1.00


class BlockRunner:
    """Block 시퀀스를 순차 실행한다.

    pos_fn: callable() -> (x, y)  현재 캐릭터 위치(공유 위치상태, CharScanner가 갱신)
    humanizer: Intent 를 받아 사람같은 입력으로 송출 (M1)
    stop_fn:  callable() -> bool  True면 무한왕복/등반 루프 중단(정지/안전)
    """

    def __init__(self, input_backend, pos_fn: Callable[[], tuple[int, int]],
                 jump_key: str = "alt", teleport_key: str = "space",
                 jump_while_move: bool = False,
                 sleep_fn: Callable[[float], None] | None = None,
                 stop_fn: Callable[[], bool] | None = None,
                 dwell_fn: Callable[[], bool] | None = None,
                 poll_sec: float = 0.05,
                 floor_judge=None, recovery_graph=None, max_recover: int = 3,
                 on_segment_enter: Callable[[Block], None] | None = None,
                 on_segment_exit: Callable[[Block], None] | None = None,
                 log_fn: Callable[[str], None] | None = None,
                 position_sample_fn=None, position_refresh_fn=None, monster_present_fn=None,
                 ladder_motion_fn=None, ladder_profile: dict | None = None,
                 minimap_size_fn: Callable[[], tuple[int, int]] | None = None):
        self._backend = input_backend
        self._route_inputs = RouteInputOwner(input_backend)
        self._priority_inputs = PriorityInputExecutor(input_backend, self._route_inputs, sleep_fn=sleep_fn)
        self._pos = pos_fn
        self._jump_key = jump_key
        self._jump_while_move = jump_while_move   # 걷기 동안 점프키 홀드(바니합)
        self._tele_key = teleport_key
        self._sleep = sleep_fn or time.sleep
        self._stop = stop_fn or (lambda: False)
        # True면 이동 중 그 자리에 정지(park) — 밀집 사냥(DWELL) 동안 메인 틱이 공격하게 양보
        self._dwell = dwell_fn or (lambda: False)
        self._poll = poll_sec
        self._judge = floor_judge
        self._graph = recovery_graph
        self._max_recover = max_recover
        self._position_sample = position_sample_fn
        self._position_refresh = position_refresh_fn
        self._monster_present = monster_present_fn or (lambda: False)
        self._ladder_motion = ladder_motion_fn or (lambda active: None)
        self._minimap_size = minimap_size_fn
        profile = ladder_profile or {}
        self._ladder_profile = LadderProfile(
            launch_distance_right=float(profile.get("launch_distance_right", 7.0)),
            launch_distance_left=float(profile.get("launch_distance_left", 2.0)),
            jump_hold_sec=float(profile.get("jump_hold_sec", 0.10)),
            up_delay_sec=float(profile.get("up_delay_sec", 0.125)),
            direction_hold_sec=float(profile.get("direction_hold_sec", 0.08)),
            stable_tolerance=int(profile.get("stable_tolerance", 2)),
            stable_samples=max(1, int(profile.get("stable_samples", 3))),
            position_max_age_sec=float(profile.get("position_max_age_sec", 0.60)),
            grab_confirm_sec=float(profile.get("grab_confirm_sec", 1.00)),
        )
        from core.navigation.ladder_controller import LadderController, LadderControllerConfig
        self._ladder_controller = LadderController(
            input_backend=self._backend,
            direction_owner=self._route_inputs,
            position_sample_fn=self._position_sample,
            position_fn=self._pos,
            finish_climb_fn=self._finish_climb,
            ladder_motion_fn=self._ladder_motion,
            stop_fn=self._stop,
            sleep_fn=self._sleep,
            log_fn=lambda message: self._log_once(message),
            jump_key=self._jump_key,
            config=LadderControllerConfig(
                launch_distance=float(profile.get("launch_distance", 5.0)),
                jump_hold_sec=self._ladder_profile.jump_hold_sec,
                up_delay_sec=self._ladder_profile.up_delay_sec,
                x_tolerance=3,
                y_rise_required=3,
                stable_samples=2,
                verify_timeout_sec=0.10,
                arrival_tolerance=Y_ARRIVE_TOL,
                poll_sec=0.03,
            ),
        )
        self._ladder_debug = None
        self._on_seg_enter = on_segment_enter   # callable(Block) | None — 블록 진입 통지
        self._on_seg_exit = on_segment_exit     # callable(Block) | None — 블록 이탈 통지(finally)
        self._log = log_fn or (lambda m: None)  # UI 로그 콜백(동작 가시화)
        self._last_log = None                   # 직전 로그(연속 중복 억제)
        self._up_input_call_samples: list[float] = []

    def release_inputs(self) -> None:
        """유지 중인 모든 입력키 해제(정지/이탈 시 키 눌림 방지)."""
        self._route_inputs.release_all()

    @property
    def teleport_key(self) -> str:
        return self._tele_key

    def ladder_debug_state(self):
        return self._ladder_controller.debug_state() or (
            dict(self._ladder_debug) if self._ladder_debug else None
        )

    def _fresh_position(self, stale_grace_sec: float = 0.0):
        if self._position_sample is None:
            return self._pos(), 0.0
        position, seen_at = self._position_sample()
        if position is None or seen_at is None:
            return None, None
        age = max(0.0, time.monotonic() - seen_at)
        max_age = max(0.0, self._ladder_profile.position_max_age_sec + stale_grace_sec)
        if age > max_age:
            return None, age
        return position, age

    def _get_pos(self):
        """좌표 샘플이 있으면 허용 시간 안의 최신 위치만 반환한다."""
        position, _age = self._fresh_position()
        return position

    def refresh_position(self):
        """CharScanner가 저장한 최신 좌표를 추가 캡처 없이 반환한다."""
        return self._fresh_position()

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
        """좌표 확인과 내부 상태 대기는 설정된 고정값을 그대로 사용한다."""
        self._sleep(max(0.0, float(base)))

    def _resolve_block_ratios(self, block: Block) -> Block:
        """저장된 미니맵 비율 좌표를 현재 미니맵 픽셀 좌표로 환산한다."""
        if self._minimap_size is None:
            return block
        try:
            width, height = self._minimap_size()
            width, height = int(width), int(height)
        except Exception:
            return block
        if width <= 0 or height <= 0:
            return block

        values = {}
        for key in (
            "target_x", "start_x", "end_x", "pos_x", "ladder_x",
            "rand_margin", "jump_offset",
        ):
            ratio = getattr(block, f"{key}_ratio", None)
            if ratio is not None:
                values[key] = int(round(float(ratio) * width))
        for key in ("pos_y", "y_top", "y_bot"):
            ratio = getattr(block, f"{key}_ratio", None)
            if ratio is not None:
                values[key] = int(round(float(ratio) * height))
        return replace(block, **values) if values else block

    def run_route(self, blocks: list[Block], max_steps: int = 200) -> bool:
        """블록 리스트를 순서대로 실행. 모두 성공하면 True."""
        total = len(blocks)
        for index, b in enumerate(blocks, start=1):
            while not self._stop():
                self._log_once(f"루트 블록 {index}/{total} 시작: {self._desc(b)}")
                if self.run_block(b, max_steps=max_steps):
                    self._log_once(f"루트 블록 {index}/{total} 완료")
                    break
                self.release_inputs()
                self._log_once(
                    f"루트 블록 {index}/{total} 실패 -> 첫 블록으로 돌아가지 않고 같은 블록 재시도"
                )
                self._jsleep(0.2)
            else:
                return False
        return True

    def _log_floor_status(self, block: Block) -> None:
        """현재 인식 층 / 이 블록의 목표 층을 로그로 표시(층 이동 진단용)."""
        if self._judge is None:
            return
        from core.navigation.map_graph import expected_floor
        _x, y = self._pos()
        cur = self._judge.floor_at(y)
        want = expected_floor(block.to_dict(), self._judge)
        cur_s = cur.name if cur is not None else f"층사이(y={y})"
        self._log_once(f"📍 현재 {cur_s} / 목표 {want or '-'}")

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

    def run_block(self, block: Block, max_steps: int = 200,
                  arrival_tolerance: float | None = None,
                  interrupt_fn: Callable[[], bool] | None = None) -> bool:
        block = self._resolve_block_ratios(block)
        if self._on_seg_enter is not None:
            self._on_seg_enter(block)
        self._log_once(f"▶ {self._desc(block)}")
        self._log_floor_status(block)
        try:
            self._recover_if_needed(block, max_steps)
            if block.type == "move":
                # 구간 모드: start_x < end_x 이면 mode(count/infinite/pass)에 따라 왕복/통과
                if block.end_x > block.start_x:
                    if block.mode == "pass":
                        # 통과: 구간을 한 방향으로 1회만 지나감(end_x까지)
                        return self._exec_move(
                            Block(type="move", target_x=block.end_x, move_type=block.move_type),
                            max_steps, arrival_tolerance=arrival_tolerance,
                            interrupt_fn=interrupt_fn)
                    infinite = (block.mode == "infinite")
                    sweeps = max(1, block.sweeps)
                    return self.run_sweep(block.start_x, block.end_x, sweeps,
                                          block.move_type, max_steps=max_steps,
                                          infinite=infinite, margin=block.rand_margin)
                return self._exec_move(
                    block, max_steps, arrival_tolerance=arrival_tolerance,
                    interrupt_fn=interrupt_fn)
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
        end_t = round(random.uniform(end_x - m, end_x), 4)
        start_t = round(random.uniform(start_x, start_x + m), 4)
        return end_t, start_t

    def run_sweep(self, start_x: int, end_x: int, sweeps: int,
                  move_type: str = "walk", max_steps: int = 200,
                  step_fn=None, infinite: bool = False, margin: int = 0) -> bool:
        """start_x ~ end_x 사이를 sweeps회 왕복. 한 sweep = 끝→시작 1회.

        infinite=True면 stop_fn()이 True가 될 때까지 무한 왕복.
        margin>0이면 매 왕복 끝점을 구간 안에서 랜덤화(소수점4자리, 매번 다른 지점에서 턴).
        step_fn: 테스트용 위치 강제 콜백(실기에선 None=실제 이동).
        """
        def one_sweep(sweep_label: str) -> bool:
            end_t, start_t = self._sweep_targets(start_x, end_x, margin)
            for leg_name, tx in (("끝점", end_t), ("시작점", start_t)):
                if self._stop():
                    return False
                self._log_once(f"{sweep_label} {leg_name} 이동 -> X={tx:.2f}")
                blk = Block(type="move", target_x=tx, move_type=move_type)
                if step_fn is not None:
                    step_fn(tx)           # 테스트: 즉시 도달
                elif not self._exec_move(blk, max_steps, release_on_arrival=False):
                    self.release_inputs()
                    return False
            return True

        if infinite:
            sweep_index = 0
            while not self._stop():
                sweep_index += 1
                if not one_sweep(f"무한왕복 {sweep_index}회"):
                    return False
            self.release_inputs()
            return True
        for sweep_index in range(1, sweeps + 1):
            if not one_sweep(f"왕복 {sweep_index}/{sweeps}"):
                return False
        self.release_inputs()
        return True

    # ── 이동 ──────────────────────────────────────────────────────────
    def _exec_move(self, block: Block, max_steps: int,
                   allow_jump_hold: bool = True,
                   arrival_tolerance: float | None = None,
                   interrupt_fn: Callable[[], bool] | None = None,
                   release_on_arrival: bool = True) -> bool:
        """target_x 까지 walk/teleport 로 접근. TOLERANCE 이내 도달 시 True.

        '진척 기반' 끼임 판정: 목표까지 거리가 한 번이라도 줄면 리셋. MOVE_STUCK_POLLS회
        (≈1.5초) 동안 한 번도 가까워지지 않으면 포기 — 거친 미니맵에서 캐릭터가 느리게
        움직여 x가 잠깐 안 변해도 거짓 '멈춤'이 안 되게 한다(벽일 때만 포기).

        jump_while_move 설정 시 걷기 동안 점프키를 누른 채 유지(바니합).
        텔레포트 이동·사다리 접근(allow_jump_hold=False)엔 적용하지 않는다."""
        jump_hold = (self._jump_while_move and allow_jump_hold
                     and block.move_type != "teleport")

        def _stop_move_keys():
            self._route_inputs.release_direction()
            if jump_hold:
                self._route_inputs.release_action(self._jump_key)

        best = None
        no_progress = 0
        previous_x = None
        last_boundary_refresh_at = 0.0
        for _ in range(max_steps):
            # 밀집 사냥(DWELL) 중엔 이동키 떼고 제자리 정지 — 메인 틱이 공격. 해제되면 이동 재개.
            while self._dwell() and not self._stop():
                _stop_move_keys()
                self._jsleep(self._poll)
            if self._stop():
                _stop_move_keys()
                return False
            x, _y = self._pos()
            if interrupt_fn is not None and interrupt_fn():
                _stop_move_keys()
                return True
            dist = block.target_x - x
            now = time.monotonic()
            tolerance = TOLERANCE if arrival_tolerance is None else arrival_tolerance
            if (
                abs(dist) <= 20.0
                and self._position_refresh is not None
                and now - last_boundary_refresh_at >= self._poll
            ):
                for _refresh_index in range(3):
                    refreshed, _seen_at = self._position_refresh()
                    last_boundary_refresh_at = time.monotonic()
                    if refreshed is None:
                        break
                    x, _y = refreshed
                    dist = block.target_x - x
                    reached_or_crossed = (
                        abs(dist) <= tolerance
                        or (
                            previous_x is not None
                            and min(previous_x, x) <= block.target_x <= max(previous_x, x)
                        )
                    )
                    if reached_or_crossed:
                        break
            crossed_target = (
                previous_x is not None
                and min(previous_x, x) <= block.target_x <= max(previous_x, x)
            )
            if abs(dist) <= tolerance or crossed_target:
                if release_on_arrival:
                    _stop_move_keys()
                return True   # 도착 (폐루프 종료)

            if best is None or abs(dist) < best:
                best = abs(dist)          # 목표에 조금이라도 가까워짐 → 진척
                no_progress = 0
            else:
                no_progress += 1
                if no_progress >= MOVE_STUCK_POLLS:
                    self._log_once(
                        f"⚠ 이동 진척 없음: x={x}→목표 {block.target_x}, 계속 이동")
                    no_progress = 0

            direction = "right" if dist > 0 else "left"
            previous_x = x
            use_tele = (block.move_type == "teleport" and abs(dist) > TELEPORT_MIN_DIST)

            # 좌우 이동키는 '한 번 누르고 계속 유지'(C _walk_to_x). 방향이 바뀌면
            # hold_dir가 기존 키를 떼고 새 키를 누른다. 도착 전까진 떼지 않는다.
            self._route_inputs.hold_direction(direction)
            if jump_hold:
                self._route_inputs.hold_action(self._jump_key)   # 걷는 동안 점프키도 누른 채 유지
            if use_tele:
                # 방향 유지한 채 텔포 키 (C _teleport_to_x)
                self._route_inputs.press_action(self._tele_key, 0.05)
            # 다음 위치 갱신을 기다린다 — 안 쉬면 스캐너(≈0.05s)보다 빨리 읽어
            # 위치가 안 변한 것처럼 보여 거짓 '멈춤'이 된다(시작 시 좌표 미수신 포함).
            self._jsleep(self._poll)
        return False

    # ── 사다리 (A/B/C map_navigator 방식 포팅: 접근점 점프 + 재시도 + 등반 진척감지) ──
    def _do_ladder(self, block: Block, max_steps: int) -> bool:
        """up: 접근점에서 사다리 쪽으로 점프+↑ 잡기(못 잡으면 재시도).
        down: 현재 위치에서 바로 아래점프 — ladder_x로 이동 안 함(사용자 요청)."""
        x, y = self._pos()
        if x is None or y is None:
            self._route_inputs.release_all()
            return False   # 좌표 인식 실패 — 스킵
        if block.ladder_dir == "down":
            return self._descend_ladder(
                block.ladder_x, block.exit_side, block.y_bot, max_steps
            )
        return self._ladder_controller.run(block, max_steps)

    def _climb_with_retry(self, block: Block, max_steps: int) -> bool:
        """등반 시도 → 못 잡으면(y가 안 올라감) 재접근·재점프 재시도(A/B/C 재시도).
        매 시도 현재 위치로 방향을 재계산 → 사다리를 지나쳤으면 반대로 돌아 '쳐다보고' 점프."""
        attempt = 0
        while not self._stop():
            attempt += 1
            if self._stop():
                self._route_inputs.release_all(); return False
            # 이미 위층(y_top)에 도달했으면 등반 완료 — 절대 아래로 복귀시키지 않는다.
            # (사다리 블록의 '목표 층'은 아래층이라, 정점 도달 후 복귀가 발동해 다시 내려가던 버그)
            _x, y0 = self._pos()
            if y0 is not None and y0 <= block.y_top + Y_ARRIVE_TOL:
                self._route_inputs.release_all()
                self._log_once("✓ 사다리 등반 완료(정점 도달)")
                return True
            # 아래로 떨어졌으면(몬스터 피격 등) 사다리 바닥층으로 복귀 후 재등반.
            self._recover_if_needed(block, max_steps)
            x, y = self._pos()
            if x is None or y is None:
                self._route_inputs.release_all(); return False
            side = self._grab_side(block, x)   # 잡기·발판확인에 쓸 한 방향
            already_grabbed = (
                y <= block.y_bot - 4
                and y > block.y_top + Y_ARRIVE_TOL
                and abs(x - block.ladder_x) <= LADDER_X_TOL
            )
            if already_grabbed:
                self._route_inputs.release_direction()
                self._route_inputs.hold_action("up")
                self._log_once(
                    f"사다리 재시도 취소: 이미 잡은 상태 "
                    f"(x={x}, y={y}, X 오차={abs(x - block.ladder_x)}px) → Up 등반 계속"
                )
                ok = self._finish_climb(
                    block.ladder_x, block.y_top, max_steps, side
                )
            elif abs(y - block.y_bot) <= SAME_LEVEL_TOL:
                # 같은 층(사다리 밑): 사다리 X로 가서 ↑만
                self._log_once(f"사다리 등반(같은층) x={block.ladder_x}, y {y}→{block.y_top}")
                self._exec_move(Block(type="move", target_x=block.ladder_x, move_type="walk"),
                                max_steps, allow_jump_hold=False)   # 점프하며 접근 시 밧줄 못 잡음
                ok = self._climb_hold_until(block.ladder_x, block.y_top, max_steps, side)
            else:
                self._log_once(
                    f"사다리 점프잡기 x={block.ladder_x} ({side}) 시도 {attempt}/{MAX_GRAB_RETRY}, "
                    f"y {y}→{block.y_top}")
                ok = self._jump_grab_stable(block.ladder_x, side, block.y_top, max_steps)
            if ok:
                self._log_once("✓ 사다리 등반 완료")
                return True
            self._route_inputs.release_all()
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
            return random.choice(("left", "right"))
        return "left" if block.ladder_x < char_x else "right"   # auto

    def _climb_loop(self, y_top: int, max_steps: int) -> bool:
        """↑가 눌린 상태에서 y_top까지 등반. 도달 시 True. y가 CLIMB_STUCK_POLLS 동안
        한 번도 안 줄면(로프 못 잡음/미끄러짐) False → 호출부가 재시도한다."""
        best = None
        no_prog = 0
        for _ in range(max_steps):
            if self._stop():
                return False
            _x, y = self._pos()
            if y is None:
                return False
            # 목표 층 y에 도달(또는 매달림이 정점을 지나쳐 이미 도달)하면 등반 완료.
            # 엉뚱한 위층에서 잡는 오인식은 floor_judge 다층 인식 + _recover_if_needed가 먼저 막는다.
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
        """발판 확인 = 등반 완료 판정: ↑를 유지한 채 confirm_dir 한 방향으로 밀어 x가
        사다리에서 벗어나면(=발판 위) True. 로프 매달림이면 x 안 변함 → False(재시도).
        ↑를 떼지 않는다 — 좌우 이동 확인이 끝날 때까지 ↑ 유지(사용자 요청; ↑+좌우 동시 가능).
        한 방향만 써서 좌우 왔다갔다(이상한 움직임) 없음."""
        self._route_inputs.hold_direction(confirm_dir)    # ↑ 유지한 상태에서 좌우 한 방향 추가
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
            self._route_inputs.release_direction()

    def _finish_climb(self, ladder_x: int, y_top: int, max_steps: int, confirm_dir: str) -> bool:
        """↑ 등반 → 정점 후 ↑ 더(dismount) → ↑ 유지한 채 한 방향 이동으로 발판 확인 → 완료.
        ↑는 좌우 이동 확인이 끝날 때까지 계속 유지된다(사용자 요청)."""
        self._route_inputs.hold_action("up")
        try:
            if not self._climb_loop(y_top, max_steps):
                return False
            self._jsleep(LADDER_TOP_SETTLE_SEC)   # 정점에서 ↑ 더 눌러 발판으로 올라섬
            return self._confirm_on_platform(ladder_x, confirm_dir, max_steps)
        finally:
            self._route_inputs.release_action("up")

    def _climb_hold_until(self, ladder_x: int, y_top: int, max_steps: int,
                          confirm_dir: str) -> bool:
        """같은 층(사다리 밑)에서 ↑만으로 등반 + 발판 확인(한 방향)."""
        return self._finish_climb(ladder_x, y_top, max_steps, confirm_dir)

    def _grab_offset(self, base: int) -> float:
        """점프 접근 거리: 설정 base에서 ±10% 랜덤(소수점4자리). base<=0이면 0(사다리 X에서 점프)."""
        if base <= 0:
            return 0.0
        return round(random.uniform(base * 0.9, base * 1.1), 4)

    def _jump_grab(self, ladder_x: int, side: str, y_top: int, max_steps: int,
                   jump_offset: int = JUMP_GRAB_OFFSET) -> bool:
        """접근점(사다리에서 side 반대쪽으로 jump_offset±10% 떨어진 곳)으로 가서, 거기서
        사다리 쪽으로 점프+↑ 잡기 → y_top까지 등반 (A/B/C jump_offset 접근 점프, 거리 랜덤)."""
        # 접근점: side=right면 사다리 왼쪽(ladder_x-offset)에서 오른쪽으로 점프해 잡음. 거리 ±10% 랜덤
        offset = self._grab_offset(jump_offset)
        approach_x = (ladder_x - offset if side == "right"
                      else ladder_x + offset)
        reached = False
        previous_x = None
        for _ in range(max_steps):
            if self._stop():
                self._route_inputs.release_all()
                return False

            x, _y = self._pos()
            if x is None:
                self._jsleep(self._poll)
                continue

            near_approach = abs(x - approach_x) <= LADDER_X_TOL
            near_ladder = abs(x - ladder_x) <= LADDER_X_TOL
            crossed_approach = (
                previous_x is not None
                and min(previous_x, x) <= approach_x <= max(previous_x, x)
            )
            crossed_ladder = (
                previous_x is not None
                and min(previous_x, x) <= ladder_x <= max(previous_x, x)
            )
            if near_approach or near_ladder or crossed_approach or crossed_ladder:
                reached = True
                break

            move_dir = "right" if approach_x > x else "left"
            self._route_inputs.hold_direction(move_dir)
            previous_x = x
            self._jsleep(self._poll)

        self._route_inputs.release_direction()
        if not reached:
            self._route_inputs.release_all()
            return False
        x, _y = self._pos()
        if x is None:
            self._route_inputs.release_all()
            return False
        jump_dir = "right" if ladder_x > x else "left"
        self._route_inputs.hold_direction(jump_dir)
        # 사다리 쪽으로 점프(방향 유지=모멘텀) → ↑ 매달림 → 방향키 해제
        self._route_inputs.press_action(self._jump_key, 0.05)
        self._jsleep(JUMP_TO_UP_SEC)    # 점프 직후 빠르게 ↑로 전환
        self._route_inputs.hold_action("up")
        direction_hold = min(0.08, LADDER_HANG_SEC)
        self._jsleep(direction_hold)
        self._route_inputs.release_direction()
        if LADDER_HANG_SEC > direction_hold:
            self._jsleep(LADDER_HANG_SEC - direction_hold)
        self._route_inputs.release_action("up")           # 점프잡기 안정화 ↑ 해제 후 _finish_climb이 다시 등반
        # y_top까지 등반 + 발판 확인(side 한 방향 이동돼야 완료). 미확인이면 False로 재시도 유도
        return self._finish_climb(ladder_x, y_top, max_steps, jump_dir)

    def _jump_grab_stable(self, ladder_x: int, side: str, y_top: int,
                          max_steps: int) -> bool:
        profile = self._ladder_profile
        attack_paused = False
        try:
            self._ladder_motion(True)
            attack_paused = True
            self._log_once("사다리 판정 시작: 공격 스레드 중지")
            right_launch_distance = profile.launch_distance_right
            left_launch_distance = profile.launch_distance_left
            approach_x = None
            previous_x = None
            launch_sample = None
            jump_dir = None
            approach_direction = self._route_inputs.direction
            for _ in range(max_steps):
                if self._stop():
                    self._route_inputs.release_all()
                    return False
                sample, age = self._fresh_position()
                if sample is None:
                    self._route_inputs.release_direction()
                    self._ladder_debug = {"phase": "APPROACH", "ladder_x": ladder_x, "stale_age": age}
                    self._log_once("사다리 점프 대기: 캐릭터 좌표 없음")
                    self._jsleep(self._poll)
                    continue
                x, y = sample
                ladder_distance = abs(x - ladder_x)
                if approach_x is None:
                    launch_distance = (
                        right_launch_distance if x < ladder_x else left_launch_distance
                    )
                    if ladder_distance <= launch_distance:
                        if x < ladder_x:
                            jump_dir = "right"
                        elif x > ladder_x:
                            jump_dir = "left"
                        else:
                            jump_dir = (
                                approach_direction
                                if approach_direction in ("left", "right")
                                else "right"
                            )
                        self._route_inputs.hold_direction(jump_dir)
                        launch_sample = (x, y)
                        self._ladder_debug = {
                            "phase": "LAUNCH", "ladder_x": ladder_x,
                            "character_x": x, "character_y": y,
                            "distance": ladder_distance, "jump_dir": jump_dir,
                            "launch_x": x,
                        }
                        self._log_once(
                            f"사다리 즉시 점프: 캐릭터 X={x}, 사다리 X={ladder_x}, "
                            f"거리={ladder_distance:.2f}, 방향={jump_dir}"
                        )
                        break
                    approach_x = (
                        ladder_x - launch_distance
                        if x < ladder_x
                        else ladder_x + launch_distance
                    )
                error = approach_x - x
                crossed = previous_x is not None and min(previous_x, x) <= approach_x <= max(previous_x, x)
                launch_reached = abs(error) <= 1.0
                crossed_near_ladder = crossed and ladder_distance <= launch_distance + 1.0
                if launch_reached or crossed_near_ladder:
                    if x < ladder_x:
                        jump_dir = "right"
                    elif x > ladder_x:
                        jump_dir = "left"
                    else:
                        jump_dir = (
                            approach_direction
                            if approach_direction in ("left", "right")
                            else "right"
                        )
                    self._route_inputs.hold_direction(jump_dir)
                    launch_sample = (x, y)
                    self._ladder_debug = {
                        "phase": "LAUNCH", "ladder_x": ladder_x, "character_x": x,
                        "character_y": y, "distance": ladder_distance,
                        "jump_dir": jump_dir, "launch_x": approach_x,
                    }
                    self._log_once(
                        f"사다리 점프 확정: 캐릭터 X={x}, 출발 X={approach_x:.2f}, "
                        f"사다리 X={ladder_x}, 거리={ladder_distance:.2f}, 방향={jump_dir}"
                    )
                    break

                if crossed:
                    launch_distance = (
                        right_launch_distance if x < ladder_x else left_launch_distance
                    )
                    approach_x = (
                        ladder_x - launch_distance
                        if x < ladder_x
                        else ladder_x + launch_distance
                    )
                    error = approach_x - x

                approach_direction = "right" if error > 0 else "left"
                self._route_inputs.hold_direction(approach_direction)
                self._ladder_debug = {
                    "phase": "APPROACH", "ladder_x": ladder_x, "character_x": x,
                    "character_y": y, "target_x": approach_x, "error": error,
                }
                previous_x = x
                self._jsleep(self._poll)
            else:
                self._route_inputs.release_all()
                return False

            if launch_sample is None or jump_dir is None:
                self._route_inputs.release_all()
                return False
            x, start_y = launch_sample
            self._ladder_debug = {
                "phase": "JUMP_GRAB", "ladder_x": ladder_x,
                "character_x": x, "character_y": start_y,
            }
            self._route_inputs.hold_direction(jump_dir)
            jump_requested_at = time.monotonic()
            input_events = {}

            def trace(message):
                event_at = time.monotonic()
                if f"{self._jump_key} key_down" in message:
                    input_events["jump_down"] = event_at
                elif f"{self._jump_key} key_up" in message:
                    input_events["jump_up"] = event_at
                self._log_once(
                    f"[사다리진단] {message}, 요청 후="
                    f"{event_at - jump_requested_at:.4f}초"
                )

            jump_released_at = None
            trajectory = []
            last_position_seen_at = None
            self._log_once(f"[사다리진단] 점프 요청 t=0.0000초, Y={start_y}")
            up_target = profile.up_delay_sec
            sequence = self._priority_inputs.perform_ladder_jump(
                jump_key=self._jump_key,
                jump_hold_sec=profile.jump_hold_sec,
                up_delay_sec=up_target,
                trace_fn=trace,
            )
            self._log_once(
                "[사다리진단] 점프 유지 종료 시 좌우 방향키 해제, 중심 이탈 방지"
            )
            jump_started_at = sequence["jump_down_at"]
            jump_released_at = sequence["jump_up_at"]
            up_requested_at = sequence["up_requested_at"]
            up_pressed_at = sequence["up_down_at"]
            up_input_call = up_pressed_at - up_requested_at
            trajectory.append((jump_started_at, start_y))
            released_sample, released_age = self._fresh_position()
            released_y = None
            if released_sample is not None:
                released_y = released_sample[1]
                observed_at = jump_released_at - (released_age or 0.0)
                if observed_at >= jump_started_at:
                    trajectory.append((observed_at, released_y))
                    last_position_seen_at = observed_at
            self._log_once(
                f"[사다리진단] 실제 점프키 유지={jump_released_at - jump_started_at:.4f}초, "
                f"Y={released_y if released_y is not None else '감지 없음'}"
            )
            self._log_once(
                f"사다리 점프: 중심거리 {abs(x - ladder_x):.4f}, "
                f"점프 시작 후 위키 목표 {up_target:.4f}초"
            )
            if self._stop():
                self._route_inputs.release_all()
                return False
            up_sample, up_age = self._fresh_position()
            up_y = None
            if up_sample is not None:
                up_y = up_sample[1]
                observed_at = up_pressed_at - (up_age or 0.0)
                if (observed_at >= jump_started_at and
                        (last_position_seen_at is None or observed_at > last_position_seen_at)):
                    trajectory.append((observed_at, up_y))
                    last_position_seen_at = observed_at
            self._log_once(
                f"[사다리진단] up key_down 전달, 입력 호출="
                f"{up_input_call:.4f}초, 목표={up_target:.4f}초, 실제="
                f"{up_pressed_at - jump_started_at:.4f}초, 점프키 해제 후="
                f"{up_pressed_at - jump_released_at:.4f}초, "
                f"오차={up_pressed_at - jump_started_at - up_target:+.4f}초, "
                f"Y={up_y if up_y is not None else '감지 없음'}"
            )
            rising_frames = 0
            last_y = start_y
            x_error = None
            polls = max(2, int(profile.grab_confirm_sec / max(self._poll, 0.001)))
            for _ in range(polls):
                if self._stop():
                    self._route_inputs.release_all()
                    return False
                self._jsleep(self._poll)
                sample, _age = self._fresh_position()
                if sample is None:
                    continue
                current_x, current_y = sample
                observed_at = time.monotonic() - (_age or 0.0)
                if (observed_at >= jump_started_at and
                        (last_position_seen_at is None or observed_at > last_position_seen_at)):
                    trajectory.append((observed_at, current_y))
                    last_position_seen_at = observed_at
                x_error = abs(current_x - ladder_x)
                x_aligned = x_error <= LADDER_X_TOL
                if x_aligned and current_y < last_y:
                    rising_frames += 1
                elif not x_aligned or current_y >= start_y:
                    rising_frames = 0
                last_y = current_y
                elapsed_after_jump = time.monotonic() - jump_started_at
                if elapsed_after_jump >= 0.35:
                    observed_min_y = min((value for _at, value in trajectory), default=start_y)
                    if observed_min_y >= start_y - 1:
                        self._log_once(
                            f"[사다리진단] 좌표 샘플에서 상승 미관측: "
                            f"{elapsed_after_jump:.4f}초 동안 Y={start_y}→{observed_min_y}. "
                            "실제 점프 여부는 확정하지 않고 재시도"
                        )
                        self._route_inputs.release_action("up")
                        self._route_inputs.release_direction()
                        return False
                self._ladder_debug = {
                    "phase": "VERIFY_GRAB", "ladder_x": ladder_x,
                    "character_x": current_x, "character_y": current_y,
                    "ladder_x_error": x_error, "x_aligned": x_aligned,
                    "rising_frames": rising_frames,
                }
                elevated_and_aligned = current_y <= start_y - 4 and x_aligned
                if elevated_and_aligned:
                    self._log_once(
                        f"사다리 잡기 확인: y={start_y}→{current_y}, "
                        f"X 오차={x_error}px, 상승 표본={rising_frames}회. "
                        "추가 점프 없이 Up 등반 전환"
                    )
                    return self._finish_climb(ladder_x, y_top, max_steps, jump_dir)
            self._route_inputs.release_action("up")
            if trajectory:
                apex_at, apex_y = min(trajectory, key=lambda item: item[1])
                apex_confirmed = any(
                    observed_at > apex_at and observed_y > apex_y
                    for observed_at, observed_y in trajectory
                )
                if apex_y >= start_y:
                    self._log_once(
                        f"[사다리진단] 점프 상승 감지 없음: 시작 Y={start_y}, "
                        f"최소 Y={apex_y}"
                    )
                elif apex_confirmed and apex_at - jump_started_at <= 0.5:
                    apex_from_start = apex_at - jump_started_at
                    apex_from_release = max(0.0, apex_at - jump_released_at)
                    self._log_once(
                        f"[사다리진단] 점프 최고점 확인: Y={apex_y}, "
                        f"실제 점프 시작 후={apex_from_start:.4f}초, "
                        f"점프키 해제 후 권장 위키 간격={apex_from_release:.4f}초"
                    )
                else:
                    self._log_once(
                        f"[사다리진단] 최고점 미확정 또는 0.5초 초과 표본 제외: 시작 Y={start_y}, "
                        f"관측 최소 Y={apex_y}"
                    )
            x_error_text = "감지 없음" if x_error is None else f"{x_error}px"
            self._log_once(
                f"사다리 잡기 실패: X/Y 조건 불충족"
                f"(y={start_y}→{last_y}, X 오차={x_error_text}, 상승={rising_frames}회)"
            )
            return False
        finally:
            self._ladder_motion(False)

    def _descend_ladder(self, ladder_x: int, exit_side: str,
                        y_bot: int, max_steps: int) -> bool:
        """밧줄 X를 옆으로 피해서 아래점프하고, 걸리면 방향점프로 탈출한다."""
        escape_dir = exit_side if exit_side in ("left", "right") else "left"
        safe_offset = 8
        safe_x = ladder_x - safe_offset if escape_dir == "left" else ladder_x + safe_offset

        for _ in range(min(max_steps, 40)):
            if self._stop():
                self._route_inputs.release_all()
                return False
            x, _y = self._pos()
            if x is None:
                self._jsleep(self._poll)
                continue
            reached_safe_x = x <= safe_x if escape_dir == "left" else x >= safe_x
            if reached_safe_x:
                break
            self._route_inputs.hold_direction(escape_dir)
            self._jsleep(self._poll)
        self._route_inputs.release_direction()
        self._log_once(
            f"사다리 하강 준비: 밧줄 X={ladder_x}에서 {escape_dir} 방향으로 벗어난 뒤 아래점프"
        )

        self._route_inputs.hold_action("down")
        self._jsleep(JUMP_TO_UP_SEC)    # 아래키 살짝 — 발판 드랍 인식
        self._route_inputs.press_action(self._jump_key, 0.05)  # ↓+점프
        self._jsleep(0.1)
        self._route_inputs.release_action("down")

        last_escape_at = -1e9
        for _ in range(max_steps):
            if self._stop():
                self._route_inputs.release_all()
                return False
            x, y = self._pos()
            if y is not None and abs(y - y_bot) <= Y_ARRIVE_TOL:
                return True   # 아래 발판 도착
            now = time.monotonic()
            if (
                x is not None
                and abs(x - ladder_x) <= 8
                and now - last_escape_at >= 0.5
            ):
                self._route_inputs.release_direction()
                self._route_inputs.hold_direction(escape_dir)
                self._route_inputs.press_action(self._jump_key, 0.12)
                self._route_inputs.release_direction()
                last_escape_at = now
                self._log_once(
                    f"하강 중 밧줄 X={ladder_x} 감지 → {escape_dir}+점프 탈출"
                )
            self._jsleep(self._poll)
        return True   # 하강은 도착 확인 약해도 완료 처리(C와 동일 성향)

    def _do_jump(self, block: Block) -> bool:
        """단순 점프 — 방향 키(있으면) 유지한 채 점프키 1회(C _do_jump). 점프 후 키 정리."""
        if block.direction in ("left", "right"):
            self._route_inputs.hold_direction(block.direction)
        elif block.direction == "down":
            self._route_inputs.hold_action("down")
        self._route_inputs.press_action(self._jump_key, 0.05)
        if block.direction == "down":
            self._route_inputs.release_action("down")
        elif block.direction in ("left", "right"):
            self._route_inputs.release_direction()   # 점프 후 방향키 떼기(잔류 이동 방지)
        return True
