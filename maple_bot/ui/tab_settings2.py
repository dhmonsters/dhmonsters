# 설정2 탭 - 사냥 일시정지/매크로예약/잡템 자동판매 UI
from __future__ import annotations
import glob
import os

import cv2
import mss
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QListWidget, QDialog, QDialogButtonBox,
    QScrollArea, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal

from ui.region_selector import RegionSelector


class TabSettings2(QWidget):
    _junk_status_sig    = pyqtSignal(str)   # 배경 스레드 → 메인 스레드 상태 전달
    _junk_done_sig      = pyqtSignal()      # 판매 완료 → 버튼 재활성화
    _update_result_sig  = pyqtSignal(object)  # 업데이트 확인 결과 (dict | None)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._junk_status_sig.connect(self._on_junk_status)
        self._junk_done_sig.connect(lambda: self.btn_junk_run.setEnabled(True))
        self._update_result_sig.connect(self._on_update_result)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        layout.addWidget(self._build_update_group())
        layout.addWidget(self._build_game_window_group())
        layout.addWidget(self._build_junk_sell_group())
        layout.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.load_from_config()

    # ── 앱 정보 / 업데이트 ───────────────────────────────────────────
    def _build_update_group(self) -> QGroupBox:
        from core.updater import get_current_version
        group = QGroupBox("앱 정보 / 업데이트")
        row = QHBoxLayout(group)

        self.lbl_cur_version = QLabel(f"현재 버전: {get_current_version()}")
        row.addWidget(self.lbl_cur_version)
        row.addSpacing(16)

        self.btn_check_update = QPushButton("🔄 업데이트 확인")
        self.btn_check_update.setFixedWidth(130)
        self.btn_check_update.clicked.connect(self._check_update_manually)
        row.addWidget(self.btn_check_update)
        row.addStretch()
        return group

    def _check_update_manually(self) -> None:
        """수동 업데이트 확인 — 백그라운드 스레드에서 API 호출 후 시그널로 결과 전달."""
        import threading
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("확인 중...")

        def _worker():
            from core.updater import check_for_update
            info = check_for_update()
            self._update_result_sig.emit(info)  # None or dict

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_result(self, info) -> None:
        """업데이트 확인 결과 처리 (메인 스레드)."""
        self.btn_check_update.setEnabled(True)
        self.btn_check_update.setText("🔄 업데이트 확인")
        if info:
            from ui.dialog_update import UpdateDialog
            dlg = UpdateDialog(info, parent=self)
            dlg.exec()
        else:
            QMessageBox.information(self, "업데이트 확인", "현재 최신 버전입니다.")

    # ── 게임 창 설정 ─────────────────────────────────────────────────
    def _build_game_window_group(self) -> QGroupBox:
        group = QGroupBox("게임 창 설정")
        layout = QVBoxLayout(group)

        note = QLabel(
            "봇이 포커스를 맞출 게임 창의 정확한 제목을 입력하세요.\n"
            "🔍 창 목록 버튼으로 현재 열린 창을 확인할 수 있습니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(note)

        row = QHBoxLayout()
        row.addWidget(QLabel("창 제목"))
        self.edit_window_title = QLineEdit()
        self.edit_window_title.setPlaceholderText("MapleStory")
        self.edit_window_title.setFixedWidth(200)
        row.addWidget(self.edit_window_title)

        btn_list = QPushButton("🔍 창 목록")
        btn_list.setFixedWidth(80)
        btn_list.clicked.connect(self._show_window_list)
        row.addWidget(btn_list)

        btn_save = QPushButton("저장")
        btn_save.setFixedWidth(55)
        btn_save.clicked.connect(self._save_window_title)
        row.addWidget(btn_save)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _show_window_list(self) -> None:
        """현재 열린 창 제목 목록을 팝업으로 표시. 더블클릭하면 자동 입력."""
        import win32gui
        titles: list[str] = []

        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd).strip()
                if t:
                    titles.append(t)

        win32gui.EnumWindows(_cb, None)
        titles = sorted(set(titles))

        dlg = QDialog(self)
        dlg.setWindowTitle("열린 창 목록 — 더블클릭하면 자동 입력됩니다")
        dlg.resize(420, 380)
        lst = QListWidget()
        lst.addItems(titles)

        def _pick(item):
            self.edit_window_title.setText(item.text())
            dlg.accept()

        lst.itemDoubleClicked.connect(_pick)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)

        lay = QVBoxLayout(dlg)
        lay.addWidget(lst)
        lay.addWidget(btns)
        dlg.exec()

    def _save_window_title(self) -> None:
        title = self.edit_window_title.text().strip()
        if not title:
            QMessageBox.warning(self, "오류", "창 제목을 입력하세요.")
            return
        self.config.set("settings2", "game_window_title", title)
        self.config.save()
        QMessageBox.information(self, "저장", f"게임 창 제목이 '{title}'로 저장되었습니다.\n봇 재시작 후 적용됩니다.")

    # ── 잡템 자동 판매 ────────────────────────────────────────────────
    def _build_junk_sell_group(self):
        group = QGroupBox("잡템 자동 판매")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("── 좌표 설정 ──────────────────────"))

        # (설정키, 표시명, 영역여부)
        coord_defs = [
            ("cash_tab",     "캐시 탭",       False),
            ("first_slot",   "첫번째 슬롯",    False),
            ("shop_etc_tab", "상점 기타 탭",   False),
            ("shop_area",    "상점 목록 영역",  True),
            ("scroll_pos",   "스크롤 위치",     False),
            ("sell_confirm", "판매 확인 버튼",  False),
        ]
        self._junk_coord_lbls: dict[str, QLabel] = {}

        for key, title, is_area in coord_defs:
            row = QHBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setFixedWidth(110)
            lbl_val = QLabel("미설정")
            lbl_val.setStyleSheet("color: gray; font-size: 10px;")
            self._junk_coord_lbls[key] = lbl_val

            btn_set = QPushButton("📍 드래그" if is_area else "📍")
            btn_set.setFixedWidth(78 if is_area else 32)
            btn_set.clicked.connect(lambda _, k=key, a=is_area: self._set_junk_coord(k, a))

            btn_rst = QPushButton("✕")
            btn_rst.setFixedWidth(24)
            btn_rst.clicked.connect(lambda _, k=key: self._reset_junk_coord(k))

            row.addWidget(lbl_title)
            row.addWidget(lbl_val)
            row.addStretch()
            row.addWidget(btn_set)
            row.addWidget(btn_rst)
            layout.addLayout(row)

        layout.addWidget(QLabel("── 판매 아이템 템플릿 ──────────────────"))

        tpl_row = QHBoxLayout()
        self.lbl_junk_tpl = QLabel("없음")
        self.lbl_junk_tpl.setStyleSheet("color: gray;")
        btn_tpl_add = QPushButton("+ 추가 캡처")
        btn_tpl_add.setFixedWidth(90)
        btn_tpl_add.setToolTip("판매할 아이템 아이콘 부분을 드래그해서 등록합니다.")
        btn_tpl_add.clicked.connect(self._capture_junk_template)
        btn_tpl_del = QPushButton("전체 삭제")
        btn_tpl_del.setFixedWidth(70)
        btn_tpl_del.clicked.connect(self._clear_junk_templates)
        tpl_row.addWidget(self.lbl_junk_tpl)
        tpl_row.addStretch()
        tpl_row.addWidget(btn_tpl_add)
        tpl_row.addWidget(btn_tpl_del)
        layout.addLayout(tpl_row)
        self._refresh_junk_tpl_label()

        # 판매 실행
        run_row = QHBoxLayout()
        self.btn_junk_run = QPushButton("▶ 판매 실행")
        self.btn_junk_run.setFixedWidth(120)
        self.btn_junk_run.clicked.connect(self._run_junk_sell)
        self.lbl_junk_status = QLabel("대기 중")
        self.lbl_junk_status.setStyleSheet("color: gray; font-size: 10px;")
        run_row.addWidget(self.btn_junk_run)
        run_row.addWidget(self.lbl_junk_status)
        run_row.addStretch()
        layout.addLayout(run_row)

        return group

    # ── 잡템 좌표 설정 ────────────────────────────────────────────────
    def _set_junk_coord(self, key: str, is_area: bool) -> None:
        self._pending_junk_key  = key
        self._pending_junk_area = is_area
        sel = RegionSelector()
        sel.region_selected.connect(self._save_junk_coord)
        self._junk_selector = sel
        sel.show()

    def _save_junk_coord(self, x: int, y: int, w: int, h: int) -> None:
        key     = self._pending_junk_key
        is_area = self._pending_junk_area
        if is_area:
            val  = [x, y, w, h]
            text = f"X={x} Y={y} W={w} H={h}"
        else:
            cx, cy = x + w // 2, y + h // 2
            val  = [cx, cy]
            text = f"X={cx} Y={cy}"
        self.config.set("settings2", "junk_sell", key, val)
        self.config.save()
        lbl = self._junk_coord_lbls.get(key)
        if lbl:
            lbl.setText(text)
            lbl.setStyleSheet("color: green; font-size: 10px;")

    def _reset_junk_coord(self, key: str) -> None:
        self.config.set("settings2", "junk_sell", key, None)
        self.config.save()
        lbl = self._junk_coord_lbls.get(key)
        if lbl:
            lbl.setText("미설정")
            lbl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 잡템 템플릿 관리 ─────────────────────────────────────────────
    def _capture_junk_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_junk_template)
        self._junk_tpl_selector = sel
        sel.show()

    def _save_junk_template(self, x: int, y: int, w: int, h: int) -> None:
        os.makedirs("templates/junk", exist_ok=True)
        existing = sorted(glob.glob("templates/junk/item_*.png"))
        next_num = len(existing) + 1
        path = f"templates/junk/item_{next_num}.png"
        with mss.mss() as sct:
            raw = sct.grab({"left": x, "top": y, "width": w, "height": h})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite(path, img)
        self._refresh_junk_tpl_label()
        QMessageBox.information(self, "완료", f"아이템 템플릿 {next_num}번 저장 완료 ({w}×{h}px)")

    def _clear_junk_templates(self) -> None:
        files = glob.glob("templates/junk/item_*.png")
        if not files:
            QMessageBox.information(self, "알림", "삭제할 템플릿이 없습니다.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인", f"템플릿 {len(files)}개를 모두 삭제하시겠습니까?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for f in files:
            os.remove(f)
        self._refresh_junk_tpl_label()

    def _refresh_junk_tpl_label(self) -> None:
        files = glob.glob("templates/junk/item_*.png")
        count = len(files)
        if count:
            self.lbl_junk_tpl.setText(f"✅ {count}개 등록됨")
            self.lbl_junk_tpl.setStyleSheet("color: green;")
        else:
            self.lbl_junk_tpl.setText("없음 (+ 추가 캡처로 등록하세요)")
            self.lbl_junk_tpl.setStyleSheet("color: gray;")

    # ── 판매 실행 ────────────────────────────────────────────────────
    def _run_junk_sell(self) -> None:
        import threading
        from core.screen_reader import ScreenReader
        from core.input_controller import InputController
        from core.junk_seller import sell_junk

        self.btn_junk_run.setEnabled(False)
        self._junk_status_sig.emit("판매 시작 중...")

        screen     = ScreenReader()
        input_ctrl = InputController("")

        def _run():
            try:
                sell_junk(
                    self.config,
                    screen,
                    input_ctrl,
                    lambda msg: self._junk_status_sig.emit(msg),
                )
            except Exception as e:
                self._junk_status_sig.emit(f"오류: {e}")
            finally:
                self._junk_done_sig.emit()

        threading.Thread(target=_run, daemon=True).start()

    def _on_junk_status(self, msg: str) -> None:
        self.lbl_junk_status.setText(msg)

    # ── config 연동 ───────────────────────────────────────────────────
    def load_from_config(self):
        title = self.config.get("settings2", "game_window_title") or "MapleStory"
        self.edit_window_title.setText(title)

        # 잡템 판매 좌표 라벨 갱신
        junk = self.config.get("settings2", "junk_sell") or {}
        for key, lbl in self._junk_coord_lbls.items():
            v = junk.get(key)
            if v and len(v) == 4:
                lbl.setText(f"X={v[0]} Y={v[1]} W={v[2]} H={v[3]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
            elif v and len(v) == 2:
                lbl.setText(f"X={v[0]} Y={v[1]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")

    def save_to_config(self):
        title = self.edit_window_title.text().strip()
        if title:
            self.config.set("settings2", "game_window_title", title)
