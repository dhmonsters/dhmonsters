# 최신 Claude 통합 런타임 진입점. core_ui 기반 UI와 BotRuntime을 연결한다.`r`n# 실행 방법: py -3.14 run_integrated.py`r`nfrom __future__ import annotations

import json
import faulthandler
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _extra_path in (ROOT, ROOT / "_internal", ROOT.parent):
    _path_text = str(_extra_path)
    if _extra_path.exists() and _path_text not in sys.path:
        sys.path.insert(0, _path_text)
_CRASH_LOG_HANDLE = None


def _load_core_runtime_attr(name: str):
    try:
        import core.runtime as runtime_module
        return getattr(runtime_module, name)
    except ModuleNotFoundError:
        import importlib.util

        candidates = [
            ROOT / "core" / "runtime.py",
            ROOT / "_internal" / "core" / "runtime.py",
        ]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "core" / "runtime.py")

        for path in candidates:
            if not path.exists():
                continue
            spec = importlib.util.spec_from_file_location("core.runtime", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["core.runtime"] = module
                spec.loader.exec_module(module)
                return getattr(module, name)
        raise


def _write_runtime_log(kind: str, message: str) -> None:
    """런타임 시작과 예외를 파일 로그로 기록한다."""
    path = ROOT / "logs" / "claude_runtime.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {kind}\n")
            log.write(message.rstrip() + "\n")
    except Exception:
        pass


def _install_runtime_logging() -> None:
    """프로그램 시작 단계에서 크래시 로그와 예외 훅을 설치한다."""
    global _CRASH_LOG_HANDLE
    path = ROOT / "logs" / "claude_runtime.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _CRASH_LOG_HANDLE = path.open("a", encoding="utf-8")
        faulthandler.enable(file=_CRASH_LOG_HANDLE, all_threads=True)
    except Exception:
        _CRASH_LOG_HANDLE = None

    def handle_exception(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _write_runtime_log("UNHANDLED EXCEPTION", text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle_exception

    if hasattr(threading, "excepthook"):
        def handle_thread_exception(args):
            text = "".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback))
            _write_runtime_log(
                f"THREAD EXCEPTION: {args.thread.name if args.thread else 'unknown'}",
                text,
            )
            threading.__excepthook__(args)
        threading.excepthook = handle_thread_exception

    _write_runtime_log("START", f"pid={__import__('os').getpid()}")


def build_runtime():
    _write_runtime_log("BOOT", "build_runtime: start")
    """ConfigManager ?????????????????됰Ŧ?????????쇰뮛??????????????袁⑸즴筌?씛彛???돗????????????????袁⑸즴筌??????BotRuntime ?????????????
    ??????袁⑸즴筌?씛彛???돗??????? (runtime, RuntimeConfig, ConfigManager)."""
    from core.screen_reader import ScreenReader
    from core.config_manager import ConfigManager
    from core.humanize.backend import select_backend
    from core.config_adapter import to_runtime_config
    BotRuntime = _load_core_runtime_attr("BotRuntime")

    # 1) ???????嚥???癲??????????????影??젘??(ConfigManager ??UI ?????釉먮폁???????????썹땟戮녹??諭???????????거????????????????源낆┸???)
    cm = ConfigManager()
    _write_runtime_log("BOOT", "build_runtime: config loaded")
    rc = to_runtime_config(cm._data)
    _write_runtime_log("BOOT", "build_runtime: runtime config converted")
    rc.junk_config = cm          # ?????????⑤즾??????????ConfigManager get ?????釉먮폁??????饔낅떽???????꾩렯???????????쇰뮛?????????????

    # 2) ???????嚥???癲??關?쒎첎???????????????????됰Ŧ?????????쇰뮛????????(mss ???????????????ScreenReader ?????
    screen = ScreenReader()
    def capture(region=None):
        return screen.capture(region)

    # 3) ???????????대첐????????袁⑸즴筌?씛彛???돗????????????????????????????(Interception ?????????, SendInput ?????
    backend = select_backend()
    print(f"[input] backend selected: {backend.name}")

    # 3-1) HP/MP ?????????????ル탛?????怨쀫엥????(A ??????袁⑸즴筌?씛彛????얜궙??뷀떐?됯퍓堉??Detector ????? ???????????????????? ???? ?????????????ш끽維뽳쭩?뱀땡???얩맪??傭?끆????嶺????????????袁⑸즴筌?씛彛???돗?????????????????
    from core.detector import Detector
    _det = Detector(screen, cm)
    def hp_mp_reader():
        return _det.hp_mp_ratios()

    # 4) ??????????????????
    rt = BotRuntime(screen_capture=capture, input_backend=backend, config=rc,
                    hp_mp_reader=hp_mp_reader)
    _write_runtime_log("BOOT", "build_runtime: runtime created")
    return rt, rc, cm


