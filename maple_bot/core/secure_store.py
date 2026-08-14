# 라이선스 상태를 Windows DPAPI로 보호해 저장하는 모듈
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


_MAGIC = b"CLAUDE-LICENSE-V2\0"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DataBlob, object]:
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    source, source_buffer = _blob(data)
    result = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "Claude license", None, None, None, 0,
        ctypes.byref(result),
    )
    del source_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    source, source_buffer = _blob(data)
    result = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0,
        ctypes.byref(result),
    )
    del source_buffer
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)


def load_protected_json(path: str | os.PathLike[str]) -> dict | None:
    target = Path(path)
    if not target.exists():
        return None
    raw = target.read_bytes()
    if raw.startswith(_MAGIC):
        raw = _unprotect(raw[len(_MAGIC):])
    return json.loads(raw.decode("utf-8"))


def save_protected_json(path: str | os.PathLike[str], value: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = _MAGIC + _protect(raw)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, target)

