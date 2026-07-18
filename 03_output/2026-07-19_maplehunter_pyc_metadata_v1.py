# Python PYC 코드 객체를 실행하지 않고 구조화하는 안전한 메타데이터 추출기
import hashlib
import marshal
import types
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


def extract_pyc(path):
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) < 17:
        raise ValueError("PYC file is too short")
    code = marshal.loads(raw[16:])
    if not isinstance(code, types.CodeType):
        raise ValueError("PYC payload is not a code object")
    return {
        "path": str(path),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "code": describe_code_metadata(code),
    }
