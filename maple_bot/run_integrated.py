# 통합 봇 진입점 — 신규 8모듈(M1~M10)을 실제로 켜는 실행 경로
# 실행: py -3.14 run_integrated.py
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build_runtime():
    """ConfigManager → 어댑터 → 실 캡처/백엔드 주입 → BotRuntime 조립.
    반환: (runtime, RuntimeConfig, ConfigManager)."""
    from core.screen_reader import ScreenReader
    from core.config_manager import ConfigManager
    from core.humanize.backend import select_backend
    from core.config_adapter import to_runtime_config
    from core.runtime import BotRuntime

    # 1) 설정 로드 (ConfigManager — UI 편집/저장과 공유)
    cm = ConfigManager()
    rc = to_runtime_config(cm._data)
    rc.junk_config = cm          # 잡템 판매는 ConfigManager get 인터페이스 사용

    # 2) 실제 화면 캡처 (mss 기반 ScreenReader 재사용)
    screen = ScreenReader()
    def capture(region=None):
        return screen.capture(region)

    # 3) 입력 백엔드 자동선택 (Interception 우선, SendInput 폴백)
    backend = select_backend()
    print(f"[입력] 백엔드: {backend.name}")

    # 4) 런타임 조립
    rt = BotRuntime(screen_capture=capture, input_backend=backend, config=rc)
    return rt, rc, cm


class BotController:
    """UI 시작/정지 버튼 ↔ BotRuntime 메인루프 연결."""

    def __init__(self, runtime, log_fn=print):
        self._rt = runtime
        self._log = log_fn
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._rt.start_scanners()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="BotMainLoop")
        self._thread.start()
        self._log("▶ 봇 시작")

    def stop(self):
        self._stop.set()
        self._rt.stop_scanners()
        self._log("■ 봇 정지")

    def _loop(self):
        """메인 루프: 이벤트 처리 → 모드별 틱."""
        while not self._stop.is_set():
            try:
                self._rt.orchestrator.process_pending()
                if self._rt.orchestrator.mode == "hunting":
                    self._rt.hunting_tick()
                elif self._rt.orchestrator.mode == "safety":
                    self._rt.safety_tick()
            except Exception as e:
                self._log(f"[오류] {e}")
            time.sleep(0.03)


def main():
    from PyQt6.QtWidgets import QApplication
    from core_ui.shell import MainShell
    from core_ui.theme import apply_font

    app = QApplication(sys.argv)
    fam = apply_font(app)            # DESIGN.md Inter + 자간 -0.16px
    print(f"[폰트] {fam} 적용")

    rt, rc, cm = build_runtime()
    shell = MainShell(config=cm)     # 실제 설정 페이지 바인딩
    shell.append_log(f"설정 로드: 미니맵 {rc.minimap_region}, 층 {len(rc.floors)}개, 버프 {len(rc.buffs)}개")

    controller = BotController(rt, log_fn=shell.append_log)
    shell.btn_start.clicked.connect(controller.start)
    shell.btn_stop.clicked.connect(controller.stop)

    shell.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
