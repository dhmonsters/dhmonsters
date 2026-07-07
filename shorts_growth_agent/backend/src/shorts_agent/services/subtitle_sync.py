# 자막 텍스트 라인에 대한 시간 구간을 비례 분배해 동기화합니다.
from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start_ms: int
    end_ms: int


class SubtitleSyncService:
    def sync(self, lines: list[str], total_duration_ms: int) -> list[SubtitleCue]:
        if not lines:
            return []

        slot = total_duration_ms // len(lines)
        cues = []
        for index, line in enumerate(lines):
            start = index * slot
            end = total_duration_ms if index == len(lines) - 1 else (index + 1) * slot
            cues.append(SubtitleCue(text=line, start_ms=start, end_ms=end))
        return cues
