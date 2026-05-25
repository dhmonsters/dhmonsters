# GitHub Raw에서 최신 버전 정보를 조회하고 인스톨러를 다운로드/실행하는 업데이터
from __future__ import annotations
import os
import sys
import subprocess
import tempfile
from typing import Callable

# GitHub Raw URL — version.json 위치
_VERSION_URL = "https://raw.githubusercontent.com/dhmonsters/dhmonsters/main/maple_bot/version.json"

# 로컬 버전 파일 경로
_LOCAL_VERSION_FILE = "version.txt"


def _read_local_version() -> str:
    """로컬 version.txt에서 현재 버전을 읽는다."""
    try:
        if getattr(sys, "frozen", False):
            # PyInstaller exe: version.txt는 exe와 같은 폴더에 위치
            base = os.path.dirname(sys.executable)
        else:
            # 소스 실행: core/updater.py 기준으로 두 단계 위 (프로젝트 루트)
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, _LOCAL_VERSION_FILE)
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """'1.2.3' → (1, 2, 3) 으로 변환."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


def get_current_version() -> str:
    """현재 로컬 버전 문자열을 반환한다."""
    return _read_local_version()


def check_for_update() -> dict | None:
    """
    GitHub Raw에서 version.json을 읽어 최신 버전 정보를 반환한다.
    최신 버전이 없거나 오류 발생 시 None 반환.

    반환 dict 형식:
        {
            "current":      "1.1.2",
            "latest":       "1.2.0",
            "notes":        "변경 사항 요약",
            "download_url": "https://..."
        }
    """
    import requests

    current = _read_local_version()
    try:
        resp = requests.get(_VERSION_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    latest = data.get("version", "0.0.0")
    if _parse_version(latest) > _parse_version(current):
        return {
            "current":      current,
            "version":      latest,
            "notes":        data.get("notes", ""),
            "download_url": data.get("download_url", ""),
        }
    return None


def download_update(
    url: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> str:
    """인스톨러를 임시 폴더에 다운로드하고 경로를 반환한다."""
    import requests

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    suffix = ".exe" if url.lower().endswith(".exe") else ".tmp"
    fd, path = tempfile.mkstemp(suffix=suffix)

    downloaded = 0
    with os.fdopen(fd, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)

    return path


def apply_update(installer_path: str) -> None:
    """인스톨러를 실행하고 현재 앱을 종료한다."""
    subprocess.Popen([installer_path], close_fds=True)
    sys.exit(0)
