# 사냥 패턴 데이터 모델과 키 입력 단계의 JSON 직렬화를 정의한다.
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


STEP_DEFAULTS: dict[str, dict[str, Any]] = {
    "move": {"direction": "right", "duration": 1.5},
    "jump": {"direction": "none"},
    "rope": {"direction": "up", "duration": 1.0},
    "attack": {"key": "ctrl", "repeat": 3, "interval": 0.15},
    "attack_if_monster": {
        "key": "ctrl",
        "repeat": 3,
        "interval": 0.15,
        "monster_template": "",
    },
    "skill": {"key": "1", "cooldown": 30.0},
    "wait": {"duration": 0.5},
}
STEP_TYPES = list(STEP_DEFAULTS.keys())


@dataclass
class Step:
    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def make(cls, step_type: str, **overrides) -> "Step":
        params = dict(STEP_DEFAULTS.get(step_type, {}))
        params.update(overrides)
        return cls(type=step_type, params=params)

    def label(self) -> str:
        p = self.params
        if self.type == "move":
            return f"이동 {p.get('direction')} {p.get('duration')}초"
        if self.type == "jump":
            direction = p.get("direction", "none")
            label = "위" if direction == "up" else "아래" if direction == "down" else ""
            return f"점프 {label}".rstrip()
        if self.type == "rope":
            return f"로프 {p.get('direction')} {p.get('duration')}초"
        if self.type == "attack":
            return f"공격 {p.get('key')} × {p.get('repeat')}"
        if self.type == "attack_if_monster":
            template = p.get("monster_template") or "미설정"
            return f"몬스터 감지 → 공격 {p.get('key')} × {p.get('repeat')} [{template}]"
        if self.type == "skill":
            return f"스킬 {p.get('key')} (쿨 {p.get('cooldown')}초)"
        if self.type == "wait":
            return f"대기 {p.get('duration')}초"
        return self.type

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Step":
        return cls(type=data["type"], params=dict(data.get("params", {})))


@dataclass
class HuntPattern:
    name: str
    steps: list[Step] = field(default_factory=list)
    loop: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "loop": self.loop,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HuntPattern":
        steps = [Step.from_dict(step) for step in data.get("steps", [])]
        return cls(name=data.get("name", "패턴"), steps=steps, loop=data.get("loop", True))


KEY_OPTIONS = [
    "right", "left", "up", "down",
    "ctrl", "alt", "shift", "space", "enter", "tab",
    "home", "end", "insert", "delete", "pageup", "pagedown",
    "z", "x", "c", "v", "a", "s", "d", "f", "g",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
]

ACTION_HOLD = "hold"
ACTION_TAP = "tap"
ACTION_COMBO = "combo"


@dataclass
class KeyStep:
    key: str
    action: str
    min_sec: float
    max_sec: float
    repeat_min: int = 1
    repeat_max: int = 1
    combo_keys: list = field(default_factory=list)
    tap_hold_base: float = 0.06
    tap_hold_var: float = 0.01
    combo_holds: list = field(default_factory=list)

    def label(self) -> str:
        if self.action == ACTION_HOLD:
            return f"[누름] {self.key} {self.min_sec}~{self.max_sec}초"
        if self.action == ACTION_COMBO:
            keys = self.combo_keys if self.combo_keys else [self.key]
            parts = []
            for index, key in enumerate(keys):
                if index < len(self.combo_holds):
                    base, variation = self.combo_holds[index]
                    parts.append(f"{key}({int(base * 1000)}+/-{int(variation * 1000)}ms)")
                else:
                    parts.append(key)
            keys_text = " -> ".join(parts)
            return (
                f"[연속기] {keys_text} {self.repeat_min}~{self.repeat_max}회 "
                f"간격 {self.min_sec}~{self.max_sec}초"
            )
        hold_text = f"유지 {self.tap_hold_base}+/-{self.tap_hold_var}초"
        return (
            f"[탭] {self.key} {self.repeat_min}~{self.repeat_max}회 "
            f"간격 {self.min_sec}~{self.max_sec}초 {hold_text}"
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KeyStep":
        return cls(
            key=data["key"],
            action=data.get("action", ACTION_HOLD),
            min_sec=float(data.get("min_sec", 0.5)),
            max_sec=float(data.get("max_sec", 1.0)),
            repeat_min=int(data.get("repeat_min", 1)),
            repeat_max=int(data.get("repeat_max", 1)),
            combo_keys=list(data.get("combo_keys", [])),
            tap_hold_base=float(data.get("tap_hold_base", 0.06)),
            tap_hold_var=float(data.get("tap_hold_var", 0.01)),
            combo_holds=list(data.get("combo_holds", [])),
        )


@dataclass
class KeyPattern:
    name: str
    steps: list[KeyStep] = field(default_factory=list)
    loop: bool = True
    between_min: float = 0.05
    between_max: float = 0.20

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "loop": self.loop,
            "between_min": self.between_min,
            "between_max": self.between_max,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KeyPattern":
        steps = [KeyStep.from_dict(step) for step in data.get("steps", [])]
        return cls(
            name=data.get("name", "키 패턴"),
            steps=steps,
            loop=data.get("loop", True),
            between_min=float(data.get("between_min", 0.05)),
            between_max=float(data.get("between_max", 0.20)),
        )
