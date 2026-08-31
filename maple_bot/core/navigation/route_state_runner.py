# ??λ맂 ?숈꽑 ?④퀎瑜??쒖꽌?濡??ㅽ뻾?섎뒗 踰붿슜 ?곹깭 癒몄떊?대떎.
from __future__ import annotations

import threading
import time

from core.input_timing import randomize_hold
from core.navigation.block import Block
from core.navigation.block_runner import TELEPORT_MIN_DIST
from core.navigation.route_recovery import RouteRecoveryResolver
from core.navigation.route_state import RouteStep, RouteStepType


class RouteStateRunner:
    def __init__(self, get_steps, is_active, position_store, input_owner,
                 block_runner=None, log_fn=None, idle_sleep: float = 0.03) -> None:
        self._get_steps = get_steps
        self._is_active = is_active
        self._positions = position_store
        self._input = input_owner
        self._block_runner = block_runner
        self._teleport_key = str(getattr(block_runner, "teleport_key", "space") or "space")
        self._log = log_fn or (lambda _m: None)
        self._idle_sleep = max(0.01, float(idle_sleep))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._index = 0
        self._retry_count = 0
        self._recovery = RouteRecoveryResolver()
        self._move_progress: dict[str, int] = {}
        self._redirect_index: int | None = None

    def start(self) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="route-state", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._input.release_all()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        while not self._stop.is_set():
            if not self._is_active():
                self._input.release_all()
                time.sleep(self._idle_sleep)
                continue
            self.run_once()

    def run_once(self) -> bool:
        steps = [s if isinstance(s, RouteStep) else RouteStep.from_dict(s)
                 for s in (self._get_steps() or [])]
        if not steps:
            self._input.release_all()
            time.sleep(self._idle_sleep)
            return False
        if self._index >= len(steps):
            self._index = 0
        step = steps[self._index]
        self._log(f"동선 단계 시작 {self._index + 1}/{len(steps)} · {step.type.value}")
        succeeded = self._execute(step, steps)
        if succeeded:
            self._input.release_all()
            self._log(f"동선 단계 완료 · {step.id}")
            next_index = None
            if step.next_step_id:
                next_index = next((i for i, item in enumerate(steps)
                                   if item.id == step.next_step_id), None)
            self._index = next_index if next_index is not None else (self._index + 1) % len(steps)
            self._retry_count = 0
            return True

        self._input.release_all()
        if self._redirect_index is not None:
            target = self._redirect_index
            self._redirect_index = None
            self._index = target
            self._retry_count = 0
            target_step = steps[target]
            self._move_progress.pop(target_step.id, None)
            self._log(
                f"층 변경 복구: 현재 위치와 가까운 이동 블록부터 진행 · "
                f"{target_step.id} ({target + 1}/{len(steps)})"
            )
            return False
        id_to_index = {item.id: i for i, item in enumerate(steps)}
        action, target = self._recovery.resolve(step, self._retry_count, id_to_index)
        self._retry_count += 1
        if action == "retry":
            self._log(f"동선 단계 재시도 {self._retry_count}/{step.failure.max_retries} · {step.id}")
        elif action == "recover" and target is not None:
            self._log(f"동선 복구 단계 이동 · {step.id} -> {steps[target].id}")
            self._index = target
            self._retry_count = 0
        elif action == "skip":
            self._log(f"동선 단계 건너뜀 · {step.id}")
            self._index = (self._index + 1) % len(steps)
            self._retry_count = 0
        else:
            self._log(f"동선 안전 정지 · {step.id}")
            self._stop.set()
        return False

    def _execute(self, step: RouteStep, steps: list[RouteStep]) -> bool:
        if step.type == RouteStepType.MOVE:
            return self._execute_move(step, steps)
        if step.type == RouteStepType.ACTION:
            key = str(step.parameters.get("skill_key") or step.parameters.get("action_key") or "")
            if not key:
                return True
            self._input.hold_action(key)
            time.sleep(randomize_hold(max(0.0, float(step.parameters.get("hold_sec", 0.1)))))
            self._input.release_action(key)
            return True
        return self._execute_complex(step)

    def _execute_move(self, step: RouteStep, steps: list[RouteStep]) -> bool:
        params = step.parameters
        start_x = int(params.get("start_x", params.get("target_x", 0)))
        end_x = int(params.get("end_x", params.get("target_x", start_x)))
        range_margin = max(0, int(params.get("range_margin", 8)))
        allowed_min = int(params.get("allowed_min_x", min(start_x, end_x) - range_margin))
        allowed_max = int(params.get("allowed_max_x", max(start_x, end_x) + range_margin))
        sweeps = max(1, int(params.get("sweeps", step.completion.repeat_count)))
        mode = str(params.get("mode", "count"))
        targets = [end_x] if mode == "pass" else [
            value for _ in range(sweeps) for value in (end_x, start_x)
        ]
        timeout = max(1.0, float(step.failure.timeout_sec))
        tolerance = max(0, int(step.completion.tolerance))
        progress = min(max(0, self._move_progress.get(step.id, 0)), len(targets))
        floor_candidate = None
        floor_confirmations = 0

        while progress < len(targets):
            target = targets[progress]
            missing_since = None
            recovery_target = None
            if start_x == end_x:
                travel_direction = None
            elif target == end_x:
                travel_direction = "right" if end_x > start_x else "left"
            else:
                travel_direction = "left" if end_x > start_x else "right"

            while not self._stop.is_set() and self._is_active():
                sample = self._positions.latest(max_age_sec=0.25)
                if sample is None:
                    self._input.release_direction()
                    now = time.monotonic()
                    if missing_since is None:
                        missing_since = now
                    if now - missing_since >= timeout:
                        return False
                    time.sleep(self._idle_sleep)
                    continue

                if missing_since is not None:
                    missing_since = None

                nearest_index = self._recovery.nearest_move_index(steps, sample)
                if (nearest_index is not None and nearest_index != self._index
                        and self._recovery.is_floor_change(
                            step, steps[nearest_index], sample,
                            tolerance=int(params.get("floor_tolerance", 8)),
                            hysteresis=int(params.get("floor_hysteresis", 4)),
                        )):
                    if floor_candidate == nearest_index:
                        floor_confirmations += 1
                    else:
                        floor_candidate = nearest_index
                        floor_confirmations = 1
                    if floor_confirmations >= max(1, int(params.get("floor_confirmations", 3))):
                        self._input.release_direction()
                        self._redirect_index = nearest_index
                        self._log(
                            f"층 변경 감지: {step.id}에서 {steps[nearest_index].id}로 복구 · "
                            f"현재 X={sample.x}, Y={sample.y}"
                        )
                        return False
                else:
                    floor_candidate = None
                    floor_confirmations = 0

                reached = abs(sample.x - target) <= tolerance
                passed = ((travel_direction == "right" and sample.x >= target)
                          or (travel_direction == "left" and sample.x <= target))
                if reached or passed:
                    self._input.release_direction()
                    progress += 1
                    self._move_progress[step.id] = progress
                    self._log(
                        f"이동 구간 통과: {step.id} · {progress}/{len(targets)} · "
                        f"X={sample.x}, 목표={target}"
                    )
                    break

                direction = travel_direction or ("right" if target > sample.x else "left")
                self._input.hold_direction(direction)
                if (str(params.get("move_type", "walk")) == "teleport"
                        and abs(sample.x - target) > TELEPORT_MIN_DIST):
                    self._input.press_action(self._teleport_key, 0.05)
                time.sleep(self._idle_sleep)
            else:
                return False

        self._move_progress.pop(step.id, None)
        return True

    def _execute_complex(self, step: RouteStep) -> bool:
        if self._block_runner is None:
            return False
        data = dict(step.parameters)
        if step.type == RouteStepType.LADDER_UP:
            data.update(type="ladder", ladder_dir="up")
        elif step.type == RouteStepType.DROP_DOWN:
            data.update(type="ladder", ladder_dir="down")
        elif step.type == RouteStepType.JUMP:
            data.update(type="jump")
        elif step.type == RouteStepType.TELEPORT:
            data.update(type="move", move_type="teleport")
        try:
            return bool(self._block_runner.run_block(Block.from_dict(data), max_steps=200))
        except Exception as exc:
            self._log(f"동선 단계 실행 오류 · {step.id} · {exc}")
            return False
