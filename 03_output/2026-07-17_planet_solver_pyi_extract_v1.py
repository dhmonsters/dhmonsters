# PyInstaller 패키지에서 지정한 항목만 안전한 출력 폴더로 추출하는 도구
import argparse
import json
import re
import zlib
from pathlib import Path, PurePosixPath


def safe_relative(name):
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive path: {name}")
    return Path(*path.parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--exe-name", required=True)
    parser.add_argument("--match", action="append", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    record = next(item for item in metadata if Path(item["path"]).name == args.exe_name)
    package = record["pe"]["pyinstaller"]
    patterns = [re.compile(pattern, re.IGNORECASE) for pattern in args.match]
    raw = Path(record["path"]).read_bytes()
    extracted = []

    for entry in package["toc_entries"]:
        name = entry["name"]
        if not any(pattern.search(name) for pattern in patterns):
            continue
        start = package["package_start"] + entry["position"]
        end = start + entry["compressed_size"]
        payload = raw[start:end]
        if entry["compressed"]:
            payload = zlib.decompress(payload)
        if len(payload) != entry["uncompressed_size"]:
            raise ValueError(f"Size mismatch: {name}")
        destination = args.output_dir / args.exe_name / safe_relative(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        extracted.append({"name": name, "path": str(destination), "size": len(payload)})

    manifest = args.output_dir / f"{args.exe_name}_extracted.json"
    manifest.write_text(json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(extracted), "manifest": str(manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
