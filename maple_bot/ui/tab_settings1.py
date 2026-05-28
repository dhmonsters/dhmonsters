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
        layout.addWidget(self._build_yolo_group())
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

        # ── YOLO 모델 경로 (거짓말탐지기 + 투명도형 공용) ───────────────
        layout.addWidget(QLabel("── YOLO 감지 모델 경로 ──────────────"))
        yolo_note = QLabel(
            "거짓말탐지기 감지 및 투명 도형 찾기에 공용으로 사용하는 YOLO 모델 경로입니다."
        )
        yolo_note.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(yolo_note)
        yolo_row = QHBoxLayout()
        yolo_row.addWidget(QLabel("모델 경로"))
        self.edit_lie_yolo = QLineEdit()
        self.edit_lie_yolo.setPlaceholderText("lie_detector.onnx 경로")
        btn_lie_yolo_browse = QPushButton("…")
        btn_lie_yolo_browse.setFixedWidth(30)
        btn_lie_yolo_browse.clicked.connect(self._browse_lie_yolo)
        btn_lie_yolo_clear = QPushButton("✕")
        btn_lie_yolo_clear.setFixedWidth(24)
        btn_lie_yolo_clear.clicked.connect(lambda: self.edit_lie_yolo.clear())
        yolo_row.addWidget(self.edit_lie_yolo)
        yolo_row.addWidget(btn_lie_yolo_browse)
        yolo_row.addWidget(btn_lie_yolo_clear)
        layout.addLayout(yolo_row)

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

    def _browse_lie_yolo(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "거짓말탐지기 YOLO 모델 선택", "", "ONNX 모델 (*.onnx);;모든 파일 (*)"
        )
        if path:
            self.edit_lie_yolo.setText(path)


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

        board_h_row = QHBoxLayout()
        board_h_row.addWidget(QLabel("게임판 높이"))
        from PyQt6.QtWidgets import QSpinBox as _QSpinBox
        self.spin_transparent_board_h = _QSpinBox()
        self.spin_transparent_board_h.setRange(100, 1200)
        self.spin_transparent_board_h.setValue(500)
        self.spin_transparent_board_h.setSuffix(" px")
        self.spin_transparent_board_h.setFixedWidth(90)
        self.spin_transparent_board_h.setToolTip(
            "YOLO로 빨간 헤더 감지 후 그 아래 퍼즐 영역의 높이 (픽셀).\n"
            "헤더 bottom부터 이 값만큼 board ROI로 자동 설정됩니다."
        )
        self.spin_transparent_board_h.valueChanged.connect(self._save_transparent_shape)
        board_h_row.addWidget(self.spin_transparent_board_h)
        board_h_row.addStretch()
        layout.addLayout(board_h_row)

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
        self.config.set("settings1", "transparent_shape", "yolo_model_path",
                        self.edit_lie_yolo.text().strip())
        self.config.set("settings1", "transparent_shape", "board_height",
                        self.spin_transparent_board_h.value())
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

    # ── YOLO11 설정 ───────────────────────────────────────────────────
    def _build_yolo_group(self):
        from PyQt6.QtWidgets import QDoubleSpinBox, QFileDialog
        group = QGroupBox("YOLO11 몬스터 감지 설정")
        layout = QVBoxLayout(group)

        # 활성화
        self.chk_yolo_enabled = QCheckBox("YOLO11 감지 활성화 (비활성 시 기존 템플릿 매칭 사용)")
        self.chk_yolo_enabled.stateChanged.connect(self._save_yolo_settings)
        layout.addWidget(self.chk_yolo_enabled)

        # 모델 경로
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("모델 경로"))
        self.edit_yolo_model = QLineEdit()
        self.edit_yolo_model.setPlaceholderText("*.pt 파일 경로 (비우면 폴백)")
        self.edit_yolo_model.editingFinished.connect(self._save_yolo_settings)
        model_row.addWidget(self.edit_yolo_model)
        btn_browse = QPushButton("찾아보기")
        btn_browse.setFixedWidth(70)
        btn_browse.clicked.connect(self._browse_yolo_model)
        model_row.addWidget(btn_browse)
        layout.addLayout(model_row)

        # 신뢰도 / IoU
        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("신뢰도"))
        self.spin_yolo_conf = QDoubleSpinBox()
        self.spin_yolo_conf.setRange(0.1, 1.0)
        self.spin_yolo_conf.setSingleStep(0.05)
        self.spin_yolo_conf.setDecimals(2)
        self.spin_yolo_conf.setFixedWidth(65)
        self.spin_yolo_conf.valueChanged.connect(self._save_yolo_settings)
        params_row.addWidget(self.spin_yolo_conf)
        params_row.addSpacing(12)
        params_row.addWidget(QLabel("IoU"))
        self.spin_yolo_iou = QDoubleSpinBox()
        self.spin_yolo_iou.setRange(0.1, 1.0)
        self.spin_yolo_iou.setSingleStep(0.05)
        self.spin_yolo_iou.setDecimals(2)
        self.spin_yolo_iou.setFixedWidth(65)
        self.spin_yolo_iou.valueChanged.connect(self._save_yolo_settings)
        params_row.addWidget(self.spin_yolo_iou)
        params_row.addSpacing(12)
        params_row.addWidget(QLabel("추론 간격(프레임)"))
        self.spin_yolo_every_n = QSpinBox()
        self.spin_yolo_every_n.setRange(1, 30)
        self.spin_yolo_every_n.setFixedWidth(55)
        self.spin_yolo_every_n.valueChanged.connect(self._save_yolo_settings)
        params_row.addWidget(self.spin_yolo_every_n)
        params_row.addStretch()
        layout.addLayout(params_row)

        return group

    def _browse_yolo_model(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "YOLO 모델 선택", "", "PyTorch 모델 (*.pt);;모든 파일 (*)"
        )
        if path:
            self.edit_yolo_model.setText(path)
            self._save_yolo_settings()

    def _save_yolo_settings(self) -> None:
        self.config.set("yolo", "enabled",      self.chk_yolo_enabled.isChecked())
        self.config.set("yolo", "model_path",   self.edit_yolo_model.text().strip())
        self.config.set("yolo", "confidence",   self.spin_yolo_conf.value())
        self.config.set("yolo", "iou",          self.spin_yolo_iou.value())
        self.config.set("yolo", "every_n_frame", self.spin_yolo_every_n.value())
        self.config.save()

    # ── config 연동 ───────────────────────────────────────────────────
    def load_from_config(self):
        ld = self.config.get("settings1", "lie_detector") or {}
        self.edit_lie_yolo.setText(ld.get("yolo_model_path", ""))
        self.chk_lie_enabled.setChecked(ld.get("enabled", False))
        self.chk_play_alarm.setChecked(ld.get("play_alarm", False))
        self.chk_tg_enabled.setChecked(ld.get("tg_enabled", False))
        self.edit_tg_prefix.setText(ld.get("tg_prefix", ""))
        self.edit_tg_token.setText(ld.get("tg_token", ""))
        self.edit_tg_chat.setText(ld.get("tg_chat_id", ""))
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
        # 로드 중 시그널이 _save_transparent_shape() 를 호출해 빈 경로로 덮어쓰는 것 방지
        for _w in (self.chk_transparent_enabled, self.chk_transparent_debug,
                   self.spin_transparent_board_h):
            _w.blockSignals(True)
        self.chk_transparent_enabled.setChecked(bool(ts.get("enabled", False)))
        self.chk_transparent_debug.setChecked(bool(ts.get("debug_overlay", False)))
        self.spin_transparent_board_h.setValue(int(ts.get("board_height", 500)))
        for _w in (self.chk_transparent_enabled, self.chk_transparent_debug,
                   self.spin_transparent_board_h):
            _w.blockSignals(False)
        self._refresh_transparent_status_labels()

        yolo = self.config.get("yolo") or {}
        for _w in (self.chk_yolo_enabled, self.spin_yolo_conf,
                   self.spin_yolo_iou, self.spin_yolo_every_n):
            _w.blockSignals(True)
        self.chk_yolo_enabled.setChecked(bool(yolo.get("enabled", False)))
        self.edit_yolo_model.setText(yolo.get("model_path", ""))
        self.spin_yolo_conf.setValue(float(yolo.get("confidence", 0.5)))
        self.spin_yolo_iou.setValue(float(yolo.get("iou", 0.45)))
        self.spin_yolo_every_n.setValue(int(yolo.get("every_n_frame", 2)))
        for _w in (self.chk_yolo_enabled, self.spin_yolo_conf,
                   self.spin_yolo_iou, self.spin_yolo_every_n):
            _w.blockSignals(False)

    def save_to_config(self):
        self.config.set("settings1", "lie_detector", "yolo_model_path", self.edit_lie_yolo.text().strip())
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

        self.config.set("yolo", "enabled",       self.chk_yolo_enabled.isChecked())
        self.config.set("yolo", "model_path",    self.edit_yolo_model.text().strip())
        self.config.set("yolo", "confidence",    self.spin_yolo_conf.value())
        self.config.set("yolo", "iou",           self.spin_yolo_iou.value())
        self.config.set("yolo", "every_n_frame", self.spin_yolo_every_n.value())

        self.config.set("settings1", "transparent_shape", "yolo_model_path",
                        self.edit_lie_yolo.text().strip())
        self.config.set("settings1", "transparent_shape", "board_height",
                        self.spin_transparent_board_h.value())


