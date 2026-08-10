# 범용 동선의 실행 단계와 완료·실패·입력 정책을 정의합니다.
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RouteStepType(str, Enum):
    MOVE = "move"
    LADDER_UP = "ladder_up"
    DROP_DOWN = "drop_down"
    JUMP = "jump"
    TELEPORT = "teleport"
    ACTION = "action"


class CompletionType(str, Enum):
    X_REACHED = "x_reached"
    X_PASSED = "x_passed"
    Y_RANGE = "y_range"
    FLOOR_CHANGED = "floor_changed"
    REPEAT_COUNT = "repeat_count"
    ACTION_DONE = "action_done"


class PassDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    EITHER = "either"


class FailureAction(str, Enum):
    RETRY = "retry"
    REAPPROACH = "reapproach"
    SAFE_STOP = "safe_stop"
    SKIP = "skip"


@dataclass(frozen=True)
class PositionSample:
    x: int
    y: int
    sequence: int
    captured_at: float

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be zero or greater")
        if self.captured_at < 0:
            raise ValueError("captured_at must be zero or greater")


@dataclass
class CompletionRule:
    type: CompletionType
    target_x: int | None = None
    pass_direction: PassDirection = PassDirection.EITHER
    tolerance: int = 0
    y_min: int | None = None
    y_max: int | None = None
    confirmations: int = 1
    repeat_count: int = 1

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise ValueError("tolerance must be zero or greater")
        if self.confirmations < 1:
            raise ValueError("confirmations must be one or greater")
        if self.repeat_count < 1:
            raise ValueError("repeat_count must be one or greater")
        if self.y_min is not None and self.y_max is not None and self.y_min > self.y_max:
            raise ValueError("y_min must not exceed y_max")
        if self.type in {CompletionType.X_REACHED, CompletionType.X_PASSED} and self.target_x is None:
            raise ValueError(f"{self.type.value} requires target_x")
        if self.type == CompletionType.Y_RANGE and (self.y_min is None or self.y_max is None):
            raise ValueError("y_range requires y_min and y_max")


@dataclass
class FailurePolicy:
    action: FailureAction = FailureAction.RETRY
    max_retries: int = 0
    recovery_step_id: str | None = None
    timeout_sec: float = 15.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be zero or greater")
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be greater than zero")
        if self.action == FailureAction.REAPPROACH and not self.recovery_step_id:
            raise ValueError("reapproach requires recovery_step_id")


@dataclass
class InputPolicy:
    allow_attack: bool = True
    allow_pickup: bool = True
    allow_potion: bool = True
    allow_buff: bool = True


@dataclass
class RouteStep:
    id: str
    type: RouteStepType
    name: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    completion: CompletionRule = field(
        default_factory=lambda: CompletionRule(type=CompletionType.ACTION_DONE)
    )
    failure: FailurePolicy = field(default_factory=FailurePolicy)
    input_policy: InputPolicy = field(default_factory=InputPolicy)
    next_step_id: str | None = None

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        if not self.id:
            raise ValueError("route step id is required")
        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a dictionary")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        step_type = data.pop("type")
        parameters = data.get("parameters", {})
        data["step_type"] = step_type
        data.update(parameters)
        data["type"] = {
            RouteStepType.MOVE.value: "move",
            RouteStepType.LADDER_UP.value: "ladder",
            RouteStepType.DROP_DOWN.value: "ladder",
            RouteStepType.JUMP.value: "jump",
            RouteStepType.TELEPORT.value: "move",
            RouteStepType.ACTION.value: "attack",
        }[step_type]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouteStep":
        known = {
            "id", "type", "step_type", "name", "parameters", "completion",
            "failure", "input_policy", "next_step_id",
        }
        parameters = dict(data.get("parameters", {}))
        parameters.update({k: v for k, v in data.items() if k not in known})
        step_type = data.get("step_type")
        if not step_type:
            old_type = data.get("type", "move")
            if old_type == "ladder":
                step_type = (RouteStepType.DROP_DOWN.value
                             if parameters.get("ladder_dir") == "down"
                             else RouteStepType.LADDER_UP.value)
            elif old_type == "attack":
                step_type = RouteStepType.ACTION.value
            elif old_type == "jump":
                step_type = RouteStepType.JUMP.value
            else:
                step_type = (RouteStepType.TELEPORT.value
                             if parameters.get("move_type") == "teleport"
                             else RouteStepType.MOVE.value)
        return cls(
            id=str(data.get("id") or "step"),
            type=RouteStepType(step_type),
            name=str(data.get("name", "")),
            parameters=parameters,
            completion=CompletionRule(**data.get("completion", {"type": CompletionType.ACTION_DONE})),
            failure=FailurePolicy(**data.get("failure", {})),
            input_policy=InputPolicy(**data.get("input_policy", {})),
            next_step_id=data.get("next_step_id"),
        )
