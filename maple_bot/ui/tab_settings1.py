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
    QCheckBox, QSpinBox, QComboBox, QLabel, QLineEdit, QScrollArea,
    QPushButton, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.region_selector import RegionSelector
from ui.widgets import HotkeyCapture
from ui.dialog_lie_setup import LieDetectorSetupDialog


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

        # ── 퍼즐 해제 좌표 (2~5번 영역) ─────────────────────────────
        layout.addWidget(QLabel("── 퍼즐 해제 좌표 ──────────────────"))

        # 창 인식 상태 안내 라벨
        self.lbl_coord_mode = QLabel()
        self.lbl_coord_mode.setStyleSheet("font-size: 11px;")
        self._refresh_coord_mode_label()
        layout.addWidget(self.lbl_coord_mode)

        # 한번에 설정 — 2단계 버튼
        quick_row = QHBoxLayout()
        btn_capture_ss = QPushButton("📷 스크린샷 캡처")
        btn_capture_ss.setToolTip(
            "거짓말탐지기 창 전체를 드래그로 선택하면\n"
            "스크린샷을 저장하고 즉시 닫힙니다.\n"
            "이후 '이미지에서 설정' 버튼으로 열어서 영역을 지정하세요."
        )
        btn_capture_ss.clicked.connect(self._capture_lie_screenshot)

        btn_open_ss = QPushButton("🖼 이미지에서 설정")
        btn_open_ss.setToolTip(
            "저장된 스크린샷을 열어 각 영역을 드래그로 설정합니다.\n"
            "캡처 없이 게임 화면 밖에서 여유롭게 지정할 수 있습니다."
        )
        btn_open_ss.clicked.connect(self._open_lie_setup_from_file)
        self._btn_open_ss = btn_open_ss  # 저장 이미지 없을 때 비활성화 참조용

        quick_row.addWidget(btn_capture_ss)
        quick_row.addWidget(btn_open_ss)
        quick_row.addStretch()
        layout.addLayout(quick_row)
        self._solve_areas = {}   # key → QLabel
        solve_area_defs = [
            ("puzzle_area", "②  퍼즐 영역 (빈칸 탐색)"),
            ("piece_area",  "③  바 (드래그 범위)"),
            ("next_btn",    "④  >> 버튼"),
            ("confirm_btn", "⑤  확인 버튼"),
            ("done_btn",    "완료 팝업 확인"),
        ]
        for key, title in solve_area_defs:
            row = QHBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setFixedWidth(140)
            lbl_coord = QLabel("미설정")
            lbl_coord.setStyleSheet("color: gray;")
            self._solve_areas[key] = lbl_coord
            btn_set = QPushButton("📍")
            btn_set.setFixedWidth(32)
            btn_set.clicked.connect(lambda _, k=key: self._set_solve_area(k))
            btn_rst = QPushButton("✕")
            btn_rst.setFixedWidth(24)
            btn_rst.clicked.connect(lambda _, k=key: self._reset_solve_area(k))
            row.addWidget(lbl_title)
            row.addWidget(lbl_coord)
            row.addStretch()
            row.addWidget(btn_set)
            row.addWidget(btn_rst)
            layout.addLayout(row)

        # ── 좌표 프리셋 저장/불러오기 ─────────────────────────────────
        layout.addWidget(QLabel("── 좌표 프리셋 ──────────────────────"))
        preset_row = QHBoxLayout()
        self._combo_preset = QComboBox()
        self._combo_preset.setMinimumWidth(140)
        self._combo_preset.setToolTip("저장된 프리셋 목록")
        btn_preset_save = QPushButton("💾 저장")
        btn_preset_save.setFixedWidth(70)
        btn_preset_save.setToolTip("현재 좌표 + 템플릿을 프리셋으로 저장합니다.")
        btn_preset_save.clicked.connect(self._save_lie_preset)
        btn_preset_load = QPushButton("📂 불러오기")
        btn_preset_load.setFixedWidth(80)
        btn_preset_load.setToolTip("선택한 프리셋을 불러옵니다.")
        btn_preset_load.clicked.connect(self._load_lie_preset)
        btn_preset_del = QPushButton("🗑")
        btn_preset_del.setFixedWidth(30)
        btn_preset_del.setToolTip("선택한 프리셋을 삭제합니다.")
        btn_preset_del.clicked.connect(self._delete_lie_preset)
        preset_row.addWidget(self._combo_preset)
        preset_row.addWidget(btn_preset_save)
        preset_row.addWidget(btn_preset_load)
        preset_row.addWidget(btn_preset_del)
        preset_row.addStretch()
        layout.addLayout(preset_row)
        self._refresh_preset_combo()

        # 빈칸 템플릿 캡처
        blank_row = QHBoxLayout()
        self.lbl_lie_blank = QLabel("❌ 빈칸 템플릿 없음")
        self.lbl_lie_blank.setStyleSheet("color: red;")
        self._refresh_blank_label()
        btn_blank_cap = QPushButton("⑥ 빈칸 캡처")
        btn_blank_cap.setFixedWidth(90)
        btn_blank_cap.setToolTip("거짓말탐지기 빈칸 부분만 드래그해서 캡처합니다.")
        btn_blank_cap.clicked.connect(self._capture_lie_blank)
        btn_blank_del = QPushButton("삭제")
        btn_blank_del.setFixedWidth(45)
        btn_blank_del.clicked.connect(self._delete_lie_blank)
        blank_row.addWidget(self.lbl_lie_blank)
        blank_row.addStretch()
        blank_row.addWidget(btn_blank_cap)
        blank_row.addWidget(btn_blank_del)
        layout.addLayout(blank_row)

        # 해제 단축키
        solve_hk_row = QHBoxLayout()
        solve_hk_row.addWidget(QLabel("해제 단축키"))
        self.btn_lie_solve_hk = HotkeyCapture("", self._apply_lie_solve_hotkey)
        self.btn_lie_solve_hk.setFixedWidth(90)
        self.btn_lie_solve_hk.setToolTip("이 키를 누르면 설정된 좌표로 퍼즐 해제를 시도합니다.")
        solve_hk_row.addWidget(self.btn_lie_solve_hk)
        solve_hk_row.addStretch()
        layout.addLayout(solve_hk_row)

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
            ("chk_close_maple",   "메이플 스토리 종료"),
            ("chk_shutdown_pc",   "사용자 컴퓨터 종료"),
            ("chk_reconnect",     "종료 후 다른 캐릭 접속"),
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

    def _refresh_blank_label(self) -> None:
        path = "templates/lie_blank.png"
        import os
        if os.path.exists(path):
            self.lbl_lie_blank.setText("✅ 빈칸 템플릿 저장됨")
            self.lbl_lie_blank.setStyleSheet("color: green;")
        else:
            self.lbl_lie_blank.setText("❌ 빈칸 템플릿 없음")
            self.lbl_lie_blank.setStyleSheet("color: red;")

    def _capture_lie_blank(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_lie_blank)
        self._blank_selector = sel
        sel.show()

    def _save_lie_blank(self, x: int, y: int, w: int, h: int) -> None:
        os.makedirs("templates", exist_ok=True)
        with mss.mss() as sct:
            raw = sct.grab({"left": x, "top": y, "width": w, "height": h})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite("templates/lie_blank.png", img)
        self._refresh_blank_label()
        QMessageBox.information(self, "완료", f"빈칸 템플릿 저장 완료 ({w}×{h} px)")

    def _delete_lie_blank(self) -> None:
        import os
        path = "templates/lie_blank.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_blank_label()

    def _apply_lie_solve_hotkey(self, key: str) -> None:
        if not self._hk or not key:
            return
        # 해제 실행 콜백은 bot_loop에서 수행 — 여기선 key만 저장
        self.config.set("settings1", "lie_detector", "solve_hotkey", key)

    # ── 프리셋 관리 ───────────────────────────────────────────────────
    _PRESET_ROOT = "presets/lie_detector"

    def _preset_dir(self, name: str) -> str:
        return os.path.join(self._PRESET_ROOT, name)

    def _refresh_preset_combo(self) -> None:
        """저장된 프리셋 목록을 콤보박스에 갱신한다."""
        self._combo_preset.clear()
        if os.path.isdir(self._PRESET_ROOT):
            names = sorted(
                d for d in os.listdir(self._PRESET_ROOT)
                if os.path.isdir(os.path.join(self._PRESET_ROOT, d))
            )
            self._combo_preset.addItems(names)

    def _save_lie_preset(self) -> None:
        """현재 좌표 설정 + 템플릿 이미지를 프리셋으로 저장한다."""
        import json, glob, shutil
        name, ok = QInputDialog.getText(self, "프리셋 저장", "프리셋 이름을 입력하세요.")
        if not ok or not name.strip():
            return
        name = name.strip()

        preset_dir = self._preset_dir(name)
        tpl_dir    = os.path.join(preset_dir, "templates")
        os.makedirs(tpl_dir, exist_ok=True)

        # 현재 좌표 저장
        ld = self.config.get("settings1", "lie_detector") or {}
        coord_keys = ["puzzle_area", "piece_area", "next_btn", "confirm_btn", "done_btn"]
        coords = {k: ld.get(k) for k in coord_keys}
        with open(os.path.join(preset_dir, "coords.json"), "w", encoding="utf-8") as f:
            json.dump(coords, f, ensure_ascii=False, indent=2)

        # 템플릿 이미지 복사
        copied = 0
        for src in sorted(glob.glob("templates/lie_detector_*.png")):
            shutil.copy2(src, tpl_dir)
            copied += 1
        blank_src = "templates/lie_blank.png"
        if os.path.exists(blank_src):
            shutil.copy2(blank_src, tpl_dir)

        self._refresh_preset_combo()
        # 방금 저장한 항목 선택
        idx = self._combo_preset.findText(name)
        if idx >= 0:
            self._combo_preset.setCurrentIndex(idx)
        QMessageBox.information(
            self, "저장 완료",
            f"프리셋 '{name}' 저장 완료\n좌표 + 템플릿 {copied}개"
        )

    def _load_lie_preset(self) -> None:
        """선택한 프리셋을 불러와 좌표와 템플릿을 복원한다."""
        import json, glob, shutil
        name = self._combo_preset.currentText()
        if not name:
            QMessageBox.warning(self, "알림", "불러올 프리셋을 선택하세요.")
            return

        preset_dir = self._preset_dir(name)
        coord_file = os.path.join(preset_dir, "coords.json")
        if not os.path.exists(coord_file):
            QMessageBox.warning(self, "오류", f"프리셋 파일을 찾을 수 없습니다:\n{coord_file}")
            return

        # 좌표 복원
        with open(coord_file, encoding="utf-8") as f:
            coords = json.load(f)
        for key, val in coords.items():
            self.config.set("settings1", "lie_detector", key, val)
        self.config.save()
        self._refresh_solve_area_labels()

        # 템플릿 복원 — 기존 삭제 후 복사
        os.makedirs("templates", exist_ok=True)
        for old in glob.glob("templates/lie_detector_*.png"):
            os.remove(old)
        blank_dst = "templates/lie_blank.png"
        if os.path.exists(blank_dst):
            os.remove(blank_dst)

        tpl_src_dir = os.path.join(preset_dir, "templates")
        copied = 0
        if os.path.isdir(tpl_src_dir):
            for src in sorted(glob.glob(os.path.join(tpl_src_dir, "*.png"))):
                dst = os.path.join("templates", os.path.basename(src))
                shutil.copy2(src, dst)
                copied += 1

        self._refresh_template_label()
        self._refresh_blank_label()
        QMessageBox.information(
            self, "불러오기 완료",
            f"프리셋 '{name}' 복원 완료\n좌표 + 템플릿 {copied}개"
        )

    def _delete_lie_preset(self) -> None:
        """선택한 프리셋 폴더를 삭제한다."""
        import shutil
        name = self._combo_preset.currentText()
        if not name:
            QMessageBox.warning(self, "알림", "삭제할 프리셋을 선택하세요.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"프리셋 '{name}'을 삭제하시겠습니까?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        preset_dir = self._preset_dir(name)
        if os.path.isdir(preset_dir):
            shutil.rmtree(preset_dir)
        self._refresh_preset_combo()

    # ── 한번에 설정 — 2단계 흐름 ────────────────────────────────────

    _SS_IMG_PATH    = "templates/lie_setup_screenshot.png"
    _SS_REGION_PATH = "templates/lie_setup_region.json"

    def _capture_lie_screenshot(self) -> None:
        """① 드래그로 거짓말탐지기 창 전체 선택 → 스크린샷+영역 저장 후 즉시 닫힘."""
        sel = RegionSelector()
        sel.region_selected.connect(self._save_lie_screenshot)
        self._quick_selector = sel
        sel.show()

    def _save_lie_screenshot(self, x: int, y: int, w: int, h: int) -> None:
        """선택 영역을 스크린샷으로 저장한다."""
        import json as _json
        os.makedirs("templates", exist_ok=True)
        with mss.mss() as sct:
            raw = sct.grab({"left": x, "top": y, "width": w, "height": h})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite(self._SS_IMG_PATH, img)
        with open(self._SS_REGION_PATH, "w", encoding="utf-8") as f:
            _json.dump({"x": x, "y": y, "w": w, "h": h}, f)
        QMessageBox.information(
            self, "캡처 완료",
            f"스크린샷 저장 완료 ({w}×{h} px)\n"
            "'이미지에서 설정' 버튼으로 영역을 지정하세요."
        )

    def _open_lie_setup_from_file(self) -> None:
        """② 저장된 스크린샷을 열어 다이얼로그에서 하위 영역 설정."""
        import json as _json
        if not os.path.exists(self._SS_IMG_PATH) or not os.path.exists(self._SS_REGION_PATH):
            QMessageBox.warning(
                self, "스크린샷 없음",
                "먼저 '📷 스크린샷 캡처' 버튼으로 스크린샷을 저장해 주세요."
            )
            return

        img = cv2.imread(self._SS_IMG_PATH)
        if img is None:
            QMessageBox.warning(self, "오류", f"스크린샷 파일을 읽을 수 없습니다.\n{self._SS_IMG_PATH}")
            return

        with open(self._SS_REGION_PATH, encoding="utf-8") as f:
            rj = _json.load(f)
        full_region = (rj["x"], rj["y"], rj["w"], rj["h"])

        existing = self.config.get("settings1", "lie_detector") or {}
        dlg = LieDetectorSetupDialog(
            full_region=full_region,
            screenshot=img,
            existing=existing,
            parent=self,
        )
        if not dlg.exec():
            return

        # 결과 처리 — 키별 특수 처리
        saved_mode = "absolute"
        for key, coords in dlg.result_coords.items():
            if key == "region":
                # 감지 영역 → 상대좌표 변환 후 저장
                ax, ay, aw, ah = coords
                rx, ry, rw, rh, mode = self._abs_to_rel(ax, ay, aw, ah)
                self.config.set("settings1", "lie_detector", "region", [rx, ry, rw, rh])
                saved_mode = mode
                tag = " [상대]" if mode == "relative" else " [절대]"
                self.lbl_lie_region.setText(f"감지 영역: X={rx} Y={ry} W={rw} H={rh}{tag}")
                self.lbl_lie_region.setStyleSheet("color: green;")
            elif key == "lie_blank":
                # 빈칸 → 전체 스크린샷에서 해당 영역 크롭 → templates/lie_blank.png
                fx, fy, fw, fh = full_region
                ax, ay, aw, ah = coords
                ix = ax - fx
                iy = ay - fy
                ix = max(0, min(ix, img.shape[1] - 1))
                iy = max(0, min(iy, img.shape[0] - 1))
                aw = min(aw, img.shape[1] - ix)
                ah = min(ah, img.shape[0] - iy)
                if aw > 0 and ah > 0:
                    crop = img[iy:iy + ah, ix:ix + aw]
                    cv2.imwrite("templates/lie_blank.png", crop)
                    self._refresh_blank_label()
            else:
                # 나머지 퍼즐 좌표 — 상대좌표 변환 후 저장
                ax, ay, aw, ah = coords
                rx, ry, rw, rh, mode = self._abs_to_rel(ax, ay, aw, ah)
                self.config.set("settings1", "lie_detector", key, [rx, ry, rw, rh])
                saved_mode = mode

        self.config.set("settings1", "lie_detector", "coord_mode", saved_mode)
        self.config.save()
        self._refresh_solve_area_labels()
        self._refresh_coord_mode_label()

    # ── 창 기반 상대좌표 유틸 ────────────────────────────────────────
    def _game_window_title(self) -> str:
        return self.config.get("settings2", "game_window_title") or "MapleStory"

    def _abs_to_rel(self, x: int, y: int, w: int, h: int) -> tuple:
        """절대좌표 → 게임창 클라이언트 기준 상대좌표.
        게임 창을 찾지 못하면 절대좌표 그대로 반환한다."""
        import win32gui
        try:
            hwnd = win32gui.FindWindow(None, self._game_window_title())
            if hwnd:
                ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
                return x - ox, y - oy, w, h, "relative"
        except Exception:
            pass
        return x, y, w, h, "absolute"

    def _refresh_coord_mode_label(self) -> None:
        """퍼즐 좌표 섹션 상단 안내 라벨을 현재 창 인식 상태에 맞게 갱신한다."""
        import win32gui
        title = self._game_window_title()
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
                self.lbl_coord_mode.setText(
                    f"🟢 '{title}' 창 인식됨 (X={ox}, Y={oy}) — 좌표를 상대좌표로 저장합니다."
                )
                self.lbl_coord_mode.setStyleSheet("color: green; font-size: 11px;")
                return
        except Exception:
            pass
        self.lbl_coord_mode.setText(
            f"🟡 '{title}' 창 미인식 — 절대좌표로 저장합니다. (창 이동 시 재설정 필요)"
        )
        self.lbl_coord_mode.setStyleSheet("color: #b8860b; font-size: 11px;")

    def _refresh_solve_area_labels(self) -> None:
        """config에서 퍼즐 좌표를 다시 읽어 라벨을 갱신한다."""
        ld = self.config.get("settings1", "lie_detector") or {}
        mode = ld.get("coord_mode", "absolute")
        tag  = " [상대]" if mode == "relative" else " [절대]"
        for key, lbl in self._solve_areas.items():
            coords = ld.get(key)
            if coords and len(coords) == 4:
                x, y, w, h = coords
                lbl.setText(f"X={x} Y={y} W={w} H={h}{tag}")
                lbl.setStyleSheet("color: green;")
            else:
                lbl.setText("미설정")
                lbl.setStyleSheet("color: gray;")

    def _set_solve_area(self, area_key: str) -> None:
        self._pending_solve_area = area_key
        sel = RegionSelector()
        sel.region_selected.connect(self._save_solve_area)
        self._solve_selector = sel
        sel.show()

    def _save_solve_area(self, x: int, y: int, w: int, h: int) -> None:
        key = self._pending_solve_area
        rx, ry, rw, rh, mode = self._abs_to_rel(x, y, w, h)
        self.config.set("settings1", "lie_detector", key, [rx, ry, rw, rh])
        self.config.set("settings1", "lie_detector", "coord_mode", mode)
        self.config.save()
        tag = " [상대]" if mode == "relative" else " [절대]"
        self._solve_areas[key].setText(f"X={rx} Y={ry} W={rw} H={rh}{tag}")
        self._solve_areas[key].setStyleSheet("color: green;")

    def _reset_solve_area(self, area_key: str) -> None:
        self.config.set("settings1", "lie_detector", area_key, None)
        self.config.save()
        self._solve_areas[area_key].setText("미설정")
        self._solve_areas[area_key].setStyleSheet("color: gray;")

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
        # 1. 영역 config 저장
        self.config.set("settings1", "lie_detector", "region", [x, y, w, h])
        self.config.save()
        self.lbl_lie_region.setText(f"감지 영역: X={x} Y={y} W={w} H={h}")
        self.lbl_lie_region.setStyleSheet("color: green;")

        # 2. 동일 영역을 템플릿으로도 자동 저장
        import glob
        os.makedirs("templates", exist_ok=True)
        existing = sorted(glob.glob("templates/lie_detector_*.png"))
        next_num = len(existing) + 1
        path = f"templates/lie_detector_{next_num}.png"
        with mss.mss() as sct:
            raw = sct.grab({"left": x, "top": y, "width": w, "height": h})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite(path, img)
        self._refresh_template_label()
        QMessageBox.information(
            self, "영역 설정 완료",
            f"감지 영역 저장 완료\n"
            f"템플릿 {next_num}번으로 자동 캡처됨 ({w}×{h} px)"
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
        self.chk_close_maple.setChecked(ld.get("close_maple", False))
        self.chk_shutdown_pc.setChecked(ld.get("shutdown_pc", False))
        self.chk_reconnect.setChecked(ld.get("reconnect_after", False))
        self.chk_tg_enabled.setChecked(ld.get("tg_enabled", False))
        self.edit_tg_prefix.setText(ld.get("tg_prefix", ""))
        self.edit_tg_token.setText(ld.get("tg_token", ""))
        self.edit_tg_chat.setText(ld.get("tg_chat_id", ""))
        region = ld.get("region")
        if region and len(region) == 4:
            x, y, w, h = region
            self.lbl_lie_region.setText(f"감지 영역: X={x} Y={y} W={w} H={h}")
            self.lbl_lie_region.setStyleSheet("color: green;")
        else:
            self.lbl_lie_region.setText("감지 영역: 전체 화면")
            self.lbl_lie_region.setStyleSheet("color: gray;")
        hk_key = ld.get("region_hotkey", "")
        if hk_key:
            self.btn_lie_region_hk.set_key(hk_key)
        self._refresh_solve_area_labels()
        self._refresh_coord_mode_label()
        solve_hk = ld.get("solve_hotkey", "")
        if solve_hk:
            self.btn_lie_solve_hk.set_key(solve_hk)
        self._refresh_blank_label()

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


    def save_to_config(self):
        self.config.set("settings1", "lie_detector", "enabled",       self.chk_lie_enabled.isChecked())
        self.config.set("settings1", "lie_detector", "play_alarm",    self.chk_play_alarm.isChecked())
        self.config.set("settings1", "lie_detector", "close_maple",   self.chk_close_maple.isChecked())
        self.config.set("settings1", "lie_detector", "shutdown_pc",   self.chk_shutdown_pc.isChecked())
        self.config.set("settings1", "lie_detector", "reconnect_after", self.chk_reconnect.isChecked())
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


