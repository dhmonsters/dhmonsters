# Claude 통합 실행 진입점으로 core_ui와 BotRuntime을 연결한다.
# 실행 방법은 py -3.14 run_integrated.py이다.
from __future__ import annotations

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
    """?고????쒖옉怨??덉쇅瑜??뚯씪 濡쒓렇濡?湲곕줉?쒕떎."""
    path = ROOT / "logs" / "claude_runtime.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {kind}\n")
            log.write(message.rstrip() + "\n")
    except Exception:
        pass


def _install_runtime_logging() -> None:
    """?꾨줈洹몃옩 ?쒖옉 ?④퀎?먯꽌 ?щ옒??濡쒓렇? ?덉쇅 ?낆쓣 ?ㅼ튂?쒕떎."""
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


def _focus_game_window_before_runtime(rc) -> str:
    """BotRuntime 생성 전에 게임창을 찾고 포커스합니다."""
    import win32con
    import win32gui
    from core.game_window import find_game_hwnd, find_window_hwnd_by_title

    configured_title = str(getattr(rc, "game_window_title", "") or "").strip()
    hwnd = find_window_hwnd_by_title(configured_title) if configured_title else None
    if not hwnd:
        hwnd = find_game_hwnd()
    if not hwnd:
        raise RuntimeError("게임창을 찾지 못했습니다. MapleStory Worlds 게임창을 먼저 켠 뒤 다시 실행해 주세요.")
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        raise RuntimeError(f"게임창 포커스에 실패했습니다. 관리자 권한과 게임창 상태를 확인해 주세요. ({exc})")
    return win32gui.GetWindowText(hwnd) or configured_title


def build_runtime():
    _write_runtime_log("BOOT", "build_runtime: start")
    """ConfigManager ??????????????????거??????????곕츥??????????????熬곣뫖利당춯??쎾퐲????????????????????熬곣뫖利당춯??????BotRuntime ?????????????
    ??????熬곣뫖利당춯??쎾퐲??????????? (runtime, RuntimeConfig, ConfigManager)."""
    from core.screen_reader import ScreenReader
    from core.config_manager import ConfigManager
    from core.humanize.backend import select_backend
    from core.config_adapter import to_runtime_config
    BotRuntime = _load_core_runtime_attr("BotRuntime")

    # 1) ???????????????????????????壤굿?????(ConfigManager ??UI ??????됰Ŧ?????????????밸븶筌믩끃??獄????????????嫄????????????????繹먮굞????)
    cm = ConfigManager()
    _write_runtime_log("BOOT", "build_runtime: config loaded")
    rc = to_runtime_config(cm._data)
    _write_runtime_log("BOOT", "build_runtime: runtime config converted")
    rc.junk_config = cm          # ??????????ㅼ┥??????????ConfigManager get ??????됰Ŧ???????耀붾굝????????袁⑸젽????????????곕츥?????????????

    # 2) ??????????????????롮쾸????????????????????거??????????곕츥????????(mss ???????????????ScreenReader ?????
    screen = ScreenReader()
    def capture(region=None):
        return screen.capture(region)

    # 3) 게임창을 먼저 찾고 포커스한 뒤 Interception 입력 백엔드를 선택합니다.
    focused_title = _focus_game_window_before_runtime(rc)
    if focused_title:
        rc.game_window_title = focused_title
    _write_runtime_log("BOOT", f"build_runtime: game window focused title={focused_title or rc.game_window_title}")
    backend = select_backend()
    print(f"[input] backend selected: {backend.name}")

    # 3-1) HP/MP ??????????????ロ깫??????⑥レ뿥????(A ??????熬곣뫖利당춯??쎾퐲?????쒓텤??酉????뜐?됀??Detector ????? ???????????????????? ???? ???????????????썹땟戮녹??諭?????⑸㎦?????????癲????????????熬곣뫖利당춯??쎾퐲?????????????????????
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
    """誘몃땲留??몄쭛 UI? ?고????곹깭 ?쒓났?먮? ?곌껐?쒕떎."""
    from PyQt6.QtWidgets import QWidget
    from core_ui.world_map_editor import WorldMapEditor
    from core_ui.minimap_canvas import RouteCanvas

    route_canvas = shell.findChild(RouteCanvas)
    if isinstance(route_canvas, RouteCanvas):
        route_canvas.set_character_provider(runtime.char_scanner.position)
        route_canvas.set_region_provider(runtime.char_scanner.capture_region)
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


