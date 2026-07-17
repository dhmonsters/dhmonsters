# Python 3.13 PyInstaller PYZ에서 자체 모듈의 코드 구조와 상수를 추출하는 도구
import argparse
import dis
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


def describe_code(code):
    children = [item for item in code.co_consts if isinstance(item, types.CodeType)]
    try:
        instructions = [
            {"offset": ins.offset, "op": ins.opname, "arg": ins.argrepr}
            for ins in dis.get_instructions(code)
        ]
        instructions_error = None
    except (IndexError, ValueError) as exc:
        instructions = []
        instructions_error = f"{type(exc).__name__}: {exc}"
    result = {
        "name": code.co_name,
        "qualname": getattr(code, "co_qualname", code.co_name),
        "filename": code.co_filename,
        "first_line": code.co_firstlineno,
        "argcount": code.co_argcount,
        "varnames": list(code.co_varnames),
        "names": list(code.co_names),
        "constants": [safe_constant(item) for item in code.co_consts if not isinstance(item, types.CodeType)],
        "instructions": instructions,
        "children": [describe_code(child) for child in children],
    }
    if instructions_error:
        result["instructions_error"] = instructions_error
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pyz", type=Path)
    parser.add_argument("--module", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    raw = args.pyz.read_bytes()
    if raw[:4] != b"PYZ\0":
        raise ValueError("Not a PyInstaller PYZ archive")
    toc_offset = struct.unpack("!I", raw[8:12])[0]
    toc = dict(marshal.loads(raw[toc_offset:]))
    result = {}
    for module in args.module:
        item_type, position, length = toc[module]
        compressed = raw[position:position + length]
        code = marshal.loads(zlib.decompress(compressed))
        result[module] = {
            "toc_type": item_type,
            "compressed_size": length,
            "code": describe_code(code),
        }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
