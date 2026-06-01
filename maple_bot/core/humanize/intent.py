# 행동 의도(Intent) — 모듈은 '무엇을' 만 말하고, '언제·어떻게'는 Humanizer가 결정
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskProfile(str, Enum):
    """안티밴 위험도 프로파일 — Humanizer가 이 값으로 타이밍 분포를 조절."""
    CAREFUL = "careful"   # 느리고 불규칙 (안전 최우선)
    NORMAL = "normal"     # 기본
    FAST = "fast"         # 빠름 (효율 우선, 위험↑)


_VALID_ACTIONS = {"key", "hold", "move_dir"}


@dataclass
class Intent:
    """행동 의도. base_* 는 '의도값'일 뿐 — 실제 입력 타이밍은 Humanizer가 분포 적용해 결정한다.

    action:
      "key"      — 키 1회 입력 (base_hold_sec 동안 누름)
      "hold"     — 키를 계속 누름 (방향키 등)
      "move_dir" — 방향 이동 의도 (key에 left/right/up/down)
    """
    action: str
    key: str = ""
    base_hold_sec: float = 0.05
    base_delay: float = 0.0
    risk_profile: RiskProfile = RiskProfile.NORMAL

    def __post_init__(self) -> None:
        if self.action not in _VALID_ACTIONS:
            raise ValueError(
                f"알 수 없는 action: {self.action!r} (허용: {sorted(_VALID_ACTIONS)})"
            )
        if self.action in ("key", "hold", "move_dir") and not self.key:
            raise ValueError(f"action={self.action!r} 에는 key 가 필요합니다.")
        # Enum 강제 (문자열로 들어와도 변환)
        if not isinstance(self.risk_profile, RiskProfile):
            self.risk_profile = RiskProfile(self.risk_profile)
