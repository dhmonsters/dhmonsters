# Ed25519 장치 라이선스와 짧은 서버 세션을 검증하는 클라이언트
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.secure_store import load_protected_json, save_protected_json


PUBLIC_KEY_RAW_B64 = "4XBPh3V4XfpCE2Ayl86IylVSgwoshF814qF2iBWG8sA="
SESSION_SECONDS = 60 * 60
HEARTBEAT_SECONDS = 10 * 60
OFFLINE_GRACE_SECONDS = 7 * 24 * 60 * 60


class LicenseV2Error(RuntimeError):
    pass


class AuthoritativeDenial(LicenseV2Error):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TransientLicenseError(LicenseV2Error):
    pass


@dataclass(frozen=True)
class LicenseDecision:
    allowed: bool
    online: bool
    reason: str
    offline_remaining: float = 0.0


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _parse_time(value: str | None) -> float:
    if not value:
        return 0.0
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_envelope(envelope: dict[str, Any], expected_type: str) -> dict[str, Any]:
    if int(envelope.get("v", 0)) != 2:
        raise LicenseV2Error("지원하지 않는 서명 형식입니다.")
    payload_bytes = _b64url_decode(str(envelope.get("payload", "")))
    signature = _b64url_decode(str(envelope.get("signature", "")))
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_RAW_B64))
    try:
        public_key.verify(signature, payload_bytes)
    except Exception as exc:
        raise LicenseV2Error("라이선스 서명이 올바르지 않습니다.") from exc
    payload = json.loads(payload_bytes.decode("utf-8"))
    if payload.get("type") != expected_type:
        raise LicenseV2Error("라이선스 서명 용도가 올바르지 않습니다.")
    return payload