def bind_character_offset_controls(shell, runtime):
    """감지 좌표 보정 UI를 실행 중인 캐릭터 스캐너에 즉시 연결한다."""
    from PyQt6.QtWidgets import QSpinBox

    offset_x = shell.findChild(QSpinBox, "characterPositionOffsetX")
    offset_y = shell.findChild(QSpinBox, "characterPositionOffsetY")
    if offset_x is None or offset_y is None:
        return

    def apply_offset():
        runtime.char_scanner.set_position_offset(offset_x.value(), offset_y.value())

    offset_x.valueChanged.connect(lambda _value: apply_offset())
    offset_y.valueChanged.connect(lambda _value: apply_offset())
    apply_offset()


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
    """蹂몄껜 UI ?앹꽦 ???낅뜲?댄듃媛 ?덉쑝硫?癒쇱? ?덈궡?쒕떎."""
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
    """?쇱씠?좎뒪媛 ?좏슚?쒖? ?뺤씤?섍퀬 ?꾩슂?섎㈃ ?몄쬆 李쎌쓣 ?꾩슫??"""
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
            self._rt._release_runtime_inputs()
        except Exception as exc:
            self._log(f"safe-stop input release error: {exc}", "system")
        if self._rt.floor_hunt_runner is not None:
            self._rt.floor_hunt_runner.stop()
        self._log(f"bot safe stop completed: {reason}", "system")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if self.is_running():
            self._rt.resume_lie_safety_if_clear()
            return
        game_title = str(getattr(self._rt._cfg, "game_window_title", "") or "").strip()
        self._log(f"game window focus: prepared ({game_title or 'auto-detected'})", "system")
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
        self._movement_thread = None
        if self._rt.floor_hunt_runner is None:
            self._movement_thread = threading.Thread(
                target=self._movement_loop, daemon=True, name="BotMovementLoop",
            )
        self._attack_thread = threading.Thread(target=self._attack_loop, daemon=True, name="BotAttackLoop")
        self._support_thread = threading.Thread(target=self._support_loop, daemon=True, name="BotSupportLoop")
        self._pickup_thread = threading.Thread(target=self._pickup_loop, daemon=True, name="BotPickupLoop")
        self._thread.start()
        if self._movement_thread is not None:
            self._movement_thread.start()
        self._attack_thread.start()
        self._support_thread.start()
        self._pickup_thread.start()

    def stop(self, reason: str = "manual") -> None:
        if not isinstance(reason, str):
            reason = "manual"
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
            self._rt._release_runtime_inputs()
        except Exception:
            pass
        self._log(f"bot stop (input released, reason={reason})", "system")

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
                self._rt.block_runner._route_inputs.release_direction()
                self._stop.wait(0.2)
                continue
            self._stop.wait(0.03)

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


def _start_with_fresh_config(controller, runtime, config_manager, shell) -> None:
    """F1 입력마다 공격과 픽업 설정을 갱신한 뒤 봇을 시작하거나 재개한다."""
    from core.config_adapter import to_runtime_config
    from core.acting.attack_sequence import AttackSequenceRunner

    fresh = to_runtime_config(config_manager._data)
    runtime.release_pickup_key()
    runtime._cfg.attack_key = fresh.attack_key
    runtime._cfg.attack_sequences = fresh.attack_sequences
    runtime._cfg.pickup_key = fresh.pickup_key
    runtime._cfg.pickup_interval = fresh.pickup_interval
    runtime._cfg.pickup_always = fresh.pickup_always
    runtime.attack_sequence_runner = AttackSequenceRunner(
        fresh.attack_sequences,
        lambda key, hold: runtime.combat.attack(
            key, mode="duration", hold=hold or runtime._attack_hold(),
        ),
    )
    shell.append_log(
        f"attack/pickup config refreshed: default=[{fresh.attack_key}], "
        f"sequences={len(fresh.attack_sequences)}, "
        f"pickup=[{fresh.pickup_key or 'off'}], always={fresh.pickup_always}",
        "system",
    )

    if controller.is_running():
        controller.start()
        return

    runtime.reload_character_filter(fresh)
    runtime.reload_monster_templates(fresh)
    runtime.reload_lie_scanner(fresh)
    runtime.reload_floor_hunt_runner(fresh)
    controller.start()


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

    try:
        rt, rc, cm = build_runtime()
    except Exception as exc:
        _write_runtime_log("BOOT ERROR", str(exc))
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Claude 실행 준비 실패", str(exc))
        sys.exit(1)
    _write_runtime_log("BOOT", "main: runtime ready")
    shell = MainShell(config=cm)
    _write_runtime_log("BOOT", "main: shell created")
    bind_world_editor(shell, rt)
    bind_character_offset_controls(shell, rt)
    _write_runtime_log("BOOT", "main: world editor bound")
    backend = getattr(rt, "input_backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))
    if backend_name == "interception":
        shell.append_log("Interception driver: loaded", "system")
    else:
        shell.append_log("Interception driver: load failed", "system")
    shell.append_log(f"config loaded: minimap={rc.minimap_region}, floors={len(rc.floors)}, buffs={len(rc.buffs)}", "system")

    controller = BotController(rt, log_fn=shell.append_log)
    rt.log = shell.append_log
    from core import interception_backend
    interception_backend.set_timing_log_callback(
        lambda message: rt.log(message, "이동")
    )

    def safe_start():
        try:
            _start_with_fresh_config(controller, rt, cm, shell)
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
    from PyQt6.QtWidgets import QPushButton
    sell_btn = shell.findChild(QPushButton, "autoSellRunButton")
    sell_stop_btn = shell.findChild(QPushButton, "autoSellStopButton")
    if sell_btn is not None:
        sell_btn.clicked.connect(safe_junk_sell)
    else:
        shell.append_log("auto sell run button not found in automation page", "auto")
    if sell_stop_btn is not None:
        sell_stop_btn.clicked.connect(safe_junk_sell_stop)
    else:
        shell.append_log("auto sell stop button not found in automation page", "auto")
    shell.show()
    _write_runtime_log("BOOT", "main: shell shown")
    _start_update_check(shell)
    exit_code = app.exec()
    _write_runtime_log("NORMAL EXIT", f"code={exit_code}")
    sys.exit(exit_code)
if __name__ == "__main__":
    main()

