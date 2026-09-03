# 배포 실행파일이 설치 폴더의 구형 모듈을 불러오지 않는지 검증한다.
from pathlib import Path

import run_integrated


def test_frozen_runtime_uses_only_pyinstaller_bundle_for_imports():
    assert hasattr(run_integrated, "_runtime_import_paths")

    install_root = Path("C:/Program Files/Claude")
    bundle_root = install_root / "_internal"

    assert run_integrated._runtime_import_paths(
        install_root,
        frozen=True,
        bundle_root=bundle_root,
    ) == (bundle_root,)


def test_source_runtime_keeps_project_import_paths():
    assert hasattr(run_integrated, "_runtime_import_paths")

    project_root = Path("C:/workspace/maple_bot")

    assert run_integrated._runtime_import_paths(
        project_root,
        frozen=False,
    ) == (project_root, project_root.parent)
