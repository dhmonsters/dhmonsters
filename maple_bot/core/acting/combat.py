# Combat — 게이지 비율 기반 물약(A 방식 채택) + 공격. 모든 입력은 Humanizer 경유
from __future__ import annotations

from dataclasses import dataclass
import time

from core.humanize.intent import Intent
from core.humanize.timing import down_5, plus_minus_5


@dataclass
class PotionRule:
    """HP/MP 물약 규칙 (A potion_manager 방식)."""
    enabled: bool = False
    key: str = ""
    secondary_key: str = ""
    threshold: float = 0.7   # 이 비율 미만이면 사용
    cooldown: float = 3.0    # 재사용 최소 간격(초)
    verify_delay: float = 0.2
    min_recovery: float = 0.01


class Combat:
    """게이지 비율로 물약을 쓰고(A 능동방식) 공격을 수행한다.

    C의 팝업감지 방식 대신 A의 게이지 측정 방식 채택(도면 카테고리3).
    모든 키 입력은 Humanizer 를 통과한다(헌법).
    """

    def __init__(self, humanizer,
                 hp_rule: PotionRule | None = None,
                 mp_rule: PotionRule | None = None,
                 log_fn=None, clock=None, input_backend=None):
        self._h = humanizer
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
        self._log = log_fn or (lambda msg, cat: None)   # log(msg, cat) — 공격/물약 로그
        import time as _t
        self._clock = clock or _t.monotonic
        self._atk_log_last = -1e9   # 공격 로그 폭주 방지(초당 1회만 표시)
        self._atk_last = -1e9       # 마지막 공격 시각(스킬 딜레이/쿨다운 게이팅)
        self._cur_interval = None   # 이번 사이클의 재누름 간격(−5%~0 랜덤, 발동 시 재추첨)

    def check_potions(self, hp_ratio: float, mp_ratio: float, now: float) -> None:
        """HP/MP 비율을 확인하고 임계 미만이면 물약 사용(독립 처리)."""
        self._hp_last = self._maybe_potion(self._hp, hp_ratio, now, self._hp_last, "HP")
        self._mp_last = self._maybe_potion(self._mp, mp_ratio, now, self._mp_last, "MP")

    def attack(self, skill_key: str, mode: str = "duration", value: float = 0.0,
               now: float | None = None, interval: float = 0.0,
               hold: float = 0.08) -> None:
        """공격. mode='count'면 value회. interval>0이면 스킬 딜레이로 그 간격마다만 발동
        (재누름 간격 — 매 틱 도배 방지). 재누름 간격은 발동마다 −5%~0 랜덤(설정값 초과 안 함).
        hold=공격키 누름 유지 시간(초, =목표 방수×스킬1회 시간). hold_jitter_pct>0이면
        Humanizer가 홀드를 −그 비율~0(4자리)로 랜덤화한다."""
        if not skill_key:
            return
        if interval > 0 and now is not None:
            cur = self._cur_interval if self._cur_interval is not None else interval
            if now - self._atk_last < cur:
                return                       # 스킬 딜레이 — 아직 다음 타격 전
            self._atk_last = now
            self._cur_interval = self._h.humanize(interval)
        if mode == "count":
            for _ in range(int(value)):
                self._h.perform(Intent(action="key", key=skill_key, base_hold_sec=hold))
        else:
            self._h.perform(Intent(action="key", key=skill_key, base_hold_sec=hold))
        t = self._clock()
        if t - self._atk_log_last >= 1.0:   # 로그는 초당 1회만(가독)
            self._atk_log_last = t
            self._log(f"공격 [{skill_key}]", "공격")

    # ── 내부 ──────────────────────────────────────────────────────────
    def _jitter_down(self, base: float) -> float:
        """재누름 간격을 −5%~0(4자리)로 랜덤화. Humanizer.jitter_down 재사용(없으면 그대로)."""
        return down_5(base)

    def _press_potion(self, key: str, hold_sec: float = 0.05) -> None:
        """Humanizer 공통 잠금을 사용하지 않고 물약키를 독립 입력한다."""
        if not key:
            return
        if self._input is None:
            self._h.perform(Intent(action="key", key=key, base_hold_sec=hold_sec))
            return
        applied_hold = plus_minus_5(hold_sec)
        self._input.key_down(key)
        try:
            time.sleep(applied_hold)
        finally:
            self._input.key_up(key)

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
                self._log(
                    f"{label} 2차 물약 [{rule.secondary_key}] ({int(ratio * 100)}%)",
                    "물약",
                )
            return last
        if now < self._potion_next_allowed[label]:
            return last
        if ratio < rule.threshold:
            self._press_potion(rule.key)
            self._log(f"{label} 물약 [{rule.key}] ({int(ratio * 100)}%)", "물약")
            if rule.secondary_key:
                self._potion_pending[label] = {
                    "baseline": ratio,
                    "check_at": now + down_5(rule.verify_delay),
                }
            self._potion_next_allowed[label] = now + plus_minus_5(rule.cooldown)
            return now
        return last
