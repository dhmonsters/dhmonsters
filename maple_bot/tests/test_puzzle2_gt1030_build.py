# Puzzle2 GT1030 전용 배포 설정이 기존 RTX 패키지와 분리되는지 검증한다.
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_gt1030_spec_uses_separate_distribution_name() -> None:
    text = (PROJECT_ROOT / "puzzle2_gt1030_portable.spec").read_text(
        encoding="utf-8"
    )

    assert 'name="Puzzle2_GT1030"' in text
    assert 'name="puzzle2_gt1030"' in text
    assert "triangle_guard_v6496.pt" in text
    assert 'excludes=["tkinter", "pytest"]' in text


def test_gt1030_build_runs_packaged_sm61_model_check() -> None:
    text = (PROJECT_ROOT / "build_puzzle2_gt1030_portable.ps1").read_text(
        encoding="utf-8"
    )

    assert "--runtime-self-check" in text
    assert "--required-arch" in text
    assert "sm_61" in text
    assert "2026-08-10_puzzle2_gt1030_portable_v1.zip" in text
    assert "2026-08-10_puzzle2_portable_v1.zip" not in text
