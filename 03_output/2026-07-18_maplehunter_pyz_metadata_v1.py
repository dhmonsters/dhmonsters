# Python 3.13 PYZ 코드 객체를 명령 역어셈블 없이 안전하게 구조화하는 도구
import argparse
import json
import marshal
import struct
import types
import zlib
from pathlib import Path


def safe_constant(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"bytes_length": len(value), "hex_prefix": value[:24].hex()}
    if isinstance(value, tuple):
        return [safe_constant(item) for item in value if not isinstance(item, types.CodeType)]
    return repr(value)[:500]


def describe_code_metadata(code):
    children = [item for item in code.co_consts if isinstance(item, types.CodeType)]
    return {
        "name": code.co_name,
        "qualname": getattr(code, "co_qualname", code.co_name),
        "filename": code.co_filename,
        "first_line": code.co_firstlineno,
        "argcount": code.co_argcount,
        "varnames": list(code.co_varnames),
        "names": list(code.co_names),
        "constants": [
            safe_constant(item)
            for item in code.co_consts
            if not isinstance(item, types.CodeType)
        ],
        "children": [describe_code_metadata(child) for child in children],
    }


def extract_modules(pyz_path, module_names):
    raw = pyz_path.read_bytes()
    if raw[:4] != b"PYZ\0":
        raise ValueError("Not a PyInstaller PYZ archive")
    toc_offset = struct.unpack("!I", raw[8:12])[0]
    toc = dict(marshal.loads(raw[toc_offset:]))
    result = {}
    for module_name in module_names:
        item_type, position, length = toc[module_name]
        code = marshal.loads(zlib.decompress(raw[position:position + length]))
        result[module_name] = {
            "toc_type": item_type,
            "compressed_size": length,
            "code": describe_code_metadata(code),
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pyz", type=Path)
    parser.add_argument("--module", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = extract_modules(args.pyz, args.module)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
