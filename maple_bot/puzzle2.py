# 받은 SOT 코어를 실제 게임창에서 검증하는 독립 실행 진입점이다.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.puzzle2.runtime import SotLiveRuntime
from core.puzzle2.vendor import DEFAULT_VENDOR_ROOT, VendorLayout


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Puzzle2 V6497 SOT 라이브 검증")
    parser.add_argument("--vendor-root", default=str(DEFAULT_VENDOR_ROOT))
    parser.add_argument("--output-root", default="")
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
