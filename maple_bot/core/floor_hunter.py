# 층별 핑퐁 사냥 실행 모듈 — 밧줄/낙하로 층 이동, 각 층 왕복 사냥
import time
import threading
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class FloorHunter:
    """설정된 층 목록을 핑퐁(왕복) 패턴으로 순환하며 사냥한다.

    패턴 예시 (4층 기준):  1→2→3→4→3→2→1→2→...
    각 층에서 sweeps번 왕복 후 인접 층으로 이동한다.

    이동 방식:
      올라가기 — up_point 좌표 방향으로 이동 후 UP 키 홀드 (밧줄/발판)
      내려가기 — down_point 좌표 방향으로 이동 후 DOWN+ALT (낙하)
    """

    def __init__(
        self,
        input_ctrl,
        on_status: Callable[[str], None] | None = None,
    ):
        self._input = input_ctrl
        self._status = on_status or (lambda msg: None)
        self._config: dict = {}
        self._pause_event = threading.Event()  # set → 일시정지

    # ── 외부 제어 ─────────────────────────────────────────────────────
    def set_config(self, config: dict) -> None:
        self._config = config

    def pause(self) -> None:
        """층별 사냥을 일시정지한다 (거탐 해제 등 다른 작업 중)."""
        self._pause_event.set()

    def resume(self) -> None:
        """일시정지를 해제한다."""
        self._pause_event.clear()

    # ── 메인 루프 ─────────────────────────────────────────────────────
    def run(self, stop_event: threading.Event) -> None:
        """핑퐁 패턴으로 층별 사냥을 실행한다. stop_event 설정 시 즉시 종료."""
        floors = self._config.get("floors", [])
        if not floors:
            self._status("⚠ 층별 사냥: 층 정보 없음 — 설정 탭에서 층을 추가하세요.")
            return

        attack_key      = self._config.get("attack_key", "ctrl")
        attack_interval = float(self._config.get("attack_interval", 0.5))
        move_speed      = float(self._config.get("move_speed", 180))  # px/s

        n = len(floors)
        idx = 0
        direction = 1  # +1: 위층, -1: 아래층

        while not stop_event.is_set():
            self._wait_if_paused(stop_event)
            if stop_event.is_set():
                break

            floor = floors[idx]
            name     = floor.get("name", f"{idx + 1}층")
            sweeps   = max(1, int(floor.get("sweeps", 2)))
            sweep_sec = max(0.5, float(floor.get("sweep_sec", 4.0)))

            self._status(f"[층별] {name} 사냥 ({sweeps}왕복 × {sweep_sec:.1f}s)")
            self._hunt_floor(floor, sweeps, sweep_sec, attack_key, attack_interval, stop_event)

            if stop_event.is_set():
                break

            # ── 핑퐁: 다음 층 인덱스 계산 ────────────────────────────
            next_idx = idx + direction
            if next_idx >= n:
                direction = -1
                next_idx = idx - 1
            elif next_idx < 0:
                direction = 1
                next_idx = idx + 1 if n > 1 else 0

            if next_idx == idx or n == 1:
                # 층이 1개이거나 인덱스 변화 없음 → 동일 층 반복
                continue

            # ── 층 이동 ───────────────────────────────────────────────
            going_up = (next_idx > idx)
            next_floor = floors[next_idx]
            arrow = "↑ 올라가기" if going_up else "↓ 내려가기"
            self._status(
                f"[층별] {floor.get('name', f'{idx+1}층')}"
                f" → {next_floor.get('name', f'{next_idx+1}층')}  ({arrow})"
            )
            if going_up:
                self._go_up(floor, move_speed, stop_event)
            else:
                self._go_down(floor, move_speed, stop_event)

            idx = next_idx

    # ── 층 사냥 ───────────────────────────────────────────────────────
    def _hunt_floor(self, floor, sweeps, sweep_sec, attack_key, attack_interval, stop_event):
        """지정 층을 sweeps번 왕복 사냥한다 (1왕복 = 오른쪽→왼쪽 or 왼쪽→오른쪽)."""
        going_right = True
        for _ in range(sweeps * 2):   # 왕복 n회 = 2n 방향 전환
            if stop_event.is_set():
                break
            self._wait_if_paused(stop_event)
            direction_key = "right" if going_right else "left"
            self._sweep_half(direction_key, sweep_sec, attack_key, attack_interval, stop_event)
            going_right = not going_right

    def _sweep_half(self, direction_key, duration, attack_key, attack_interval, stop_event):
        """한 방향으로 duration초 이동하며 attack_key를 주기적으로 탭한다."""
        self._input.key_down(direction_key)
        elapsed   = 0.0
        last_atk  = -attack_interval  # 첫 스텝에서 즉시 공격
        step      = 0.05

        while elapsed < duration and not stop_event.is_set():
            if self._pause_event.is_set():
                # 일시정지: 방향키 해제 후 대기 → 재개 시 다시 누름
                self._input.key_up(direction_key)
                self._wait_if_paused(stop_event)
                if not stop_event.is_set():
                    self._input.key_down(direction_key)

            time.sleep(step)
            elapsed += step
            if elapsed - last_atk >= attack_interval:
                self._input.press_key(attack_key, hold_sec=0.04)
                last_atk = elapsed

        self._input.key_up(direction_key)
        time.sleep(0.05)

    # ── 층 이동 ───────────────────────────────────────────────────────
    def _go_up(self, floor, move_speed, stop_event):
        """up_point 방향으로 이동한 뒤 UP 홀드 (밧줄/발판 타기)."""
        up_pt  = floor.get("up_point")
        region = floor.get("region")
        if not up_pt or not region:
            logger.warning("[층별] up_point 미설정 — 올라가기 스킵")
            self._status("⚠ [층별] 올라가기 좌표 미설정")
            return

        self._walk_to_x(up_pt[0], region, move_speed, stop_event)
        if stop_event.is_set():
            return

        time.sleep(0.15)
        self._input.key_down("up")
        self._sleep_check(1.5, stop_event)
        self._input.key_up("up")
        self._sleep_check(1.2, stop_event)   # 도착 대기

    def _go_down(self, floor, move_speed, stop_event):
        """down_point 방향으로 이동한 뒤 DOWN+ALT (낙하)."""
        down_pt = floor.get("down_point")
        region  = floor.get("region")
        if not down_pt or not region:
            logger.warning("[층별] down_point 미설정 — 내려가기 스킵")
            self._status("⚠ [층별] 내려가기 좌표 미설정")
            return

        self._walk_to_x(down_pt[0], region, move_speed, stop_event)
        if stop_event.is_set():
            return

        time.sleep(0.15)
        self._input.key_down("down")
        self._input.key_down("alt")
        time.sleep(0.3)
        self._input.key_up("alt")
        self._input.key_up("down")
        self._sleep_check(1.2, stop_event)   # 착지 대기

    # ── 이동 유틸 ─────────────────────────────────────────────────────
    def _walk_to_x(self, target_x: int, region: list, speed: float, stop_event):
        """region 기준으로 target_x 방향으로 방향키를 눌러 이동한다.
        어디서 시작하든 층 전체 폭만큼 이동 → 목표 좌표에 도달 보장."""
        rx, ry, rw, rh = region
        center_x = rx + rw // 2
        if abs(target_x - center_x) < 10:
            return
        direction = "right" if target_x > center_x else "left"
        # 층 전체 폭을 이동하는 시간 = 어디서 시작해도 끝까지 도달하는 최대 시간
        duration = min(rw / max(speed, 1), 6.0)
        self._input.key_down(direction)
        self._sleep_check(duration, stop_event)
        self._input.key_up(direction)

    def _sleep_check(self, duration: float, stop_event, step: float = 0.05):
        """stop_event를 주기적으로 확인하며 duration초 대기한다."""
        elapsed = 0.0
        while elapsed < duration and not stop_event.is_set():
            time.sleep(step)
            elapsed += step

    def _wait_if_paused(self, stop_event):
        """pause_event가 set인 동안 대기한다."""
        while self._pause_event.is_set() and not stop_event.is_set():
            time.sleep(0.1)
