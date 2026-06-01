# Humanizer — 모든 행동의 단일 통제점. Intent를 사람같은 타이밍으로 변형해 백엔드로 송출
from __future__ import annotations

import random
import time
from typing import Callable

from core.humanize.intent import Intent, RiskProfile


# risk_profile 별 변형 파라미터.
#   hold_jitter: base_hold_sec 에 곱할 (min, max) 배수 — 사람은 누르는 시간이 매번 다름
#   reaction:    감지→행동 사이 반응 지연 (min, max) 초 — 사람 반응속도(150~400ms 근처)
#   sloppy:      의도적 불완전성 확률 (미세 과/부족) — 완벽하면 봇
_PROFILE = {
    RiskProfile.CAREFUL: {"hold_jitter": (0.75, 1.6), "reaction": (0.22, 0.45), "sloppy": 0.06},
    RiskProfile.NORMAL:  {"hold_jitter": (0.8, 1.4),  "reaction": (0.14, 0.30), "sloppy": 0.03},
    RiskProfile.FAST:    {"hold_jitter": (0.85, 1.2), "reaction": (0.05, 0.13), "sloppy": 0.01},
}

# hold_sec 안전 범위 — 지터가 폭주하지 않도록 클램프
_HOLD_MIN = 0.03
_HOLD_MAX = 0.30


class Humanizer:
    """Intent → 사람같은 변형 → InputBackend.

    모든 모듈은 Intent 만 만들고, '언제·어떻게'는 여기서만 결정한다.
    고정 상수 타이밍을 직접 입력하지 않는다(헌법).
    """

    def __init__(self, backend, sleep_fn: Callable[[float], None] | None = None,
                 rng: random.Random | None = None):
        self._backend = backend
        self._sleep = sleep_fn or time.sleep
        self._rng = rng or random.Random()
        self._held: str | None = None   # 현재 누른 채 유지 중인 이동키(left/right)

    # ── 이동키 유지/해제 (C _walk_to_x 방식) ──────────────────────────
    # 좌우 이동키는 '한 번 누르고 계속 유지'한다. 매 틱 톡톡 누르지 않는다.
    # 떼는 경우는 둘뿐 — 방향이 바뀔 때(hold_dir로 자동), 제자리 공격 등(release_dir).
    def hold_dir(self, key: str,
                 risk_profile: RiskProfile = RiskProfile.NORMAL) -> None:
        """좌우 이동키를 누른 채 유지. 같은 방향이면 그대로(no-op),
        다른 방향이면 기존 키를 떼고 새 키를 누른다(방향 전환)."""
        if self._held == key:
            return                          # 이미 같은 방향 유지 중 → 계속 누름 유지
        p = _PROFILE[risk_profile]
        if self._held is not None:
            self._backend.key_up(self._held)   # 방향 전환: 기존 키 떼기
            self._sleep(self._uniform(*p["reaction"]))  # 전환 사이 사람같은 미세 지연
        self._backend.key_down(key)
        self._held = key

    def release_dir(self) -> None:
        """유지 중인 이동키를 뗀다(제자리 공격/정지/안전 진입 시)."""
        if self._held is not None:
            self._backend.key_up(self._held)
            self._held = None

    def held_dir(self) -> str | None:
        """현재 유지 중인 이동키(없으면 None)."""
        return self._held

    # ── 공개 API ──────────────────────────────────────────────────────
    def perform(self, intent: Intent) -> None:
        """의도를 변형해 실제 입력으로 송출."""
        p = _PROFILE[intent.risk_profile]

        # 행동 전 반응 지연 (base_delay + 프로파일 반응시간)
        delay = intent.base_delay + self._uniform(*p["reaction"])
        if delay > 0:
            self._sleep(delay)

        if intent.action == "hold":
            self._backend.key_down(intent.key)
            return
        if intent.action == "move_dir":
            self._backend.key_down(intent.key)
            return

        # action == "key": 홀드 시간을 지터해 누름
        hold = self._jitter_hold(intent.base_hold_sec, p)
        self._backend.press(intent.key, hold)

    def reaction_delay(self, profile: RiskProfile) -> float:
        """프로파일별 반응 지연 1회 샘플 (테스트/외부 사용)."""
        lo, hi = _PROFILE[profile]["reaction"]
        return self._uniform(lo, hi)

    # ── 내부 ──────────────────────────────────────────────────────────
    def _jitter_hold(self, base: float, p: dict) -> float:
        factor = self._uniform(*p["hold_jitter"])
        val = base * factor
        # 의도적 불완전성: 가끔 미세하게 더/덜
        if self._rng.random() < p["sloppy"]:
            val *= self._uniform(0.7, 1.3)
        return max(_HOLD_MIN, min(_HOLD_MAX, val))

    def _uniform(self, lo: float, hi: float) -> float:
        return self._rng.uniform(lo, hi)