def bind_world_editor(shell, runtime):
    """미니맵 편집 UI와 런타임 상태 제공자를 연결한다."""
    from PyQt6.QtWidgets import QWidget
    from core_ui.world_map_editor import WorldMapEditor
    from core_ui.minimap_canvas import RouteCanvas

    route_canvas = shell.findChild(RouteCanvas)
    if route_canvas is not None:
        route_canvas.set_character_provider(runtime.char_scanner.position)
        route_canvas.set_ladder_state_provider(runtime.ladder_debug_state)
    current_position_checker = shell.findChild(QWidget, "currentPositionChecker")
    if (
        current_position_checker is not None
        and hasattr(current_position_checker, "set_character_provider")
    ):
        current_position_checker.set_character_provider(
            runtime.char_scanner.detect_position_once,
            route_canvas.minimap_size if route_canvas is not None else None,
        )

    editor = shell.findChild(WorldMapEditor, "worldMapEditor")
    if editor is None:
        return None
    editor.destination_requested.connect(runtime.navigate_world_to)
    editor.route_start_requested.connect(runtime.start_world_route)
    editor.set_runtime_state_provider(
        position_fn=runtime.world_position,
        tracking_state_fn=runtime.world_tracking_state,
        viewport_fn=runtime.world_viewport,
    )
    return editor


def _start_update_check(parent_window) -> None:
    from PyQt6.QtCore import QObject, pyqtSignal

    class _UpdateNotifier(QObject):
        update_available = pyqtSignal(dict)

    notifier = _UpdateNotifier(parent_window)
    notifier.update_available.connect(
        lambda info: _show_update_dialog(info, parent_window)
    )

    def worker():
        try:
            from core.updater import check_for_update
            info = check_for_update()
            if info:
                notifier.update_available.emit(info)
        except Exception as exc:
            try:
                parent_window.append_log(f"update check failed: {exc}", "system")
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True, name="UpdateCheck").start()


def _show_update_dialog(info: dict, parent_window) -> None:
    from ui.dialog_update import UpdateDialog

    dialog = UpdateDialog(info, parent=parent_window)
    dialog.exec()

def _run_preflight_update_check() -> None:
    """본체 UI 생성 전 업데이트가 있으면 먼저 안내한다."""
    try:
        from core.updater import check_for_update
        info = check_for_update()
        if info:
            from ui.dialog_update import UpdateDialog
            dialog = UpdateDialog(info, parent=None)
            dialog.exec()
    except Exception:
        pass


def _ensure_license_gate() -> bool:
    """라이선스가 유효한지 확인하고 필요하면 인증 창을 띄운다."""
    try:
        from core.hw_fingerprint import get_hwid
        from core import license_manager
        hwid = get_hwid()
        license_manager.check(hwid)
        return True
    except Exception:
        try:
            from core.hw_fingerprint import get_hwid
            from ui.dialog_license import LicenseDialog
            dialog = LicenseDialog(get_hwid(), parent=None)
            return bool(dialog.exec())
        except Exception:
            return False

