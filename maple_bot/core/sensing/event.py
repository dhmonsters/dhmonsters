# Event — 감지부가 오케스트레이터에 보내는 통지 단위 (느슨 결합의 매개)
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Event:
    """감지 이벤트.

    type: "char_pos" | "user_detected" | "user_gone" | "lie" | "potion_low"
          | "anti_mob" | "chat" ...
    data: type별 페이로드 (예: char_pos → {"x":.., "y":..})
    ts:   생성 시각 (자동)
    """
    type: str
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.type:
            raise ValueError("Event.type 은 비어있을 수 없습니다.")
