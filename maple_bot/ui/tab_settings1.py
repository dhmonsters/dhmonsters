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
        layout.addWidget(self._build_yolo_capture_group())
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

        # Planet Solver 버튼 행
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton
        row = QHBoxLayout()
        btn_open = QPushButton("🪐 Planet Solver 열기")
        btn_open.setToolTip("로컬 M1+M2 모델로 투명도형 자동 추적 창을 엽니다 (서버 인증 없음)")
        btn_open.clicked.connect(self._open_planet_solver)
        row.addWidget(btn_open)
        btn_orig = QPushButton("원본 exe 실행")
        btn_orig.setToolTip("Planet_solver_v1.0.5.exe 를 직접 실행합니다 (서버 인증 필요)")
        btn_orig.clicked.connect(self._open_planet_solver_exe)
        row.addWidget(btn_orig)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _open_planet_solver(self):
        """로컬 ncnn M1+M2 모델을 사용하는 자체 Planet Solver 창을 연다.

        서버 인증 없이 즉시 창이 열리며, 창 내 ▶ 시작 버튼으로 추적을 시작한다.
        """
        from ui.planet_solver_window import PlanetSolverWindow
        if not hasattr(self, "_planet_win") or self._planet_win is None:
            self._planet_win = PlanetSolverWindow(config=self.config)
        self._planet_win.show()
        self._planet_win.raise_()
        self._planet_win.activateWindow()

    def _open_planet_solver_exe(self):
        """Planet_solver_v1.0.5.exe 를 직접 실행한다 (서버 인증 포함, 원본 동작 확인용)."""
        import os, subprocess
        _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exe = os.path.join(_here, "_planet_solver_extract", "Planet_solver_v1.0.5.exe")
        if not os.path.exists(exe):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "파일 없음", f"찾을 수 없습니다:\n{exe}")
            return
        try:
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "실행 오류", str(e))

    def _save_transparent_shape(self):
        self.config.set("settings1", "transparent_shape", "enabled",
                        self.chk_transparent_enabled.isChecked())
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

    # ── YOLO 학습 데이터 캡처 ─────────────────────────────────────────
    # 저장 경로 고정
    CAPTURE_SAVE_DIR = r"C:\Users\PC\Desktop\02_work\05_AI\yolo_train\dataset\raw"

    def _build_yolo_capture_group(self):
        import threading
        from PyQt6.QtWidgets import QDoubleSpinBox
        group = QGroupBox("YOLO 학습 데이터 캡처")
        layout = QVBoxLayout(group)

        # 경로 표시 (고정)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("저장 경로"))
        lbl_path = QLabel(self.CAPTURE_SAVE_DIR)
        lbl_path.setStyleSheet("color: #6bcb77; font-size: 10px;")
        lbl_path.setWordWrap(True)
        path_row.addWidget(lbl_path, stretch=1)
        layout.addLayout(path_row)

        # ── 시작 단축키 ──
        hk_start_row = QHBoxLayout()
        hk_start_row.addWidget(QLabel("시작 단축키"))
        self.edit_capture_key_start = QLineEdit()
        self.edit_capture_key_start.setPlaceholderText("예: f6, ins")
        self.edit_capture_key_start.setFixedWidth(90)
        hk_start_row.addWidget(self.edit_capture_key_start)
        btn_reg_start = QPushButton("등록")
        btn_reg_start.setFixedWidth(50)
        btn_reg_start.clicked.connect(self._register_capture_start_hk)
        hk_start_row.addWidget(btn_reg_start)
        self.lbl_capture_start_status = QLabel("")
        self.lbl_capture_start_status.setStyleSheet("color: #6bcb77; font-size: 10px;")
        hk_start_row.addWidget(self.lbl_capture_start_status)
        hk_start_row.addStretch()
        layout.addLayout(hk_start_row)

        # ── 멈춤 단축키 ──
        hk_stop_row = QHBoxLayout()
        hk_stop_row.addWidget(QLabel("멈춤 단축키"))
        self.edit_capture_key_stop = QLineEdit()
        self.edit_capture_key_stop.setPlaceholderText("예: f7, del")
        self.edit_capture_key_stop.setFixedWidth(90)
        hk_stop_row.addWidget(self.edit_capture_key_stop)
        btn_reg_stop = QPushButton("등록")
        btn_reg_stop.setFixedWidth(50)
        btn_reg_stop.clicked.connect(self._register_capture_stop_hk)
        hk_stop_row.addWidget(btn_reg_stop)
        self.lbl_capture_stop_status = QLabel("")
        self.lbl_capture_stop_status.setStyleSheet("color: #f44336; font-size: 10px;")
        hk_stop_row.addWidget(self.lbl_capture_stop_status)
        hk_stop_row.addStretch()
        layout.addLayout(hk_stop_row)

        # ── 간격 + 상태 ──
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("간격"))
        self.spin_auto_interval = QDoubleSpinBox()
        self.spin_auto_interval.setRange(0.1, 60.0)
        self.spin_auto_interval.setSingleStep(0.1)
        self.spin_auto_interval.setDecimals(1)
        self.spin_auto_interval.setValue(0.5)
        self.spin_auto_interval.setSuffix(" 초")
        self.spin_auto_interval.setFixedWidth(75)
        bottom_row.addWidget(self.spin_auto_interval)
        bottom_row.addSpacing(12)
        self.lbl_capture_count = QLabel("캡처: 0장")
        self.lbl_capture_count.setStyleSheet("font-size: 10px;")
        bottom_row.addWidget(self.lbl_capture_count)
        bottom_row.addStretch()
        layout.addLayout(bottom_row)

        # 내부 상태
        self._capture_count = 0
        self._auto_capture_active = False
        self._auto_capture_thread = None
        self._auto_capture_stop = threading.Event()

        return group

    def _get_capture_folder(self) -> str:
        os.makedirs(self.CAPTURE_SAVE_DIR, exist_ok=True)
        return self.CAPTURE_SAVE_DIR

    def _next_capture_index(self, folder: str) -> int:
        existing = [f for f in os.listdir(folder) if f.endswith(".png")]
        return len(existing)

    def _register_capture_start_hk(self) -> None:
        if self._hk is None:
            QMessageBox.warning(self, "오류", "HotkeyManager가 초기화되지 않았습니다.")
            return
        key = self.edit_capture_key_start.text().strip()
        if not key:
            return
        err = self._hk.register("yolo_capture_start", key, self._start_auto_capture)
        if err:
            QMessageBox.warning(self, "단축키 오류", err)
        else:
            self.lbl_capture_start_status.setText(f"[{key.upper()}] 등록됨")
            self.config.set("yolo_capture", "hotkey_start", key)
            self.config.set("yolo_capture", "auto_interval_sec", self.spin_auto_interval.value())
            self.config.save()

    def _register_capture_stop_hk(self) -> None:
        if self._hk is None:
            QMessageBox.warning(self, "오류", "HotkeyManager가 초기화되지 않았습니다.")
            return
        key = self.edit_capture_key_stop.text().strip()
        if not key:
            return
        err = self._hk.register("yolo_capture_stop", key, self._stop_auto_capture)
        if err:
            QMessageBox.warning(self, "단축키 오류", err)
        else:
            self.lbl_capture_stop_status.setText(f"[{key.upper()}] 등록됨")
            self.config.set("yolo_capture", "hotkey_stop", key)
            self.config.save()

    def _do_capture(self) -> None:
        folder = self._get_capture_folder()
        idx = self._next_capture_index(folder) + 1
        path = os.path.join(folder, f"{idx:05d}.png")
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            cv2.imwrite(path, cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR))
        self._capture_count += 1
        self.lbl_capture_count.setText(f"캡처: {self._capture_count}장  ({os.path.basename(path)})")

    def _start_auto_capture(self) -> None:
        import threading
        if self._auto_capture_active:
            return
        self._auto_capture_stop.clear()
        interval = self.spin_auto_interval.value()

        def _loop():
            while not self._auto_capture_stop.is_set():
                self._do_capture()
                self._auto_capture_stop.wait(interval)

        self._auto_capture_thread = threading.Thread(target=_loop, daemon=True)
        self._auto_capture_thread.start()
        self._auto_capture_active = True
        self.lbl_capture_count.setStyleSheet("color: #6bcb77; font-size: 10px;")

    def _stop_auto_capture(self) -> None:
        self._auto_capture_stop.set()
        self._auto_capture_active = False
        self.lbl_capture_count.setStyleSheet("font-size: 10px;")

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
        self.chk_transparent_enabled.blockSignals(True)
        self.chk_transparent_enabled.setChecked(bool(ts.get("enabled", False)))
        self.chk_transparent_enabled.blockSignals(False)

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

        yolo_cap = self.config.get("yolo_capture") or {}
        self.spin_auto_interval.setValue(float(yolo_cap.get("auto_interval_sec", 0.5)))
        _key_start = yolo_cap.get("hotkey_start", "")
        _key_stop  = yolo_cap.get("hotkey_stop", "")
        if _key_start:
            self.edit_capture_key_start.setText(_key_start)
            if self._hk is not None:
                self._hk.register("yolo_capture_start", _key_start, self._start_auto_capture)
                self.lbl_capture_start_status.setText(f"[{_key_start.upper()}] 등록됨")
        if _key_stop:
            self.edit_capture_key_stop.setText(_key_stop)
            if self._hk is not None:
                self._hk.register("yolo_capture_stop", _key_stop, self._stop_auto_capture)
                self.lbl_capture_stop_status.setText(f"[{_key_stop.upper()}] 등록됨")

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

        self.config.set("yolo", "enabled",       self.chk_yolo_enabled.isChecked())
        self.config.set("yolo", "model_path",    self.edit_yolo_model.text().strip())
        self.config.set("yolo", "confidence",    self.spin_yolo_conf.value())
        self.config.set("yolo", "iou",           self.spin_yolo_iou.value())
        self.config.set("yolo", "every_n_frame", self.spin_yolo_every_n.value())

        self.config.set("settings1", "transparent_shape", "enabled",
                        self.chk_transparent_enabled.isChecked())