class BotController:
    """UI start/stop buttons connected to BotRuntime worker loops."""

    def __init__(self, runtime, log_fn=print):
        self._rt = runtime
        self._log = log_fn
        self._thread: threading.Thread | None = None
        self._movement_thread: threading.Thread | None = None
        self._attack_thread: threading.Thread | None = None
        self._support_thread: threading.Thread | None = None
        self._pickup_thread: threading.Thread | None = None
        self._stop = threading.Event()
        from core import license_manager
        license_manager.register_safe_stop(self._safe_stop)

    def _restart_char_scanner(self) -> bool:
        if self._rt.char_scanner.is_running():
            return False
        self._rt.char_scanner.start(self._rt.event_queue)
        return self._rt.char_scanner.is_running()

    def _safe_stop(self, reason: str) -> None:
        self._stop.set()
        self._rt.set_running(False)
        try:
            self._rt.release_pickup_key()
            self._rt.humanizer.release_all()
        except Exception as exc:
            self._log(f"safe-stop input release error: {exc}", "system")
        if self._rt.floor_hunt_runner is not None:
            self._rt.floor_hunt_runner.stop()
        self._log(f"bot safe stop completed: {reason}", "system")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        game_title = str(getattr(self._rt._cfg, "game_window_title", "") or "").strip()
        if game_title:
            from core.input_controller import InputController
            focused = InputController(game_title).focus_game_window()
            self._log(f"game window focus: {'ok' if focused else 'fail'} ({game_title})", "system")
        else:
            self._log("game window title is not configured", "system")
        self._stop.clear()
        self._rt.set_running(True)
        self._rt.start_scanners()
        try:
            rg = self._rt._resolve_region(self._rt._cfg.minimap_region)
            self._log(f"minimap region: {rg} / character color: {self._rt._cfg.char_rgb or 'default yellow'}", "system")
        except Exception:
            pass
        if self._rt.floor_hunt_runner is not None:
            self._rt.floor_hunt_runner.start()
            self._log("bot start (floor route runner)", "system")
        else:
            self._log("bot start", "system")
        self._thread = threading.Thread(target=self._loop, daemon=True, name="BotMainLoop")
        self._movement_thread = threading.Thread(target=self._movement_loop, daemon=True, name="BotMovementLoop")
        self._attack_thread = threading.Thread(target=self._attack_loop, daemon=True, name="BotAttackLoop")
        self._support_thread = threading.Thread(target=self._support_loop, daemon=True, name="BotSupportLoop")
        self._pickup_thread = threading.Thread(target=self._pickup_loop, daemon=True, name="BotPickupLoop")
        self._thread.start()
        self._movement_thread.start()
        self._attack_thread.start()
        self._support_thread.start()
        self._pickup_thread.start()

    def stop(self):
        self._stop.set()
        self._rt.stop_junk_sell()
        self._rt.set_running(False)
        self._rt.release_pickup_key()
        if self._rt.floor_hunt_runner is not None:
            self._rt.floor_hunt_runner.stop()
        self._rt.stop_scanners()
        for worker in (
            self._movement_thread, self._attack_thread,
            self._support_thread, self._pickup_thread, self._thread,
        ):
            if worker and worker.is_alive() and worker is not threading.current_thread():
                worker.join(timeout=1.5)
        try:
            self._rt.humanizer.release_all()
        except Exception:
            pass
        self._log("bot stop (input released)", "system")

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._rt.orchestrator.process_pending()
                if self._rt.orchestrator.mode == "hunting":
                    self._rt.monitor_tick()
                else:
                    self._rt.safety_tick()
            except Exception as e:
                self._log(f"[error] {e}", "system")
            time.sleep(0.03)

    def _movement_loop(self):
        while not self._stop.is_set():
            try:
                self._rt.movement_tick()
            except Exception as e:
                self._log(f"[movement error] {e}", "move")
                self._rt.humanizer.release_dir()
                self._stop.wait(0.2)

    def _attack_loop(self):
        while not self._stop.is_set():
            try:
                self._rt.attack_tick()
            except Exception as e:
                self._log(f"[attack error] {e}", "attack")
            self._stop.wait(0.03)

    def _support_loop(self):
        while not self._stop.is_set():
            try:
                self._rt.support_tick()
            except Exception as e:
                self._log(f"[support error] {e}", "support")
            self._stop.wait(0.03)

    def _pickup_loop(self):
        while not self._stop.is_set():
            try:
                self._rt.pickup_tick()
            except Exception as e:
                self._log(f"[pickup error] {e}", "pickup")
            self._stop.wait(0.03)


