# 메이플 월드 자동사냥 봇 진입점
import sys
import os
import threading

# EXE/스크립트 위치를 작업 디렉토리로 고정
# → config.json, templates/ 등 상대경로가 항상 올바르게 동작함
_base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
os.chdir(_base)

# PyInstaller 번들 환경에서 certifi CA 인증서 경로 수동 지정
# → requests HTTPS 연결 시 "TLS CA certificate bundle" 오류 방지
if getattr(sys, "frozen", False):
    _certifi_pem = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
    if os.path.exists(_certifi_pem):
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _certifi_pem)
        os.environ.setdefault("SSL_CERT_FILE", _certifi_pem)

from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow

# 라이선스 기능 활성화 여부
_LICENSE_ENABLED = True


def _check_license(app: QApplication) -> bool:
    """라이선스를 확인하고 유효하면 True를 반환한다."""
    from core.hw_fingerprint import get_hwid
    from core import license_manager

    hwid = get_hwid()
    try:
        license_manager.check(hwid)
        return True
    except license_manager.LicenseError as exc:
        err = str(exc)
        needs_input = (
            err == "NO_LICENSE"
            or "이 PC에 등록된 라이선스가 아닙니다" in err
            or "라이선스 파일이 손상되었습니다" in err
            or "라이선스 서명이 유효하지 않습니다" in err
            or "라이선스 파일 파싱 오류" in err
        )
        if needs_input:
            # 잘못된 / 다른 PC의 license.dat 가 남아있으면 삭제 후 재입력
            if err != "NO_LICENSE":
                try:
                    os.remove(license_manager.LICENSE_FILE)
                except Exception:
                    pass
            from ui.dialog_license import LicenseDialog
            dlg = LicenseDialog(hwid)
            if dlg.exec() == LicenseDialog.DialogCode.Accepted:
                return True
            return False
        else:
            QMessageBox.critical(None, "라이선스 오류", err)
            return False


def _start_update_check(parent_window) -> None:
    """백그라운드에서 업데이트를 확인하고, 새 버전이 있으면 팝업을 띄운다."""
    from PyQt6.QtCore import QObject, pyqtSignal

    class _Notifier(QObject):
        update_available = pyqtSignal(dict)

    # 노티파이어를 메인 스레드에서 생성해 시그널이 메인 스레드 이벤트 루프로 전달되게 함
    notifier = _Notifier()
    notifier.update_available.connect(
        lambda info: _show_update_dialog(info, parent_window)
    )

    def _worker():
        from core.updater import check_for_update
        info = check_for_update()
        if info:
            notifier.update_available.emit(info)  # 스레드 안전 — 큐드 커넥션으로 메인 스레드 전달

    threading.Thread(target=_worker, daemon=True).start()


def _show_update_dialog(info: dict, parent) -> None:
    from ui.dialog_update import UpdateDialog
    dlg = UpdateDialog(info, parent=parent)
    dlg.exec()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if _LICENSE_ENABLED:
        if not _check_license(app):
            sys.exit(1)

    window = MainWindow()
    window.show()

    # 라이선스 통과 후 업데이트 확인 (백그라운드 — 3초 뒤 시작)
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(3000, lambda: _start_update_check(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
