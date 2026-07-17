# 测谎 패키지의 PE 구조와 기능 관련 문자열을 실행 없이 조사하는 도구
import datetime
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import pefile


sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\Users\PC\Downloads\Telegram Desktop\测谎")
PE_SUFFIXES = {".exe", ".dll", ".sys", ".aes"}
KEYWORDS = (
    "http", "tcp", "udp", "socket", "connect", "listen", "server", "client",
    "pipe", "\\\\.\\", "device", "driver", "service", "sc.exe", "createfile",
    "ioctl", "deviceiocontrol", "kernel", "physicalmemory", "process", "thread",
    "debug", "dbg", "hook", "inject", "virtual", "vmx", "vt_", "hypervisor",
    "unreal", "ue4", "ue5", "gworld", "fname", "uobject", "actor", "bone",
    "cheat", "engine", "polygraph", "ffmpeg", "record", "capture", "screen",
    "audio", "camera", "face", "voice", "emotion", "lie", "truth", "detect",
    "aihelper", "aes", "encrypt", "decrypt", "license", "login", "token",
    "wechat", "telegram", "password", "username", "vmprotect", ".ini", ".log",
    ".dll", ".sys", ".exe", "loadlibrary", "writeprocessmemory", "createremotethread",
)


def decode(value: bytes | None) -> str:
    return "" if value is None else value.decode("latin1", "replace")


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    size = len(data)
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def printable_strings(data: bytes) -> set[str]:
    values = {
        match.decode("latin1", "replace")
        for match in re.findall(rb"[\x20-\x7e]{5,}", data)
    }
    for offset in (0, 1):
        text = data[offset:].decode("utf-16le", "ignore")
        values.update(re.findall(r"[\x20-\x7e\u3131-\uD79D\u4e00-\u9fff]{5,}", text))
    return values


def interesting_strings(data: bytes) -> list[str]:
    values = printable_strings(data)
    selected = []
    for value in values:
        cleaned = value.strip().replace("\x00", "")
        lowered = cleaned.casefold()
        if any(keyword in lowered for keyword in KEYWORDS):
            selected.append(cleaned[:500])
    return sorted(set(selected), key=lambda value: (value.casefold(), value))[:800]


def version_info(pe: pefile.PE) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in getattr(pe, "FileInfo", []) or []:
        for subentry in entry if isinstance(entry, list) else [entry]:
            if getattr(subentry, "Key", b"") == b"StringFileInfo":
                for table in subentry.StringTable:
                    for key, value in table.entries.items():
                        result[decode(key)] = decode(value)
    return result


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    result = {
        "name": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "file_entropy": round(entropy(data), 4),
        "prefix_hex": data[:32].hex(),
    }
    try:
        pe = pefile.PE(data=data, fast_load=False)
        timestamp = datetime.datetime.fromtimestamp(
            pe.FILE_HEADER.TimeDateStamp, datetime.UTC
        ).isoformat()
        result.update(
            {
                "machine": hex(pe.FILE_HEADER.Machine),
                "characteristics": hex(pe.FILE_HEADER.Characteristics),
                "timestamp_utc": timestamp,
                "subsystem": pe.OPTIONAL_HEADER.Subsystem,
                "entrypoint": hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
                "imagebase": hex(pe.OPTIONAL_HEADER.ImageBase),
                "size_of_image": pe.OPTIONAL_HEADER.SizeOfImage,
                "dll_characteristics": hex(pe.OPTIONAL_HEADER.DllCharacteristics),
                "sections": [
                    {
                        "name": decode(section.Name.rstrip(b"\x00")),
                        "virtual_size": section.Misc_VirtualSize,
                        "raw_size": section.SizeOfRawData,
                        "entropy": round(section.get_entropy(), 4),
                    }
                    for section in pe.sections
                ],
                "imports": {
                    decode(entry.dll): [
                        decode(symbol.name) if symbol.name else f"#{symbol.ordinal}"
                        for symbol in entry.imports
                    ]
                    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
                },
                "exports": [
                    decode(symbol.name) if symbol.name else f"#{symbol.ordinal}"
                    for symbol in getattr(
                        getattr(pe, "DIRECTORY_ENTRY_EXPORT", None), "symbols", []
                    )
                ],
                "version_info": version_info(pe),
            }
        )
        overlay_start = pe.get_overlay_data_start_offset()
        if overlay_start is not None:
            overlay = data[overlay_start:]
            result["overlay"] = {
                "offset": overlay_start,
                "bytes": len(overlay),
                "entropy": round(entropy(overlay), 4),
                "sha256": hashlib.sha256(overlay).hexdigest().upper(),
                "prefix_hex": overlay[:32].hex(),
            }
        debug_paths = []
        for debug_entry in getattr(pe, "DIRECTORY_ENTRY_DEBUG", []) or []:
            raw = pe.get_data(debug_entry.struct.AddressOfRawData, debug_entry.struct.SizeOfData)
            match = re.search(rb"[A-Za-z]:\\[^\x00]+\.pdb", raw)
            if match:
                debug_paths.append(match.group().decode("latin1", "replace"))
        result["pdb_paths"] = debug_paths
    except Exception as error:
        result["pe_error"] = repr(error)
    result["interesting_strings"] = interesting_strings(data)
    return result


requested = set(sys.argv[1:])
files = sorted(
    path for path in BASE.iterdir()
    if path.is_file()
    and path.suffix.casefold() in PE_SUFFIXES
    and (not requested or path.name in requested)
)
print(json.dumps([inspect(path) for path in files], ensure_ascii=False, indent=2))