def main():
    _install_runtime_logging()
    from core.admin_util import ensure_admin
    _write_runtime_log("BOOT", "main: before ensure_admin")
    ensure_admin()
    _write_runtime_log("BOOT", "main: after ensure_admin")

    from PyQt6.QtWidgets import QApplication
    from core_ui.shell import MainShell
    from core_ui.theme import apply_font

    app = QApplication(sys.argv)
    fam = apply_font(app)
    print(f"[font] {fam} applied")

    if not _ensure_license_gate():
        _write_runtime_log("LICENSE", "license gate rejected")
        sys.exit(1)
    _write_runtime_log("LICENSE", "license gate accepted")

    rt, rc, cm = build_runtime()
    _write_runtime_log("BOOT", "main: runtime ready")
    shell = MainShell(config=cm)
    _write_runtime_log("BOOT", "main: shell created")
    bind_world_editor(shell, rt)
    _write_runtime_log("BOOT", "main: world editor bound")
    backend = getattr(getattr(rt, "humanizer", None), "_backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))
    if backend_name == "interception":
        shell.append_log("Interception driver: loaded", "system")
    else:
        shell.append_log(f"Interception driver: load failed ({backend_name} fallback)", "system")
    shell.append_log(f"config loaded: minimap={rc.minimap_region}, floors={len(rc.floors)}, buffs={len(rc.buffs)}", "system")

    controller = BotController(rt, log_fn=shell.append_log)
    rt.log = shell.append_log

    from PyQt6.QtWidgets import QPushButton
    sell_btn = QPushButton("Auto Sell")
    sell_btn.setObjectName("navtab")
    sell_btn.setMinimumWidth(82)
    sell_stop_btn = QPushButton("Stop Sell")
    sell_stop_btn.setObjectName("navtab")
    sell_stop_btn.setMinimumWidth(82)
    try:
        shell.btn_start.parentWidget().layout().insertWidget(2, sell_btn)
        shell.btn_start.parentWidget().layout().insertWidget(3, sell_stop_btn)
    except Exception:
        pass

    def safe_start():
        try:
            from core.config_adapter import to_runtime_config
            from core.acting.attack_sequence import AttackSequenceRunner
            fresh = to_runtime_config(cm._data)
            rt.reload_monster_templates(fresh)
            rt.reload_lie_scanner(fresh)
            rt.reload_floor_hunt_runner(fresh)
            rt._cfg.attack_key = fresh.attack_key
            rt._cfg.attack_sequences = fresh.attack_sequences
            rt.attack_sequence_runner = AttackSequenceRunner(
                fresh.attack_sequences,
                lambda key, hold: rt.combat.attack(
                    key, mode="duration", hold=hold or rt._attack_hold(),
                ),
            )
            shell.append_log(
                f"attack config refreshed: default=[{fresh.attack_key}], sequences={len(fresh.attack_sequences)}",
                "system",
            )
            controller.start()
            shell.set_status("running", running=True)
        except Exception as exc:
            try:
                controller.stop()
            except Exception as cleanup_exc:
                shell.append_log(f"[start cleanup error] {cleanup_exc}", "system")
            shell.append_log(f"[start error] {exc}", "system")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(shell, "Claude start error", str(exc))

    def safe_stop():
        try:
            controller.stop()
        except Exception as exc:
            shell.append_log(f"[stop error] {exc}", "system")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(shell, "Claude stop error", str(exc))
        finally:
            shell.set_status("stopped", running=False)

    def safe_junk_sell():
        try:
            started = rt.start_junk_sell()
            if started:
                shell.append_log("auto sell requested", "auto")
        except Exception as exc:
            shell.append_log(f"[auto sell start error] {exc}", "auto")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(shell, "Claude auto sell error", str(exc))

    def safe_junk_sell_stop():
        try:
            rt.stop_junk_sell()
            shell.append_log("auto sell stop requested", "auto")
        except Exception as exc:
            shell.append_log(f"[auto sell stop error] {exc}", "auto")

    shell.btn_start.clicked.connect(safe_start)
    shell.btn_stop.clicked.connect(safe_stop)
    sell_btn.clicked.connect(safe_junk_sell)
    sell_stop_btn.clicked.connect(safe_junk_sell_stop)
    shell.show()
    _write_runtime_log("BOOT", "main: shell shown")
    _start_update_check(shell)
    exit_code = app.exec()
    _write_runtime_log("NORMAL EXIT", f"code={exit_code}")
    sys.exit(exit_code)
if __name__ == "__main__":
    main()




