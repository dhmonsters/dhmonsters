# GT 1030에서 CUDA 호환성과 Puzzle2 유사 처리량을 검사하는 실행 진입점이다.
from __future__ import annotations

import ctypes
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from core.puzzle2.cuda_probe import evaluate_probe, run_cuda_probe


def _output_path() -> Path:
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    return root / "gt1030_probe_report.json"


def _show_result(title: str, message: str, *, error: bool = False) -> None:
    flags = 0x10 if error else 0x40
    ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def dialog_enabled(argv: list[str] | None = None) -> bool:
    return "--no-dialog" not in (argv if argv is not None else sys.argv)


def main() -> int:
    report_path = _output_path()
    show_dialog = dialog_enabled()
    payload: dict[str, object]
    exit_code = 1
    try:
        metrics = run_cuda_probe()
        decision = evaluate_probe(metrics)
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": decision.status,
            "reasons": list(decision.reasons),
            "metrics": asdict(metrics),
        }
        exit_code = 0 if decision.status == "PASS" else 2
        message = (
            f"판정: {decision.status}\n\n"
            f"GPU: {metrics.gpu_name}\n"
            f"Compute: sm_{metrics.compute_major}{metrics.compute_minor}\n"
            f"전용 VRAM: {metrics.dedicated_total_mb:.0f} MB\n"
            f"현재 여유: {metrics.dedicated_free_mb:.0f} MB\n"
            f"512 MB 할당: {'성공' if metrics.allocation_512mb else '실패'}\n"
            f"유사 연산: {metrics.equivalent_fps:.1f} FPS\n\n"
            f"보고서: {report_path.name}"
        )
        if show_dialog:
            _show_result("GT 1030 CUDA 검사", message, error=decision.status == "FAIL")
    except Exception as exc:
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "FAIL",
            "reasons": [f"{exc.__class__.__name__}: {exc}"],
            "metrics": {},
        }
        if show_dialog:
            _show_result(
                "GT 1030 CUDA 검사 실패",
                f"CUDA 검사를 완료하지 못했습니다.\n\n{exc.__class__.__name__}: {exc}\n\n"
                f"보고서: {report_path.name}",
                error=True,
            )
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
