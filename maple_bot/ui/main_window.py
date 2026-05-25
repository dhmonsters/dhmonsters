# 메인 윈도우 - 탭 기반 레이아웃과 설정 저장/로드 관리
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar

from core.config_manager import ConfigManager
from core.bot_loop import BotLoop
from core.hotkey_manager import HotkeyManager
from ui.tab_main import TabMain
from ui.tab_hunt import TabHunt
from ui.tab_attack import TabAttack
from ui.tab_recovery import TabRecovery
from ui.tab_position import TabPosition
from ui.tab_coordinate import TabCoordinate
from ui.tab_settings1 import TabSettings1
from ui.tab_settings2 import TabSettings2
from ui.tab_misc import TabMisc
from ui.overlay.debug_overlay import DebugOverlay


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.hotkey_manager = HotkeyManager(self)
        self.setWindowTitle("DHMONSTERS v1.2.1")
        self.setMinimumSize(520, 600)
        self._build_ui()
        self._setup_bot()

    def _build_ui(self):
        tabs = QTabWidget()

        self.tab_main = TabMain(self.config)
        self.tab_hunt = TabHunt(self.config)
        self.tab_settings1 = TabSettings1(self.config)
        self.tab_settings2 = TabSettings2(self.config)

        self.tab_attack = TabAttack(self.config)
        self.tab_recovery = TabRecovery(self.config)
        self.tab_coordinate = TabCoordinate(self.config)
        self.tab_position = TabPosition(self.config)

        # 단축키 매니저 연결 (탭 생성 후 load_from_config 실행된 뒤에 등록)
        self.tab_main.load_from_config()
        self.tab_main.set_hotkey_manager(self.hotkey_manager)
        self.tab_recovery.set_hotkey_manager(self.hotkey_manager)
        self.tab_coordinate.set_hotkey_manager(self.hotkey_manager)
        self.tab_position.set_hotkey_manager(self.hotkey_manager)
        self.tab_settings1.set_hotkey_manager(self.hotkey_manager)
        # 거짓말탐지기 해제 단축키 등록
        solve_key = (self.config.get("settings1", "lie_detector") or {}).get("solve_hotkey", "")
        if solve_key:
            self.hotkey_manager.register("lie_solve", solve_key, self._on_lie_solve)

        # 모든 단축키 등록 완료 후 기타 탭 생성 및 연결
        self.tab_misc = TabMisc(self.config)
        self.tab_misc.set_hotkey_manager(self.hotkey_manager)

        all_tabs = [
            (self.tab_main,           "메인"),
            (self.tab_hunt,           "사냥"),
            (self.tab_attack,         "공격"),
            (self.tab_recovery,       "회복"),
            (self.tab_position,       "위치"),
            (self.tab_coordinate,     "좌표"),
            (self.tab_settings1,      "설정1"),
            (self.tab_settings2,      "설정2"),
            (self.tab_misc,           "기타"),
        ]
        for widget, name in all_tabs:
            tabs.addTab(widget, name)

        self.setCentralWidget(tabs)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("준비")

        # 설정2 탭의 상점/판매 로그를 메인 로그창에도 출력
        self.tab_settings2.set_log_callback(self.tab_main.emit_status)

    def _save_all(self) -> None:
        """모든 탭의 설정을 config에 반영하고 파일에 저장한다."""
        self.tab_main.save_to_config()
        self.tab_hunt.save_to_config()
        self.tab_attack.save_to_config()
        self.tab_recovery.save_to_config()
        self.tab_coordinate.save_to_config()
        self.tab_position.save_to_config()
        self.tab_settings1.save_to_config()
        self.tab_settings2.save_to_config()
        self.config.save()

    def _setup_bot(self):
        """봇 루프를 생성하고 메인/사냥 탭에 연결."""
        self.bot = BotLoop(
            config=self.config,
            on_status=self._on_bot_status,
        )
        self.tab_main.set_bot(self.bot)
        self.tab_main.set_pre_start_callback(self._save_all)
        self.tab_hunt.set_bot(self.bot)
        self.bot.set_on_stop(self.tab_main.on_bot_stopped)

        self.overlay = DebugOverlay(game_state=self.bot.game_state, config=self.config)

    def _on_bot_status(self, msg: str) -> None:
        """봇 스레드 → UI 스레드로 상태 전달."""
        self.tab_main.emit_status(msg)
        self.statusBar().showMessage(msg)

    def _on_lie_solve(self) -> None:
        """거짓말탐지기 해제 단축키 → 별도 스레드에서 실행."""
        import threading
        threading.Thread(target=self.bot._solve_lie_detector_manual, daemon=True).start()

    def closeEvent(self, event):
        if self.bot.is_running:
            self.bot.stop()
        self.hotkey_manager.stop()
        self._save_all()
        event.accept()
