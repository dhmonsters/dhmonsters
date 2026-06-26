# 투명도형 퍼즐 실행용 배치 런처 구성을 검증한다.
from pathlib import Path


def test_run_puzzle_test_batch_exists_and_invokes_transparent_test():
    launcher = Path(__file__).resolve().parents[1] / "run_puzzle_test.bat"

    assert launcher.exists()

    text = launcher.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("REM ")
    assert "Python314\\python.exe" in text
    assert ".codex_pydeps" in text
    assert "puzzle.py" in text
    assert "--transparent-test" in text
    assert "--max-frames" in text
    assert "%MAX_FRAMES%" in text
