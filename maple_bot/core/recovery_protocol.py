# 복구 실행기와 실제 앱 사이의 준비 완료 및 치명적 오류 파일 규약을 제공한다.
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_from_env(name: str, payload: dict[str, Any]) -> bool:
    raw_path = os.environ.get(name, "").strip()
    if not raw_path:
        return False
    target = Path(raw_path)
    temporary = target.with_name(target.name + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return True
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def is_launcher_managed() -> bool:
    return os.environ.get("CLAUDE_RECOVERY_MANAGED") == "1"


def write_ready() -> bool:
    return _write_json_from_env(
        "CLAUDE_RECOVERY_READY_FILE",
        {"status": "ready", "pid": os.getpid(), "created_at": _utc_now()},
    )


def write_normal_exit(reason: str) -> bool:
    return _write_json_from_env(
        "CLAUDE_RECOVERY_NORMAL_FILE",
        {
            "status": "normal",
            "reason": str(reason),
            "pid": os.getpid(),
            "created_at": _utc_now(),
        },
    )


def write_fatal(
    kind: str,
    message: str,
    traceback_text: str = "",
    exit_code: int = 1,
) -> bool:
    return _write_json_from_env(
        "CLAUDE_RECOVERY_CRASH_FILE",
        {
            "kind": str(kind),
            "message": str(message),
            "traceback": str(traceback_text),
            "exit_code": int(exit_code),
            "pid": os.getpid(),
            "created_at": _utc_now(),
        },
    )
