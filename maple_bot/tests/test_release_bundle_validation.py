# Claude 배포본에 작업 환경 DLL이 섞이지 않는지 검증한다.
from pathlib import Path


def test_rejects_codex_runtime_sources_and_root_poppler_icu(tmp_path: Path) -> None:
    from release_bundle_validation import validate_release_bundle

    analysis = tmp_path / "Analysis-00.toc"
    analysis.write_text(
        "C:\\\\Users\\\\PC\\\\.cache\\\\codex-runtimes\\\\"
        "codex-primary-runtime\\\\dependencies\\\\native\\\\poppler"
        "\\\\Library\\\\bin\\\\icuuc.dll",
        encoding="utf-8",
    )
    internal = tmp_path / "dist" / "Claude" / "_internal"
    internal.mkdir(parents=True)
    (internal / "icuuc.dll").write_bytes(b"foreign-icu")
    (internal / "icudt78.dll").write_bytes(b"foreign-icu-data")

    errors = validate_release_bundle(analysis, internal.parent)

    assert errors == [
        "PyInstaller 분석 목록에 Codex 작업용 런타임 경로가 포함됐습니다.",
        "배포본 _internal 루트에 금지된 DLL이 있습니다: icudt78.dll, icuuc.dll",
    ]


def test_accepts_bundle_without_foreign_runtime_files(tmp_path: Path) -> None:
    from release_bundle_validation import validate_release_bundle

    analysis = tmp_path / "Analysis-00.toc"
    analysis.write_text("C:\\\\Windows\\\\System32\\\\kernel32.dll", encoding="utf-8")
    bundle = tmp_path / "dist" / "Claude"
    (bundle / "_internal").mkdir(parents=True)

    assert validate_release_bundle(analysis, bundle) == []
