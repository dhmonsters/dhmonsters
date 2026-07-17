# Planetlie 실행 파일과 DLL의 PE 구조를 정적으로 조사하는 도구
import datetime
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import pefile


BASE = Path(r"C:\Users\PC\Downloads\planetliev1.02\planetlie")
EXPORT_CACHE: dict[str, dict[int, str]] = {}


def decode_name(value: bytes) -> str:
    return value.decode("latin1", "replace")


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def local_export_map(dll_name: str) -> dict[int, str]:
    key = dll_name.lower()
    if key in EXPORT_CACHE:
        return EXPORT_CACHE[key]
    candidate = BASE / dll_name
    if not candidate.exists():
        EXPORT_CACHE[key] = {}
        return {}
    dll = pefile.PE(str(candidate), fast_load=True)
    dll.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]]
    )
    table = getattr(dll, "DIRECTORY_ENTRY_EXPORT", None)
    EXPORT_CACHE[key] = {
        symbol.ordinal: decode_name(symbol.name)
        for symbol in getattr(table, "symbols", [])
        if symbol.name
    }
    return EXPORT_CACHE[key]


def inspect_pe(path: Path) -> dict:
    result = {"name": path.name}
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"],
            ]
        )
        result.update(
            {
                "machine": hex(pe.FILE_HEADER.Machine),
                "timestamp_utc": datetime.datetime.fromtimestamp(
                    pe.FILE_HEADER.TimeDateStamp, datetime.UTC
                ).isoformat(),
                "subsystem": pe.OPTIONAL_HEADER.Subsystem,
                "entrypoint": hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
                "imagebase": hex(pe.OPTIONAL_HEADER.ImageBase),
                "sections": [
                    decode_name(section.Name.rstrip(b"\x00")) for section in pe.sections
                ],
                "imports": [
                    decode_name(entry.dll)
                    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
                ],
            }
        )
        if path.name in {
            "nika.exe",
            "HDDebug.dll",
            "869f2.exe",
            "igj5c.dll",
            "mxdin.dll",
            "dmreg.dll",
        }:
            result["import_symbols"] = {
                decode_name(entry.dll): [
                    decode_name(symbol.name)
                    if symbol.name
                    else local_export_map(decode_name(entry.dll)).get(
                        symbol.ordinal, f"#{symbol.ordinal}"
                    )
                    for symbol in entry.imports
                ]
                for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
            }
        export_table = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
        result["exports"] = [
            decode_name(symbol.name) if symbol.name else f"#{symbol.ordinal}"
            for symbol in getattr(export_table, "symbols", [])
        ][:200]
        overlay_start = pe.get_overlay_data_start_offset()
        result["overlay_bytes"] = (
            0 if overlay_start is None else path.stat().st_size - overlay_start
        )
        if overlay_start is not None:
            overlay = path.read_bytes()[overlay_start:]
            result["overlay_sha256"] = hashlib.sha256(overlay).hexdigest()
            result["overlay_entropy"] = round(entropy(overlay), 4)
            result["overlay_prefix_hex"] = overlay[:32].hex()
    except Exception as error:
        result["error"] = repr(error)
    return result


requested_names = set(sys.argv[1:])
files = sorted(
    path
    for path in [*BASE.glob("*.exe"), *BASE.glob("*.dll")]
    if not requested_names or path.name in requested_names
)
print(json.dumps([inspect_pe(path) for path in files], ensure_ascii=False, indent=2))
