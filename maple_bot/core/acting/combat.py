# 공격과 HP/MP 물약 입력을 입력 백엔드로 직접 전송합니다.
from __future__ import annotations

from dataclasses import dataclass

@dataclass
class PotionRule:
    enabled: bool = False
    key: str = ""
    secondary_key: str = ""
    threshold: float = 0.7
    cooldown: float = 3.0
    verify_delay: float = 0.2
    min_recovery: float = 0.01


class Combat:
    def __init__(self, input_backend, hp_rule: PotionRule | None = None,
                 mp_rule: PotionRule | None = None, log_fn=None, clock=None):
        self._input = input_backend
        self._hp = hp_rule or PotionRule()
        self._mp = mp_rule or PotionRule()
        for rule in (self._hp, self._mp):
            if float(rule.cooldown) == 3.0:
                rule.cooldown = 1.0
        self._hp_last = -1e9
        self._mp_last = -1e9
        self._potion_pending = {"HP": None, "MP": None}
        self._potion_next_allowed = {"HP": -1e9, "MP": -1e9}
        self._log = log_fn or (lambda msg, cat: None)
        import time as _time
        self._clock = clock or _time.monotonic
        self._atk_log_last = -1e9
        self._atk_last = -1e9
        self._cur_interval = None

    def check_potions(self, hp_ratio: float, mp_ratio: float, now: float) -> None:
        self._hp_last = self._maybe_potion(self._hp, hp_ratio, now, self._hp_last, "HP")
        self._mp_last = self._maybe_potion(self._mp, mp_ratio, now, self._mp_last, "MP")

    def attack(self, skill_key: str, mode: str = "duration", value: float = 0.0,
               now: float | None = None, interval: float = 0.0,
               hold: float = 0.08) -> None:
        if not skill_key:
            return
        if interval > 0 and now is not None:
            current_interval = self._cur_interval if self._cur_interval is not None else interval
            if now - self._atk_last < current_interval:
                return
            self._atk_last = now
            self._cur_interval = interval
        count = int(value) if mode == "count" else 1
        for _ in range(max(0, count)):
            self._input.press(skill_key, hold)
        timestamp = self._clock()
        if timestamp - self._atk_log_last >= 1.0:
            self._atk_log_last = timestamp
            self._log(f"공격 [{skill_key}]", "공격")

    def _press_potion(self, key: str, hold_sec: float = 0.05) -> None:
        if key:
            self._input.press(key, hold_sec)

    def _maybe_potion(self, rule: PotionRule, ratio: float, now: float, last: float,
                      label: str = "") -> float:
        if not rule.enabled or not rule.key:
            self._potion_pending[label] = None
            return last
        pending = self._potion_pending.get(label)
        if pending is not None:
            if now < pending["check_at"]:
                return last
            self._potion_pending[label] = None
            recovered = ratio - pending["baseline"] >= rule.min_recovery
            if not recovered and ratio < rule.threshold and rule.secondary_key:
                self._press_potion(rule.secondary_key)
                self._log(f"{label} 2차 물약 [{rule.secondary_key}] ({int(ratio * 100)}%)", "물약")
            return last
        if now < self._potion_next_allowed[label]:
            return last
        if ratio < rule.threshold:
            self._press_potion(rule.key)
            self._log(f"{label} 물약 [{rule.key}] ({int(ratio * 100)}%)", "물약")
            if rule.secondary_key:
                self._potion_pending[label] = {
                    "baseline": ratio,
                    "check_at": now + rule.verify_delay,
                }
            self._potion_next_allowed[label] = now + rule.cooldown
            return now
        return last