class LicenseClient:
    def __init__(self, server_url: str, anon_key: str, storage_path: str, timeout: int = 8):
        self.server_url = server_url.rstrip("/")
        self.anon_key = anon_key
        self.storage_path = storage_path
        self.timeout = timeout
        self.state: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        try:
            self.state = load_protected_json(self.storage_path) or {}
        except Exception as exc:
            raise LicenseV2Error("저장된 라이선스 파일을 읽을 수 없습니다.") from exc
        return self.state

    def activate(self, license_key: str, hwid: str) -> LicenseDecision:
        response = self._post("license-session", {
            "action": "activate",
            "license_key": license_key.strip(),
            "hwid": hwid,
        })
        self._accept_session(response, license_key.strip(), hwid)
        return LicenseDecision(True, True, "activated", OFFLINE_GRACE_SECONDS)

    def check(self, hwid: str) -> LicenseDecision:
        state = self.load()
        if not state:
            raise LicenseV2Error("라이선스가 등록되지 않았습니다.")
        if int(state.get("version", 1)) < 2:
            return self._migrate_legacy(state, hwid)
        self._verify_local_state(state, hwid)
        try:
            response = self._post("license-session", {
                "action": "refresh",
                "license_key": state.get("license_key", ""),
                "device_token": state.get("device_token"),
                "session_token": state.get("session_token"),
                "hwid": hwid,
            })
            self._accept_session(response, str(state.get("license_key", "")), hwid)
            return LicenseDecision(True, True, "verified", OFFLINE_GRACE_SECONDS)
        except AuthoritativeDenial:
            raise
        except TransientLicenseError:
            return self._offline_decision(state)

    def heartbeat(self, hwid: str) -> LicenseDecision:
        state = self.load()
        self._verify_local_state(state, hwid)
        try:
            response = self._post("license-heartbeat", {
                "session_token": state.get("session_token"),
                "device_token": state.get("device_token"),
                "hwid": hwid,
            })
            self._accept_session(response, str(state.get("license_key", "")), hwid)
            return LicenseDecision(True, True, "heartbeat", OFFLINE_GRACE_SECONDS)
        except AuthoritativeDenial:
            raise
        except TransientLicenseError:
            return self._offline_decision(state)

    def _migrate_legacy(self, state: dict[str, Any], hwid: str) -> LicenseDecision:
        license_key = str(state.get("license_key", "")).strip()
        if not license_key:
            raise LicenseV2Error("기존 라이선스를 갱신하려면 라이선스 키를 다시 입력해야 합니다.")
        response = self._post("license-session", {
            "action": "migrate",
            "license_key": license_key,
            "legacy_token": state.get("token"),
            "hwid": hwid,
        })
        self._accept_session(response, license_key, hwid)
        return LicenseDecision(True, True, "migrated", OFFLINE_GRACE_SECONDS)

    def _verify_local_state(self, state: dict[str, Any], hwid: str) -> None:
        device = verify_envelope(state.get("device_token") or {}, "device_license")
        if device.get("hwid_hash") != hash_value(hwid):
            raise AuthoritativeDenial("device_mismatch", "다른 컴퓨터에 등록된 라이선스입니다.")
        status = str(device.get("status", ""))
        if status in {"revoked", "expired"}:
            raise AuthoritativeDenial(status, "사용할 수 없는 라이선스입니다.")
        if _parse_time(device.get("expires_at")) <= _now():
            raise AuthoritativeDenial("expired", "라이선스 사용 기간이 만료되었습니다.")
        verify_envelope(state.get("manifest") or {}, "runtime_manifest")

    def _accept_session(self, response: dict[str, Any], license_key: str, hwid: str) -> None:
        device_token = response.get("device_token")
        manifest = response.get("manifest")
        device = verify_envelope(device_token, "device_license")
        policy = verify_envelope(manifest, "runtime_manifest")
        if device.get("hwid_hash") != hash_value(hwid):
            raise AuthoritativeDenial("device_mismatch", "서버의 장치 정보가 현재 컴퓨터와 다릅니다.")
        if _parse_time(policy.get("expires_at")) <= _now():
            raise LicenseV2Error("서버 정책의 유효기간이 지났습니다.")
        self.state = {
            "version": 2,
            "license_key": license_key,
            "device_token": device_token,
            "session_token": response.get("session_token"),
            "session_expires_at": response.get("session_expires_at"),
            "manifest": manifest,
            "last_online_at": datetime.now(timezone.utc).isoformat(),
        }
        save_protected_json(self.storage_path, self.state)

    def _offline_decision(self, state: dict[str, Any]) -> LicenseDecision:
        elapsed = _now() - _parse_time(state.get("last_online_at"))
        remaining = OFFLINE_GRACE_SECONDS - max(0.0, elapsed)
        if remaining <= 0:
            raise LicenseV2Error("오프라인 사용 가능 기간 7일이 지났습니다. 인터넷 연결 후 다시 실행해 주세요.")
        return LicenseDecision(True, False, "offline_grace", remaining)

    def _post(self, function_name: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            import requests
            response = requests.post(
                f"{self.server_url}/{function_name}",
                json=body,
                headers={
                    "Authorization": f"Bearer {self.anon_key}",
                    "apikey": self.anon_key,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except Exception as exc:
            raise TransientLicenseError("라이선스 서버에 연결할 수 없습니다.") from exc
        try:
            payload = response.json()
        except Exception as exc:
            raise TransientLicenseError("라이선스 서버 응답을 읽을 수 없습니다.") from exc
        code = str(payload.get("code", ""))
        if code in {"revoked", "expired", "device_mismatch", "invalid_license"}:
            raise AuthoritativeDenial(code, str(payload.get("message", "라이선스가 거부되었습니다.")))
        if response.status_code >= 500:
            raise TransientLicenseError(str(payload.get("message", "라이선스 서버 오류입니다.")))
        if not response.ok or not payload.get("ok"):
            raise LicenseV2Error(str(payload.get("message", "라이선스 확인에 실패했습니다.")))
        return payload

