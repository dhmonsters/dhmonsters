# GitHub Raw에서 업데이트 정보를 확인하고 검증된 설치기를 적용한다.
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Callable

from core import recovery_protocol, update_recovery


_VERSION_URL = (
    "https://raw.githubusercontent.com/dhmonsters/dhmonsters/"
    "main/maple_bot/version.json"
)
_LOCAL_VERSION_FILE = "version.txt"


def _read_local_version() -> str:
    try:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, _LOCAL_VERSION_FILE), encoding="utf-8-sig") as stream:
            return stream.read().strip().lstrip("\ufeff")
    except Exception:
        return "0.0.0"


def _parse_version(value: str) -> tuple[int, ...]:
    try:
        text = str(value or "").strip().lstrip("\ufeff").lower()
        if text.startswith("v"):
            text = text[1:]
        parts = [int(item) for item in re.findall(r"\d+", text)]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def get_current_version() -> str:
    return _read_local_version()


def check_for_update() -> dict | None:
    import requests

    current = _read_local_version()
    try:
        response = requests.get(_VERSION_URL, timeout=5)
        response.raise_for_status()
        data = json.loads(response.content.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise RuntimeError("version.json 형식이 올바르지 않습니다.")
        release = update_recovery.validate_release_info(data)
    except Exception as exc:
        raise RuntimeError(f"업데이트 정보를 확인하지 못했습니다: {exc}") from exc

    if _parse_version(release["version"]) <= _parse_version(current):
        return None
    return {
        "current": current,
        "version": release["version"],
        "notes": str(data.get("notes", "")),
        "download_url": release["download_url"],
        "sha256": release["sha256"],
    }


def download_update(
    url: str,
    expected_sha256: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> str:
    import requests

    update_recovery.validate_release_url(url)
    expected = str(expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("업데이트 SHA-256이 올바르지 않습니다.")

    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    suffix = ".exe" if url.lower().endswith(".exe") else ".tmp"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        downloaded = 0
        with os.fdopen(fd, "wb") as stream:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                stream.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)
        actual = update_recovery.sha256_file(path)
        if actual != expected:
            raise RuntimeError(
                "업데이트 설치 파일 SHA-256이 일치하지 않습니다. "
                f"expected={expected} actual={actual}"
            )
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def apply_update(installer_path: str, update_info: dict) -> None:
    current_release = update_recovery.read_local_release()
    if _parse_version(update_info.get("version", "0.0.0")) > _parse_version(
        current_release["version"]
    ):
        update_recovery.ensure_previous_installer(current_release)
    subprocess.Popen([installer_path], close_fds=True)
    recovery_protocol.write_normal_exit("update_handoff")
    sys.exit(0)
