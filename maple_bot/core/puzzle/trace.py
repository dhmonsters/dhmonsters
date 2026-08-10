# 투명도형 퍼즐 세션 이벤트를 JSONL trace로 기록한다.
from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import Any

from core.puzzle.models import PuzzleSession


SENSITIVE_KEYS = {"tg_token", "telegram_token", "chat_id"}


class TraceLogger:
    def __init__(
        self,
        session: PuzzleSession,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.session = session
        self._clock = clock or time.time
        self.session.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def write_event(
        self,
        type: str,
        frame_index: int | None,
        payload: Mapping[str, object],
    ) -> None:
        event = {
            "type": type,
            "session_id": self.session.session_id,
            "frame_index": frame_index,
            "timestamp_ms": int(round(self._clock() * 1000)),
            "payload": _mask_sensitive(payload),
        }
        with self.session.trace_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            fp.write("\n")


def _mask_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "***" if str(key) in SENSITIVE_KEYS else _mask_sensitive(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_mask_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_sensitive(item) for item in value)
    return value
