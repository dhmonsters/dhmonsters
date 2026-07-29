# GitHub Raw?먯꽌 理쒖떊 踰꾩쟾 ?뺣낫瑜?議고쉶?섍퀬 ?몄뒪?⑤윭瑜??ㅼ슫濡쒕뱶/?ㅽ뻾?섎뒗 ?낅뜲?댄꽣
from __future__ import annotations
import os
import sys
import subprocess
import tempfile
import re
import json
from typing import Callable

# GitHub Raw URL ??version.json ?꾩튂
_VERSION_URL = "https://raw.githubusercontent.com/dhmonsters/dhmonsters/main/maple_bot/version.json"

# 濡쒖뺄 踰꾩쟾 ?뚯씪 寃쎈줈
_LOCAL_VERSION_FILE = "version.txt"


def _read_local_version() -> str:
    """濡쒖뺄 version.txt?먯꽌 ?꾩옱 踰꾩쟾???쎈뒗??"""
    try:
        if getattr(sys, "frozen", False):
            # PyInstaller exe: version.txt??exe? 媛숈? ?대뜑???꾩튂
            base = os.path.dirname(sys.executable)
        else:
            # ?뚯뒪 ?ㅽ뻾: core/updater.py 湲곗??쇰줈 ???④퀎 ??(?꾨줈?앺듃 猷⑦듃)
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, _LOCAL_VERSION_FILE)
        with open(path, encoding="utf-8-sig") as f:
            return f.read().strip().lstrip("\ufeff")
    except Exception:
        return "0.0.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """버전 표기 차이를 정리해 숫자 튜플로 변환한다."""
    try:
        text = str(v or "").strip().lstrip("\ufeff").lower()
        if text.startswith("v"):
            text = text[1:]
        parts = [int(x) for x in re.findall(r"\d+", text)]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def get_current_version() -> str:
    """?꾩옱 濡쒖뺄 踰꾩쟾 臾몄옄?댁쓣 諛섑솚?쒕떎."""
    return _read_local_version()


def check_for_update() -> dict | None:
    """
    GitHub Raw?먯꽌 version.json???쎌뼱 理쒖떊 踰꾩쟾 ?뺣낫瑜?諛섑솚?쒕떎.
    理쒖떊 踰꾩쟾???녾굅???ㅻ쪟 諛쒖깮 ??None 諛섑솚.

    諛섑솚 dict ?뺤떇:
        {
            "current":      "1.1.2",
            "latest":       "1.2.0",
            "notes":        "蹂寃??ы빆 ?붿빟",
            "download_url": "https://..."
        }
    """
    import requests

    current = _read_local_version()
    try:
        resp = requests.get(_VERSION_URL, timeout=5)
        resp.raise_for_status()
        data = json.loads(resp.content.decode("utf-8-sig"))
    except Exception as exc:
        raise RuntimeError(f"업데이트 정보를 확인하지 못했습니다: {exc}") from exc

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
    """?몄뒪?⑤윭瑜??꾩떆 ?대뜑???ㅼ슫濡쒕뱶?섍퀬 寃쎈줈瑜?諛섑솚?쒕떎."""
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
    """?몄뒪?⑤윭瑜??ㅽ뻾?섍퀬 ?꾩옱 ?깆쓣 醫낅즺?쒕떎."""
    subprocess.Popen([installer_path], close_fds=True)
    sys.exit(0)
