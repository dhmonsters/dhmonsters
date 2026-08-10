# 기존 UI와 Ed25519 라이선스 v2 클라이언트를 연결하는 호환 모듈
from __future__ import annotations

import os

from core.license_runtime import configure_runtime as _configure_license_runtime
from core.license_runtime import register_safe_stop
from core.license_v2 import AuthoritativeDenial, LicenseClient, LicenseV2Error


LICENSE_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "MapleBot",
    "license.dat",
)

_SUPABASE_PROJECT = "djdpfwoolwqrasqretng"
_SUPABASE_ANON = "sb_publishable_qUnX4JoLF1MqNzjZGSURmQ_HerOiHZr"
SERVER_URL = f"https://{_SUPABASE_PROJECT}.supabase.co/functions/v1"
REQUEST_TIMEOUT = 8


class LicenseError(RuntimeError):
    pass


_CLIENT = LicenseClient(SERVER_URL, _SUPABASE_ANON, LICENSE_FILE, REQUEST_TIMEOUT)


def check(hwid: str) -> None:
    """저장된 장치 라이선스를 확인하고 실행 중 하트비트를 시작한다."""
    try:
        _CLIENT.check(hwid)
        _configure_license_runtime(_CLIENT, hwid)
    except (AuthoritativeDenial, LicenseV2Error) as exc:
        raise LicenseError(str(exc)) from exc


def activate(license_key: str, hwid: str) -> None:
    """라이선스 키를 현재 장치에 연결하고 보호 저장한다."""
    try:
        _CLIENT.activate(license_key, hwid)
        _configure_license_runtime(_CLIENT, hwid)
    except (AuthoritativeDenial, LicenseV2Error) as exc:
        raise LicenseError(str(exc)) from exc

