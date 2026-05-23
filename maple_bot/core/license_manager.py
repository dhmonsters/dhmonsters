# 라이선스 검증 로직 — 로컬 토큰 확인 + 서버 온라인 재검증
from __future__ import annotations
import json
import os
import time
import logging

logger = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────────────
LICENSE_FILE    = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "MapleBot", "license.dat"
)

# Supabase 프로젝트 설정 — 아래 두 값을 실제 값으로 교체
# Supabase 대시보드 → Settings → API 에서 확인
_SUPABASE_PROJECT = "djdpfwoolwqrasqretng"
_SUPABASE_ANON    = "sb_publishable_qUnX4JoLF1MqNzjZGSURmQ_HerOiHZr"

SERVER_URL      = f"https://{_SUPABASE_PROJECT}.supabase.co/functions/v1"
OFFLINE_GRACE   = 7 * 24 * 3600   # 오프라인 허용 기간 (7일, 초 단위)
REQUEST_TIMEOUT = 8                # 서버 요청 타임아웃 (초)

# gen_secret.py 실행 결과의 JWT_SECRET 값으로 교체 (Supabase 환경변수와 동일해야 함)
_JWT_SECRET = "cb4155372cbeeeee804e32e03a29e73a8a6d9576720689dcbf57e4896a251bc4"


# ── 공개 API ──────────────────────────────────────────────────────────

class LicenseError(Exception):
    """라이선스 검증 실패 시 발생하는 예외."""


def check(hwid: str) -> None:
    """앱 시작 시 호출. 라이선스가 유효하지 않으면 LicenseError를 발생시킨다."""
    dat = _load_license_file()

    if dat is None:
        raise LicenseError("NO_LICENSE")   # 파일 없음 → 키 입력 필요

    _verify_local(dat, hwid)               # 로컬 서명 + HWID 검증

    # admin_issued 토큰은 서버 재검증 불필요 (오프라인 발급)
    payload = _jwt_decode(dat.get("token", ""))
    if payload.get("admin_issued"):
        return

    # 7일 이상 온라인 검증 안 했으면 서버에 재확인
    last_online = dat.get("last_online", 0)
    if time.time() - last_online >= OFFLINE_GRACE:
        _verify_online(dat, hwid)


def activate(license_key: str, hwid: str) -> None:
    """처음 활성화. 서버에 키와 HWID를 보내 토큰을 받아 저장한다."""
    try:
        import requests
        resp = requests.post(
            f"{SERVER_URL}/activate",
            json={"license_key": license_key, "hwid": hwid},
            headers={"Authorization": f"Bearer {_SUPABASE_ANON}"},
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as exc:
        raise LicenseError(f"서버 연결 실패: {exc}") from exc

    if resp.status_code != 200:
        msg = _safe_json(resp).get("detail", resp.text)
        raise LicenseError(f"활성화 거부: {msg}")

    data = resp.json()
    _save_license_file({
        "token":       data["token"],
        "license_key": license_key,
        "hwid":        hwid,
        "last_online": time.time(),
    })


# ── 내부 ──────────────────────────────────────────────────────────────

def _verify_local(dat: dict, hwid: str) -> None:
    """JWT 서명과 HWID를 로컬에서 검증한다."""
    token = dat.get("token", "")
    payload = _jwt_decode(token)           # 서명 검증

    if payload.get("hwid") != hwid:
        raise LicenseError("이 PC에 등록된 라이선스가 아닙니다.")

    exp = payload.get("exp", 0)
    if exp and time.time() > exp:
        raise LicenseError("라이선스 기간이 만료되었습니다.")


def _verify_online(dat: dict, hwid: str) -> None:
    """서버에 토큰 유효성을 확인하고 last_online을 갱신한다."""
    try:
        import requests
        resp = requests.post(
            f"{SERVER_URL}/verify",
            json={"token": dat.get("token"), "hwid": hwid},
            headers={"Authorization": f"Bearer {_SUPABASE_ANON}"},
            timeout=REQUEST_TIMEOUT,
        )
    except Exception:
        # 서버 연결 실패 → 오프라인 유예 기간 연장 (관대하게 처리)
        logger.warning("라이선스 서버 연결 실패 — 오프라인 모드로 진행")
        return

    if resp.status_code != 200:
        msg = _safe_json(resp).get("detail", "검증 거부")
        raise LicenseError(f"온라인 검증 실패: {msg}")

    # 성공 — last_online 갱신
    dat["last_online"] = time.time()
    _save_license_file(dat)


def _load_license_file() -> dict | None:
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_license_file(dat: dict) -> None:
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(dat, f)


def _safe_json(resp) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}


# ── 경량 JWT 구현 (PyJWT 없이 동작하는 fallback 포함) ────────────────

def _jwt_decode(token: str) -> dict:
    """HS256 JWT 서명을 검증하고 payload를 반환한다."""
    import base64
    import hmac
    import hashlib

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise LicenseError("라이선스 파일이 손상되었습니다.")

        header_b64, payload_b64, sig_b64 = parts
        expected_sig = hmac.new(
            _JWT_SECRET.encode(),
            f"{header_b64}.{payload_b64}".encode(),
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()

        if not hmac.compare_digest(sig_b64, expected_b64):
            raise LicenseError("라이선스 서명이 유효하지 않습니다.")

        # 패딩 복원 후 디코딩
        padding = 4 - len(payload_b64) % 4
        payload_json = base64.urlsafe_b64decode(payload_b64 + "=" * padding)
        return json.loads(payload_json)

    except LicenseError:
        raise
    except Exception as exc:
        raise LicenseError(f"라이선스 파일 파싱 오류: {exc}") from exc
