# 투명도형 퍼즐 라이브 캡처 사전점검 결과 생성을 검증한다.

import numpy as np

from core.puzzle.capture_preflight import run_capture_check


def test_capture_check_success_writes_png_and_report(tmp_path):
    frame = np.full((6, 8, 3), 55, dtype=np.uint8)

    result = run_capture_check(output_root=tmp_path, frame_grabber=lambda: frame)

    assert result.ok is True
    assert result.width == 8
    assert result.height == 6
    assert result.image_path is not None
    assert result.image_path.name == "capture_check.png"
    assert result.image_path.stat().st_size > 0
    assert result.report_path.exists()
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "status: ok" in report_text
    assert "frame: 8x6" in report_text


def test_capture_check_failure_writes_report_without_raising(tmp_path):
    def fail_capture():
        raise RuntimeError("screen capture failed")

    result = run_capture_check(output_root=tmp_path, frame_grabber=fail_capture)

    assert result.ok is False
    assert result.image_path is None
    assert result.error == "screen capture failed"
    assert result.report_path.exists()
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "status: failed" in report_text
    assert "screen capture failed" in report_text
