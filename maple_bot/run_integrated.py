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

    # 3-1) HP/MP 비율 리더 (A 방식 Detector 재사용) — 물약 판정용. 통합 포팅 때 누락됐던 배선.
    from core.detector import Detector
    _det = Detector(screen, cm)
    def hp_mp_reader():
        return (_det.hp_ratio(), _det.mp_ratio())

    # 4) 런타임 조립
    rt = BotRuntime(screen_capture=capture, input_backend=backend, config=rc,
                    hp_mp_reader=hp_mp_reader)
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
        self._rt.set_running(True)
        self._rt.start_scanners()
        # 진단: 실제로 캡처하는 미니맵 영역(창 보정 반영) — 노란점 인식 안 될 때 확인용
        try:
            rg = self._rt._resolve_region(self._rt._cfg.minimap_region)
            self._log(f"미니맵 캡처영역: {rg} / 캐릭터색: {self._rt._cfg.char_rgb or '기본 노랑'}")
        except Exception:
            pass
        # 층별 반복 사냥 루트는 별도 스레드로(블로킹 사다리 등반 중 메인루프 선점 유지)
        if self._rt.floor_hunt_runner is not None:
            self._rt.floor_hunt_runner.start()
            self._log("▶ 봇 시작 (층별 루트 실행기)")
        else:
            self._log("▶ 봇 시작")
        self._thread = threading.Thread(target=self._loop, daemon=True, name="BotMainLoop")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._rt.set_running(False)
        if self._rt.floor_hunt_runner is not None:
            self._rt.floor_hunt_runner.stop()
        self._rt.stop_scanners()
        # 종료 시 유지 중인 이동키 해제(안 떼면 게임에서 계속 이동) — 백스톱
        try:
            self._rt.humanizer.release_all()
        except Exception:
            pass
        self._log("■ 봇 정지 (입력키 해제됨)")

    def _loop(self):
        """메인 루프: 이벤트 처리 → 모드별 틱(루트 모드면 이동·공격은 루트 스레드 담당)."""
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
    rt.log = shell.append_log          # 봇 동작(블록 실행 등)을 로그창에 표시
    shell.btn_start.clicked.connect(controller.start)
    shell.btn_stop.clicked.connect(controller.stop)

    # 실시간 미니맵 캔버스에 몬스터 점 표시 — 런타임 탐지를 공급자로 연결
    try:
        from core_ui.minimap_canvas import MinimapCanvas
        canvas = shell.findChild(MinimapCanvas)
        if canvas is not None:
            canvas.set_monster_provider(rt.detect_monsters_rel)
    except Exception:
        pass

    shell.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
