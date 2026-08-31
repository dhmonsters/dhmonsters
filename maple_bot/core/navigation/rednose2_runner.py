# RedNose2 v5 route runner: Hunter-style teleport state machine for the Red Nose 2 map.
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Callable

from core.humanize.timing import down_5
from core.internal_trace import trace_event


logger = logging.getLogger(__name__)


class RedNose2RouteRunner:
    """Runs RedNose2 route blocks with a Hunter-style teleport flow."""

    def __init__(self, block_runner, get_blocks: Callable[[], list],
                 is_active: Callable[[], bool],
                 profile: dict | None = None,
                 log_fn: Callable[[str], None] | None = None,
                 sleep_fn: Callable[[float], None] | None = None,
                 minimap_region_fn: Callable[[], dict] | None = None):
        self._br = block_runner
        self._get_blocks = get_blocks
        self._is_active = is_active
        self._profile = profile or {}
        ui_log = log_fn or (lambda message: None)

        def traced_log(message: str) -> None:
            trace_event("rednose2", "state", message=message)
            ui_log(message)

        self._log = traced_log
        self._sleep = sleep_fn or time.sleep
        self._minimap_region_fn = minimap_region_fn
        self._index = 0
        self._signature: tuple = ()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.controls_attack = True
        self.owns_movement = False
        self._last_teleport_log_at = 0.0
        self._last_inactive_log_at = 0.0
        self._last_pickup_at = time.monotonic()
        self._next_collection_at = self._last_pickup_at + self._random_hunt_cycle_sec()
        self._main_move_index = 0
        self._collection_stage: str | None = None
        self._coord_scaled: bool | None = None
        self._coord_mode_logged: str | None = None
        self._last_horizontal_intent: str | None = None
        self._last_detected_position: tuple[float, float] | None = None
        self._last_floor2_x: float | None = None

    def start(self) -> None:
        thread = self._thread
        if thread is not None and thread.is_alive():
            self._log("[rednose2v5] runner restart requested: previous thread cleanup")
            self._stop.set()
            self._br.release_inputs()
            if thread is not threading.current_thread():
                thread.join(timeout=1.5)
            if thread.is_alive():
                self._log("[rednose2v5] runner start blocked: previous thread still alive")
                return
            self._thread = None
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="rednose2-route", daemon=True)
        self._thread.start()
        self._log("[rednose2v5] runner started")

    def stop(self) -> None:
        self._stop.set()
        self._br.release_inputs()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.8)
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None
        self._log("[rednose2v5] runner stop requested")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self._active():
                    self._br.release_inputs()
                    now = time.monotonic()
                    if now - self._last_inactive_log_at >= 1.0:
                        self._last_inactive_log_at = now
                        self._log(
                            f"[rednose2v5] runner waiting inactive: "
                            f"bot_active={self._is_active()}, stop={self._stop.is_set()}"
                        )
                    self._sleep(0.03)
                    continue
                self.run_once()
            except Exception as exc:
                self._br.release_inputs()
                self._log(f"[rednose2v5] runner error: {type(exc).__name__}: {exc}")
                logger.exception("rednose2 runner error")
                self._sleep(0.2)

    def reset(self) -> None:
        self._index = 0
        self._signature = ()
        self._last_pickup_at = time.monotonic()
        self._next_collection_at = self._last_pickup_at + self._random_hunt_cycle_sec()
        self._main_move_index = 0
        self._collection_stage = None
        self._last_horizontal_intent = None
        self._last_detected_position = None
        self._last_floor2_x = None

    @staticmethod
    def _block_signature(block) -> tuple:
        return tuple(sorted(block.to_dict().items()))

    @staticmethod
    def _entry_y(block) -> int | None:
        if block.type == "ladder":
            value = block.y_bot if block.ladder_dir == "up" else block.y_top
            return int(value) if int(value) > 0 else None
        value = int(getattr(block, "pos_y", -1))
        return value if value >= 0 else None

    def _current_pos(self):
        getter = getattr(self._br, "_get_pos", None)
        if not callable(getter):
            getter = getattr(self._br, "_pos", None)
        position = getter() if callable(getter) else None
        if position is not None and position[0] is not None and position[1] is not None:
            self._last_detected_position = (float(position[0]), float(position[1]))
            floor2_min, floor2_max = self._floor2_y_range()
            tolerance = self._floor_y_tolerance()
            if floor2_min - tolerance <= float(position[1]) <= floor2_max + tolerance:
                self._last_floor2_x = float(position[0])
        return position

    def _fresh_pos(self):
        position, _seen_at = self._fresh_sample()
        return position

    def _fresh_sample(self):
        refresher = getattr(self._br, "refresh_position", None)
        if callable(refresher):
            return refresher()
        return self._current_pos(), time.monotonic()

    def _active(self) -> bool:
        block_stop = getattr(self._br, "_stop", None)
        if callable(block_stop) and block_stop():
            return False
        return (not self._stop.is_set()) and self._is_active()

    def _route_inputs(self):
        return getattr(self._br, "_route_inputs")

    def _attack_key(self) -> str:
        return str(self._profile.get("attack_key") or "a").strip()

    def _teleport_key(self) -> str:
        return str(self._profile.get("teleport_key") or "space").strip()

    def _arrival_tolerance(self) -> int:
        return max(1, int(round(
            float(self._profile.get("arrival_tolerance", 3)) * self._plain_scale_x()
        )))

    def _close_walk_px(self) -> int:
        return max(0, int(round(
            float(self._profile.get("close_walk_px", 8)) * self._plain_scale_x()
        )))

    def _teleport_interval(self) -> float:
        return max(0.0, float(self._profile.get("teleport_interval_sec", 0.4)))

    def _segment_interval(self, key: str, fallback: float | None = None) -> float:
        base = self._teleport_interval() if fallback is None else fallback
        return max(0.0, float(self._profile.get(key, base)))

    def _teleport_step_px(self) -> float:
        return max(
            1.0,
            float(self._profile.get("teleport_step_px", 13.0)) * self._plain_scale_x(),
        )

    def _teleport_stop_px(self) -> float:
        if self._profile.get("teleport_stop_px") is None:
            return self._teleport_step_px()
        return max(
            1.0,
            float(self._profile["teleport_stop_px"]) * self._plain_scale_x(),
        )

    def _max_step_sec(self) -> float:
        return max(3.0, float(self._profile.get("max_step_sec", 18.0)))

    def _pickup_route_enabled(self) -> bool:
        return bool(self._profile.get("pickup_route_enabled", False))

    def _pickup_cycle_sec(self) -> float:
        return max(10.0, float(self._profile.get("pickup_cycle_sec", 120.0)))

    def _random_hunt_cycle_sec(self) -> float:
        min_sec = float(self._profile.get("hunt_cycle_min_sec", 92.83))
        max_sec = float(self._profile.get("hunt_cycle_max_sec", 102.483))
        if max_sec < min_sec:
            min_sec, max_sec = max_sec, min_sec
        return round(random.uniform(max(10.0, min_sec), max(10.0, max_sec)), 4)

    def _pickup_max_sec(self) -> float:
        return max(10.0, float(self._profile.get("pickup_max_sec", 60.0)))

    def _ladder_y_tolerance(self) -> int:
        return max(1, int(round(
            float(self._profile.get("ladder_y_tolerance", 6)) * self._plain_scale_y()
        )))

    def _minimap_size(self) -> tuple[int, int]:
        if self._minimap_region_fn is not None:
            try:
                region = self._minimap_region_fn()
                width = int(region.get("width", 0))
                height = int(region.get("height", 0))
                if width > 0 and height > 0:
                    return width, height
            except Exception:
                pass
        return (
            max(1, int(self._profile.get("minimap_width", self._profile.get("base_minimap_width", 244)))),
            max(1, int(self._profile.get("minimap_height", self._profile.get("base_minimap_height", 144)))),
        )

    def _base_minimap_size(self) -> tuple[int, int]:
        return (
            max(1, int(self._profile.get("base_minimap_width", self._profile.get("minimap_width", 244)))),
            max(1, int(self._profile.get("base_minimap_height", self._profile.get("minimap_height", 144)))),
        )

    def _plain_scale_x(self) -> float:
        width, _height = self._minimap_size()
        base_width, _base_height = self._base_minimap_size()
        return width / base_width

    def _plain_scale_y(self) -> float:
        _width, height = self._minimap_size()
        _base_width, base_height = self._base_minimap_size()
        return height / base_height

    def _raw_y_range(self, min_key: str, max_key: str, fallback_min: float, fallback_max: float) -> tuple[int, int]:
        low = int(round(float(self._profile.get(min_key, fallback_min))))
        high = int(round(float(self._profile.get(max_key, fallback_max))))
        return min(low, high), max(low, high)

    @staticmethod
    def _range_contains(value: int, ranges: list[tuple[int, int]], tolerance: int = 1) -> bool:
        for low, high in ranges:
            if low - tolerance <= value <= high + tolerance:
                return True
        return False

    def _use_scaled_coords(self) -> bool:
        self._coord_scaled = True
        mode = "minimap-ratio"
        if self._coord_mode_logged != mode:
            width, height = self._minimap_size()
            base_width, base_height = self._base_minimap_size()
            self._log(
                f"[rednose2v5] coord mode={mode}, minimap={width}x{height}, "
                f"base={base_width}x{base_height}"
            )
            self._coord_mode_logged = mode
        return True

    def _floor_y_tolerance(self) -> int:
        return max(1, int(round(
            float(self._profile.get("floor_y_tolerance", 4)) * self._plain_scale_y()
        )))

    def _scaled_x(self, value: float) -> float:
        scale = self._plain_scale_x() if self._use_scaled_coords() else 1.0
        return float(value) * scale

    def _scaled_y(self, value: float) -> int:
        scale = self._plain_scale_y() if self._use_scaled_coords() else 1.0
        return int(round(float(value) * scale))

    def _profile_y(self, key: str, fallback: float) -> int:
        _width, height = self._minimap_size()
        ratio = self._profile.get(f"{key}_ratio")
        if ratio is not None:
            return int(round(float(ratio) * height))
        return self._scaled_y(float(self._profile.get(key, fallback)))

    def _profile_x(self, key: str, fallback: float) -> float:
        width, _height = self._minimap_size()
        ratio = self._profile.get(f"{key}_ratio")
        if ratio is not None:
            return float(ratio) * width
        return self._scaled_x(float(self._profile.get(key, fallback)))

    def _point_x(self, key: str, fallback: float) -> float:
        return self._profile_x(f"{key}_x", fallback)

    def _point_y(self, key: str, fallback: float) -> int:
        return self._profile_y(f"{key}_y", fallback)

    def _stair7_x_range(self) -> tuple[float, float]:
        center = self._point_x("stair7", 41)
        left = self._profile_x("stair7_x_min", 37)
        right = self._profile_x("stair7_x_max", 45)
        return min(left, right), max(left, right)

    def _is_in_stair7_x_range(self) -> bool:
        pos = self._current_pos()
        if pos is None or pos[0] is None:
            return False
        left, right = self._stair7_x_range()
        return left <= float(pos[0]) <= right

    def _stair7_right_bias_x(self) -> float:
        return self._profile_x("stair7_right_bias_x", 45)

    def _stair7_teleport_stop_range(self) -> tuple[float, float]:
        left, right = self._stair7_x_range()
        step_px = self._teleport_step_px()
        return left - step_px, right + step_px

    def _stair7_floor1_teleport_stop_range(self) -> tuple[float, float] | None:
        if self._is_lower_floor_v5(None):
            return self._stair7_teleport_stop_range()
        return None

    def _platform1415_x_range(self) -> tuple[float, float]:
        left = self._profile_x("platform1415_x_min", 94)
        right = self._profile_x("platform1415_x_max", 96)
        return min(left, right), max(left, right)

    def _is_in_platform1415_x_range(self) -> bool:
        pos = self._current_pos()
        if pos is None or pos[0] is None:
            return False
        left, right = self._platform1415_x_range()
        return left <= float(pos[0]) <= right

    def _block_x(self, block, key: str, fallback: float = 0.0) -> float:
        width, _height = self._minimap_size()
        ratio = getattr(block, f"{key}_ratio", None)
        if ratio is not None:
            return float(ratio) * width
        return self._scaled_x(float(getattr(block, key, fallback)))

    def _block_y(self, block, key: str, fallback: float = 0.0) -> int:
        _width, height = self._minimap_size()
        ratio = getattr(block, f"{key}_ratio", None)
        if ratio is not None:
            return int(round(float(ratio) * height))
        return self._scaled_y(float(getattr(block, key, fallback)))

    def _floor3_y_range(self) -> tuple[int, int]:
        return (
            self._profile_y("floor3_y_min", float(self._profile.get("floor3_y_min", 47))),
            self._profile_y("floor3_y_max", float(self._profile.get("floor3_y_max", 51))),
        )

    def _floor2_y_range(self) -> tuple[int, int]:
        return (
            self._profile_y("floor2_y_min", float(self._profile.get("floor2_y_min", 58))),
            self._profile_y("floor2_y_max", float(self._profile.get("floor2_y_max", 66))),
        )

    def _floor1_y_range(self) -> tuple[int, int]:
        return (
            self._profile_y("floor1_y_min", float(self._profile.get("floor1_y_min", 72))),
            self._profile_y("floor1_y_max", float(self._profile.get("floor1_y_max", 82))),
        )

    def _floor2_left_x(self) -> float:
        return self._profile_x("floor2_left_x", float(self._profile.get("floor2_left_x", 55)))

    def _floor2_right_x(self) -> float:
        return self._profile_x("floor2_right_x", float(self._profile.get("floor2_right_x", 124)))

    def _floor2_right_safe_x(self) -> float:
        return self._profile_x(
            "floor2_right_safe_x",
            float(self._profile.get("floor2_right_safe_x", self._profile.get("floor2_right_x", 124))),
        )

    def _is_y_between(self, min_key: str, max_key: str,
                      fallback_min: float, fallback_max: float,
                      tolerance: int = 1) -> bool:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            pos = self._fresh_pos()
        if pos is None or pos[1] is None:
            return False
        lower = self._profile_y(min_key, fallback_min)
        upper = self._profile_y(max_key, fallback_max)
        if upper < lower:
            lower, upper = upper, lower
        y = int(pos[1])
        return lower - tolerance <= y <= upper + tolerance

    def _is_near_point(self, prefix: str, fallback_x: float, fallback_y: float,
                       x_tolerance: int = 4, y_tolerance: int = 2,
                       require_x: bool = True) -> bool:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return False
        target_y = self._point_y(prefix, fallback_y)
        if abs(int(pos[1]) - target_y) > y_tolerance:
            return False
        if not require_x:
            return True
        target_x = self._point_x(prefix, fallback_x)
        return abs(float(pos[0]) - target_x) <= x_tolerance

    def _wait_point(self, prefix: str, fallback_x: float, fallback_y: float,
                    timeout_sec: float = 0.8, require_x: bool = True,
                    x_tolerance: int = 4, y_tolerance: int = 2) -> bool:
        return self._wait_floor(
            lambda: self._is_near_point(
                prefix,
                fallback_x,
                fallback_y,
                x_tolerance=x_tolerance,
                y_tolerance=y_tolerance,
                require_x=require_x,
            ),
            timeout_sec,
        )

    def _wait_y_range(self, min_key: str, max_key: str,
                      fallback_min: float, fallback_max: float,
                      timeout_sec: float = 0.8) -> bool:
        return self._wait_floor(
            lambda: self._is_y_between(min_key, max_key, fallback_min, fallback_max),
            timeout_sec,
        )

    def _is_stair7_return_y(self) -> bool:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return False
        _floor2_min, floor2_max = self._floor2_y_range()
        floor1_min, _floor1_max = self._floor1_y_range()
        return floor2_max < float(pos[1]) < floor1_min

    def _is_platform24_floor1_y(self) -> bool:
        return self._is_y_between("floor1_y_min", "floor1_y_max", 75, 77, tolerance=1)

    def _hold_attack_for(self, seconds: float) -> None:
        attack_key = self._attack_key()
        if not attack_key:
            return
        h = self._route_inputs()
        h.hold_action(attack_key)
        self._sleep(down_5(seconds))
        h.release_action(attack_key)

    def _release_attack_key(self) -> None:
        attack_key = self._attack_key()
        if attack_key:
            self._route_inputs().release_action(attack_key)

    def _release_owned_inputs(self) -> None:
        """빨코2 루틴이 직접 잡은 이동/공격 입력만 해제한다."""
        h = self._route_inputs()
        h.release_direction()
        self._release_attack_key()

    def _teleport_once(self, direction: str) -> None:
        self._teleport_once_with_hold(direction, float(self._profile.get("teleport_hold_sec", 0.05)))

    def _teleport_once_with_hold(self, direction: str, hold_sec: float,
                                 lead_sec: float | None = None) -> None:
        teleport_key = self._teleport_key()
        if not teleport_key:
            return
        if direction in ("up", "down"):
            current = self._current_pos()
            if current is None and self._last_position_was_floor1():
                self._route_inputs().release_direction()
                self._log(
                    f"[rednose2v5] {direction} teleport blocked: "
                    "position missing after floor1 detection"
                )
                return
        h = self._route_inputs()
        if direction in ("left", "right"):
            self._last_horizontal_intent = direction
            h.hold_direction(direction)
            if lead_sec is None:
                lead_sec = float(self._profile.get("teleport_lead_sec", 0.07))
            if lead_sec > 0:
                self._sleep(lead_sec)
            h.press_action(teleport_key, hold_sec)
            h.release_direction()
            return

        h.release_direction()
        h.hold_action(direction)
        vertical_lead_sec = (
            float(self._profile.get("vertical_teleport_lead_sec", 0.15))
            if lead_sec is None
            else max(0.0, float(lead_sec))
        )
        self._sleep(vertical_lead_sec)
        try:
            h.press_action(teleport_key, hold_sec)
        finally:
            h.release_action(direction)

    def _last_position_was_floor1(self) -> bool:
        position = self._last_detected_position
        if position is None:
            return False
        floor1_min, floor1_max = self._floor1_y_range()
        tolerance = self._floor_y_tolerance()
        return floor1_min - tolerance <= float(position[1]) <= floor1_max + tolerance

    def _position_loss_direction(
        self,
        last_position: tuple[float, float] | None,
        last_direction: str | None,
    ) -> str | None:
        if last_position is None:
            return last_direction
        x = float(last_position[0])
        left_edge = self._profile_x(
            "position_loss_left_edge_x",
            self._floor2_left_x(),
        )
        right_edge = self._profile_x(
            "position_loss_right_edge_x",
            self._floor2_right_safe_x(),
        )
        if x <= left_edge:
            return "right"
        if x >= right_edge:
            return "left"
        return last_direction

    def _teleport_attack(
        self,
        direction: str,
        attack_hold_sec: float | None = None,
        teleport_hold_sec: float | None = None,
    ) -> None:
        attack_key = self._attack_key()
        teleport_key = self._teleport_key()
        if not attack_key or not teleport_key:
            return
        h = self._route_inputs()
        attack_hold_value = (
            self._profile.get("attack_hold_sec", 0.08)
            if attack_hold_sec is None
            else attack_hold_sec
        )
        teleport_hold = (
            self._profile.get("teleport_hold_sec", 0.05)
            if teleport_hold_sec is None
            else teleport_hold_sec
        )
        attack_hold = down_5(float(attack_hold_value))
        started_at = time.monotonic()
        h.hold_direction(direction)
        h.hold_action(attack_key)
        try:
            self._sleep(float(self._profile.get("attack_to_teleport_sec", 0.05)))
            h.press_action(teleport_key, float(teleport_hold))
            remaining = attack_hold - (time.monotonic() - started_at)
            if remaining > 0.0:
                self._sleep(remaining)
        finally:
            h.release_direction()
            h.release_action(attack_key)

    def _tap_attack(self, count: int = 1) -> None:
        attack_key = self._attack_key()
        if not attack_key:
            return
        h = self._route_inputs()
        hold_sec = float(self._profile.get("attack_hold_sec", 0.08))
        interval_sec = float(self._profile.get("retry_attack_interval_sec", 0.12))
        for index in range(max(1, int(count))):
            h.press_action(attack_key, hold_sec)
            if index < count - 1:
                self._sleep(interval_sec)

    def _retry_attack_once(self) -> None:
        attack_key = self._attack_key()
        if not attack_key:
            return
        h = self._route_inputs()
        hold_sec = float(self._profile.get("retry_attack_hold_sec", 1.5))
        h.press_action(attack_key, hold_sec)

    def _stair7_up_right_teleport_once(self) -> None:
        self._teleport_once("up")
        pos = self._current_pos()
        bias_correct_sec = float(self._profile.get("stair7_right_bias_correct_sec", 0.0))
        if bias_correct_sec > 0.0 and pos is not None and float(pos[0]) >= self._stair7_right_bias_x():
            h = self._route_inputs()
            h.hold_direction("left")
            self._sleep(bias_correct_sec)
            h.release_direction()
        self._teleport_once_with_hold(
            "right",
            float(self._profile.get("stair7_right_teleport_hold_sec", self._profile.get("teleport_hold_sec", 0.05))),
            lead_sec=float(self._profile.get("stair7_right_teleport_lead_sec", 0.0)),
        )
        self._route_inputs().release_direction()

    def _targets_for_move(self, block) -> list[float]:
        start_x = self._block_x(block, "start_x", 0)
        end_x = self._block_x(block, "end_x", 0)
        if end_x > start_x:
            mode = str(getattr(block, "mode", "count") or "count")
            if mode == "pass":
                return [end_x]
            sweeps = max(1, int(getattr(block, "sweeps", 1)))
            return [value for _ in range(sweeps) for value in (end_x, start_x)]
        return [self._block_x(block, "target_x", 0)]

    def _move_to_target_v5(self, target_x: float, attack: bool = True,
                           interval_sec: float | None = None,
                           floor_guard: Callable[[], bool] | None = None,
                           guard_label: str = "",
                           teleport_landing_range: tuple[float, float] | None = None,
                           teleport_stop_range: tuple[float, float] | None = None,
                           teleport_stop_distance: float | None = None,
                           arrival_tolerance: float | None = None,
                           arrival_range: tuple[float, float] | None = None,
                           allow_crossed_arrival: bool = True,
                           arrival_side: str | None = None,
                           active_fn: Callable[[], bool] | None = None,
                           opening_attack_timings: tuple[tuple[float, float, float], ...] = ()) -> bool:
        h = self._route_inputs()
        is_active = active_fn or self._active
        tolerance = self._arrival_tolerance() if arrival_tolerance is None else max(0.0, float(arrival_tolerance))
        stop_distance = (
            self._teleport_stop_px()
            if teleport_stop_distance is None
            else max(0.0, float(teleport_stop_distance))
        )
        previous_x = None
        last_direction = self._last_horizontal_intent
        last_detected_position = self._last_detected_position
        position_missing_since: float | None = None
        next_teleport_at = 0.0
        last_teleport_position: tuple[float, float] | None = None
        crossed_target = False
        teleport_count = 0
        started = time.monotonic()
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        first_pos = self._current_pos()
        if first_pos is not None:
            last_detected_position = (float(first_pos[0]), float(first_pos[1]))
        if first_pos is None:
            self._log(
                f"[rednose2v5] move enter target={target_x:.0f}, "
                f"attack={attack}, pos=None, active={is_active()}"
            )
        else:
            self._log(
                f"[rednose2v5] move enter target={target_x:.0f}, "
                f"attack={attack}, pos=x{int(first_pos[0])}/y{int(first_pos[1])}, "
                f"active={is_active()}"
            )
        try:
            while is_active():
                pos = self._current_pos()
                if pos is None:
                    now = time.monotonic()
                    if position_missing_since is None:
                        position_missing_since = now
                    recovery_sec = max(
                        0.0,
                        float(self._profile.get("position_loss_recovery_sec", 0.8)),
                    )
                    recovery_direction = self._position_loss_direction(
                        last_detected_position,
                        last_direction,
                    )
                    if (
                        recovery_direction in {"left", "right"}
                        and now - position_missing_since <= recovery_sec
                    ):
                        h.hold_direction(recovery_direction)
                    else:
                        h.release_direction()
                    self._sleep(0.03)
                    continue
                position_missing_since = None
                last_detected_position = (float(pos[0]), float(pos[1]))
                self._last_detected_position = last_detected_position
                if floor_guard is not None and not floor_guard():
                    first_off_floor = pos
                    fresh_pos, _fresh_seen_at = self._fresh_sample()
                    if fresh_pos is not None and floor_guard():
                        self._log(
                            f"[rednose2v5] transient off-floor ignored "
                            f"x={int(first_off_floor[0])}/y={int(first_off_floor[1])} "
                            f"-> x={int(fresh_pos[0])}/y={int(fresh_pos[1])}"
                        )
                        pos = fresh_pos
                    else:
                        h.release_direction()
                        self._release_attack_key()
                        label = f" during {guard_label}" if guard_label else ""
                        self._log(
                            f"[rednose2v5] floor changed{label}; recover required "
                            f"(pos=x{int(pos[0])}/y{int(pos[1])}, floor={self._floor_name_v5(None)})"
                        )
                        return False
                x = float(pos[0])
                y = float(pos[1])
                current_position = (x, y)
                if last_teleport_position is not None and current_position != last_teleport_position:
                    self._log(
                        f"[rednose2v5] teleport position updated "
                        f"x={int(last_teleport_position[0])}/y={int(last_teleport_position[1])} "
                        f"-> x={int(x)}/y={int(y)}"
                    )
                    last_teleport_position = None
                dist = target_x - x
                crossed = previous_x is not None and min(previous_x, x) <= target_x <= max(previous_x, x)
                crossed_target = crossed_target or crossed
                side_reached = (
                    (arrival_side == "left" and x <= target_x + tolerance)
                    or (arrival_side == "right" and x >= target_x - tolerance)
                )
                if arrival_range is not None:
                    arrival_left, arrival_right = sorted(arrival_range)
                    reached = arrival_left <= x <= arrival_right
                else:
                    reached = side_reached or abs(dist) <= tolerance or (allow_crossed_arrival and crossed)
                if reached:
                    released_direction = h.direction
                    release_started = time.perf_counter()
                    self._log(
                        f"[rednose2v5] direction key_up request key={released_direction}, "
                        f"x={int(x)}, target={target_x:.0f}"
                    )
                    h.release_direction()
                    release_elapsed_ms = (time.perf_counter() - release_started) * 1000.0
                    self._log(
                        f"[rednose2v5] direction key_up sent key={released_direction}, "
                        f"call={release_elapsed_ms:.3f}ms"
                    )
                    self._log(
                        f"[rednose2v5] move reached target={target_x:.0f}, "
                        f"x={int(x)}, dist={dist:.1f}, side={arrival_side}, crossed={crossed}"
                    )
                    return True

                direction = "right" if dist > 0 else "left"
                last_direction = direction
                self._last_horizontal_intent = direction
                previous_direction = h.direction
                direction_changed = previous_direction != direction
                if direction_changed:
                    direction_started = time.perf_counter()
                    self._log(
                        f"[rednose2v5] direction key_down request key={direction}, "
                        f"previous={previous_direction}, x={int(x)}, target={target_x:.0f}"
                    )
                h.hold_direction(direction)
                if direction_changed:
                    direction_elapsed_ms = (time.perf_counter() - direction_started) * 1000.0
                    self._log(
                        f"[rednose2v5] direction key_down sent key={direction}, "
                        f"call={direction_elapsed_ms:.3f}ms"
                    )
                now = time.monotonic()
                teleport_lands_in_range = True
                if teleport_landing_range is not None:
                    step_px = self._teleport_step_px()
                    landing_x = x + step_px if direction == "right" else x - step_px
                    landing_left, landing_right = teleport_landing_range
                    teleport_lands_in_range = landing_left <= landing_x <= landing_right
                outside_stop_range = True
                if teleport_stop_range is not None:
                    stop_left, stop_right = teleport_stop_range
                    outside_stop_range = x < stop_left or x > stop_right
                can_teleport = (
                    not crossed_target
                    and abs(dist) > stop_distance
                    and teleport_lands_in_range
                    and outside_stop_range
                    and now >= next_teleport_at
                    and last_teleport_position is None
                )
                if can_teleport:
                    opening_timing = None
                    if attack:
                        opening_timing = (
                            opening_attack_timings[teleport_count]
                            if teleport_count < len(opening_attack_timings)
                            else None
                        )
                        if opening_timing is None:
                            self._teleport_attack(direction)
                        else:
                            self._teleport_attack(
                                direction,
                                attack_hold_sec=opening_timing[0],
                                teleport_hold_sec=opening_timing[1],
                            )
                        log_label = "teleport-attack"
                    else:
                        self._release_attack_key()
                        self._teleport_once(direction)
                        log_label = "teleport-move"
                    last_teleport_position = current_position
                    interval = (
                        opening_timing[2]
                        if attack and opening_timing is not None
                        else self._teleport_interval() if interval_sec is None else interval_sec
                    )
                    teleport_count += 1
                    next_teleport_at = time.monotonic() + max(0.0, float(interval))
                    if now - self._last_teleport_log_at >= 0.5:
                        self._last_teleport_log_at = now
                        self._log(
                            f"[rednose2v5] {log_label} direction={direction}, "
                            f"x={int(x)}, target={target_x:.0f}, dist={dist:.1f}"
                        )
                    latest_after_input, _latest_seen_at = self._fresh_sample()
                    if latest_after_input is not None:
                        latest_position = (
                            float(latest_after_input[0]),
                            float(latest_after_input[1]),
                        )
                        self._log(
                            "[rednose2v5] teleport fresh position consumed "
                            f"x={int(current_position[0])}/y={int(current_position[1])} "
                            f"-> x={int(latest_position[0])}/y={int(latest_position[1])}"
                        )
                        last_teleport_position = None
                        previous_x = x
                        continue
                previous_x = x
                if time.monotonic() - started >= self._max_step_sec():
                    h.release_direction()
                    self._log(f"[rednose2v5] move timeout: x={int(x)}, target={target_x:.0f}")
                    return False
                self._sleep(0.03)
            h.release_direction()
            self._release_attack_key()
            self._log(
                f"[rednose2v5] move aborted inactive target={target_x:.0f}, "
                f"active={is_active()}, stop={self._stop.is_set()}"
            )
            return False
        finally:
            self.owns_movement = previous_owns_movement

    def _split_pickup_route(self, blocks: list) -> tuple[object | None, object | None, list]:
        ladder_index = next((i for i, block in enumerate(blocks) if block.type == "ladder"), -1)
        if ladder_index < 0:
            return None, None, [block for block in blocks if block.type == "move"]
        lower_moves = [block for block in blocks[:ladder_index] if block.type == "move"]
        upper_moves = [block for block in blocks[ladder_index + 1:] if block.type == "move"]
        return lower_moves[0] if lower_moves else None, blocks[ladder_index], upper_moves

    def _is_upper_floor_v5(self, ladder_block) -> bool:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return False
        y = int(pos[1])
        floor2_min, floor2_max = self._floor2_y_range()
        tolerance = self._floor_y_tolerance()
        return floor2_min - tolerance <= y <= floor2_max + tolerance

    def _is_lower_floor_v5(self, ladder_block) -> bool:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return False
        y = int(pos[1])
        floor1_min, floor1_max = self._floor1_y_range()
        tolerance = self._floor_y_tolerance()
        return floor1_min - tolerance <= y <= floor1_max + tolerance

    def _floor_name_v5(self, ladder_block) -> str:
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return "unknown"
        y = int(pos[1])
        tolerance = self._floor_y_tolerance()
        floor3_min, floor3_max = self._floor3_y_range()
        if floor3_min - tolerance <= y <= floor3_max + tolerance:
            return "upper-teleport-zone"
        floor2_min, floor2_max = self._floor2_y_range()
        if floor2_min - tolerance <= y <= floor2_max + tolerance:
            return "floor2"
        floor1_min, floor1_max = self._floor1_y_range()
        if floor1_min - tolerance <= y <= floor1_max + tolerance:
            return "floor1"
        if self._is_upper_floor_v5(ladder_block):
            return "upper"
        if self._is_lower_floor_v5(ladder_block):
            return "lower"
        return f"between(y={y})"

    def _move_label_v5(self, block, default_name: str) -> str:
        start_x = int(self._block_x(block, "start_x", 0))
        end_x = int(self._block_x(block, "end_x", 0))
        pos_y = self._block_y(block, "pos_y", -1)
        return f"{default_name} X{start_x}<->X{end_x} Y{pos_y}"

    def _wait_floor(self, predicate: Callable[[], bool], timeout_sec: float) -> bool:
        deadline = time.monotonic() + max(0.05, timeout_sec)
        while self._active() and time.monotonic() < deadline:
            if predicate():
                return True
            self._sleep(0.03)
        return predicate()

    def _drop_to_lower_floor_v5(self, ladder_block) -> bool:
        attempts = max(1, int(self._profile.get("drop_teleport_attempts", 8)))
        settle_sec = max(0.05, float(self._profile.get("vertical_teleport_settle_sec", 0.25)))
        h = self._route_inputs()
        self._release_attack_key()
        h.release_direction()
        if self._is_lower_floor_v5(ladder_block):
            return True
        for attempt in range(1, attempts + 1):
            if not self._active():
                return False
            self._log(f"[rednose2v5] pickup enter {attempt}/{attempts}: down-teleport")
            self._teleport_once("down")
            if self._wait_floor(lambda: self._is_lower_floor_v5(ladder_block), settle_sec):
                return True
        return False

    def _run_ladder_v5(self, block) -> bool:
        h = self._route_inputs()
        ladder_x = self._block_x(block, "ladder_x", 0)
        attempts = max(1, int(self._profile.get("ladder_teleport_attempts", 10)))
        settle_sec = max(0.05, float(self._profile.get("vertical_teleport_settle_sec", 0.25)))
        recover_interval = max(0.05, float(self._profile.get("recover_teleport_interval_sec", 0.1)))
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        try:
            self._release_attack_key()
            h.release_direction()
            if self._is_upper_floor_v5(block):
                return True

            for attempt in range(1, attempts + 1):
                if not self._active():
                    return False
                self._log(f"[rednose2v5] Hunter floor transition {attempt}/{attempts}: align X={ladder_x:.0f}, up-teleport")
                if not self._move_to_target_v5(ladder_x, attack=False, interval_sec=recover_interval):
                    return False
                self._release_attack_key()
                h.release_direction()
                self._teleport_once("up")
                if self._wait_floor(lambda: self._is_upper_floor_v5(block), settle_sec):
                    self._release_owned_inputs()
                    return True

                self._teleport_once("right")
                if self._wait_floor(lambda: self._is_upper_floor_v5(block), settle_sec):
                    self._release_owned_inputs()
                    return True

                pos = self._current_pos()
                y_text = "?" if pos is None or pos[1] is None else str(int(pos[1]))
                self._log(f"[rednose2v5] floor transition not reached, y={y_text}; retry")
            self._release_owned_inputs()
            return False
        finally:
            self.owns_movement = previous_owns_movement

    def _run_move_v5(self, block, floor_guard: Callable[[], bool] | None = None,
                     guard_label: str = "") -> bool:
        targets = self._targets_for_move(block)
        for index, target in enumerate(targets, start=1):
            self._log(f"[rednose2v5] move {index}/{len(targets)} start -> X={target:.0f}")
            if not self._move_to_target_v5(
                target,
                floor_guard=floor_guard,
                guard_label=guard_label,
            ):
                self._release_owned_inputs()
                return False
            self._log(f"[rednose2v5] move {index}/{len(targets)} complete -> X={target:.0f}")
        self._release_owned_inputs()
        return True

    def _run_pickup_route_v5(self, lower_move, ladder_block) -> bool:
        started = time.monotonic()
        self._log("[rednose2v5] floor1 pickup route start")
        if ladder_block is not None and not self._drop_to_lower_floor_v5(ladder_block):
            self._log("[rednose2v5] floor1 entry failed")
            return False
        if lower_move is not None and not self._run_move_v5(
            lower_move,
            floor_guard=lambda: ladder_block is None or self._is_lower_floor_v5(ladder_block),
            guard_label=self._move_label_v5(lower_move, "floor1 pickup"),
        ):
            self._log("[rednose2v5] floor1 pickup move failed")
            return False
        if ladder_block is not None:
            if time.monotonic() - started > self._pickup_max_sec():
                self._log("[rednose2v5] floor1 pickup timeout")
                return False
            if not self._run_ladder_v5(ladder_block):
                self._log("[rednose2v5] return to floor2 failed")
                return False
        self._last_pickup_at = time.monotonic()
        self._log("[rednose2v5] floor1 pickup route complete")
        return True

    def _run_pickup_cycle_once(self, blocks: list) -> bool:
        return self._run_rednose_new_v5_once()

    def _recover_floor2_hunt_from_fall(self) -> bool:
        fell_from_left = (
            self._last_floor2_x is not None
            and self._last_floor2_x < self._point_x("stair7", 41)
        )
        recovered = self._return_floor2_from_stair7()
        if not recovered:
            return False
        if fell_from_left:
            self._log("[rednose2v5] left-side fall recovered; slow pickup sweep to right edge")
            if not self._move_floor2_right_edge():
                return False
            self._main_move_index = 1
        self._last_pickup_at = time.monotonic()
        self._next_collection_at = self._last_pickup_at + self._random_hunt_cycle_sec()
        self._collection_stage = None
        self._log(
            f"[rednose2v5] off-floor recovery complete; "
            f"collection timer reset to {self._next_collection_at - self._last_pickup_at:.4f}s"
        )
        return True

    def _run_floor2_hunt_once(self) -> bool:
        if not self._active():
            return False
        if not self._is_upper_floor_v5(None):
            deadline = time.monotonic() + 0.6
            while self._active() and time.monotonic() < deadline:
                pos = self._fresh_pos()
                if pos is not None and pos[1] is not None and self._is_upper_floor_v5(None):
                    break
                self._sleep(0.05)
        if not self._active():
            return False
        if not self._is_upper_floor_v5(None):
            self._log("[rednose2v5] floor2 hunt detected off-floor; recover through stair7")
            return self._recover_floor2_hunt_from_fall()

        if time.monotonic() >= self._next_collection_at:
            return self._run_rednose_new_v5_collection()

        if not self._active():
            return False
        target = self._floor2_right_x() if self._main_move_index % 2 == 0 else self._floor2_left_x()
        arrival_side = "right" if self._main_move_index % 2 == 0 else "left"
        self._log(
            f"[rednose2v5] floor2 timed hunt target X={target:.0f}, "
            f"collection in {max(0.0, self._next_collection_at - time.monotonic()):.1f}s"
        )
        pos = self._current_pos()
        pos_text = "None" if pos is None else f"x{int(pos[0])}/y{int(pos[1])}"
        self._log(
            f"[rednose2v5] floor2 move request pos={pos_text}, "
            f"rangeY={self._floor2_y_range()}, active={self._active()}"
        )
        if self._move_to_target_v5(
            target,
            attack=True,
            interval_sec=self._segment_interval("floor2_hunt_teleport_interval_sec"),
            floor_guard=lambda: self._is_upper_floor_v5(None),
            guard_label="rednose-new floor2 timed hunt",
            teleport_stop_distance=0.0,
            arrival_side=arrival_side,
        ):
            self._main_move_index += 1
            return True
        if not self._is_upper_floor_v5(None):
            self._log("[rednose2v5] floor2 hunt left floor; recover through stair7")
            return self._recover_floor2_hunt_from_fall()
        return False

    def _run_rednose_new_v5_once(self) -> bool:
        if self._next_collection_at <= 0:
            self._next_collection_at = time.monotonic() + self._random_hunt_cycle_sec()
        if self._collection_stage is not None:
            return self._run_rednose_new_v5_collection()
        return self._run_floor2_hunt_once()

    def _run_rednose_new_v5_collection(self) -> bool:
        h = self._route_inputs()
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        try:
            collection_in_progress = self._collection_stage is not None
            stage = self._collection_stage or "platform24"
            stage, upper_platform_confirmed = self._advance_collection_stage_from_position(stage)
            self._collection_stage = stage
            if not self._is_upper_floor_v5(None) and not upper_platform_confirmed:
                self._log("[rednose2v5] collection requested off floor2; recover through stair7 first")
                if not self._return_floor2_from_stair7():
                    return False
                if not collection_in_progress:
                    self._last_pickup_at = time.monotonic()
                    self._next_collection_at = self._last_pickup_at + self._random_hunt_cycle_sec()
                    self._collection_stage = None
                    self._log(
                        f"[rednose2v5] accidental fall recovery complete; resume floor2 hunt, "
                        f"collection timer reset to {self._next_collection_at - self._last_pickup_at:.4f}s"
                    )
                    return True
                self._collection_stage = "right_edge"
                self._log(
                    f"[rednose2v5] collection floor1 recovery reselected "
                    f"stage={stage} -> right_edge"
                )
                return True

            self._log(f"[rednose2v5] rednose-new collection route start · stage={stage}")
            self._release_attack_key()

            if stage == "platform24":
                if not self._enter_platform24():
                    if not self._is_upper_floor_v5(None):
                        self._log("[rednose2v5] step 24 reached floor1 early; continue collection through stair7")
                        stage = "stair7_return"
                        self._collection_stage = stage
                    else:
                        self._collection_stage = None
                        return False
                else:
                    stage = "floor1_drop"
                    self._collection_stage = stage

            if stage == "floor1_drop":
                if not self._drop_from_platform24_to_floor1():
                    self._collection_stage = None
                    return False
                self._log("[rednose2v5] floor1 drop confirmed; right-teleport twice before stair7")
                self._teleport_once("right")
                self._teleport_once("right")
                stage = "stair7_return"
                self._collection_stage = stage

            if stage == "stair7_return":
                if not self._return_floor2_from_stair7():
                    return False
                stage = "right_edge"
                self._collection_stage = stage

            if stage == "right_edge":
                if not self._move_floor2_right_edge():
                    if not self._is_upper_floor_v5(None):
                        self._log("[rednose2v5] right edge failed off floor2; recover and retry right edge")
                        self._collection_stage = "right_edge"
                        return self._return_floor2_from_stair7()
                    self._collection_stage = None
                    return False
                stage = "platform1415"
                self._collection_stage = stage

            if stage == "platform1415":
                if not self._enter_platform1415():
                    self._collection_stage = self._reselect_collection_stage_after_failure(
                        "right_edge"
                    )
                    return False
                stage = "platform16"
                self._collection_stage = stage

            if stage == "platform16":
                if not self._enter_platform16():
                    self._collection_stage = self._reselect_collection_stage_after_failure(
                        "platform1415"
                    )
                    return False
                stage = "platform27"
                self._collection_stage = stage

            if stage == "platform27":
                if not self._enter_platform27():
                    self._collection_stage = self._reselect_collection_stage_after_failure(
                        "platform16"
                    )
                    return False
                stage = "return_floor2"
                self._collection_stage = stage

            if stage == "return_floor2":
                if not self._finish_platform27_and_return_floor2():
                    self._collection_stage = self._reselect_collection_stage_after_failure(
                        "platform27"
                    )
                    return False

            self._last_pickup_at = time.monotonic()
            self._next_collection_at = self._last_pickup_at + self._random_hunt_cycle_sec()
            self._main_move_index = random.choice((0, 1))
            self._collection_stage = None
            self._log(
                f"[rednose2v5] rednose-new collection route complete; "
                f"next collection in {self._next_collection_at - self._last_pickup_at:.4f}s"
            )
            return True
        finally:
            self._release_owned_inputs()
            self.owns_movement = previous_owns_movement

    def _advance_collection_stage_from_position(self, stage: str) -> tuple[str, bool]:
        """현재 Y가 이미 도착한 상위 발판이면 앞 단계를 건너뛴다."""
        position = self._current_pos()
        if position is None or position[1] is None:
            return stage, False
        y = float(position[1])

        def in_range(min_key: str, max_key: str, fallback_min: float, fallback_max: float) -> bool:
            lower = self._profile_y(min_key, fallback_min)
            upper = self._profile_y(max_key, fallback_max)
            return min(lower, upper) <= y <= max(lower, upper)

        if in_range("platform27_y_min", "platform27_y_max", 50, 50):
            return "return_floor2", True
        if in_range("platform16_y_min", "platform16_y_max", 47, 48):
            return "platform27", True
        if in_range("platform1415_y_min", "platform1415_y_max", 54, 55):
            return "platform16", True
        return stage, False

    def _reselect_collection_stage_after_failure(self, confirmed_stage: str) -> str:
        """실패 후 실제 위치를 우선하고 미검출이면 확정 단계의 다음 순서를 유지한다."""
        next_by_confirmed = {
            "right_edge": "platform1415",
            "platform1415": "platform16",
            "platform16": "platform27",
            "platform27": "return_floor2",
        }
        fallback_stage = next_by_confirmed[confirmed_stage]
        position = self._current_pos()
        if position is None or position[1] is None:
            self._log(
                f"[rednose2v5] collection stage reselect position=missing, "
                f"confirmed={confirmed_stage}, next={fallback_stage}"
            )
            return fallback_stage

        detected_stage, upper_platform_confirmed = self._advance_collection_stage_from_position(
            fallback_stage
        )
        if upper_platform_confirmed:
            selected_stage = detected_stage
        elif self._is_lower_floor_v5(None):
            selected_stage = "stair7_return"
        elif self._is_upper_floor_v5(None):
            selected_stage = "right_edge"
        else:
            selected_stage = fallback_stage
        self._log(
            f"[rednose2v5] collection stage reselect "
            f"x={float(position[0]):.0f}, y={float(position[1]):.0f}, "
            f"confirmed={confirmed_stage}, next={selected_stage}"
        )
        return selected_stage

    def _manual_active(self) -> bool:
        block_stop = getattr(self._br, "_stop", None)
        if callable(block_stop) and block_stop():
            return False
        return not self._stop.is_set()

    def can_start_auto_sell(self) -> bool:
        """회수 입력이 끝난 2층 일반 사냥 상태에서만 자동판매를 허용한다."""
        return (
            self.can_pause_for_auto_sell()
            and not self.owns_movement
        )

    def can_pause_for_auto_sell(self) -> bool:
        """회수 중이 아니고 판매 진입 가능한 층이면 정상 사냥을 멈출 수 있다."""
        return (
            self._collection_stage is None
            and self._auto_sell_floor() in {"floor2", "shop-entry"}
        )

    def auto_sell_block_reason(self, require_idle: bool = False) -> str:
        """자동판매 진입을 막는 빨코2 상태를 로그용으로 반환한다."""
        if self._collection_stage is not None:
            return f"회수 단계 진행 중({self._collection_stage})"
        floor = self._auto_sell_floor()
        if floor not in {"floor2", "shop-entry"}:
            return f"자동판매 진입 불가 위치({floor})"
        if require_idle and self.owns_movement:
            return "정상 사냥 이동 입력 반환 대기 초과"
        return ""

    def _auto_sell_floor(self) -> str:
        """자동판매 진입용으로 허용 오차 없이 현재 층을 구분한다."""
        pos = self._current_pos()
        if pos is None or pos[1] is None:
            return "unknown"
        x = float(pos[0])
        y = int(pos[1])
        floor3_min, floor3_max = self._floor3_y_range()
        floor2_min, floor2_max = self._floor2_y_range()
        floor1_min, floor1_max = self._floor1_y_range()
        if floor3_min <= y <= floor3_max:
            entry_min = self._profile_x("auto_sell_entry_x_min", 123)
            entry_max = self._profile_x("auto_sell_entry_x_max", 136)
            return "shop-entry" if entry_min <= x <= entry_max else "upper-platform"
        if floor2_min <= y <= floor2_max:
            return "floor2"
        if floor1_min <= y <= floor1_max:
            return "floor1"
        if y < floor2_min:
            return "upper-platform"
        return "between"

    def _wait_auto_sell_floor(self, expected: str, timeout_sec: float) -> bool:
        """자동판매 텔포 뒤 실제 도착 층이 확인될 때까지만 짧게 기다린다."""
        deadline = time.monotonic() + max(0.05, float(timeout_sec))
        while self._manual_active() and time.monotonic() < deadline:
            self._fresh_pos()
            if self._auto_sell_floor() == expected:
                return True
            self._sleep(0.03)
        return self._auto_sell_floor() == expected

    def _drop_to_floor2_for_auto_sell(self) -> bool:
        """회수 중 상단 발판에서 아랫텔포로 2층까지 내려온다."""
        for attempt in range(1, 9):
            if not self._manual_active():
                return False
            self._log(f"[rednose2v5] auto-sell floor2 recovery: down-teleport ({attempt}/8)")
            self._teleport_once("down")
            for _wait in range(10):
                self._fresh_pos()
                floor_name = self._auto_sell_floor()
                if floor_name == "floor2":
                    return True
                if floor_name == "floor1":
                    return self._return_floor2_from_stair7(active_fn=self._manual_active)
                self._sleep(0.03)
        return False

    def prepare_auto_sell_from_floor2(self) -> bool:
        """빨코2 자동판매 전용 진입. 2층 X=123~136 범위에서 윗텔포한다."""
        x_min = self._profile_x("auto_sell_entry_x_min", 123)
        x_max = self._profile_x("auto_sell_entry_x_max", 136)
        target_x = self._profile_x("auto_sell_entry_x", 129.5)
        floor_name = self._auto_sell_floor()
        if floor_name == "shop-entry":
            self._log("[rednose2v5] auto-sell entry ready: already on shop entry floor")
            return True
        if floor_name != "floor2":
            for _attempt in range(10):
                self._fresh_pos()
                floor_name = self._auto_sell_floor()
                if floor_name not in {"unknown", "between"}:
                    break
                self._sleep(0.05)
            if floor_name == "shop-entry":
                self._log("[rednose2v5] auto-sell entry ready after refresh: shop entry floor")
                return True
            if floor_name != "floor2":
                self._log(f"[rednose2v5] auto-sell entry blocked: unsupported floor={floor_name}")
                return False
        self._log(
            f"[rednose2v5] auto-sell entry: align X={target_x:.0f} "
            f"range {x_min:.0f}-{x_max:.0f}, up-teleport"
        )
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        try:
            pos = self._current_pos()
            if pos is None or not (x_min <= float(pos[0]) <= x_max):
                if not self._move_to_target_v5(
                    target_x,
                    attack=False,
                    interval_sec=0.1,
                    floor_guard=lambda: self._is_upper_floor_v5(None),
                    guard_label="rednose2 auto-sell entry",
                    arrival_tolerance=3.0,
                    active_fn=self._manual_active,
                ):
                    return False
            pos = None
            for wait_attempt in range(1, 11):
                pos = self._fresh_pos()
                if pos is not None and self._is_upper_floor_v5(pos) and x_min <= float(pos[0]) <= x_max:
                    break
                x_text = "?" if pos is None or pos[0] is None else f"{float(pos[0]):.0f}"
                y_text = "?" if pos is None or pos[1] is None else f"{float(pos[1]):.0f}"
                self._log(
                    f"[rednose2v5] auto-sell entry wait fresh pos "
                    f"({wait_attempt}/10): x={x_text}, y={y_text}, "
                    f"range {x_min:.0f}-{x_max:.0f}, floor2={self._is_upper_floor_v5(pos)}"
                )
                self._sleep(0.08)
            if pos is None or not (x_min <= float(pos[0]) <= x_max):
                x_text = "?" if pos is None or pos[0] is None else f"{float(pos[0]):.0f}"
                y_text = "?" if pos is None or pos[1] is None else f"{float(pos[1]):.0f}"
                self._log(
                    f"[rednose2v5] auto-sell entry blocked: "
                    f"x={x_text}, y={y_text}, range {x_min:.0f}-{x_max:.0f}, "
                    f"floor2={self._is_upper_floor_v5(pos)}"
                )
                return False
            if not self._is_upper_floor_v5(pos):
                x_text = "?" if pos is None or pos[0] is None else f"{float(pos[0]):.0f}"
                y_text = "?" if pos is None or pos[1] is None else f"{float(pos[1]):.0f}"
                self._log(
                    f"[rednose2v5] auto-sell entry blocked: not floor2 "
                    f"x={x_text}, y={y_text}, range {x_min:.0f}-{x_max:.0f}"
                )
                return False
            self._release_attack_key()
            entry_attempts = max(1, int(self._profile.get("auto_sell_entry_attempts", 3)))
            for attempt in range(1, entry_attempts + 1):
                self._teleport_once("up")
                if self._wait_auto_sell_floor("shop-entry", 0.6):
                    self._log(
                        f"[rednose2v5] auto-sell entry complete "
                        f"({attempt}/{entry_attempts})"
                    )
                    return True
                floor_name = self._auto_sell_floor()
                self._log(
                    f"[rednose2v5] auto-sell entry not confirmed "
                    f"({attempt}/{entry_attempts}): floor={floor_name}"
                )
                if floor_name not in {"floor2", "unknown", "between"}:
                    break
            self._log("[rednose2v5] auto-sell entry failed: safe zone not confirmed")
            return False
        finally:
            self._route_inputs().release_direction()
            self.owns_movement = previous_owns_movement

    def return_floor2_after_auto_sell(self) -> bool:
        """빨코2 자동판매 종료 후 아랫텔포로 2층 복귀한다."""
        self._log("[rednose2v5] auto-sell return: down-teleport to floor2")
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        try:
            self._release_attack_key()
            return_attempts = max(1, int(self._profile.get("auto_sell_return_attempts", 3)))
            for attempt in range(1, return_attempts + 1):
                self._teleport_once_with_hold(
                    "down",
                    float(self._profile.get("teleport_hold_sec", 0.3)),
                    lead_sec=0.30,
                )
                if not self._wait_floor(lambda: self._is_upper_floor_v5(None), 0.75):
                    self._log(
                        f"[rednose2v5] auto-sell return retry "
                        f"({attempt}/{return_attempts})"
                    )
                    continue
                self._last_pickup_at = time.monotonic()
                self._next_collection_at = self._last_pickup_at + self._random_hunt_cycle_sec()
                self._collection_stage = None
                self._main_move_index = 0
                self._log(
                    f"[rednose2v5] auto-sell return complete; "
                    f"collection timer reset to {self._next_collection_at - self._last_pickup_at:.4f}s"
                )
                return True
            self._log("[rednose2v5] auto-sell return not confirmed")
            return False
        finally:
            self._route_inputs().release_direction()
            self.owns_movement = previous_owns_movement

    def _enter_platform24(self) -> bool:
        approach_x = self._profile_x("platform24_approach_x", 43)
        attempts = max(1, int(self._profile.get("platform24_attempts", 3)))
        self._log(f"[rednose2v5] step 24: approach X={approach_x:.0f}, left-teleport")
        for attempt in range(1, attempts + 1):
            if not self._is_upper_floor_v5(None):
                self._log(f"[rednose2v5] step 24 interrupted off floor2 ({attempt}/{attempts})")
                return False
            if not self._move_to_target_v5(
                approach_x,
                attack=True,
                interval_sec=self._segment_interval("platform24_approach_interval_sec"),
                arrival_side="left",
            ):
                return False
            self._release_attack_key()
            self._teleport_once("left")
            if self._wait_point(
                "platform24",
                30,
                61,
                timeout_sec=0.45,
                x_tolerance=2,
                y_tolerance=1,
            ):
                self._log(f"[rednose2v5] step 24 reached ({attempt}/{attempts})")
                return True
            if not self._is_upper_floor_v5(None):
                self._log(f"[rednose2v5] step 24 skipped by floor1 arrival ({attempt}/{attempts})")
                return True
            self._log(f"[rednose2v5] step 24 not confirmed ({attempt}/{attempts})")
        return False

    def _drop_from_platform24_to_floor1(self) -> bool:
        attempts = max(1, int(self._profile.get("drop_teleport_attempts", 3)))
        self._release_attack_key()
        self._log("[rednose2v5] step floor1: down-teleport from platform24")
        if self._is_platform24_floor1_y():
            self._log("[rednose2v5] floor1 already reached before down-teleport")
            return True
        for attempt in range(1, attempts + 1):
            self._teleport_once("down")
            if self._wait_floor(self._is_platform24_floor1_y, 0.45):
                self._log(f"[rednose2v5] floor1 reached ({attempt}/{attempts})")
                return True
        return False

    def _return_floor2_from_stair7(self, active_fn: Callable[[], bool] | None = None) -> bool:
        stair_x = self._point_x("stair7", 41)
        stair_left, stair_right = self._stair7_x_range()
        attempts = max(1, int(self._profile.get("stair7_return_attempts", 10)))
        self._log(
            f"[rednose2v5] step stair7: approach X={stair_x:.0f} "
            f"range {stair_left:.0f}-{stair_right:.0f}, up/right teleport"
        )
        is_active = active_fn or self._active
        if self._is_upper_floor_v5(None):
            self._log("[rednose2v5] already on floor2 before stair7 return")
            return True
        for attempt in range(1, attempts + 1):
            if not is_active():
                return False
            if self._is_upper_floor_v5(None):
                self._log("[rednose2v5] floor2 reached during stair7 recovery")
                return True
            if self._is_stair7_return_y():
                self._log(f"[rednose2v5] stair7 intermediate Y confirmed ({attempt}/{attempts})")
                self._stair7_up_right_teleport_once()
                if self._wait_floor(lambda: self._is_upper_floor_v5(None), 0.55):
                    return True
                continue
            if not self._is_in_stair7_x_range() and not self._move_to_target_v5(
                stair_x,
                attack=False,
                interval_sec=0.1,
                teleport_stop_range=self._stair7_floor1_teleport_stop_range(),
                arrival_tolerance=3.0,
                allow_crossed_arrival=False,
                active_fn=is_active,
            ):
                return False
            pos = self._current_pos()
            if pos is None or not (stair_left <= float(pos[0]) <= stair_right):
                self._log(f"[rednose2v5] stair7 X not aligned ({attempt}/{attempts})")
                self._retry_attack_once()
                continue
            pos = self._fresh_pos()
            if self._is_upper_floor_v5(None):
                self._log("[rednose2v5] floor2 reached before stair7 up-teleport")
                return True
            if pos is None or not (stair_left <= float(pos[0]) <= stair_right):
                x_text = "?" if pos is None or pos[0] is None else f"{float(pos[0]):.0f}"
                y_text = "?" if pos is None or pos[1] is None else f"{float(pos[1]):.0f}"
                self._log(
                    f"[rednose2v5] stair7 fresh X blocked before up-teleport: "
                    f"x={x_text}, y={y_text}, range {stair_left:.0f}-{stair_right:.0f} "
                    f"({attempt}/{attempts})"
                )
                self._retry_attack_once()
                continue
            floor1_min, floor1_max = self._floor1_y_range()
            tolerance = self._floor_y_tolerance()
            stair7_return_max = self._profile_y("stair7_return_y_max", 68)
            y_min = stair7_return_max + 1
            y_max = floor1_max + tolerance
            if not (y_min <= float(pos[1]) <= y_max):
                self._log(
                    f"[rednose2v5] stair7 fresh Y blocked before up-teleport: "
                    f"x={float(pos[0]):.0f}, y={float(pos[1]):.0f}, "
                    f"floor1 {floor1_min:.0f}-{floor1_max:.0f} ({attempt}/{attempts})"
                )
                continue
            self._log(
                f"[rednose2v5] stair7 up commit x={float(pos[0]):.0f}, "
                f"y={float(pos[1]):.0f}, range {stair_left:.0f}-{stair_right:.0f}"
            )
            self._teleport_once("up")
            if self._wait_floor(lambda: self._is_upper_floor_v5(None), 0.18):
                self._log(f"[rednose2v5] floor2 reached by stair7 up-teleport ({attempt}/{attempts})")
                return True
            if not self._wait_floor(lambda: self._is_stair7_return_y(), 0.35):
                self._log(f"[rednose2v5] stair7 Y not confirmed; skip right teleport ({attempt}/{attempts})")
                self._retry_attack_once()
                continue
            self._stair7_up_right_teleport_once()
            if self._wait_floor(lambda: self._is_upper_floor_v5(None), 0.55):
                self._log(f"[rednose2v5] floor2 returned from stair7 ({attempt}/{attempts})")
                return True
            self._log(f"[rednose2v5] stair7 return retry ({attempt}/{attempts})")
            self._retry_attack_once()
        return False

    def _move_floor2_right_edge(self) -> bool:
        target_x = self._floor2_right_safe_x()
        self._log(f"[rednose2v5] step right edge: safe stop X>={target_x:.0f}")
        opening_timings = (
            (
                float(self._profile.get(
                    "floor2_recovery_first_attack_hold_sec",
                    self._profile.get("attack_hold_sec", 0.9),
                )),
                float(self._profile.get(
                    "floor2_recovery_first_teleport_hold_sec",
                    self._profile.get("teleport_hold_sec", 0.3),
                )),
                self._segment_interval("floor2_recovery_first_interval_sec", 0.9),
            ),
            (
                float(self._profile.get(
                    "floor2_recovery_second_attack_hold_sec",
                    self._profile.get("attack_hold_sec", 0.9),
                )),
                float(self._profile.get(
                    "floor2_recovery_second_teleport_hold_sec",
                    self._profile.get("teleport_hold_sec", 0.3),
                )),
                self._segment_interval("floor2_recovery_second_interval_sec", 0.9),
            ),
        )
        return self._move_to_target_v5(
            target_x,
            attack=True,
            interval_sec=self._segment_interval("floor2_right_edge_teleport_interval_sec", 1.8),
            floor_guard=lambda: self._is_upper_floor_v5(None),
            guard_label="rednose-new right edge",
            teleport_stop_distance=0.0,
            arrival_tolerance=0.0,
            arrival_side="right",
            opening_attack_timings=opening_timings,
        )

    def _enter_platform1415(self) -> bool:
        approach_x = self._profile_x("platform1415_16_approach_x", 95)
        platform_left, platform_right = self._platform1415_x_range()
        attempts = max(1, int(self._profile.get("platform1415_attempts", 3)))
        self._log(
            f"[rednose2v5] step 14/15: approach X={approach_x:.0f} "
            f"range {platform_left:.0f}-{platform_right:.0f}, up-teleport"
        )
        for attempt in range(1, attempts + 1):
            if self._is_lower_floor_v5(None):
                self._log(f"[rednose2v5] platform 14/15 blocked on floor1 ({attempt}/{attempts})")
                return False
            if not self._is_in_platform1415_x_range() and not self._move_to_target_v5(
                approach_x,
                attack=True,
                interval_sec=self._segment_interval("floor2_right_edge_teleport_interval_sec", 0.9),
                arrival_range=(platform_left, platform_right),
                floor_guard=self._collection_x_move_allowed,
                guard_label="platform 14/15 approach",
            ):
                return False
            if not self._is_in_platform1415_x_range():
                self._log(f"[rednose2v5] platform 14/15 X not aligned ({attempt}/{attempts})")
                self._retry_attack_once()
                continue
            self._release_attack_key()
            self._teleport_once("up")
            if self._wait_y_range("platform1415_y_min", "platform1415_y_max", 54, 55, 0.75):
                self._log(f"[rednose2v5] platform 14/15 reached ({attempt}/{attempts})")
                return True
            if attempt < attempts:
                self._route_inputs().press_action(
                    self._attack_key(),
                    float(self._profile.get("platform1415_retry_attack_sec", 0.6)),
                )
            self._log(f"[rednose2v5] platform 14/15 retry ({attempt}/{attempts})")
        return False

    def _enter_platform16(self) -> bool:
        attempts = max(1, int(self._profile.get("platform16_attempts", 3)))
        self._release_attack_key()
        self._log("[rednose2v5] step 16: attack, up-teleport")
        for attempt in range(1, attempts + 1):
            if self._is_lower_floor_v5(None):
                self._log(f"[rednose2v5] platform 16 blocked on floor1 ({attempt}/{attempts})")
                return False
            self._hold_attack_for(float(self._profile.get("platform1415_attack_hold_sec", 0.5)))
            self._teleport_once("up")
            if self._wait_y_range("platform16_y_min", "platform16_y_max", 47, 48, 0.55):
                self._log(f"[rednose2v5] platform 16 reached ({attempt}/{attempts})")
                return True
            self._log(f"[rednose2v5] platform 16 retry ({attempt}/{attempts})")
        self._log("[rednose2v5] platform 16 failed; bypass to platform27")
        return self._enter_platform27_bypass_from_floor2()

    def _enter_platform27_bypass_from_floor2(self) -> bool:
        self._release_attack_key()
        if self._is_lower_floor_v5(None):
            self._log("[rednose2v5] platform27 bypass blocked on floor1")
            return False
        self._log("[rednose2v5] platform27 bypass: up-teleport, left-teleport")
        self._teleport_once("up")
        self._teleport_once("left")
        return True

    def _enter_platform27(self) -> bool:
        approach_x = self._profile_x("platform27_approach_x", 91)
        attempts = max(1, int(self._profile.get("platform27_attempts", 3)))
        self._release_attack_key()
        self._log(f"[rednose2v5] step 27: align X={approach_x:.0f}, left-teleport from platform16")
        for attempt in range(1, attempts + 1):
            if self._is_lower_floor_v5(None):
                self._log(f"[rednose2v5] platform 27 blocked on floor1 ({attempt}/{attempts})")
                return False
            if not self._move_to_target_v5(
                approach_x,
                attack=True,
                interval_sec=self._segment_interval("platform27_approach_interval_sec", 0.25),
                arrival_side="left",
                floor_guard=self._collection_x_move_allowed,
                guard_label="platform 27 approach",
            ):
                return False
            self._release_attack_key()
            self._teleport_once("left")
            if self._wait_y_range("platform27_y_min", "platform27_y_max", 50, 50, 0.75):
                self._hold_attack_for(float(self._profile.get("platform27_entry_attack_hold_sec", 0.5)))
                self._log(f"[rednose2v5] platform 27 reached by Y ({attempt}/{attempts})")
                return True
            self._log(f"[rednose2v5] platform 27 retry ({attempt}/{attempts})")
        return False

    def _collection_x_move_allowed(self) -> bool:
        position = self._current_pos()
        if position is None or position[1] is None:
            return False
        floor1_min, floor1_max = self._floor1_y_range()
        tolerance = self._floor_y_tolerance()
        y = float(position[1])
        return not (floor1_min - tolerance <= y <= floor1_max + tolerance)

    def _finish_platform27_and_return_floor2(self) -> bool:
        down_attempts = max(1, int(self._profile.get("platform27_down_attempts", 5)))
        self._log("[rednose2v5] step 27 finish: extra left-teleport, 0.5s attack, down-teleport")
        self._teleport_once("left")
        self._hold_attack_for(float(self._profile.get("platform27_attack_sec", 0.5)))
        for attempt in range(1, down_attempts + 1):
            self._teleport_once("down")
            if self._wait_floor(lambda: self._is_upper_floor_v5(None), 0.45):
                self._log(f"[rednose2v5] floor2 returned from platform27 ({attempt}/{down_attempts})")
                return True
            if self._is_lower_floor_v5(None):
                self._log(f"[rednose2v5] platform27 down-teleport reached floor1 ({attempt}/{down_attempts}); recover through stair7")
                return self._return_floor2_from_stair7()
        return False

    def _run_pickup_cycle_once_legacy(self, blocks: list) -> bool:
        lower_move, ladder_block, upper_moves = self._split_pickup_route(blocks)
        if not upper_moves:
            return self._run_block(blocks[self._index % len(blocks)])

        if ladder_block is not None and not self._is_upper_floor_v5(ladder_block):
            floor_name = self._floor_name_v5(ladder_block)
            self._log(f"[rednose2v5] current floor={floor_name}; recovering to floor2")
            return self._run_ladder_v5(ladder_block)

        if time.monotonic() - self._last_pickup_at >= self._pickup_cycle_sec():
            return self._run_pickup_route_v5(lower_move, ladder_block)

        self._main_move_index %= len(upper_moves)
        block = upper_moves[self._main_move_index]
        self._log(
            f"[rednose2v5] main floor2 move {self._main_move_index + 1}/{len(upper_moves)} "
            f"{self._move_label_v5(block, 'floor2')}"
        )
        if self._run_move_v5(
            block,
            floor_guard=lambda: ladder_block is None or self._is_upper_floor_v5(ladder_block),
            guard_label=self._move_label_v5(block, "floor2 main"),
        ):
            self._main_move_index = (self._main_move_index + 1) % len(upper_moves)
            return True
        return False

    def _run_block(self, block) -> bool:
        if bool(self._profile.get("enabled", True)) and block.type == "move":
            return self._run_move_v5(block)
        if bool(self._profile.get("enabled", True)) and block.type == "ladder":
            return self._run_ladder_v5(block)
        previous_owns_movement = self.owns_movement
        self.owns_movement = True
        try:
            return bool(self._br.run_block(block))
        finally:
            self.owns_movement = previous_owns_movement

    def _recover_index(self, blocks: list, current_y: int) -> int:
        candidates = []
        for index, block in enumerate(blocks):
            entry_y = self._entry_y(block)
            if entry_y is not None:
                candidates.append((abs(current_y - entry_y), index))
        return min(candidates)[1] if candidates else self._index

    def run_once(self) -> bool:
        if self._stop.is_set() or not self._active():
            return False
        if bool(self._profile.get("enabled", True)) and self._pickup_route_enabled():
            success = self._run_rednose_new_v5_once()
            if not success:
                self._br.release_inputs()
                self._sleep(0.05)
            return True

        blocks = self._get_blocks()

        if not blocks:
            return False

        signature = tuple(self._block_signature(block) for block in blocks)
        if signature != self._signature:
            self._signature = signature
            self._index = 0
            self._main_move_index = 0

        self._index %= len(blocks)
        block = blocks[self._index]
        self._log(f"[rednose2] route step start {self._index + 1}/{len(blocks)}: {block.type}")
        success = self._run_block(block)
        if success:
            self._log(f"[rednose2] route step complete {self._index + 1}/{len(blocks)}")
            self._index = (self._index + 1) % len(blocks)
            return True

        self._br.release_inputs()
        pos = self._current_pos()
        entry_y = self._entry_y(block)
        if pos is not None and entry_y is not None and abs(int(pos[1]) - entry_y) > 6:
            recovered = self._recover_index(blocks, int(pos[1]))
            self._log(f"[rednose2] recover by Y={int(pos[1])}: {self._index + 1} -> {recovered + 1}")
            self._index = recovered
        else:
            self._log(f"[rednose2] route step failed; retry same step {self._index + 1}/{len(blocks)}")
        self._sleep(0.05)
        return True
