# Planetlie 바이너리에서 기능 추정에 필요한 문자열만 정적으로 추출하는 도구
import json
import re
import sys
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\Users\PC\Downloads\planetliev1.02\planetlie")
KEYWORDS = (
    "http://",
    "https://",
    "/api/",
    "ffmpeg",
    "nika",
    "hddebug",
    "869f2",
    "igj5c",
    "mxdin",
    "dm.dll",
    "dmreg",
    "maple",
    "lie",
    "telegram",
    "socks",
    "inject",
    "hdq_",
    "botrunmonitor",
    "aion2.exe",
    "\\config\\",
    "\\.\\pipe\\",
    "transparent",
    "yolo",
)


def printable_strings(data: bytes) -> set[str]:
    values = {
        match.decode("latin1", "replace")
        for match in re.findall(rb"[\x20-\x7e]{5,}", data)
    }
    for offset in (0, 1):
        decoded = data[offset:].decode("utf-16le", "ignore")
        values.update(re.findall(r"[\x20-\x7e\u3131-\uD79D]{5,}", decoded))
    return values


def relevant_strings(path: Path) -> list[str]:
    strings = printable_strings(path.read_bytes())
    matches = [
        value.strip()
        for value in strings
        if any(keyword in value.casefold() for keyword in KEYWORDS)
    ]
    return sorted(set(matches), key=lambda value: (value.casefold(), value))[:1000]


requested = sys.argv[1:]
files = [BASE / name for name in requested]
print(
    json.dumps(
        {path.name: relevant_strings(path) for path in files if path.is_file()},
        ensure_ascii=False,
        indent=2,
    )
)
