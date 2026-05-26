# 설정1 탭 - 거짓말탐지기/유저발견/레벨정지/스텟찍기 설정 UI
import os
import numpy as np
import cv2
import mss


def _send_telegram(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """텔레그램 봇 API로 메시지를 전송한다. (token, chat_id, text) → (성공여부, 오류메시지)"""
    import urllib.request
    import urllib.parse
    import json as _json
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        req  = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        body = _json.loads(resp.read())
        if body.get("ok"):
            return True, ""
        return False, body.get("description", "알 수 없는 오류")
    except Exception as e:
        return False, str(e)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QSpinBox, QLabel, QLineEdit, QScrollArea,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.region_selector import RegionSelector
from ui.widgets import HotkeyCapture


class TabSettings1(QWidget):
    # 백그라운드 스레드 → 메인 스레드로 텔레그램 결과 전달용 시그널
    _tg_result = pyqtSignal(bool, str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._hk = None   # HotkeyManager (나중에 set_hotkey_manager로 주입)
        self._tg_result.connect(self._on_tg_result)  # 시그널 → 메인 스레드 팝업

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        layout.addWidget(self._build_lie_detector_group())
        layout.addWidget(self._build_transparent_shape_group())
        layout.addWidget(self._build_user_detected_group())
        layout.addWidget(self._build_stat_assign_group())
        layout.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.load_from_config()

    # ── 거짓말탐지기 설정 ──────────────────────────────────────────────
    def _build_lie_detector_group(self):
        group = QGroupBox("거짓말탐지기 설정")
        layout = QVBoxLayout(group)

        # 템플릿 캡처
        cap_row = QHBoxLayout()
        self.lbl_lie_template = QLabel()
        self._refresh_template_label()
        btn_capture = QPushButton("+ 템플릿 추가 캡처")
        btn_capture.setToolTip(
            "거짓말탐지기 창이 화면에 떠 있을 때 드래그로 영역을 선택하면\n"
            "번호가 붙은 템플릿으로 저장됩니다. 여러 장 추가할수록 감지율이 높아집니다."
        )
        btn_capture.clicked.connect(self._capture_lie_template)
        btn_clear = QPushButton("전체 삭제")
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self._clear_lie_templates)
        cap_row.addWidget(self.lbl_lie_template)
        cap_row.addStretch()
        cap_row.addWidget(btn_capture)
        cap_row.addWidget(btn_clear)
        layout.addLayout(cap_row)

        # 감지 영역 설정
        region_row = QHBoxLayout()
        self.lbl_lie_region = QLabel("감지 영역: 전체 화면")
        self.lbl_lie_region.setStyleSheet("color: gray;")
        btn_set_region = QPushButton("📍 영역 설정")
        btn_set_region.setFixedWidth(90)
        btn_set_region.setToolTip("거짓말탐지기가 나타나는 화면 영역을 드래그로 지정합니다.\n좁게 지정할수록 오탐이 줄어듭니다.")
        btn_set_region.clicked.connect(self._set_lie_region)
        btn_reset_region = QPushButton("초기화")
        btn_reset_region.setFixedWidth(55)
        btn_reset_region.clicked.connect(self._reset_lie_region)
        region_row.addWidget(self.lbl_lie_region)
        region_row.addStretch()
        region_row.addWidget(btn_set_region)
        region_row.addWidget(btn_reset_region)
        layout.addLayout(region_row)

        # 영역 설정 단축키
        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel("영역 설정 단축키"))
        self.btn_lie_region_hk = HotkeyCapture("", self._apply_lie_region_hotkey)
        self.btn_lie_region_hk.setFixedWidth(90)
        self.btn_lie_region_hk.setToolTip("인게임에서 이 키를 누르면 영역 선택 창이 열립니다.")
        hk_row.addWidget(self.btn_lie_region_hk)
        hk_row.addStretch()
        layout.addLayout(hk_row)

        self.chk_lie_enabled = QCheckBox("거짓말탐지기 발견 시")
        layout.addWidget(self.chk_lie_enabled)

        # 알람 테스트 버튼
        alarm_row = QHBoxLayout()
        btn_test_alarm = QPushButton("🔔 알람 소리 테스트")
        btn_test_alarm.setFixedWidth(160)
        btn_test_alarm.clicked.connect(self._test_alarm)
        alarm_row.addWidget(btn_test_alarm)
        alarm_row.addStretch()
        layout.addLayout(alarm_row)

        sub_options = [
            ("chk_play_alarm",    "컴퓨터 경보음 내기"),
        ]
        for attr, text in sub_options:
            row = QHBoxLayout()
            row.addSpacing(20)
            chk = QCheckBox(text)
            setattr(self, attr, chk)
            row.addWidget(chk)
            row.addStretch()
            layout.addLayout(row)

        # ── 텔레그램 알림 ─────────────────────────────────────────────
        layout.addWidget(QLabel("── 텔레그램 알림 ──────────────────"))

        tg_prefix_row = QHBoxLayout()
        tg_prefix_row.addWidget(QLabel("메시지 앞 단어"))
        self.edit_tg_prefix = QLineEdit()
        self.edit_tg_prefix.setPlaceholderText("예: 1번 자리  →  '1번 자리 거짓말 탐지기 발견!'")
        tg_prefix_row.addWidget(self.edit_tg_prefix)
        layout.addLayout(tg_prefix_row)

        tg_token_row = QHBoxLayout()
        tg_token_row.addWidget(QLabel("Bot Token  "))
        self.edit_tg_token = QLineEdit()
        self.edit_tg_token.setPlaceholderText("123456:ABC-DEFxxx...")
        self.edit_tg_token.setEchoMode(QLineEdit.EchoMode.Password)
        tg_token_row.addWidget(self.edit_tg_token)
        layout.addLayout(tg_token_row)

        tg_chat_row = QHBoxLayout()
        tg_chat_row.addWidget(QLabel("Chat ID   "))
        self.edit_tg_chat = QLineEdit()
        self.edit_tg_chat.setPlaceholderText("-1001234567890  또는  개인 숫자 ID")
        tg_chat_row.addWidget(self.edit_tg_chat)
        layout.addLayout(tg_chat_row)

        tg_opt_row = QHBoxLayout()
        self.chk_tg_enabled = QCheckBox("텔레그램 알림 보내기")
        btn_tg_save = QPushButton("💾 저장")
        btn_tg_save.setFixedWidth(65)
        btn_tg_save.setToolTip("Bot Token · Chat ID · 체크박스 설정을 즉시 저장합니다.")
        btn_tg_save.clicked.connect(self._save_telegram_settings)
        btn_tg_test = QPushButton("📨 테스트 전송")
        btn_tg_test.setFixedWidth(110)
        btn_tg_test.setToolTip("입력한 봇으로 테스트 메시지를 전송합니다.")
        btn_tg_test.clicked.connect(self._test_telegram)
        tg_opt_row.addWidget(self.chk_tg_enabled)
        tg_opt_row.addStretch()
        tg_opt_row.addWidget(btn_tg_save)
        tg_opt_row.addWidget(btn_tg_test)
        layout.addLayout(tg_opt_row)

        return group

    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk
        saved_key = (self.config.get("settings1", "lie_detector") or {}).get("region_hotkey", "")
        if saved_key:
            self.btn_lie_region_hk.set_key(saved_key)
            self._apply_lie_region_hotkey(saved_key)

    def _apply_lie_region_hotkey(self, key: str) -> None:
        if not self._hk or not key:
            return
        err = self._hk.register("lie_region", key, self._set_lie_region)
        if not err:
            self.config.set("settings1", "lie_detector", "region_hotkey", key)

    def _set_lie_region(self) -> None:
        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._save_lie_region)
        self._region_selector.show()

    def _save_lie_region(self, x: int, y: int, w: int, h: int) -> None:
        from core.config_manager import get_game_window_rect
        ox, oy, cw, ch = get_game_window_rect(self.config)
        if cw > 0 and ch > 0:
            region = {
                "x_ratio": (x - ox) / cw,
                "y_ratio": (y - oy) / ch,
                "w_ratio": w / cw,
                "h_ratio": h / ch,
            }
            disp_x, disp_y = int(x - ox), int(y - oy)
            mode = "비율"
        else:
            region = [x, y, w, h]
            disp_x, disp_y = x, y
            mode = "픽셀"
        # 1. 영역 config 저장
        self.config.set("settings1", "lie_detector", "region", region)
        self.config.save()
        self.lbl_lie_region.setText(f"감지 영역: X={disp_x} Y={disp_y} W={w} H={h} ({mode})")
        self.lbl_lie_region.setStyleSheet("color: green;")

        # 2. 동일 영역을 템플릿으로도 자동 저장
        import glob
        os.makedirs("templates", exist_ok=True)
        existing = sorted(glob.glob("templates/lie_detector_*.png"))
        next_num = len(existing) + 1
        path = f"templates/lie_detector_{next_num}.png"
        from ui.region_selector import logical_to_physical
        px, py, pw, ph = logical_to_physical(x, y, w, h)
        with mss.mss() as sct:
            raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite(path, img)
        self._refresh_template_label()
        QMessageBox.information(
            self, "영역 설정 완료",
            f"감지 영역 저장 완료\n"
            f"템플릿 {next_num}번으로 자동 캡처됨 ({pw}×{ph} px)"
        )

    def _reset_lie_region(self) -> None:
        self.config.set("settings1", "lie_detector", "region", None)
        self.config.save()
        self.lbl_lie_region.setText("감지 영역: 전체 화면")
        self.lbl_lie_region.setStyleSheet("color: gray;")

    def _test_alarm(self) -> None:
        """알람 소리를 즉시 재생한다."""
        import threading
        import winsound
        def _play():
            for _ in range(3):
                winsound.Beep(1000, 300)
                import time; time.sleep(0.1)
        threading.Thread(target=_play, daemon=True).start()

    def _save_telegram_settings(self) -> None:
        """텔레그램 설정(prefix / token / chat_id / 활성화)을 즉시 config에 저장한다."""
        self.config.set("settings1", "lie_detector", "tg_enabled", self.chk_tg_enabled.isChecked())
        self.config.set("settings1", "lie_detector", "tg_prefix",  self.edit_tg_prefix.text().strip())
        self.config.set("settings1", "lie_detector", "tg_token",   self.edit_tg_token.text().strip())
        self.config.set("settings1", "lie_detector", "tg_chat_id", self.edit_tg_chat.text().strip())
        self.config.save()
        QMessageBox.information(self, "저장 완료", "텔레그램 설정이 저장되었습니다.")

    def _test_telegram(self) -> None:
        """텔레그램 테스트 메시지를 전송한다 (백그라운드 스레드 → 시그널로 결과 반환)."""
        token   = self.edit_tg_token.text().strip()
        chat_id = self.edit_tg_chat.text().strip()
        if not token or not chat_id:
            QMessageBox.warning(self, "알림", "Bot Token과 Chat ID를 모두 입력하세요.")
            return

        import threading
        def _send():
            ok, err = _send_telegram(token, chat_id, "✅ [MapleBot] 텔레그램 알림 테스트 메시지입니다.")
            self._tg_result.emit(ok, err)   # 메인 스레드로 전달
        threading.Thread(target=_send, daemon=True).start()

    def _on_tg_result(self, ok: bool, err: str) -> None:
        """_tg_result 시그널 수신 — 메인 스레드에서 결과 팝업 표시."""
        if ok:
            QMessageBox.information(self, "전송 성공", "텔레그램 메시지 전송 성공!")
        else:
            QMessageBox.warning(self, "전송 실패", f"전송 실패:\n{err}")

    def _refresh_template_label(self) -> None:
        import glob
        files = sorted(glob.glob("templates/lie_detector_*.png"))
        count = len(files)
        if count > 0:
            self.lbl_lie_template.setText(f"✅ 템플릿 {count}개 저장됨")
            self.lbl_lie_template.setStyleSheet("color: green;")
        else:
            self.lbl_lie_template.setText("❌ 템플릿 없음")
            self.lbl_lie_template.setStyleSheet("color: red;")

    def _capture_lie_template(self) -> None:
        """RegionSelector로 영역 선택 후 번호가 붙은 템플릿으로 저장."""
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._save_lie_template)
        self._selector.show()

    def _save_lie_template(self, x: int, y: int, w: int, h: int) -> None:
        import glob
        os.makedirs("templates", exist_ok=True)
        # 기존 파일 수 확인 후 다음 번호로 저장
        existing = sorted(glob.glob("templates/lie_detector_*.png"))
        next_num = len(existing) + 1
        path = f"templates/lie_detector_{next_num}.png"
        with mss.mss() as sct:
            region = {"left": x, "top": y, "width": w, "height": h}
            raw = sct.grab(region)
            img = np.array(raw)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            cv2.imwrite(path, img)
        self._refresh_template_label()
        QMessageBox.information(
            self, "완료",
            f"템플릿 {next_num}번 저장 완료 ({w}×{h} px)\n"
            f"현재 총 {next_num}개 — 여러 장 추가할수록 감지율이 높아집니다."
        )

    def _clear_lie_templates(self) -> None:
        """저장된 거짓말탐지기 템플릿을 모두 삭제한다."""
        import glob
        files = glob.glob("templates/lie_detector_*.png")
        if not files:
            QMessageBox.information(self, "알림", "삭제할 템플릿이 없습니다.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"템플릿 {len(files)}개를 모두 삭제하시겠습니까?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for f in files:
            os.remove(f)
        self._refresh_template_label()

    # ── 투명 도형 찾기 설정 ───────────────────────────────────────────────
    def _build_transparent_shape_group(self):
        group = QGroupBox("투명 도형 찾기 설정")
        layout = QVBoxLayout(group)

        self.chk_transparent_enabled = QCheckBox("투명 도형 찾기 미니게임 자동 해제")
        self.chk_transparent_enabled.toggled.connect(self._save_transparent_shape)
        layout.addWidget(self.chk_transparent_enabled)

        # 타이틀 템플릿 캡처 행
        tpl_row = QHBoxLayout()
        self.lbl_transparent_title = QLabel("타이틀 템플릿: 없음")
        self.lbl_transparent_title.setStyleSheet("color: red;")
        btn_tpl = QPushButton("+ 타이틀 템플릿 캡처")
        btn_tpl.setToolTip(
            "게임 팝업 상단의 '투명 도형 찾기' 제목 텍스트 영역을\n"
            "드래그로 선택하면 templates/transparent_shape_title.png 로 저장됩니다."
        )
        btn_tpl.clicked.connect(self._capture_transparent_title)
        btn_tpl_del = QPushButton("삭제")
        btn_tpl_del.setFixedWidth(45)
        btn_tpl_del.clicked.connect(self._delete_transparent_title)
        tpl_row.addWidget(self.lbl_transparent_title)
        tpl_row.addStretch()
        tpl_row.addWidget(btn_tpl)
        tpl_row.addWidget(btn_tpl_del)
        layout.addLayout(tpl_row)

        # 게임판 ROI 캡처 행
        roi_row = QHBoxLayout()
        self.lbl_transparent_roi = QLabel("게임판 영역: 미설정")
        self.lbl_transparent_roi.setStyleSheet("color: red;")
        btn_roi = QPushButton("+ 게임판 영역 캡처")
        btn_roi.setToolTip(
            "게임판(갈색 배경 영역 전체)을 드래그로 선택하세요.\n"
            "게임창 client 좌표로 자동 변환되어 저장됩니다."
        )
        btn_roi.clicked.connect(self._capture_transparent_roi)
        btn_roi_del = QPushButton("삭제")
        btn_roi_del.setFixedWidth(45)
        btn_roi_del.clicked.connect(self._delete_transparent_roi)
        roi_row.addWidget(self.lbl_transparent_roi)
        roi_row.addStretch()
        roi_row.addWidget(btn_roi)
        roi_row.addWidget(btn_roi_del)
        layout.addLayout(roi_row)

        self.chk_transparent_debug = QCheckBox("디버그 오버레이 표시 (cv2 창)")
        self.chk_transparent_debug.toggled.connect(self._save_transparent_shape)
        layout.addWidget(self.chk_transparent_debug)

        return group

    def _refresh_transparent_status_labels(self):
        import os
        path = "templates/transparent_shape_title.png"
        if os.path.exists(path):
            self.lbl_transparent_title.setText("타이틀 템플릿: 저장됨")
            self.lbl_transparent_title.setStyleSheet("color: green;")
        else:
            self.lbl_transparent_title.setText("타이틀 템플릿: 없음")
            self.lbl_transparent_title.setStyleSheet("color: red;")

        roi_cfg = self.config.get("settings1", "transparent_shape", "board_roi")
        if roi_cfg and isinstance(roi_cfg, dict):
            from core.config_manager import get_game_window_rect
            ox, oy, cw, ch = get_game_window_rect(self.config)
            if roi_cfg.get("x_ratio") is not None and cw > 0:
                cx = int(roi_cfg["x_ratio"] * cw)
                cy = int(roi_cfg["y_ratio"] * ch)
                w  = int(roi_cfg["w_ratio"] * cw)
                h  = int(roi_cfg["h_ratio"] * ch)
            else:
                cx = roi_cfg.get("client_x", roi_cfg.get("x", 0))
                cy = roi_cfg.get("client_y", roi_cfg.get("y", 0))
                w  = roi_cfg.get("w", roi_cfg.get("width", 0))
                h  = roi_cfg.get("h", roi_cfg.get("height", 0))
            if w:
                self.lbl_transparent_roi.setText(f"게임판: client({cx},{cy}) {w}×{h}")
                self.lbl_transparent_roi.setStyleSheet("color: green;")
            else:
                self.lbl_transparent_roi.setText("게임판 영역: 미설정")
                self.lbl_transparent_roi.setStyleSheet("color: red;")
        else:
            self.lbl_transparent_roi.setText("게임판 영역: 미설정")
            self.lbl_transparent_roi.setStyleSheet("color: red;")

    def _capture_transparent_title(self):
        sel = RegionSelector()
        sel.region_selected.connect(self._save_transparent_title_region)
        self._transparent_title_selector = sel
        sel.show()

    def _save_transparent_title_region(self, x, y, w, h):
        import mss
        import os
        from ui.region_selector import logical_to_physical
        px, py, pw, ph = logical_to_physical(x, y, w, h)
        os.makedirs("templates", exist_ok=True)
        with mss.mss() as sct:
            raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite("templates/transparent_shape_title.png", img)
        self._refresh_transparent_status_labels()
        QMessageBox.information(self, "완료", f"타이틀 템플릿 저장 완료 ({pw}×{ph}px)")

    def _delete_transparent_title(self):
        import os
        path = "templates/transparent_shape_title.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_transparent_status_labels()

    def _capture_transparent_roi(self):
        sel = RegionSelector()
        sel.region_selected.connect(self._save_transparent_roi_region)
        self._transparent_roi_selector = sel
        sel.show()

    def _save_transparent_roi_region(self, abs_x, abs_y, w, h):
        from core.config_manager import get_game_window_rect
        ox, oy, cw, ch = get_game_window_rect(self.config)
        if cw > 0 and ch > 0:
            roi = {
                "x_ratio": (abs_x - ox) / cw,
                "y_ratio": (abs_y - oy) / ch,
                "w_ratio": w / cw,
                "h_ratio": h / ch,
            }
            client_x, client_y = int(abs_x - ox), int(abs_y - oy)
            mode = "비율"
        else:
            # absolute 모드 — 구버전 client_x/client_y 형식으로 저장
            from core.screen_reader import ScreenReader
            window_title = self.config.get("settings2", "game_window_title") or "MapleStory"
            origin = ScreenReader().get_window_client_origin(window_title)
            if origin:
                client_x = abs_x - origin[0]
                client_y = abs_y - origin[1]
            else:
                client_x, client_y = abs_x, abs_y
            roi = {"client_x": client_x, "client_y": client_y, "w": w, "h": h}
            mode = "픽셀"
        self.config.set("settings1", "transparent_shape", "board_roi", roi)
        self.config.save()
        self._refresh_transparent_status_labels()
        QMessageBox.information(self, "완료", f"게임판 영역 저장 완료 (client {client_x},{client_y}, {w}×{h}px, {mode})")

    def _delete_transparent_roi(self):
        self.config.set("settings1", "transparent_shape", "board_roi", None)
        self.config.save()
        self._refresh_transparent_status_labels()

    def _save_transparent_shape(self):
        self.config.set("settings1", "transparent_shape", "enabled",
                        self.chk_transparent_enabled.isChecked())
        self.config.set("settings1", "transparent_shape", "debug_overlay",
                        self.chk_transparent_debug.isChecked())
        self.config.save()

    # ── 유저발견 시 설정 ───────────────────────────────────────────────
    def _build_user_detected_group(self):
        group = QGroupBox("유저발견 시 설정")
        layout = QVBoxLayout(group)

        self.chk_user_chat = QCheckBox("미니맵에 유저발견 시 채팅")
        layout.addWidget(self.chk_user_chat)

        row = QHBoxLayout()
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(5)
        self.spin_interval.setFixedWidth(50)
        row.addWidget(self.spin_interval)
        row.addWidget(QLabel("분 간격으로 확인 후 발견 시 순서대로 말합니다"))
        row.addStretch()
        layout.addLayout(row)

        self.msg_edits = []
        for i in range(3):
            msg_row = QHBoxLayout()
            msg_row.addWidget(QLabel(f"{i + 1}"))
            edit = QLineEdit()
            edit.setPlaceholderText(f"말할 내용 {i + 1}번")
            self.msg_edits.append(edit)
            msg_row.addWidget(edit)
            layout.addLayout(msg_row)

        return group

    # ── 사냥터 이탈 감지 설정 ────────────────────────────────────────
    # ── 레벨업 스텟찍기 설정 ──────────────────────────────────────────
    def _build_stat_assign_group(self):
        group = QGroupBox("레벨업 스텟찍기 설정")
        layout = QVBoxLayout(group)

        self.chk_stat_assign = QCheckBox("레벨업 마다 스텟찍기 사용")
        layout.addWidget(self.chk_stat_assign)

        row = QHBoxLayout()
        self.stat_spins = {}
        for stat in ["STR", "INT", "DEX", "LUK"]:
            row.addWidget(QLabel(stat))
            spin = QSpinBox()
            spin.setRange(0, 99)
            spin.setFixedWidth(55)
            self.stat_spins[stat] = spin
            row.addWidget(spin)
        row.addStretch()
        layout.addLayout(row)

        return group

    # ── config 연동 ───────────────────────────────────────────────────
    def load_from_config(self):
        ld = self.config.get("settings1", "lie_detector") or {}
        self.chk_lie_enabled.setChecked(ld.get("enabled", False))
        self.chk_play_alarm.setChecked(ld.get("play_alarm", False))
        self.chk_tg_enabled.setChecked(ld.get("tg_enabled", False))
        self.edit_tg_prefix.setText(ld.get("tg_prefix", ""))
        self.edit_tg_token.setText(ld.get("tg_token", ""))
        self.edit_tg_chat.setText(ld.get("tg_chat_id", ""))
        region = ld.get("region")
        if isinstance(region, dict) and region.get("x_ratio") is not None:
            from core.config_manager import get_game_window_rect
            ox, oy, cw, ch = get_game_window_rect(self.config)
            if cw > 0:
                disp_x = int(region["x_ratio"] * cw)
                disp_y = int(region["y_ratio"] * ch)
                disp_w = int(region["w_ratio"] * cw)
                disp_h = int(region["h_ratio"] * ch)
                self.lbl_lie_region.setText(f"감지 영역: X={disp_x} Y={disp_y} W={disp_w} H={disp_h} (비율)")
            else:
                self.lbl_lie_region.setText("감지 영역: 비율 저장됨")
            self.lbl_lie_region.setStyleSheet("color: green;")
        elif region and isinstance(region, list) and len(region) == 4:
            x, y, w, h = region
            self.lbl_lie_region.setText(f"감지 영역: X={x} Y={y} W={w} H={h}")
            self.lbl_lie_region.setStyleSheet("color: green;")
        else:
            self.lbl_lie_region.setText("감지 영역: 전체 화면")
            self.lbl_lie_region.setStyleSheet("color: gray;")
        hk_key = ld.get("region_hotkey", "")
        if hk_key:
            self.btn_lie_region_hk.set_key(hk_key)

        ud = self.config.get("settings1", "user_detected") or {}
        self.chk_user_chat.setChecked(ud.get("enabled", False))
        self.spin_interval.setValue(ud.get("interval_minutes", 5))
        msgs = ud.get("messages", ["", "", ""])
        for i, edit in enumerate(self.msg_edits):
            edit.setText(msgs[i] if i < len(msgs) else "")

        sa = self.config.get("settings1", "stat_assign") or {}
        self.chk_stat_assign.setChecked(sa.get("enabled", False))
        for stat in ["STR", "INT", "DEX", "LUK"]:
            self.stat_spins[stat].setValue(sa.get(stat, 0))

        ts = self.config.get("settings1", "transparent_shape") or {}
        self.chk_transparent_enabled.setChecked(bool(ts.get("enabled", False)))
        self.chk_transparent_debug.setChecked(bool(ts.get("debug_overlay", False)))
        self._refresh_transparent_status_labels()

    def save_to_config(self):
        self.config.set("settings1", "lie_detector", "enabled",       self.chk_lie_enabled.isChecked())
        self.config.set("settings1", "lie_detector", "play_alarm",    self.chk_play_alarm.isChecked())
        self.config.set("settings1", "lie_detector", "tg_enabled",   self.chk_tg_enabled.isChecked())
        self.config.set("settings1", "lie_detector", "tg_prefix",    self.edit_tg_prefix.text().strip())
        self.config.set("settings1", "lie_detector", "tg_token",     self.edit_tg_token.text().strip())
        self.config.set("settings1", "lie_detector", "tg_chat_id",   self.edit_tg_chat.text().strip())

        self.config.set("settings1", "user_detected", "enabled",          self.chk_user_chat.isChecked())
        self.config.set("settings1", "user_detected", "interval_minutes", self.spin_interval.value())
        self.config.set("settings1", "user_detected", "messages",         [e.text() for e in self.msg_edits])

        self.config.set("settings1", "stat_assign", "enabled", self.chk_stat_assign.isChecked())
        for stat, spin in self.stat_spins.items():
            self.config.set("settings1", "stat_assign", stat, spin.value())


