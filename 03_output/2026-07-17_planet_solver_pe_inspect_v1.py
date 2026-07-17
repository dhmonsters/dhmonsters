# Windows PE 실행 파일의 구조와 PyInstaller 패키징 흔적을 읽기 전용으로 조사하는 도구
import argparse
import hashlib
import json
import math
import mmap
import re
import struct
from pathlib import Path


PYI_MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"


def entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts if count)


def read_c_string(data, offset, limit=512):
    if offset is None or offset < 0 or offset >= len(data):
        return None
    end = data.find(b"\0", offset, min(len(data), offset + limit))
    if end < 0:
        end = min(len(data), offset + limit)
    return data[offset:end].decode("ascii", errors="replace")


def parse_pe(path):
    raw = path.read_bytes()
    if raw[:2] != b"MZ":
        return {"error": "Not a PE file"}
    pe_offset = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[pe_offset:pe_offset + 4] != b"PE\0\0":
        return {"error": "Invalid PE signature"}

    coff = struct.unpack_from("<HHIIIHH", raw, pe_offset + 4)
    machine, section_count, timestamp, _, _, optional_size, characteristics = coff
    optional_offset = pe_offset + 24
    magic = struct.unpack_from("<H", raw, optional_offset)[0]
    is_pe64 = magic == 0x20B
    entry_rva = struct.unpack_from("<I", raw, optional_offset + 16)[0]
    image_base = struct.unpack_from("<Q" if is_pe64 else "<I", raw, optional_offset + (24 if is_pe64 else 28))[0]
    size_of_image = struct.unpack_from("<I", raw, optional_offset + 56)[0]
    subsystem = struct.unpack_from("<H", raw, optional_offset + 68)[0]
    data_dir_offset = optional_offset + (112 if is_pe64 else 96)
    import_rva, import_size = struct.unpack_from("<II", raw, data_dir_offset + 8)

    sections = []
    section_offset = optional_offset + optional_size
    for index in range(section_count):
        base = section_offset + index * 40
        name = raw[base:base + 8].rstrip(b"\0").decode("ascii", errors="replace")
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", raw, base + 8)
        section_characteristics = struct.unpack_from("<I", raw, base + 36)[0]
        chunk = raw[raw_pointer:raw_pointer + raw_size]
        sections.append({
            "name": name,
            "virtual_size": virtual_size,
            "virtual_address": virtual_address,
            "raw_size": raw_size,
            "raw_pointer": raw_pointer,
            "entropy": round(entropy(chunk), 4),
            "characteristics": f"0x{section_characteristics:08X}",
        })

    def rva_to_offset(rva):
        for section in sections:
            start = section["virtual_address"]
            span = max(section["virtual_size"], section["raw_size"])
            if start <= rva < start + span:
                return section["raw_pointer"] + (rva - start)
        return rva if rva < len(raw) else None

    imports = []
    import_offset = rva_to_offset(import_rva)
    if import_offset is not None and import_rva:
        for index in range(4096):
            base = import_offset + index * 20
            if base + 20 > len(raw):
                break
            descriptor = struct.unpack_from("<IIIII", raw, base)
            if descriptor == (0, 0, 0, 0, 0):
                break
            name_offset = rva_to_offset(descriptor[3])
            name = read_c_string(raw, name_offset)
            if name:
                imports.append(name)

    overlay_start = max((section["raw_pointer"] + section["raw_size"] for section in sections), default=0)
    overlay = raw[overlay_start:]
    pyi = parse_pyinstaller(raw)
    return {
        "machine": f"0x{machine:04X}",
        "format": "PE32+" if is_pe64 else "PE32",
        "section_count": section_count,
        "timestamp_raw": timestamp,
        "characteristics": f"0x{characteristics:04X}",
        "entry_rva": f"0x{entry_rva:X}",
        "image_base": f"0x{image_base:X}",
        "size_of_image": size_of_image,
        "subsystem": subsystem,
        "import_directory_size": import_size,
        "imports": imports,
        "sections": sections,
        "overlay_start": overlay_start,
        "overlay_size": len(overlay),
        "overlay_entropy": round(entropy(overlay), 4),
        "pyinstaller": pyi,
    }


def parse_pyinstaller(raw):
    cookie_pos = raw.rfind(PYI_MAGIC)
    if cookie_pos < 0:
        return {"detected": False}
    candidates = []
    for cookie_size, fmt in ((88, "!8sIIII64s"), (24, "!8sIIII")):
        if cookie_pos + cookie_size > len(raw):
            continue
        values = struct.unpack_from(fmt, raw, cookie_pos)
        package_length, toc_offset, toc_length, python_version = values[1:5]
        package_start = cookie_pos + cookie_size - package_length
        toc_start = package_start + toc_offset
        toc_end = toc_start + toc_length
        if package_start >= 0 and toc_start >= package_start and toc_end <= cookie_pos:
            python_library = ""
            if cookie_size == 88:
                python_library = values[5].split(b"\0", 1)[0].decode("ascii", errors="replace")
            names = []
            cursor = toc_start
            while cursor + 18 <= toc_end and len(names) < 20000:
                entry_length = struct.unpack_from("!i", raw, cursor)[0]
                if entry_length < 18 or cursor + entry_length > toc_end:
                    break
                _, position, compressed_size, uncompressed_size, compressed, typecode = struct.unpack_from("!iIIIBc", raw, cursor)
                name_bytes = raw[cursor + 18:cursor + entry_length].split(b"\0", 1)[0]
                name = name_bytes.decode("utf-8", errors="replace")
                names.append({
                    "name": name,
                    "type": typecode.decode("ascii", errors="replace"),
                    "compressed": bool(compressed),
                    "compressed_size": compressed_size,
                    "uncompressed_size": uncompressed_size,
                    "position": position,
                })
                cursor += entry_length
            candidates.append({
                "detected": True,
                "cookie_size": cookie_size,
                "cookie_offset": cookie_pos,
                "package_start": package_start,
                "package_length": package_length,
                "toc_offset": toc_offset,
                "toc_length": toc_length,
                "python_version_raw": python_version,
                "python_library": python_library,
                "toc_entry_count": len(names),
                "toc_entries": names,
            })
    return candidates[0] if candidates else {"detected": True, "cookie_offset": cookie_pos, "parse_error": "Cookie fields were not plausible"}


def extract_indicators(path):
    keywords = re.compile(
        r"(?i)(pyinstaller|python3?\d*\.dll|opencv|cv2|numpy|pillow|torch|onnx|tensorflow|"
        r"pyautogui|pynput|keyboard|mouse|win32api|win32gui|mss|dxcam|d3dshot|selenium|"
        r"requests|urllib|websocket|socket|http[s]?://|discord|telegram|firebase|supabase|"
        r"driver|service|\.sys\b|interception|vigem|vgamepad|sendinput|maplestory|nexon|"
        r"minimap|hsv|captcha|recording|ffmpeg|vlc|mediafoundation|sqlite|\.json\b|\.yaml\b|\.ini\b)")
    found = []
    seen = set()
    with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for match in re.finditer(rb"[ -~]{5,240}", data):
            value = match.group().decode("ascii", errors="ignore")
            if keywords.search(value):
                normalized = value.strip()
                if normalized not in seen:
                    seen.add(normalized)
                    found.append({"offset": match.start(), "text": normalized})
                    if len(found) >= 3000:
                        break
    return found


def inspect(path):
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256.hexdigest().upper(),
        "pe": parse_pe(path),
        "string_indicators": extract_indicators(path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = [inspect(path) for path in args.paths]
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
