# 빨코3 전용 텔레포트 기반 사냥·회수 루틴 실행기.
from __future__ import annotations

import random
import threading
import time
from typing import Callable

from core.humanize.intent import Intent


class RedNose3RouteRunner:
    """Runs RedNose3 by switching platforms with teleport-only inputs."""

    controls_attack = True

    def __init__(
        self,
        block_runner,
        is_active: Callable[[], bool],
        profile: dict | None = None,
        log_fn: Callable[[str], None] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        minimap_region_fn: Callable[[], dict] | None = None,
    ):
        self._br = block_runner
        self._is_active = is_active
        self._profile = profile or {}
        self._log = log_fn or (lambda message: None)
        self._sleep = sleep_fn or time.sleep
        self._minimap_region_fn = minimap_region_fn
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.owns_movement = False
        self._next_collection_at = time.monotonic() + self._random_hunt_cycle_sec()

    def start(self) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="rednose3-route", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._br.release_inputs()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def reset(self) -> None:
        self._next_collection_at = time.monotonic() + self._random_hunt_cycle_sec()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if not self._active():
                self._br.release_inputs()
                self._sleep(0.03)
                continue
            self.run_once()

    def _active(self) -> bool:
        block_stop = getattr(self._br, "_stop", None)
        if callable(block_stop) and block_stop():
            return False
        return (not self._stop.is_set()) and self._is_active()

    def _humanizer(self):
        return getattr(self._br, "_h")

    def _current_pos(self):
        getter = getattr(self._br, "_get_pos", None)
        if not callable(getter):
            getter = getattr(self._br, "_pos", None)
        return getter() if callable(getter) else None

    def _fresh_pos(self):
        refresher = getattr(self._br, "refresh_position", None)
        if callable(refresher):
            position, _seen_at = refresher()
            return position
        return self._current_pos()

    def _attack_key(self) -> str:
        return str(self._profile.get("attack_key") or "end").strip()

    def _teleport_key(self) -> str:
        return str(self._profile.get("teleport_key") or "x").strip()

    def _jump_key(self) -> str:
        return str(self._profile.get("jump_key") or "alt").strip()

    def _humanized(self, key: str, fallback: float) -> float:
        return self._humanizer().humanize(float(self._profile.get(key, fallback)))

    def _random_hunt_cycle_sec(self) -> float:
        min_sec = float(self._profile.get("hunt_cycle_min_sec", 92.83))
        max_sec = float(self._profile.get("hunt_cycle_max_sec", 102.483))
        if max_sec < min_sec:
            min_sec, max_sec = max_sec, min_sec
        return round(random.uniform(max(10.0, min_sec), max(10.0, max_sec)), 4)

    def _platform(self, number: int) -> dict:
        return dict((self._profile.get("platforms") or {}).get(str(number), {}))

    def _platform_range(self, number: int) -> tuple[float, float, int, int]:
        data = self._platform(number)
        x_min = float(data.get("x_min", data.get("x", 0)))
        x_max = float(data.get("x_max", data.get("x", x_min)))
        y_min = int(data.get("y_min", data.get("y", 0)))
        y_max = int(data.get("y_max", data.get("y", y_min)))
        return min(x_min, x_max), max(x_min, x_max), min(y_min, y_max), max(y_min, y_max)

    def _is_on_platform(self, number: int, pos=None) -> bool:
        pos = self._current_pos() if pos is None else pos
        if pos is None or pos[0] is None or pos[1] is None:
            return False
        x_min, x_max, y_min, y_max = self._platform_range(number)
        return x_min <= float(pos[0]) <= x_max and y_min <= int(pos[1]) <= y_max

    def _wait_platform(self, number: int, timeout_sec: float | None = None) -> bool:
        deadline = time.monotonic() + float(timeout_sec or self._profile.get("confirm_timeout_sec", 0.55))
        while self._active() and time.monotonic() < deadline:
            pos = self._fresh_pos()
            if self._is_on_platform(number, pos):
                return True
            self._sleep(0.03)
        return self._is_on_platform(number)

    def _is_below_platform1(self) -> bool:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return False
        return int(pos[1]) > int(self._profile.get("fall_y_threshold", 70))

    def _tap_attack(self, count: int) -> None:
        key = self._attack_key()
        if not key:
            return
        h = self._humanizer()
        hold_sec = float(self._profile.get("attack_hold_sec", 0.9))
        gap_sec = float(self._profile.get("attack_gap_sec", 0.05))
        for index in range(max(1, int(count))):
            if not self._active():
                return
            h.perform(Intent(action="key", key=key, base_hold_sec=hold_sec))
            if index < count - 1:
                self._sleep(h.humanize(gap_sec))

    def _teleport(self, direction: str) -> None:
        key = self._teleport_key()
        if not key:
            return
        h = self._humanizer()
        if direction in ("left", "right"):
            h.hold_dir(direction)
            self._sleep(self._humanized("teleport_lead_sec", 0.02))
            h.perform(Intent(action="key", key=key, base_hold_sec=float(self._profile.get("teleport_hold_sec", 0.3))))
            h.release_dir()
            self._sleep(self._humanized("after_teleport_wait_sec", 0.12))
            return

        h.release_dir()
        h.hold(direction)
        self._sleep(self._humanized("vertical_teleport_lead_sec", 0.02))
        try:
            h.perform(Intent(action="key", key=key, base_hold_sec=float(self._profile.get("teleport_hold_sec", 0.3))))
        finally:
            h.release(direction)
        self._sleep(self._humanized("after_teleport_wait_sec", 0.12))

    def _down_jump(self) -> None:
        jump_key = self._jump_key()
        if not jump_key:
            return
        h = self._humanizer()
        h.release_dir()
        h.hold("down")
        self._sleep(self._humanized("down_jump_lead_sec", 0.03))
        try:
            h.perform(Intent(action="key", key=jump_key, base_hold_sec=float(self._profile.get("down_jump_hold_sec", 0.12))))
        finally:
            h.release("down")
        self._sleep(self._humanized("after_down_jump_wait_sec", 0.25))

    def _step_to_platform(self, target: int, action: str, attempts: int | None = None) -> bool:
        max_attempts = int(attempts or self._profile.get("step_attempts", 5))
        for attempt in range(1, max_attempts + 1):
            if not self._active():
                return False
            if action == "down_jump":
                self._down_jump()
            else:
                self._teleport(action)
            if self._wait_platform(target):
                self._log(f"[rednose3] platform {target} reached ({attempt}/{max_attempts})")
                return True
            self._log(f"[rednose3] platform {target} not confirmed ({attempt}/{max_attempts})")
        return False

    def _recover_to_platform1(self) -> bool:
        self._log("[rednose3] fell below platform1; recover to platform1")
        for attempt in range(1, int(self._profile.get("recover_attempts", 10)) + 1):
            if not self._active():
                return False
            pos = self._current_pos()
            if self._is_on_platform(1, pos):
                self._log(f"[rednose3] platform1 recovered ({attempt})")
                return True
            if pos is not None and pos[1] is not None and int(pos[1]) > int(self._profile.get("fall_y_threshold", 70)):
                self._teleport("up")
            elif pos is not None and pos[0] is not None and float(pos[0]) < 55:
                self._teleport("right")
            else:
                self._teleport("left")
        return self._is_on_platform(1)

    def _main_hunt_once(self) -> bool:
        if self._is_below_platform1():
            return self._recover_to_platform1()
        if not self._is_on_platform(1):
            self._log("[rednose3] main hunt: return to platform1")
            if not self._step_to_platform(1, "right", attempts=3):
                return self._recover_to_platform1()
        self._log("[rednose3] main hunt: platform1 attack x16")
        self._tap_attack(int(self._profile.get("platform1_attack_count", 16)))
        if not self._step_to_platform(2, "left"):
            return False
        self._log("[rednose3] main hunt: platform2 attack x4")
        self._tap_attack(int(self._profile.get("platform2_attack_count", 4)))
        return self._step_to_platform(1, "right")

    def _collection_once(self) -> bool:
        self._log("[rednose3] collection route start")
        steps = [
            (2, "left"),
            (3, "left"),
            (4, "up"),
            (5, "up"),
            (6, "down_jump"),
            (4, "down"),
            (3, "down"),
            (2, "right"),
            (1, "right"),
        ]
        if self._is_below_platform1() and not self._recover_to_platform1():
            return False
        for target, action in steps:
            if not self._step_to_platform(target, action):
                self._log(f"[rednose3] collection failed at platform {target}")
                return False
            if self._is_below_platform1() and target != 1:
                return self._recover_to_platform1()
        self._next_collection_at = time.monotonic() + self._random_hunt_cycle_sec()
        self._log("[rednose3] collection route complete")
        return True

    def run_once(self) -> bool:
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        try:
            if time.monotonic() >= self._next_collection_at:
                if not self._collection_once():
                    self._br.release_inputs()
                    self._sleep(0.05)
                return True
            if not self._main_hunt_once():
                self._br.release_inputs()
                self._sleep(0.05)
            return True
        finally:
            self._humanizer().release_dir()
            self.owns_movement = previous_owns_movement
