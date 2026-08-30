# Claude 배포본에 외부 작업 환경 DLL이 섞였는지 검사한다.
from __future__ import annotations

import argparse
import re
from pathlib import Path


_FORBIDDEN_ROOT_DLLS = ("icudt78.dll", "icuuc.dll")


def validate_release_bundle(analysis_path: Path, bundle_path: Path) -> list[str]:
    errors: list[str] = []
    analysis_text = analysis_path.read_text(encoding="utf-8", errors="replace")
    if re.search(
        r"[\\/]+\.cache[\\/]+codex-runtimes[\\/]+", analysis_text.lower()
    ):
        errors.append("PyInstaller 분석 목록에 Codex 작업용 런타임 경로가 포함됐습니다.")

    internal = bundle_path / "_internal"
    forbidden = sorted(
        name for name in _FORBIDDEN_ROOT_DLLS if (internal / name).is_file()
    )
    if forbidden:
        errors.append(
            "배포본 _internal 루트에 금지된 DLL이 있습니다: "
            + ", ".join(forbidden)
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    errors = validate_release_bundle(args.analysis, args.bundle)
    for error in errors:
        print(f"[release validation error] {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
