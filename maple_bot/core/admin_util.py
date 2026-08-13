# 관리자 권한 자동 요청 — 게임이 관리자로 돌면 봇도 관리자여야 입력/핫키가 동작(UIPI 차단 회피).
from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def is_admin() -> bool:
    """현재 프로세스가 관리자 권한이면 True."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin() -> None:
    """관리자가 아니면 UAC로 자기 자신을 관리자 권한으로 재실행하고 비관리자 인스턴스는 종료한다.
    승인 거부/실패 시엔 비관리자로 그대로 진행(하드 실패하지 않음)."""
    if is_admin():
        return
    try:
        exe = sys.executable
        if getattr(sys, "frozen", False):
            # 빌드된 exe — argv[0]은 exe 자신이므로 인자만 전달
            params = " ".join(f'"{a}"' for a in sys.argv[1:])
            working_dir = str(Path(exe).resolve().parent)
        else:
            # 스크립트 — python.exe로 스크립트+인자 재실행
            params = " ".join(f'"{a}"' for a in sys.argv)
            working_dir = str(Path(sys.argv[0]).resolve().parent)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, working_dir, 1
        )
        if rc > 32:           # 성공 — 관리자 인스턴스가 떴으므로 현재(비관리자) 종료
            sys.exit(0)
    except Exception:
        pass
    # 거부/실패 — 비관리자로 계속(인게임 핫키는 안 먹을 수 있음)
