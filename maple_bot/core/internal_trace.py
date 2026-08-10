# UI와 독립된 내부 진단 이벤트를 JSONL 파일로 기록하는 모듈
from __future__ import annotations

import atexit
import json
import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


# 문제 해결 후 False로 바꾸면 호출부를 남긴 채 기록만 완전히 중단할 수 있습니다.
INTERNAL_TRACE_ENABLED = True

_enabled = INTERNAL_TRACE_ENABLED and os.environ.get("CLAUDE_INTERNAL_TRACE", "1") != "0"
_trace_path = Path(__file__).resolve().parents[1] / "logs" / "internal_trace.jsonl"
_queue: queue.SimpleQueue[dict[str, Any] | None] = queue.SimpleQueue()
_writer_thread: threading.Thread | None = None
_start_lock = threading.Lock()


def _write_loop() -> None:
    try:
        _trace_path.parent.mkdir(parents=True, exist_ok=True)
        with _trace_path.open("a", encoding="utf-8", buffering=1) as trace_file:
            while True:
                record = _queue.get()
                if record is None:
                    return
                trace_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # 진단 기록 실패가 봇 동작을 중단시키면 안 됩니다.
        return


def _ensure_writer() -> None:
    global _writer_thread
    if not _enabled or (_writer_thread is not None and _writer_thread.is_alive()):
        return
    with _start_lock:
        if _writer_thread is not None and _writer_thread.is_alive():
            return
        _writer_thread = threading.Thread(
            target=_write_loop,
            name="internal-trace-writer",
            daemon=True,
        )
        _writer_thread.start()


def trace_event(category: str, event: str, **data: Any) -> None:
    """호출 스레드를 기다리게 하지 않고 내부 진단 이벤트를 기록합니다."""
    if not _enabled:
        return
    try:
        _ensure_writer()
        _queue.put({
            "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "monotonic_ns": __import__("time").monotonic_ns(),
            "thread": threading.current_thread().name,
            "category": category,
            "event": event,
            "data": data,
        })
    except Exception:
        pass


def _shutdown_writer() -> None:
    if _writer_thread is not None:
        _queue.put(None)


atexit.register(_shutdown_writer)
