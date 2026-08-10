# 받은 SOT 코어를 실제 게임창에서 검증하는 독립 실행 진입점이다.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.puzzle2.runtime import SotLiveRuntime
from core.puzzle2.vendor import DEFAULT_VENDOR_ROOT, VendorLayout


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Puzzle2 V6497 SOT 라이브 검증")
    parser.add_argument("--vendor-root", default=str(DEFAULT_VENDOR_ROOT))
    parser.add_argument("--output-root", default="")
    parser.add_argument("--runtime-self-check", default="", metavar="REPORT_PATH")
    parser.add_argument("--required-arch", default="sm_61")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    layout = VendorLayout(Path(args.vendor_root))
    missing = layout.validate()
    if missing:
        print("V6497 필수 파일이 없습니다.", file=sys.stderr)
        for path in missing:
            print(path, file=sys.stderr)
        return 2

    if args.runtime_self_check:
        from core.puzzle2.runtime_check import run_runtime_check, save_runtime_report

        report = run_runtime_check(
            vendor_root=layout.root,
            required_arch=args.required_arch,
        )
        report_path = save_runtime_report(report, args.runtime_self_check)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"REPORT={report_path}")
        return 0 if report["status"] == "PASS" else 3

    from PyQt6.QtWidgets import QApplication

    from ui.puzzle2_console import Puzzle2Window

    app = QApplication.instance() or QApplication(sys.argv if argv is None else ["puzzle2.py", *argv])
    app.setStyle("Fusion")
    runtime = SotLiveRuntime(
        backend_loader=layout.load_backend,
        output_root=args.output_root or None,
    )
    window = Puzzle2Window(runtime=runtime)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
