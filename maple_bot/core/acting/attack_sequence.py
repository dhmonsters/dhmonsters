# 여러 공격 연속기를 가로 순서와 줄별 독립 주기에 맞춰 실행한다.
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.humanize.timing import plus_minus_5


@dataclass(frozen=True)
class AttackSequence:
    name: str
    keys: tuple[str, ...]
    hold_sec: tuple[float, ...]
    key_interval_sec: float
    repeat_interval_sec: float
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "AttackSequence":
        keys = tuple(str(key).strip() for key in (data.get("keys") or []) if str(key).strip())
        raw_hold = data.get("key_hold_sec") or []
        hold_sec = tuple(
            max(0.0, float(raw_hold[index])) if index < len(raw_hold) else 0.05
            for index in range(len(keys))
        )
        return cls(
            name=str(data.get("name", "연속기")),
            keys=keys,
            hold_sec=hold_sec,
            key_interval_sec=max(0.0, float(data.get("key_interval_sec", 0.15))),
            repeat_interval_sec=max(0.0, float(data.get("repeat_interval_sec", 1.0))),
            enabled=bool(data.get("enabled", True)),
        )


class AttackSequenceRunner:
    """sleep 없이 현재 시각만 비교해 여러 연속기를 독립 실행한다."""

    def __init__(self, sequences: list[AttackSequence], press_fn: Callable[[str, float], None]):
        self._sequences = [sequence for sequence in sequences if sequence.enabled and sequence.keys]
        self._press = press_fn
        self._states = [
            {"next_run": 0.0, "cursor": None, "next_key": 0.0}
            for _ in self._sequences
        ]

    @property
    def active(self) -> bool:
        return bool(self._sequences)

    def tick(self, now: float, allowed: bool) -> None:
        for sequence, state in zip(self._sequences, self._states):
            if not allowed:
                state["cursor"] = None
                continue

            cursor = state["cursor"]
            if cursor is None:
                if now < state["next_run"]:
                    continue
                self._press(sequence.keys[0], sequence.hold_sec[0])
                state["next_run"] = now + self._jitter(sequence.repeat_interval_sec)
                if len(sequence.keys) == 1:
                    continue
                cursor = 1
                state["cursor"] = cursor
                state["next_key"] = now + self._jitter(sequence.key_interval_sec)

            while state["cursor"] is not None and now >= state["next_key"]:
                cursor = int(state["cursor"])
                self._press(sequence.keys[cursor], sequence.hold_sec[cursor])
                cursor += 1
                if cursor >= len(sequence.keys):
                    state["cursor"] = None
                else:
                    state["cursor"] = cursor
                    state["next_key"] = now + self._jitter(sequence.key_interval_sec)
                    if sequence.key_interval_sec > 0:
                        break

    @staticmethod
    def _jitter(value: float) -> float:
        if value <= 0:
            return 0.0
        return plus_minus_5(value)
