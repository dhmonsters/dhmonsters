# 투명도형 퍼즐 세션 이벤트를 알림 전송기와 trace에 안전하게 연결한다.
from __future__ import annotations

from pathlib import Path

from core.notify.telegram import TelegramNotifier
from core.puzzle.trace import TraceLogger


class PuzzleNotifier:
    def __init__(
        self,
        telegram: TelegramNotifier | None = None,
        trace_logger: TraceLogger | None = None,
    ) -> None:
        self.telegram = telegram
        self.trace_logger = trace_logger

    def send_event(self, event_type: str, text: str, snapshot: Path | None = None) -> bool:
        message = _format_message(event_type, text, snapshot)
        sent = False
        if self.telegram is not None:
            sent = bool(self.telegram.send(message))

        if self.trace_logger is not None:
            self.trace_logger.write_event(
                "NOTIFY",
                None,
                {
                    "event_type": event_type,
                    "text": text,
                    "snapshot": str(snapshot) if snapshot is not None else None,
                    "sent": sent,
                },
            )
        return sent


def _format_message(event_type: str, text: str, snapshot: Path | None) -> str:
    message = f"[{event_type}] {text}"
    if snapshot is not None:
        message = f"{message}\nsnapshot: {snapshot.name}"
    return message
