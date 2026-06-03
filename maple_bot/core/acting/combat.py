# Combat — 게이지 비율 기반 물약(A 방식 채택) + 공격. 모든 입력은 Humanizer 경유
from __future__ import annotations

from dataclasses import dataclass

from core.humanize.intent import Intent


@dataclass
class PotionRule:
    """HP/MP 물약 규칙 (A potion_manager 방식)."""
    enabled: bool = False
    key: str = ""
    threshold: float = 0.7   # 이 비율 미만이면 사용
    cooldown: float = 3.0    # 재사용 최소 간격(초)


class Combat:
    """게이지 비율로 물약을 쓰고(A 능동방식) 공격을 수행한다.

    C의 팝업감지 방식 대신 A의 게이지 측정 방식 채택(도면 카테고리3).
    모든 키 입력은 Humanizer 를 통과한다(헌법).
    """

    def __init__(self, humanizer,
                 hp_rule: PotionRule | None = None,
                 mp_rule: PotionRule | None = None,
                 log_fn=None, clock=None):
        self._h = humanizer
        self._hp = hp_rule or PotionRule()
        self._mp = mp_rule or PotionRule()
        self._hp_last = -1e9
        self._mp_last = -1e9
        self._log = log_fn or (lambda msg, cat: None)   # log(msg, cat) — 공격/물약 로그
        import time as _t
        self._clock = clock or _t.monotonic
        self._atk_log_last = -1e9   # 공격 로그 폭주 방지(초당 1회만 표시)

    def check_potions(self, hp_ratio: float, mp_ratio: float, now: float) -> None:
        """HP/MP 비율을 확인하고 임계 미만이면 물약 사용(독립 처리)."""
        self._hp_last = self._maybe_potion(self._hp, hp_ratio, now, self._hp_last, "HP")
        self._mp_last = self._maybe_potion(self._mp, mp_ratio, now, self._mp_last, "MP")

    def attack(self, skill_key: str, mode: str = "duration", value: float = 0.0) -> None:
        """공격. mode='count' 면 value 횟수, 'duration' 이면 호출측이 주기 제어."""
        if not skill_key:
            return
        if mode == "count":
            for _ in range(int(value)):
                self._h.perform(Intent(action="key", key=skill_key, base_hold_sec=0.05))
        else:
            self._h.perform(Intent(action="key", key=skill_key, base_hold_sec=0.05))
        now = self._clock()
        if now - self._atk_log_last >= 1.0:   # 매 틱 폭주 방지 — 초당 1회만 로그
            self._atk_log_last = now
            self._log(f"공격 [{skill_key}]", "공격")

    # ── 내부 ──────────────────────────────────────────────────────────
    def _maybe_potion(self, rule: PotionRule, ratio: float, now: float, last: float,
                      label: str = "") -> float:
        if not rule.enabled or not rule.key:
            return last
        if now - last < rule.cooldown:
            return last
        if ratio < rule.threshold:
            self._h.perform(Intent(action="key", key=rule.key, base_hold_sec=0.05))
            self._log(f"{label} 물약 [{rule.key}] ({int(ratio * 100)}%)", "물약")
            return now
        return last
