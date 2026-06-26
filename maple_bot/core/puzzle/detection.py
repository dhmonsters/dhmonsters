# 투명도형 퍼즐 팝업 감지 점수를 안정적인 이벤트로 변환한다.
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DetectionEventType = Literal["DETECTION_PENDING", "PUZZLE_DETECTED", "DETECTION_NOISE"]


@dataclass(frozen=True)
class DetectionEvent:
    event_type: DetectionEventType
    frame_index: int
    score: float
    hit_count: int
    detected: bool
    reason: str


class DetectionGate:
    def __init__(self, threshold: float = 0.7, required_hits: int = 3) -> None:
        if required_hits <= 0:
            raise ValueError("required_hits must be positive")
        self.threshold = float(threshold)
        self.required_hits = int(required_hits)
        self._hit_count = 0

    def update(self, score: float, frame_index: int) -> DetectionEvent:
        score = float(score)
        if score < self.threshold:
            self._hit_count = 0
            return DetectionEvent(
                event_type="DETECTION_NOISE",
                frame_index=frame_index,
                score=score,
                hit_count=0,
                detected=False,
                reason="below_threshold",
            )

        self._hit_count += 1
        detected = self._hit_count >= self.required_hits
        return DetectionEvent(
            event_type="PUZZLE_DETECTED" if detected else "DETECTION_PENDING",
            frame_index=frame_index,
            score=score,
            hit_count=self._hit_count,
            detected=detected,
            reason="required_hits_met" if detected else "waiting_for_consecutive_hits",
        )
