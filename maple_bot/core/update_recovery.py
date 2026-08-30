# 업데이트 전 현재 버전 설치 파일을 검증해 직전 버전 복구본으로 보관한다.
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_OFFICIAL_RELEASE_PREFIX = "/dhmonsters/dhmonsters/releases/download/"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_recovery_dir() -> Path:
    override = os.environ.get("CLAUDE_RECOVERY_DIR", "").strip()
    if override:
        return Path(override)
    common = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    return Path(common) / "Claude" / "Recovery"


def get_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def validate_release_url(url: str) -> None:
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme.lower() != "https" or parsed.hostname != "github.com":
        raise ValueError("공식 GitHub HTTPS Release URL만 허용됩니다.")
    if not parsed.path.startswith(_OFFICIAL_RELEASE_PREFIX):
        raise ValueError("공식 Claude Release 경로가 아닙니다.")


def validate_release_info(info: dict) -> dict:
    version = str(info.get("version", "")).strip()
    url = str(info.get("download_url", "")).strip()
    digest = str(info.get("sha256", "")).strip().lower()
    if not version:
        raise RuntimeError("release.json에 version이 없습니다.")
    try:
        validate_release_url(url)
    except ValueError as exc:
        raise RuntimeError(f"download_url이 올바르지 않습니다: {exc}") from exc
    if not _SHA256_RE.fullmatch(digest):
        raise RuntimeError("release.json의 sha256이 올바르지 않습니다.")
    return {"version": version, "download_url": url, "sha256": digest}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_local_release(base_dir: Path | None = None) -> dict:
    root = Path(base_dir) if base_dir is not None else get_install_dir()
    path = root / "release.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise RuntimeError(f"현재 버전 release.json을 읽지 못했습니다: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("현재 버전 release.json 형식이 올바르지 않습니다.")
    return validate_release_info(payload)


def _download_to_path(url: str, destination: Path) -> None:
    import requests

    validate_release_url(url)
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with destination.open("wb") as stream:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                stream.write(chunk)


def ensure_previous_installer(
    current_release: dict,
    downloader: Callable[[str, Path], None] | None = None,
    recovery_dir: Path | None = None,
    install_dir: Path | None = None,
) -> Path:
    release = validate_release_info(current_release)
    recovery_root = Path(recovery_dir) if recovery_dir is not None else get_recovery_dir()
    installation = Path(install_dir) if install_dir is not None else get_install_dir()
    previous = recovery_root / "previous_setup.exe"
    metadata_path = recovery_root / "recovery.json"

    try:
        cached = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except Exception:
        cached = {}
    if (
        previous.is_file()
        and cached.get("previous_version") == release["version"]
        and str(cached.get("previous_sha256", "")).lower() == release["sha256"]
    ):
        try:
            if sha256_file(previous) == release["sha256"]:
                return previous
        except OSError:
            pass

    recovery_root.mkdir(parents=True, exist_ok=True)
    setup_temp = recovery_root / "previous_setup.download"
    metadata_temp = recovery_root / "recovery.json.download"
    for temporary in (setup_temp, metadata_temp):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

    download = downloader or _download_to_path
    try:
        download(release["download_url"], setup_temp)
        actual = sha256_file(setup_temp)
        if actual != release["sha256"]:
            raise RuntimeError(
                "현재 버전 설치 파일 SHA-256이 일치하지 않습니다. "
                f"expected={release['sha256']} actual={actual}"
            )
        payload = {
            "previous_version": release["version"],
            "current_version": release["version"],
            "installation_path": str(installation.resolve()),
            "previous_sha256": release["sha256"],
            "created_at": _utc_now(),
        }
        metadata_temp.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(setup_temp, previous)
        os.replace(metadata_temp, metadata_path)
        return previous
    except Exception:
        for temporary in (setup_temp, metadata_temp):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise
