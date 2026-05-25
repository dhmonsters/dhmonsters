# 구역 내 방향 결정 및 밧줄 점프/오르기 로직을 담당하는 맵 네비게이터
from __future__ import annotations
import time
import random
import logging
from typing import Callable

from core.minimap_reader import MinimapReader, Zone, RopePoint
from core.input_controller import InputController
from core.detector import Detector

logger = logging.getLogger(__name__)

ROPE_MARGIN = 8        # 밧줄 X 기준 이 픽셀 이내면 "도달"로 판정
CLIMB_DURATION = 2.0   # 밧줄 오르기 유지 시간(초)


_PATROL   = "patrol"
_APPROACH = "approach"
_JUMP     = "jump"
_CLIMB    = "climb"


def _rnd(lo: float, hi: float) -> float:
    """lo~hi 사이 랜덤 float — 소수점이 자연스럽게 이어지도록."""
    return random.uniform(lo, hi)


class MapNavigator:
    def __init__(
        self,
        minimap_reader: MinimapReader,
        input_ctrl: InputController,
        detector: Detector,
        on_status: Callable[[str], None] | None = None,
    ):
        self._minimap = minimap_reader
        self._input = input_ctrl
        self._detector = detector
        self._on_status = on_status or (lambda msg: None)

        self._zones: list[Zone] = []
        self._ropes: list[RopePoint] = []
        self._direction: str = "right"
        self._attack_key: str = "ctrl"
        self._monster_template: str = ""
        self._jump_before_attack: bool = False

        # 현재 꾹 누르고 있는 방향키
        self._held_direction: str | None = None

        # 밧줄 스테이트 머신
        self._state: str = _PATROL
        self._target_rope: RopePoint | None = None
        self._approach_x: int = 0
        self._climb_start: float = 0.0

        # 구역 내 방향 전환 목표 X (진입할 때마다 랜덤으로 새로 뽑음)
        self._right_target: int | None = None   # 이 X 이상이면 왼쪽 전환
        self._left_target:  int | None = None   # 이 X 이하이면 오른쪽 전환
        self._last_zone: Zone | None = None     # 구역이 바뀌면 목표 재설정

        # 캐릭터 위치 미감지 시 시간 기반 방향 전환 폴백
        self._fallback_timer: float = time.time()
        self._fallback_interval: float = 3.0

        # 진단용: 2초마다 현재 상태를 로그에 출력
        self._diag_timer: float = time.time()

    # ── 설정 ──────────────────────────────────────────────────────────
    def set_zones(self, zones: list[Zone]) -> None:
        self._zones = zones
        self._right_target = None  # 구역 변경 시 목표 초기화
        self._left_target  = None
        self._last_zone    = None

    def set_ropes(self, ropes: list[RopePoint]) -> None:
        self._ropes = ropes

    def cancel_rope_state(self) -> None:
        """밧줄 자동 시퀀스를 취소하고 순찰 상태로 복귀 (floor_hunt 충돌 방지용)."""
        if self._state in (_APPROACH, _JUMP, _CLIMB):
            self._state       = _PATROL
            self._target_rope = None

    @property
    def ropes(self) -> list[RopePoint]:
        return self._ropes

    def walk_toward(self, target_x: int, current_x: int) -> None:
        """target_x 방향으로 이동키를 누른다 (층 이동 전 밧줄 접근용)."""
        direction = "right" if target_x > current_x else "left"
        self._hold_direction(direction)

    def set_attack(self, key: str, monster_template: str = "",
                   jump_before_attack: bool = False) -> None:
        self._attack_key = key
        self._monster_template = monster_template
        self._jump_before_attack = jump_before_attack

    # ── 방향키 꾹 누르기 관리 ─────────────────────────────────────────
    def _hold_direction(self, direction: str) -> None:
        if self._held_direction == direction:
            return
        if self._held_direction:
            self._input.key_up(self._held_direction)
            time.sleep(_rnd(0.001, 0.011))  # 랜덤 딜레이
        self._held_direction = direction
        self._input.key_down(direction)

    def release_direction(self) -> None:
        if self._held_direction:
            self._input.key_up(self._held_direction)
            self._held_direction = None

    # ── 메인 스텝 ─────────────────────────────────────────────────────
    def run_one_step(self) -> None:
        if self._state == _CLIMB:
            self.release_direction()
            self._do_climb()
            return

        pos = self._minimap.get_character_pos()

        if self._state == _JUMP:
            self.release_direction()
            self._do_jump()
            return

        if self._state == _APPROACH and self._target_rope:
            if pos is None:
                return
            x, _ = pos
            if abs(x - self._approach_x) <= ROPE_MARGIN:
                self.release_direction()
                self._state = _JUMP
                self._status(f"점프 위치 도달 X={x} → 점프")
            else:
                direction = "right" if self._approach_x > x else "left"
                self._hold_direction(direction)
            return

        # ── 일반 순찰 ──────────────────────────────────────────────────
        now = time.time()
        if pos is None:
            if now - self._fallback_timer >= self._fallback_interval:
                self._direction = "left" if self._direction == "right" else "right"
                self._fallback_timer = now
                self._status(f"[진단] 위치 미감지 → {self._fallback_interval:.0f}초 기반 전환: {self._direction}")
            if now - self._diag_timer >= 2.0:
                self._status("[진단] 캐릭터 위치 감지 실패 (미니맵 설정 확인 필요)")
                self._diag_timer = now
            self._hold_direction(self._direction)
        else:
            zone = self._find_active_zone(pos)
            if now - self._diag_timer >= 2.0:
                if zone:
                    self._status(
                        f"[진단] X={pos[0]}  목표 L<={self._left_target} R>={self._right_target}"
                        f"  방향={self._direction}"
                    )
                else:
                    self._status(f"[진단] X={pos[0]}  구역 없음  방향={self._direction}")
                self._diag_timer = now

            if zone is None:
                if pos is not None:
                    x = pos[0]
                    if self._zones:
                        # ① 가장 가까운 구역 방향으로 복귀
                        def _x_dist(z: Zone) -> int:
                            if x < z.left_x:  return z.left_x - x
                            if x > z.right_x: return x - z.right_x
                            return 0
                        nearest = min(self._zones, key=_x_dist)
                        if x < nearest.left_x:
                            new_dir = "right"
                        elif x > nearest.right_x:
                            new_dir = "left"
                        else:
                            new_dir = self._direction  # X는 구역 안 (Y 차이)
                        if new_dir != self._direction:
                            self._direction = new_dir
                            self._status(
                                f"[진단] 구역 이탈 → '{nearest.name}' 복귀({new_dir}) X={x}"
                            )
                    else:
                        # ② 구역 미설정 폴백: 미니맵 전체 너비 끝에서 반전
                        cfg = self._minimap.config
                        map_right = max(1, cfg.width - 1)
                        if x <= 2 and self._direction == "left":
                            self._direction = "right"
                            self._status(f"[진단] 미니맵 왼쪽 끝 X={x} → 오른쪽 전환")
                        elif x >= map_right - 2 and self._direction == "right":
                            self._direction = "left"
                            self._status(f"[진단] 미니맵 오른쪽 끝 X={x} → 왼쪽 전환")
                self._hold_direction(self._direction)
            else:
                if self._check_rope_trigger(pos, zone):
                    self.release_direction()
                    return
                self._update_direction(pos, zone)
                self._hold_direction(self._direction)

        # 공격은 키 반복 모드에서 담당 — 좌표 모드는 이동만 처리

    # ── 밧줄 시퀀스 ───────────────────────────────────────────────────
    def _check_rope_trigger(self, pos: tuple[int, int], zone: Zone) -> bool:
        if not self._ropes or zone.rope_x < 0:
            return False
        x, _ = pos
        at_boundary = (x >= zone.right_x or x <= zone.left_x)
        if not at_boundary:
            return False
        rope = self._nearest_rope(zone.rope_x)
        if rope is None:
            return False
        self._target_rope = rope
        self._approach_x  = self._calc_approach_x(rope)
        self._state       = _APPROACH
        self._status(f"밧줄 접근 시작: {rope.name} X={rope.x} → 접근점 X={self._approach_x}")
        return True

    def _calc_approach_x(self, rope: RopePoint) -> int:
        if rope.approach == "left":
            return rope.x - rope.jump_offset
        if rope.approach == "right":
            return rope.x + rope.jump_offset
        return (rope.x - rope.jump_offset if self._direction == "right"
                else rope.x + rope.jump_offset)

    def _do_jump(self) -> None:
        jump_key = self._minimap.config.jump_key if self._minimap.config else "alt"
        self._input.press_key(jump_key, hold_sec=_rnd(0.083, 0.127))
        time.sleep(_rnd(0.121, 0.183))
        self._state       = _CLIMB
        self._climb_start = time.time()
        self._status(f"점프 완료 [{jump_key}] → 오르는 중")

    def _do_climb(self) -> None:
        elapsed = time.time() - self._climb_start
        if elapsed < CLIMB_DURATION:
            self._input.press_key("up", hold_sec=_rnd(0.121, 0.183))
        else:
            self._state       = _PATROL
            self._target_rope = None
            self._status("밧줄 오르기 완료 → 순찰 재개")

    def _nearest_rope(self, rope_x: int) -> RopePoint | None:
        if not self._ropes:
            return None
        return min(self._ropes, key=lambda r: abs(r.x - rope_x))

    # ── 방향 결정 ─────────────────────────────────────────────────────
    def _pick_right_target(self, zone: Zone) -> int:
        """오른쪽 전환 목표: (right_x - margin) ~ right_x 사이 랜덤.
        margin = randint(margin_min, margin_max) 으로 윈도우 크기를 결정한다."""
        margin = (random.randint(zone.random_margin_min, zone.random_margin_max)
                  if zone.random_margin_max > 0 else 0)
        lo = max(zone.left_x + 1, zone.right_x - margin)
        hi = zone.right_x
        return random.randint(lo, hi) if lo < hi else hi

    def _pick_left_target(self, zone: Zone) -> int:
        """왼쪽 전환 목표: left_x ~ (left_x + margin) 사이 랜덤."""
        margin = (random.randint(zone.random_margin_min, zone.random_margin_max)
                  if zone.random_margin_max > 0 else 0)
        lo = zone.left_x
        hi = min(zone.right_x - 1, zone.left_x + margin)
        return random.randint(lo, hi) if lo < hi else lo

    def _update_direction(self, pos: tuple[int, int], zone: Zone) -> None:
        # 구역이 바뀌었거나 처음 진입 시 목표 재설정
        if zone is not self._last_zone:
            self._right_target = self._pick_right_target(zone)
            self._left_target  = self._pick_left_target(zone)
            self._last_zone    = zone

        x, _ = pos
        if self._direction == "right" and x >= self._right_target:
            self._direction    = "left"
            self._left_target  = self._pick_left_target(zone)
            self._status(f"경계 → 왼쪽 전환 (X={x}, 다음목표 X<={self._left_target})")
        elif self._direction == "left" and x <= self._left_target:
            self._direction    = "right"
            self._right_target = self._pick_right_target(zone)
            self._status(f"경계 → 오른쪽 전환 (X={x}, 다음목표 X>={self._right_target})")

    def _find_active_zone(self, pos: tuple[int, int]) -> Zone | None:
        if not self._zones:
            return None
        if len(self._zones) == 1:
            return self._zones[0]
        return MinimapReader.find_zone(pos, self._zones)

    # ── 공격 ──────────────────────────────────────────────────────────
    def _do_attack(self) -> None:
        if self._jump_before_attack:
            self._input.press_key("space", hold_sec=_rnd(0.033, 0.071))
        self._input.press_key(self._attack_key, hold_sec=_rnd(0.033, 0.071))

    def _attack_if_monster(self, screenshot) -> None:
        if not self._monster_template:
            self._do_attack()
            return
        if self._detector.has_monster(screenshot, self._monster_template):
            self._do_attack()
            self._status(f"몬스터 감지 → 공격 [{self._attack_key}]")

    def _status(self, msg: str) -> None:
        logger.debug(msg)
        self._on_status(msg)
