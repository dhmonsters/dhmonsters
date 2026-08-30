# Claude 배포본에 외부 작업 환경 DLL이 섞였는지 검사한다.
from __future__ import annotations

import argparse
import re
from pathlib import Path


_FORBIDDEN_ROOT_DLLS = ("icudt78.dll", "icuuc.dll")


def read_pe_imports(path: Path) -> set[str]:
    """PE 파일이 정적으로 가져오는 DLL 이름을 소문자로 반환한다."""
    import pefile

    image = pefile.PE(str(path), fast_load=True)
    try:
        image.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        return {
            entry.dll.decode("ascii", errors="replace").lower()
            for entry in getattr(image, "DIRECTORY_ENTRY_IMPORT", [])
        }
    finally:
        image.close()


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
    if not (bundle_path / "Claude.exe").is_file():
        errors.append("복구 실행기 Claude.exe가 없습니다.")
    if not (bundle_path / "ClaudeApp.exe").is_file():
        errors.append("실제 앱 ClaudeApp.exe가 없습니다.")
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
