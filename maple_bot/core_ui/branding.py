# Claude 브랜드 아이콘을 소스 실행과 EXE 실행에서 공통으로 불러온다.
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon


def claude_icon() -> QIcon:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return QIcon(str(base / "assets" / "claude_logo.ico"))
