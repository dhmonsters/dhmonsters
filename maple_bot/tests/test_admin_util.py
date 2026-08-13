# 관리자 권한 재실행이 프로젝트 작업 폴더를 유지하는지 검증한다.
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import admin_util


def test_script_admin_relaunch_uses_entry_script_directory(monkeypatch, tmp_path):
    entry = tmp_path / "run_integrated.py"
    calls = []

    monkeypatch.setattr(admin_util, "is_admin", lambda: False)
    monkeypatch.setattr(admin_util.sys, "frozen", False, raising=False)
    monkeypatch.setattr(admin_util.sys, "executable", r"C:\Python\python.exe")
    monkeypatch.setattr(admin_util.sys, "argv", [str(entry)])
    monkeypatch.setattr(
        admin_util.ctypes,
        "windll",
        SimpleNamespace(
            shell32=SimpleNamespace(
                ShellExecuteW=lambda *args: calls.append(args) or 42,
            )
        ),
        raising=False,
    )

    with pytest.raises(SystemExit) as exc_info:
        admin_util.ensure_admin()

    assert exc_info.value.code == 0
    assert calls == [(
        None,
        "runas",
        r"C:\Python\python.exe",
        f'"{entry}"',
        str(Path(entry).parent),
        1,
    )]
