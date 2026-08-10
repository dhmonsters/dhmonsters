# 로컬 설정에서 민감정보를 제거한 배포용 config.json을 생성한다.
from __future__ import annotations

import json
import sys
from pathlib import Path


SENSITIVE_KEYS = {"tg_token", "tg_chat_id", "password1", "password2"}


def sanitize(value, project_root: Path):
    if isinstance(value, dict):
        return {
            key: "" if key in SENSITIVE_KEYS else sanitize(item, project_root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item, project_root) for item in value]
    if isinstance(value, str) and Path(value).is_absolute():
        try:
            return Path(value).resolve().relative_to(project_root).as_posix()
        except ValueError:
            return ""
    return value


def build_release_config(source: str | Path, destination: str | Path) -> None:
    source_path = Path(source)
    destination_path = Path(destination)
    data = json.loads(source_path.read_text(encoding="utf-8-sig"))
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        json.dumps(sanitize(data, source_path.resolve().parent), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: build_release_config.py SOURCE DESTINATION")
        return 2
    build_release_config(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
