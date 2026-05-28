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
    QScrollArea, QMessageBox, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
)
from PyQt6.QtCore import pyqtSignal

from ui.region_selector import RegionSelector


class TabSettings2(QWidget):
    _junk_status_sig    = pyqtSignal(str)   # 배경 스레드 → 메인 스레드 상태 전달
    _junk_done_sig      = pyqtSignal()      # 판매 완료 → 버튼 재활성화
    _shop_done_sig      = pyqtSignal()      # 상점열기 완료 → 버튼 재활성화
    _update_result_sig  = pyqtSignal(object)  # 업데이트 확인 결과 (dict | None)

    @staticmethod
    def _to_physical(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
        """PyQt6 논리 픽셀 → mss 물리 픽셀 변환. logical_to_physical() 위임."""
        from ui.region_selector import logical_to_physical
        return logical_to_physical(x, y, w, h)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._log_cb = None   # 메인 로그창 콜백 (MainWindow에서 주입)
        self._junk_status_sig.connect(self._on_junk_status)
        self._junk_done_sig.connect(lambda: self.btn_junk_run.setEnabled(True))
        self._shop_done_sig.connect(lambda: self.btn_open_shop.setEnabled(True))
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
            import logging
            try:
                from core.updater import check_for_update
                info = check_for_update()
            except Exception as e:
                logging.getLogger(__name__).error("업데이트 확인 실패: %s", e)
                info = None
            self._update_result_sig.emit(info)

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

        # 좌표 모드 (상대/절대)
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("좌표 모드"))
        self.combo_coord_mode = QComboBox()
        self.combo_coord_mode.addItems(["절대 좌표 (absolute)", "상대 좌표 (relative)"])
        current_mode = self.config.get("coord_mode") or "absolute"
        self.combo_coord_mode.setCurrentIndex(0 if current_mode == "absolute" else 1)
        self.combo_coord_mode.setFixedWidth(200)
        coord_row.addWidget(self.combo_coord_mode)
        btn_coord_save = QPushButton("저장")
        btn_coord_save.setFixedWidth(55)
        btn_coord_save.clicked.connect(self._save_coord_mode)
        coord_row.addWidget(btn_coord_save)
        coord_row.addStretch()
        layout.addLayout(coord_row)

        coord_note = QLabel(
            "상대 좌표: 게임 창 이동 시 좌표 재설정 불필요. 위 '창 제목'이 정확히 설정돼 있어야 합니다."
        )
        coord_note.setWordWrap(True)
        coord_note.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(coord_note)

        return group

    def _save_coord_mode(self) -> None:
        mode = "relative" if self.combo_coord_mode.currentIndex() == 1 else "absolute"
        self.config.set("coord_mode", mode)
        self.config.save()
        QMessageBox.information(self, "저장", f"좌표 모드가 '{mode}'로 저장되었습니다.")

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
        self._junk_coord_lbls: dict[str, QLabel] = {}

        # ══ ① 상점 열기 섹션 ══════════════════════════════════════════
        layout.addWidget(QLabel("─ ① 상점 열기 설정 ─────────────────────"))

        # 인벤토리 키 설정
        inv_key_row = QHBoxLayout()
        lbl_inv_key = QLabel("인벤토리 키")
        lbl_inv_key.setFixedWidth(90)
        self.edit_inventory_key = QLineEdit("i")
        self.edit_inventory_key.setFixedWidth(50)
        self.edit_inventory_key.setMaxLength(10)
        self.edit_inventory_key.setToolTip(
            "인벤토리를 여는 단축키입니다. (기본: i)\n"
            "인벤토리가 이미 열려있으면 키를 누르지 않습니다."
        )
        inv_key_row.addWidget(lbl_inv_key)
        inv_key_row.addWidget(self.edit_inventory_key)
        inv_key_row.addStretch()
        layout.addLayout(inv_key_row)

        # 캐시탭 기본 이미지 (비활성 상태 — 클릭 전 회색)
        cash_tpl_row = QHBoxLayout()
        lbl_ct = QLabel("캐시탭 이미지")
        lbl_ct.setFixedWidth(100)
        self.lbl_cash_tpl = QLabel("미등록")
        self.lbl_cash_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_cash_tpl = QPushButton("📷 캡처")
        btn_cash_tpl.setFixedWidth(65)
        btn_cash_tpl.setToolTip("캐시탭 버튼을 드래그해서 저장합니다. (클릭 전 기본 상태)")
        btn_cash_tpl.clicked.connect(self._capture_cash_tab_template)
        btn_cash_tpl_del = QPushButton("✕")
        btn_cash_tpl_del.setFixedWidth(24)
        btn_cash_tpl_del.clicked.connect(self._clear_cash_tab_template)
        cash_tpl_row.addWidget(lbl_ct)
        cash_tpl_row.addWidget(self.lbl_cash_tpl)
        cash_tpl_row.addStretch()
        cash_tpl_row.addWidget(btn_cash_tpl)
        cash_tpl_row.addWidget(btn_cash_tpl_del)
        layout.addLayout(cash_tpl_row)
        self._refresh_cash_tpl_label()

        # 캐시탭 활성 이미지 (클릭 후 분홍색 상태 — 이걸 감지해야 상점이 열린 것)
        cash_act_row = QHBoxLayout()
        lbl_ca = QLabel("캐시탭 활성 이미지")
        lbl_ca.setFixedWidth(100)
        self.lbl_cash_active_tpl = QLabel("미등록")
        self.lbl_cash_active_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_cash_act = QPushButton("📷 캡처")
        btn_cash_act.setFixedWidth(65)
        btn_cash_act.setToolTip(
            "캐시탭을 클릭했을 때 분홍색/하이라이트 상태를 드래그해서 저장합니다.\n"
            "이 이미지가 감지되면 캐시탭 클릭 성공으로 판단하고 첫번째 슬롯을 누릅니다."
        )
        btn_cash_act.clicked.connect(self._capture_cash_tab_active_template)
        btn_cash_act_del = QPushButton("✕")
        btn_cash_act_del.setFixedWidth(24)
        btn_cash_act_del.clicked.connect(self._clear_cash_tab_active_template)
        cash_act_row.addWidget(lbl_ca)
        cash_act_row.addWidget(self.lbl_cash_active_tpl)
        cash_act_row.addStretch()
        cash_act_row.addWidget(btn_cash_act)
        cash_act_row.addWidget(btn_cash_act_del)
        layout.addLayout(cash_act_row)
        self._refresh_cash_active_tpl_label()

        # 인벤토리 바 이미지 (우선 인식 앵커 — 큰 이미지라 인식 안정적)
        inv_tpl_row = QHBoxLayout()
        lbl_inv = QLabel("인벤토리 바 이미지")
        lbl_inv.setFixedWidth(120)
        self.lbl_inv_tpl = QLabel("미등록")
        self.lbl_inv_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_inv_tpl = QPushButton("📷 캡처")
        btn_inv_tpl.setFixedWidth(65)
        btn_inv_tpl.setToolTip(
            "인벤토리 상단 타이틀 바 ('ITEM INVENTORY' 글자 영역)를 드래그로 캡처하세요.\n"
            "창 크기가 고정이므로 한 번만 설정하면 됩니다.\n"
            "이 이미지를 먼저 찾아 캐시탭 위치를 역산합니다."
        )
        btn_inv_tpl.clicked.connect(self._capture_inventory_template)
        btn_inv_tpl_del = QPushButton("✕")
        btn_inv_tpl_del.setFixedWidth(24)
        btn_inv_tpl_del.clicked.connect(self._clear_inventory_template)
        inv_tpl_row.addWidget(lbl_inv)
        inv_tpl_row.addWidget(self.lbl_inv_tpl)
        inv_tpl_row.addStretch()
        inv_tpl_row.addWidget(btn_inv_tpl)
        inv_tpl_row.addWidget(btn_inv_tpl_del)
        layout.addLayout(inv_tpl_row)
        self._refresh_inv_tpl_label()

        # 설정 안내
        guide = QLabel(
            "📌 설정 순서:\n"
            "  1. 게임에서 인벤토리 열기\n"
            "  2. '인벤토리 바 이미지' 캡처 (ITEM INVENTORY 바)\n"
            "  3. '캐시탭 위치' 지정 (인벤토리 열린 상태 유지)\n"
            "  4. 캐시탭 클릭 → 분홍색으로 변하면 '캐시탭 활성 이미지' 캡처\n"
            "  5. '첫번째 슬롯' 위치 지정 (NPC 상점 첫 칸)"
        )
        guide.setStyleSheet("color: #555; font-size: 10px; padding: 4px 0px;")
        guide.setWordWrap(True)
        layout.addWidget(guide)

        # 캐시탭 좌표 (앵커 기준 오프셋 계산용 + 단독 fallback)
        self._add_junk_coord_row(layout, "cash_tab", "캐시탭 위치", False,
                                 tip="인벤토리 열린 상태에서 캐시탭 버튼을 드래그로 지정하세요.\n"
                                     "인벤토리 바 이미지와 함께 사용하면 위치가 달라져도 자동 보정됩니다.")

        # 첫번째 슬롯 좌표
        self._add_junk_coord_row(layout, "first_slot", "첫번째 슬롯", False,
                                 tip="NPC 상점의 첫번째 슬롯 위치를 지정하세요.\n"
                                     "캐시탭 활성 이미지 위치 기준 상대 오프셋으로 자동 보정됩니다.")

        # 상점 열림 확인 이미지
        shop_open_row = QHBoxLayout()
        lbl_so = QLabel("상점 열림 확인")
        lbl_so.setFixedWidth(100)
        self.lbl_shop_open_tpl = QLabel("미등록 (없으면 생략)")
        self.lbl_shop_open_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_so_cap = QPushButton("📷 캡처")
        btn_so_cap.setFixedWidth(65)
        btn_so_cap.setToolTip(
            "상점이 열렸을 때만 보이는 고유 UI 요소를 드래그해서 저장합니다.\n"
            "예) 상점 창 타이틀 바, '기타' 탭 텍스트 등.\n"
            "이 이미지가 감지되면 상점 열림 성공으로 판단합니다."
        )
        btn_so_cap.clicked.connect(self._capture_shop_open_template)
        btn_so_del = QPushButton("✕")
        btn_so_del.setFixedWidth(24)
        btn_so_del.clicked.connect(self._clear_shop_open_template)
        shop_open_row.addWidget(lbl_so)
        shop_open_row.addWidget(self.lbl_shop_open_tpl)
        shop_open_row.addStretch()
        shop_open_row.addWidget(btn_so_cap)
        shop_open_row.addWidget(btn_so_del)
        layout.addLayout(shop_open_row)
        self._refresh_shop_open_tpl_label()

        # 상점 열기 버튼
        open_row = QHBoxLayout()
        self.btn_open_shop = QPushButton("🏪 상점 열기")
        self.btn_open_shop.setFixedHeight(32)
        self.btn_open_shop.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #2ecc71; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.btn_open_shop.setToolTip("i키 → 캐시탭 클릭 → 첫번째 슬롯 클릭 순서로 상점을 엽니다.")
        self.btn_open_shop.clicked.connect(self._run_open_shop)
        self.lbl_junk_status = QLabel("대기 중")
        self.lbl_junk_status.setStyleSheet("color: gray; font-size: 10px;")
        open_row.addWidget(self.btn_open_shop)
        open_row.addWidget(self.lbl_junk_status)
        open_row.addStretch()
        layout.addLayout(open_row)

        # ══ ② 장비 판매 설정 ══════════════════════════════════════════
        layout.addSpacing(6)
        layout.addWidget(QLabel("─ ② 장비 판매 설정 ─────────────────────"))

        # 장비 일괄 판매 버튼 템플릿
        eq_btn_row = QHBoxLayout()
        lbl_eq = QLabel("장비 일괄 판매")
        lbl_eq.setFixedWidth(100)
        self.lbl_equip_sell_tpl = QLabel("미등록")
        self.lbl_equip_sell_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_eq_cap = QPushButton("📷 캡처")
        btn_eq_cap.setFixedWidth(65)
        btn_eq_cap.setToolTip("NPC 상점의 '장비 일괄 판매' 버튼 이미지를 드래그해서 저장합니다.")
        btn_eq_cap.clicked.connect(self._capture_equip_sell_template)
        btn_eq_del = QPushButton("✕")
        btn_eq_del.setFixedWidth(24)
        btn_eq_del.clicked.connect(self._clear_equip_sell_template)
        eq_btn_row.addWidget(lbl_eq)
        eq_btn_row.addWidget(self.lbl_equip_sell_tpl)
        eq_btn_row.addStretch()
        eq_btn_row.addWidget(btn_eq_cap)
        eq_btn_row.addWidget(btn_eq_del)
        layout.addLayout(eq_btn_row)
        self._refresh_equip_sell_tpl_label()

        # 장비 일괄 판매 확인 버튼 템플릿
        eq_conf_row = QHBoxLayout()
        lbl_ec = QLabel("일괄 판매 확인")
        lbl_ec.setFixedWidth(100)
        self.lbl_equip_confirm_tpl = QLabel("미등록 (없으면 Enter 키 사용)")
        self.lbl_equip_confirm_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_ec_cap = QPushButton("📷 캡처")
        btn_ec_cap.setFixedWidth(65)
        btn_ec_cap.setToolTip(
            "장비 일괄 판매 후 나타나는 확인 팝업의 '확인' 버튼 이미지를 저장합니다.\n"
            "미등록 시 확인창이 감지되지 않으면 Enter 키로 대체합니다."
        )
        btn_ec_cap.clicked.connect(self._capture_equip_confirm_template)
        btn_ec_del = QPushButton("✕")
        btn_ec_del.setFixedWidth(24)
        btn_ec_del.clicked.connect(self._clear_equip_confirm_template)
        eq_conf_row.addWidget(lbl_ec)
        eq_conf_row.addWidget(self.lbl_equip_confirm_tpl)
        eq_conf_row.addStretch()
        eq_conf_row.addWidget(btn_ec_cap)
        eq_conf_row.addWidget(btn_ec_del)
        layout.addLayout(eq_conf_row)
        self._refresh_equip_confirm_tpl_label()

        # 상점 나가기 버튼 좌표 (템플릿보다 단순 좌표가 더 안정적)
        self._add_junk_coord_row(layout, "shop_exit_btn", "상점 나가기", False,
                                 tip="상점 창의 '상점 나가기' 또는 닫기(X) 버튼 좌표입니다.\n"
                                     "미설정 시 ESC 키 2회로 대체합니다.")

        # ══ ③ 기타템 판매 설정 ════════════════════════════════════════
        layout.addSpacing(6)
        layout.addWidget(QLabel("─ ③ 기타템 판매 설정 ───────────────────"))

        # 기타템 판매 활성화 체크박스
        chk_row = QHBoxLayout()
        self.chk_junk_sell = QCheckBox("기타템 판매 활성화")
        self.chk_junk_sell.setToolTip(
            "체크 시: 장비 판매 후 상점 기타탭으로 이동해 아이템 템플릿 판매를 진행합니다.\n"
            "미체크 시: 장비 판매 후 바로 상점을 닫습니다."
        )
        self.chk_junk_sell.stateChanged.connect(self._save_junk_sell_enabled)
        chk_row.addWidget(self.chk_junk_sell)
        chk_row.addStretch()
        layout.addLayout(chk_row)

        etc_coord_defs = [
            ("shop_area",  "상점 목록 영역", True,
             "기타 탭 아이템 목록이 표시되는 영역을 드래그로 지정합니다."),
            ("scroll_pos", "스크롤 위치",   False,
             "아이템 목록 스크롤바 위치입니다. 아래로 스크롤할 때 사용합니다."),
        ]
        for key, title, is_area, tip in etc_coord_defs:
            self._add_junk_coord_row(layout, key, title, is_area, tip=tip)

        # 기타탭 활성 이미지
        etc_act_row = QHBoxLayout()
        lbl_ea = QLabel("기타탭 활성 이미지")
        lbl_ea.setFixedWidth(110)
        self.lbl_etc_active_tpl = QLabel("미등록 (없으면 0.6초 대기)")
        self.lbl_etc_active_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_ea_cap = QPushButton("📷 캡처")
        btn_ea_cap.setFixedWidth(65)
        btn_ea_cap.setToolTip("기타탭 클릭 후 활성화된(하이라이트) 상태를 드래그해서 저장합니다.")
        btn_ea_cap.clicked.connect(self._capture_etc_active_template)
        btn_ea_del = QPushButton("✕")
        btn_ea_del.setFixedWidth(24)
        btn_ea_del.clicked.connect(self._clear_etc_active_template)
        etc_act_row.addWidget(lbl_ea)
        etc_act_row.addWidget(self.lbl_etc_active_tpl)
        etc_act_row.addStretch()
        etc_act_row.addWidget(btn_ea_cap)
        etc_act_row.addWidget(btn_ea_del)
        layout.addLayout(etc_act_row)
        self._refresh_etc_active_tpl_label()

        # 스크롤 최하단 이미지
        scroll_bot_row = QHBoxLayout()
        lbl_sb = QLabel("스크롤 최하단")
        lbl_sb.setFixedWidth(110)
        self.lbl_scroll_bottom_tpl = QLabel("미등록 (없으면 3회 연속 미탐지 시 종료)")
        self.lbl_scroll_bottom_tpl.setStyleSheet("color: gray; font-size: 10px;")
        btn_sb_cap = QPushButton("📷 캡처")
        btn_sb_cap.setFixedWidth(65)
        btn_sb_cap.setToolTip(
            "스크롤이 최하단에 도달했을 때만 보이는 UI 요소를 드래그해서 저장합니다.\n"
            "예) 스크롤바 끝 표시, 빈 슬롯 영역 등."
        )
        btn_sb_cap.clicked.connect(self._capture_scroll_bottom_template)
        btn_sb_del = QPushButton("✕")
        btn_sb_del.setFixedWidth(24)
        btn_sb_del.clicked.connect(self._clear_scroll_bottom_template)
        scroll_bot_row.addWidget(lbl_sb)
        scroll_bot_row.addWidget(self.lbl_scroll_bottom_tpl)
        scroll_bot_row.addStretch()
        scroll_bot_row.addWidget(btn_sb_cap)
        scroll_bot_row.addWidget(btn_sb_del)
        layout.addLayout(scroll_bot_row)
        self._refresh_scroll_bottom_tpl_label()

        layout.addSpacing(4)
        layout.addWidget(QLabel("─ 판매 아이템 템플릿 ───────────────────"))

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

        # ══ ④ 자동 판매 주기 설정 ════════════════════════════════════════
        layout.addSpacing(6)
        layout.addWidget(QLabel("─ ④ 자동 판매 주기 설정 ──────────────"))

        auto_note = QLabel(
            "⚠ 봇 실행 중 지정 주기마다 안전지대로 이동 후 판매를 자동 실행합니다.\n"
            "안전지대 X는 미니맵 기준 몬스터가 없는 위치의 X 좌표입니다."
        )
        auto_note.setWordWrap(True)
        auto_note.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(auto_note)

        # 활성화 체크박스
        auto_chk_row = QHBoxLayout()
        self.chk_auto_sell = QCheckBox("자동 판매 활성화")
        self.chk_auto_sell.stateChanged.connect(self._save_auto_sell_settings)
        auto_chk_row.addWidget(self.chk_auto_sell)
        auto_chk_row.addStretch()
        layout.addLayout(auto_chk_row)

        # 봇 시작 시 즉시 판매 체크박스
        sell_on_start_row = QHBoxLayout()
        self.chk_sell_on_start = QCheckBox("봇 시작 시 즉시 판매")
        self.chk_sell_on_start.setToolTip(
            "체크: 봇 시작 즉시 첫 판매를 실행합니다.\n"
            "미체크: 첫 판매는 설정한 주기가 지난 뒤 실행됩니다."
        )
        self.chk_sell_on_start.stateChanged.connect(self._save_auto_sell_settings)
        sell_on_start_row.addWidget(self.chk_sell_on_start)
        sell_on_start_row.addStretch()
        layout.addLayout(sell_on_start_row)

        # 판매 주기
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("판매 주기"))
        self.spin_auto_sell_interval = QSpinBox()
        self.spin_auto_sell_interval.setRange(1, 120)
        self.spin_auto_sell_interval.setValue(10)
        self.spin_auto_sell_interval.setSuffix(" 분")
        self.spin_auto_sell_interval.setFixedWidth(80)
        self.spin_auto_sell_interval.valueChanged.connect(self._save_auto_sell_settings)
        interval_row.addWidget(self.spin_auto_sell_interval)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        # 안전지대 X,Y — 현재 내 위치로 설정 버튼
        safe_zone_row = QHBoxLayout()
        lbl_sz = QLabel("안전지대 X,Y")
        lbl_sz.setFixedWidth(85)
        self.lbl_safe_zone_x = QLabel("미설정")
        self.lbl_safe_zone_x.setStyleSheet("color: gray; font-size: 10px;")
        btn_safe_zone = QPushButton("📍 현재 위치로 설정")
        btn_safe_zone.setFixedWidth(120)
        btn_safe_zone.setToolTip(
            "캐릭터를 안전지대에 위치시킨 뒤 클릭하세요.\n"
            "미니맵 기준 현재 X, Y 좌표가 안전지대로 저장됩니다."
        )
        btn_safe_zone.clicked.connect(self._set_safe_zone_xy)
        btn_safe_zone_rst = QPushButton("✕")
        btn_safe_zone_rst.setFixedWidth(24)
        btn_safe_zone_rst.clicked.connect(self._reset_safe_zone_xy)
        safe_zone_row.addWidget(lbl_sz)
        safe_zone_row.addWidget(self.lbl_safe_zone_x)
        safe_zone_row.addStretch()
        safe_zone_row.addWidget(btn_safe_zone)
        safe_zone_row.addWidget(btn_safe_zone_rst)
        layout.addLayout(safe_zone_row)

        # 안전지대 이동 경로 설정
        layout.addWidget(QLabel("안전지대 이동 경로  (층 이동 없으면 출발지 미설정)"))

        dep_note = QLabel(
            "층 이동이 필요하면: 출발지 층(기존 사냥 구역)을 선택하고\n"
            "그 층에서 안전지대로 가는 밧줄 X·방향·이동시간을 입력하세요.\n"
            "봇이 출발지 도달 후 해당 밧줄을 타고 안전지대로 이동합니다."
        )
        dep_note.setWordWrap(True)
        dep_note.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(dep_note)

        # 출발지 층 선택
        dep_row = QHBoxLayout()
        lbl_dep = QLabel("출발지 층")
        lbl_dep.setFixedWidth(75)
        self.combo_departure_zone = QComboBox()
        self.combo_departure_zone.setFixedWidth(150)
        self.combo_departure_zone.setToolTip(
            "안전지대 이동 전 경유할 마지막 사냥 층을 선택합니다.\n"
            "'미설정' 선택 시 현재 층에서 바로 안전지대 X,Y로 걷습니다.\n"
            "🔄 버튼으로 좌표 탭의 구역 목록을 불러오세요."
        )
        self.combo_departure_zone.addItem("미설정")
        self.combo_departure_zone.currentIndexChanged.connect(self._save_departure_settings)
        btn_refresh_zones = QPushButton("🔄")
        btn_refresh_zones.setFixedWidth(28)
        btn_refresh_zones.setToolTip("좌표 탭의 구역 목록을 불러옵니다.")
        btn_refresh_zones.clicked.connect(self._populate_departure_zones)
        dep_row.addWidget(lbl_dep)
        dep_row.addWidget(self.combo_departure_zone)
        dep_row.addWidget(btn_refresh_zones)
        dep_row.addStretch()
        layout.addLayout(dep_row)

        # 밧줄 X 좌표 (미니맵 픽셀 기준 — 현재 위치로 자동 설정 권장)
        rope_x_row = QHBoxLayout()
        lbl_rx = QLabel("밧줄 X 좌표")
        lbl_rx.setFixedWidth(75)
        self.spin_extra_rope_x = QSpinBox()
        self.spin_extra_rope_x.setRange(0, 999)
        self.spin_extra_rope_x.setValue(0)
        self.spin_extra_rope_x.setFixedWidth(60)
        self.spin_extra_rope_x.setToolTip(
            "출발지 → 안전지대 밧줄의 미니맵 픽셀 X 좌표입니다.\n"
            "캐릭터를 밧줄 위(또는 바로 옆)에 위치시킨 뒤 📍 버튼으로 설정하세요.\n"
            "직접 입력 시 미니맵 내 픽셀 좌표(0~미니맵폭)를 입력해야 합니다."
        )
        self.spin_extra_rope_x.valueChanged.connect(self._save_departure_settings)
        btn_capture_rope_x = QPushButton("📍")
        btn_capture_rope_x.setFixedWidth(28)
        btn_capture_rope_x.setToolTip(
            "캐릭터를 밧줄 위(또는 바로 옆)에 위치시킨 뒤 클릭하면\n"
            "현재 미니맵 X 좌표가 자동으로 입력됩니다."
        )
        btn_capture_rope_x.clicked.connect(self._capture_extra_rope_x)
        rope_x_row.addWidget(lbl_rx)
        rope_x_row.addWidget(self.spin_extra_rope_x)
        rope_x_row.addWidget(btn_capture_rope_x)
        rope_x_row.addStretch()
        layout.addLayout(rope_x_row)

        # 이동 방향
        rope_dir_row = QHBoxLayout()
        lbl_rd = QLabel("이동 방향")
        lbl_rd.setFixedWidth(75)
        self.combo_extra_rope_dir = QComboBox()
        self.combo_extra_rope_dir.addItems(["위로 (up)", "아래로 (down)"])
        self.combo_extra_rope_dir.setFixedWidth(120)
        self.combo_extra_rope_dir.setToolTip("안전지대가 출발지보다 위층이면 '위로', 아래층이면 '아래로'.")
        self.combo_extra_rope_dir.currentIndexChanged.connect(self._save_departure_settings)
        rope_dir_row.addWidget(lbl_rd)
        rope_dir_row.addWidget(self.combo_extra_rope_dir)
        rope_dir_row.addStretch()
        layout.addLayout(rope_dir_row)

        # 이동 시간
        rope_sec_row = QHBoxLayout()
        lbl_rs = QLabel("이동 시간")
        lbl_rs.setFixedWidth(75)
        self.spin_extra_rope_climb = QDoubleSpinBox()
        self.spin_extra_rope_climb.setRange(0.5, 15.0)
        self.spin_extra_rope_climb.setSingleStep(0.5)
        self.spin_extra_rope_climb.setValue(2.5)
        self.spin_extra_rope_climb.setSuffix(" 초")
        self.spin_extra_rope_climb.setFixedWidth(85)
        self.spin_extra_rope_climb.setToolTip("밧줄을 타고 이동하는 시간(초). 실제 도착 시간에 맞게 조절하세요.")
        self.spin_extra_rope_climb.valueChanged.connect(self._save_departure_settings)
        rope_sec_row.addWidget(lbl_rs)
        rope_sec_row.addWidget(self.spin_extra_rope_climb)
        rope_sec_row.addStretch()
        layout.addLayout(rope_sec_row)

        # 판매 실행
        run_row = QHBoxLayout()
        self.btn_junk_run = QPushButton("▶ 판매 실행  (상점열기 → 판매까지 전체)")
        self.btn_junk_run.setFixedHeight(30)
        self.btn_junk_run.clicked.connect(self._run_junk_sell)
        run_row.addWidget(self.btn_junk_run)
        run_row.addStretch()
        layout.addLayout(run_row)

        return group

    def _add_junk_coord_row(self, layout, key: str, title: str,
                             is_area: bool, tip: str = "") -> None:
        """좌표 설정 행 1줄을 layout에 추가한다."""
        row = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setFixedWidth(100)
        lbl_val = QLabel("미설정")
        lbl_val.setStyleSheet("color: gray; font-size: 10px;")
        self._junk_coord_lbls[key] = lbl_val

        btn_set = QPushButton("📍 드래그" if is_area else "📍 지정")
        btn_set.setFixedWidth(68 if is_area else 55)
        if tip:
            btn_set.setToolTip(tip)
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

    # ── 잡템 좌표 설정 ────────────────────────────────────────────────
    def _set_junk_coord(self, key: str, is_area: bool) -> None:
        self._pending_junk_key  = key
        self._pending_junk_area = is_area
        sel = RegionSelector()
        sel.region_selected.connect(self._save_junk_coord)
        self._junk_selector = sel
        sel.show()

    def _save_junk_coord(self, x: int, y: int, w: int, h: int) -> None:
        try:
            key     = self._pending_junk_key
            is_area = self._pending_junk_area

            if is_area:
                # 영역 캡처용 — mss 물리 좌표로 변환
                px, py, pw, ph = self._to_physical(x, y, w, h)
                val  = [px, py, pw, ph]
                text = f"X={px} Y={py} W={pw} H={ph}"
                self.config.set("settings2", "junk_sell", key, val)

            elif key == "cash_tab":
                # 인벤토리 바 감지 → 오프셋만 저장
                self._save_cash_tab_offset(x + w // 2, y + h // 2)
                return

            elif key == "first_slot":
                # 캐시탭 활성 이미지 감지 → 오프셋만 저장
                self._save_first_slot_offset(x + w // 2, y + h // 2)
                return

            else:
                # 클릭 좌표 — 가상 데스크톱 오프셋 포함한 절대 좌표로 변환
                cx_phys, cy_phys = self._to_physical(x + w // 2, y + h // 2, 0, 0)[:2]
                val  = [cx_phys, cy_phys]
                text = f"X={cx_phys} Y={cy_phys}"
                self.config.set("settings2", "junk_sell", key, val)

            inv_key = self.edit_inventory_key.text().strip() or "i"
            self.config.set("settings2", "junk_sell", "inventory_key", inv_key)
            self.config.save()
            lbl = self._junk_coord_lbls.get(key)
            if lbl:
                lbl.setText(text)
                lbl.setStyleSheet("color: green; font-size: 10px;")
        except Exception as e:
            QMessageBox.warning(self, "좌표 저장 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _save_cash_tab_offset(self, cx: int, cy: int) -> None:
        """캐시탭 중심 좌표 → 현재 화면의 인벤토리 바를 감지해 오프셋 계산 후 저장."""
        try:
            import time as _time
            _time.sleep(0.05)
            inv_tpl = "templates/junk/inventory.png"
            if not os.path.exists(inv_tpl):
                QMessageBox.warning(self, "오류",
                    "인벤토리 바 이미지가 없습니다.\n먼저 '인벤토리 바 이미지'를 캡처하세요.")
                return
            with mss.mss() as sct:
                mon = sct.monitors[0]
                raw = sct.grab(mon)
                scene = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            template = cv2.imread(inv_tpl)
            result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val < 0.70:
                QMessageBox.warning(self, "오류",
                    f"화면에서 인벤토리 바를 찾지 못했습니다 (점수: {max_val:.2f}).\n"
                    "인벤토리를 열어놓은 상태에서 다시 지정하세요.")
                return
            th, tw = template.shape[:2]
            inv_cx = mon["left"] + max_loc[0] + tw // 2
            inv_cy = mon["top"]  + max_loc[1] + th // 2
            # cx, cy 는 RegionSelector 논리 픽셀 → mss 물리 픽셀로 변환해 비교
            cx_phys, cy_phys = self._to_physical(cx, cy, 0, 0)[:2]
            offset = [cx_phys - inv_cx, cy_phys - inv_cy]
            self.config.set("settings2", "junk_sell", "cash_tab_offset", offset)
            inv_key = self.edit_inventory_key.text().strip() or "i"
            self.config.set("settings2", "junk_sell", "inventory_key", inv_key)
            self.config.save()
            lbl = self._junk_coord_lbls.get("cash_tab")
            if lbl:
                lbl.setText(f"오프셋 dx={offset[0]} dy={offset[1]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
            QMessageBox.information(self, "완료",
                f"캐시탭 오프셋 저장: dx={offset[0]}, dy={offset[1]}\n"
                f"(인벤토리 중심 {inv_cx},{inv_cy} 기준)")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"캐시탭 오프셋 저장 중 오류가 발생했습니다:\n{e}")

    def _save_first_slot_offset(self, cx: int, cy: int) -> None:
        """첫번째 슬롯 중심 → 캐시탭 활성 이미지 감지해 오프셋 계산 후 저장."""
        try:
            import time as _time
            _time.sleep(0.05)
            active_tpl = "templates/junk/cash_tab_active.png"
            if not os.path.exists(active_tpl):
                # 활성 이미지 없으면 캐시탭 기준으로 오프셋 저장
                cash_tab_offset = (self.config.get("settings2", "junk_sell", "cash_tab_offset") or [])
                if not cash_tab_offset:
                    QMessageBox.warning(self, "오류",
                        "캐시탭 활성 이미지도 없고 캐시탭 오프셋도 없습니다.\n"
                        "캐시탭 설정을 먼저 완료하세요.")
                    return
                # 현재 화면에서 인벤토리 감지 후 캐시탭 위치 역산
                with mss.mss() as sct:
                    mon = sct.monitors[0]
                    raw = sct.grab(mon)
                    scene = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                inv_tpl = "templates/junk/inventory.png"
                template = cv2.imread(inv_tpl)
                result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val >= 0.70:
                    th, tw = template.shape[:2]
                    inv_cx = mon["left"] + max_loc[0] + tw // 2
                    inv_cy = mon["top"]  + max_loc[1] + th // 2
                    ref_x = inv_cx + cash_tab_offset[0]
                    ref_y = inv_cy + cash_tab_offset[1]
                else:
                    QMessageBox.warning(self, "오류", "인벤토리를 찾지 못했습니다.")
                    return
                cx_phys, cy_phys = self._to_physical(cx, cy, 0, 0)[:2]
                offset = [cx_phys - ref_x, cy_phys - ref_y]
                self.config.set("settings2", "junk_sell", "first_slot_offset", offset)
                self.config.save()
                lbl = self._junk_coord_lbls.get("first_slot")
                if lbl:
                    lbl.setText(f"오프셋 dx={offset[0]} dy={offset[1]}")
                    lbl.setStyleSheet("color: green; font-size: 10px;")
                return

            with mss.mss() as sct:
                mon = sct.monitors[0]
                raw = sct.grab(mon)
                scene = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            template = cv2.imread(active_tpl)
            result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val < 0.70:
                QMessageBox.warning(self, "오류",
                    f"캐시탭 활성 이미지를 찾지 못했습니다 (점수: {max_val:.2f}).\n"
                    "캐시탭이 활성화된 상태(분홍색)에서 지정하세요.")
                return
            th, tw = template.shape[:2]
            act_cx = mon["left"] + max_loc[0] + tw // 2
            act_cy = mon["top"]  + max_loc[1] + th // 2
            cx_phys, cy_phys = self._to_physical(cx, cy, 0, 0)[:2]
            offset = [cx_phys - act_cx, cy_phys - act_cy]
            self.config.set("settings2", "junk_sell", "first_slot_offset", offset)
            self.config.save()
            lbl = self._junk_coord_lbls.get("first_slot")
            if lbl:
                lbl.setText(f"오프셋 dx={offset[0]} dy={offset[1]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
            QMessageBox.information(self, "완료",
                f"첫번째 슬롯 오프셋 저장: dx={offset[0]}, dy={offset[1]}\n"
                f"(활성 캐시탭 중심 {act_cx},{act_cy} 기준)")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"첫번째 슬롯 오프셋 저장 중 오류가 발생했습니다:\n{e}")

    def _reset_junk_coord(self, key: str) -> None:
        self.config.set("settings2", "junk_sell", key, None)
        self.config.save()
        lbl = self._junk_coord_lbls.get(key)
        if lbl:
            lbl.setText("미설정")
            lbl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 캐시탭 템플릿 관리 ───────────────────────────────────────────
    def _capture_cash_tab_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_cash_tab_template)
        self._cash_tpl_selector = sel
        sel.show()

    def _save_cash_tab_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)   # RegionSelector 오버레이 완전 소멸 대기
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/cash_tab.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            self._refresh_cash_tpl_label()
            QMessageBox.information(self, "완료", f"캐시탭 템플릿 저장 완료 ({pw}×{ph}px)")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_cash_tab_template(self) -> None:
        path = "templates/junk/cash_tab.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_cash_tpl_label()

    def _refresh_cash_tpl_label(self) -> None:
        if os.path.exists("templates/junk/cash_tab.png"):
            self.lbl_cash_tpl.setText("등록됨")
            self.lbl_cash_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_cash_tpl.setText("미등록")
            self.lbl_cash_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 캐시탭 활성 이미지 (클릭 후 분홍색 상태) ────────────────────
    def _capture_cash_tab_active_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_cash_tab_active_template)
        self._cash_act_selector = sel
        sel.show()

    def _save_cash_tab_active_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/cash_tab_active.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            # 캡처 중심을 cash_tab_active_anchor 로 자동 저장 (첫번째 슬롯 오프셋 계산용)
            cx, cy = x + w // 2, y + h // 2
            self.config.set("settings2", "junk_sell", "cash_tab_active_anchor", [cx, cy])
            self.config.save()
            self._refresh_cash_active_tpl_label()
            reply = QMessageBox.question(
                self, "캐시탭 활성 이미지 저장 완료",
                f"저장 완료 ({w}×{h}px)\n\n"
                "지금 바로 첫번째 슬롯 위치를 지정하시겠습니까?\n"
                "(NPC 상점을 열어 첫번째 칸 위치를 드래그하세요)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._set_junk_coord("first_slot", False)
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_cash_tab_active_template(self) -> None:
        path = "templates/junk/cash_tab_active.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_cash_active_tpl_label()

    def _refresh_cash_active_tpl_label(self) -> None:
        if os.path.exists("templates/junk/cash_tab_active.png"):
            self.lbl_cash_active_tpl.setText("등록됨")
            self.lbl_cash_active_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_cash_active_tpl.setText("미등록 (없으면 0.5초 대기 후 진행)")
            self.lbl_cash_active_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 상점 열림 확인 이미지 ────────────────────────────────────────
    def _capture_shop_open_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_shop_open_template)
        self._shop_open_selector = sel
        sel.show()

    def _save_shop_open_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/shop_open.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            self._refresh_shop_open_tpl_label()
            QMessageBox.information(self, "완료", f"상점 열림 확인 이미지 저장 완료 ({pw}×{ph}px)")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_shop_open_template(self) -> None:
        path = "templates/junk/shop_open.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_shop_open_tpl_label()

    def _refresh_shop_open_tpl_label(self) -> None:
        if os.path.exists("templates/junk/shop_open.png"):
            self.lbl_shop_open_tpl.setText("등록됨")
            self.lbl_shop_open_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_shop_open_tpl.setText("미등록 (없으면 생략)")
            self.lbl_shop_open_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 인벤토리 바 템플릿 관리 ──────────────────────────────────────
    def _capture_inventory_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_inventory_template)
        self._inv_tpl_selector = sel
        sel.show()

    def _save_inventory_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/inventory.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            # 캡처 당시 중심 좌표를 inventory_anchor 로 자동 저장
            cx, cy = x + w // 2, y + h // 2
            self.config.set("settings2", "junk_sell", "inventory_anchor", [cx, cy])
            self.config.save()
            lbl = self._junk_coord_lbls.get("inventory_anchor")
            if lbl:
                lbl.setText(f"X={cx} Y={cy}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
            self._refresh_inv_tpl_label()
            reply = QMessageBox.question(
                self, "인벤토리 바 저장 완료",
                f"인벤토리 바 이미지 저장 완료 ({w}×{h}px)\n\n"
                "지금 바로 캐시탭 위치를 지정하시겠습니까?\n"
                "(인벤토리가 열린 상태를 유지해주세요)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._set_junk_coord("cash_tab", False)
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_inventory_template(self) -> None:
        path = "templates/junk/inventory.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_inv_tpl_label()

    def _refresh_inv_tpl_label(self) -> None:
        if os.path.exists("templates/junk/inventory.png"):
            self.lbl_inv_tpl.setText("등록됨")
            self.lbl_inv_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_inv_tpl.setText("미등록")
            self.lbl_inv_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 잡템 템플릿 관리 ─────────────────────────────────────────────
    def _capture_junk_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_junk_template)
        self._junk_tpl_selector = sel
        sel.show()

    def _save_junk_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            existing = sorted(glob.glob("templates/junk/item_*.png"))
            next_num = len(existing) + 1
            path = f"templates/junk/item_{next_num}.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            self._refresh_junk_tpl_label()
            QMessageBox.information(self, "완료", f"아이템 템플릿 {next_num}번 저장 완료 ({pw}×{ph}px)")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

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

    # ── 기타탭 활성 이미지 ───────────────────────────────────────────
    def _capture_etc_active_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_etc_active_template)
        self._etc_act_selector = sel
        sel.show()

    def _save_etc_active_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/etc_tab_active.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            # 캡처 중심 좌표를 기타탭 클릭 위치로 자동 저장 (절대 좌표 변환 적용)
            cx_phys, cy_phys = self._to_physical(x + w // 2, y + h // 2, 0, 0)[:2]
            self.config.set("settings2", "junk_sell", "shop_etc_tab", [cx_phys, cy_phys])
            self.config.save()
            self._refresh_etc_active_tpl_label()
            QMessageBox.information(self, "완료",
                f"기타탭 활성 이미지 저장 완료 ({pw}×{ph}px)\n"
                f"기타탭 클릭 위치 자동 저장: X={cx_phys} Y={cy_phys}")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_etc_active_template(self) -> None:
        path = "templates/junk/etc_tab_active.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_etc_active_tpl_label()

    def _refresh_etc_active_tpl_label(self) -> None:
        if os.path.exists("templates/junk/etc_tab_active.png"):
            pos = (self.config.get("settings2", "junk_sell") or {}).get("shop_etc_tab")
            pos_txt = f"  (클릭위치 X={pos[0]} Y={pos[1]})" if pos else ""
            self.lbl_etc_active_tpl.setText(f"등록됨{pos_txt}")
            self.lbl_etc_active_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_etc_active_tpl.setText("미등록 (없으면 0.6초 대기)")
            self.lbl_etc_active_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 스크롤 최하단 이미지 ─────────────────────────────────────────
    def _capture_scroll_bottom_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_scroll_bottom_template)
        self._scroll_bot_selector = sel
        sel.show()

    def _save_scroll_bottom_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/scroll_bottom.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            self._refresh_scroll_bottom_tpl_label()
            QMessageBox.information(self, "완료", f"스크롤 최하단 이미지 저장 완료 ({pw}×{ph}px)")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_scroll_bottom_template(self) -> None:
        path = "templates/junk/scroll_bottom.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_scroll_bottom_tpl_label()

    def _refresh_scroll_bottom_tpl_label(self) -> None:
        if os.path.exists("templates/junk/scroll_bottom.png"):
            self.lbl_scroll_bottom_tpl.setText("등록됨")
            self.lbl_scroll_bottom_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_scroll_bottom_tpl.setText("미등록 (없으면 3회 연속 미탐지 시 종료)")
            self.lbl_scroll_bottom_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 장비 일괄 판매 버튼 템플릿 ──────────────────────────────────
    def _capture_equip_sell_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_equip_sell_template)
        self._equip_sell_selector = sel
        sel.show()

    def _save_equip_sell_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/equip_sell_btn.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            self._refresh_equip_sell_tpl_label()
            QMessageBox.information(self, "완료", f"장비 일괄 판매 버튼 이미지 저장 완료 ({pw}×{ph}px)")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_equip_sell_template(self) -> None:
        path = "templates/junk/equip_sell_btn.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_equip_sell_tpl_label()

    def _refresh_equip_sell_tpl_label(self) -> None:
        if os.path.exists("templates/junk/equip_sell_btn.png"):
            self.lbl_equip_sell_tpl.setText("등록됨")
            self.lbl_equip_sell_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_equip_sell_tpl.setText("미등록")
            self.lbl_equip_sell_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 장비 일괄 판매 확인 버튼 템플릿 ─────────────────────────────
    def _capture_equip_confirm_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_equip_confirm_template)
        self._equip_conf_selector = sel
        sel.show()

    def _save_equip_confirm_template(self, x: int, y: int, w: int, h: int) -> None:
        try:
            import time as _time
            _time.sleep(0.08)
            os.makedirs("templates/junk", exist_ok=True)
            path = "templates/junk/equip_sell_confirm.png"
            px, py, pw, ph = self._to_physical(x, y, w, h)
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(path, img)
            self._refresh_equip_confirm_tpl_label()
            QMessageBox.information(self, "완료", f"확인 버튼 이미지 저장 완료 ({pw}×{ph}px)")
        except Exception as e:
            QMessageBox.warning(self, "캡처 오류", f"저장 중 오류가 발생했습니다:\n{e}")

    def _clear_equip_confirm_template(self) -> None:
        path = "templates/junk/equip_sell_confirm.png"
        if os.path.exists(path):
            os.remove(path)
        self._refresh_equip_confirm_tpl_label()

    def _refresh_equip_confirm_tpl_label(self) -> None:
        if os.path.exists("templates/junk/equip_sell_confirm.png"):
            self.lbl_equip_confirm_tpl.setText("등록됨")
            self.lbl_equip_confirm_tpl.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_equip_confirm_tpl.setText("미등록 (없으면 Enter 키 사용)")
            self.lbl_equip_confirm_tpl.setStyleSheet("color: gray; font-size: 10px;")

    # ── 기타템 판매 활성화 저장 ──────────────────────────────────────
    def _save_junk_sell_enabled(self) -> None:
        enabled = self.chk_junk_sell.isChecked()
        self.config.set("settings2", "junk_sell", "junk_sell_enabled", enabled)
        self.config.save()

    # ── 자동 판매 주기 설정 ───────────────────────────────────────────
    def _save_auto_sell_settings(self) -> None:
        self.config.set("settings2", "junk_sell", "auto_sell_enabled",
                        self.chk_auto_sell.isChecked())
        self.config.set("settings2", "junk_sell", "auto_sell_interval_min",
                        self.spin_auto_sell_interval.value())
        self.config.set("settings2", "junk_sell", "sell_on_start",
                        self.chk_sell_on_start.isChecked())
        self.config.save()

    def _read_minimap_pos(self):
        """현재 미니맵 캐릭터 위치 (x, y)를 반환. 실패 시 None."""
        from core.minimap_reader import MinimapReader, MinimapConfig
        from core.config_manager import resolve_minimap_coords
        from core.screen_reader import ScreenReader
        active  = self.config.get("hunt_grounds", "active") or ""
        presets = self.config.get("hunt_grounds", "presets") or {}
        preset  = presets.get(active) if active else None
        mm = preset.get("minimap", {}) if preset else (self.config.get("minimap") or {})
        region_x, region_y, mm_w, mm_h = resolve_minimap_coords(self.config, mm)
        cfg = MinimapConfig(
            region_x=region_x, region_y=region_y,
            width=mm_w, height=mm_h,
            char_r=mm.get("char_r", 255), char_g=mm.get("char_g", 255),
            char_b=mm.get("char_b", 255), tolerance=mm.get("tolerance", 40),
        )
        reader = MinimapReader(ScreenReader())
        reader.set_config(cfg)
        return reader.get_character_pos()

    def _set_safe_zone_xy(self) -> None:
        """미니맵에서 현재 캐릭터 X,Y 좌표를 안전지대로 저장 (비율도 함께 저장)."""
        try:
            from core.config_manager import resolve_minimap_coords
            active  = self.config.get("hunt_grounds", "active") or ""
            presets = self.config.get("hunt_grounds", "presets") or {}
            preset  = presets.get(active) if active else None
            mm      = preset.get("minimap", {}) if preset else (self.config.get("minimap") or {})
            _, _, mm_w, mm_h = resolve_minimap_coords(self.config, mm)
            pos = self._read_minimap_pos()
            if pos is None:
                QMessageBox.warning(self, "오류",
                    "캐릭터 위치를 감지하지 못했습니다.\n"
                    "미니맵 설정(좌표·색상)을 확인하세요.")
                return
            x, y = pos
            self.config.set("settings2", "junk_sell", "safe_zone_x", x)
            self.config.set("settings2", "junk_sell", "safe_zone_y", y)
            # 비율도 함께 저장 — 미니맵 크기 변경 시 자동 보정
            if mm_w > 0:
                self.config.set("settings2", "junk_sell", "safe_zone_x_ratio", x / mm_w)
            if mm_h > 0:
                self.config.set("settings2", "junk_sell", "safe_zone_y_ratio", y / mm_h)
            self.config.save()
            self.lbl_safe_zone_x.setText(f"X={x}  Y={y}")
            self.lbl_safe_zone_x.setStyleSheet("color: green; font-size: 10px;")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"안전지대 설정 중 오류가 발생했습니다:\n{e}")

    def _reset_safe_zone_xy(self) -> None:
        for k in ("safe_zone_x", "safe_zone_y", "safe_zone_x_ratio", "safe_zone_y_ratio"):
            self.config.set("settings2", "junk_sell", k, None)
        self.config.save()
        self.lbl_safe_zone_x.setText("미설정")
        self.lbl_safe_zone_x.setStyleSheet("color: gray; font-size: 10px;")

    # ── 안전지대 이동 경로 관리 ───────────────────────────────────────
    def _capture_extra_rope_x(self) -> None:
        """캐릭터 현재 미니맵 X 좌표를 밧줄 X로 캡처해서 SpinBox에 설정."""
        try:
            pos = self._read_minimap_pos()
            if pos is None:
                QMessageBox.warning(self, "오류",
                    "캐릭터 위치를 감지하지 못했습니다.\n"
                    "미니맵 설정(좌표·색상)을 확인하세요.")
                return
            x = pos[0]
            self.spin_extra_rope_x.blockSignals(True)
            self.spin_extra_rope_x.setValue(x)
            self.spin_extra_rope_x.blockSignals(False)
            self._save_departure_settings()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"밧줄 X 캡처 중 오류가 발생했습니다:\n{e}")

    def _save_departure_settings(self) -> None:
        """출발지 층 + 추가 밧줄 설정을 config에 저장."""
        dep = self.combo_departure_zone.currentText()
        if dep == "미설정":
            dep = ""
        self.config.set("settings2", "junk_sell", "departure_zone", dep)
        _extra = {
            "x":        self.spin_extra_rope_x.value(),
            "direction": "up" if self.combo_extra_rope_dir.currentIndex() == 0 else "down",
            "climb_sec": self.spin_extra_rope_climb.value(),
        }
        self.config.set("settings2", "junk_sell", "extra_rope", _extra)
        self.config.save()

    def _populate_departure_zones(self) -> None:
        """현재 활성 프리셋의 구역 이름을 출발지 드롭다운에 로드."""
        active    = self.config.get("hunt_grounds", "active") or ""
        presets   = self.config.get("hunt_grounds", "presets") or {}
        preset    = presets.get(active) if active else None
        raw_zones = preset.get("zones", []) if preset else (self.config.get("zones") or [])
        names     = [z.get("name", "") for z in raw_zones if z.get("name", "")]

        prev = self.combo_departure_zone.currentText()
        self.combo_departure_zone.blockSignals(True)
        self.combo_departure_zone.clear()
        self.combo_departure_zone.addItem("미설정")
        self.combo_departure_zone.addItems(names)
        idx = self.combo_departure_zone.findText(prev)
        self.combo_departure_zone.setCurrentIndex(max(0, idx))
        self.combo_departure_zone.blockSignals(False)

    # ── 상점 열기 ────────────────────────────────────────────────────
    def _run_open_shop(self) -> None:
        """i키 → 캐시탭 → 첫번째슬롯 순서로 상점만 열고 종료."""
        import threading
        from core.screen_reader import ScreenReader
        from core.input_controller import InputController
        from core.junk_seller import open_shop

        self.btn_open_shop.setEnabled(False)
        self._junk_status_sig.emit("상점 열기 중...")

        title      = self.config.get("settings2", "game_window_title") or "MapleStory"
        screen     = ScreenReader()
        input_ctrl = InputController(title)

        def _run():
            try:
                open_shop(
                    self.config,
                    screen,
                    input_ctrl,
                    lambda msg: self._junk_status_sig.emit(msg),
                )
            except Exception as e:
                self._junk_status_sig.emit(f"오류: {e}")
            finally:
                self._shop_done_sig.emit()

        threading.Thread(target=_run, daemon=True).start()

    # ── 판매 실행 ────────────────────────────────────────────────────
    def _run_junk_sell(self) -> None:
        import threading
        from core.screen_reader import ScreenReader
        from core.input_controller import InputController
        from core.junk_seller import sell_junk

        self.btn_junk_run.setEnabled(False)
        self._junk_status_sig.emit("판매 시작 중...")

        title      = self.config.get("settings2", "game_window_title") or "MapleStory"
        screen     = ScreenReader()
        input_ctrl = InputController(title)

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

    def set_log_callback(self, cb) -> None:
        """메인 로그창에 기록할 콜백을 주입한다 (MainWindow에서 호출)."""
        self._log_cb = cb

    def _on_junk_status(self, msg: str) -> None:
        self.lbl_junk_status.setText(msg)
        if self._log_cb:
            self._log_cb(f"[잡템] {msg}")

    # ── config 연동 ───────────────────────────────────────────────────
    def load_from_config(self):
        title = self.config.get("settings2", "game_window_title") or "MapleStory"
        self.edit_window_title.setText(title)

        # 잡템 판매 좌표 라벨 갱신
        junk = self.config.get("settings2", "junk_sell") or {}
        inv_key = junk.get("inventory_key", "i") or "i"
        self.edit_inventory_key.setText(inv_key)
        for key, lbl in self._junk_coord_lbls.items():
            # 오프셋 키 우선 확인
            offset_key = f"{key}_offset" if key in ("cash_tab", "first_slot") else None
            ov = junk.get(offset_key) if offset_key else None
            if ov and len(ov) == 2:
                lbl.setText(f"오프셋 dx={ov[0]} dy={ov[1]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
                continue
            v = junk.get(key)
            if v and len(v) == 4:
                lbl.setText(f"X={v[0]} Y={v[1]} W={v[2]} H={v[3]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
            elif v and len(v) == 2:
                lbl.setText(f"X={v[0]} Y={v[1]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
        enabled = bool(junk.get("junk_sell_enabled", False))
        self.chk_junk_sell.setChecked(enabled)

        # 자동 판매 주기 설정 로드 (신호 차단으로 config 덮어쓰기 방지)
        for _w in (self.chk_auto_sell, self.spin_auto_sell_interval, self.chk_sell_on_start):
            _w.blockSignals(True)
        self.chk_auto_sell.setChecked(bool(junk.get("auto_sell_enabled", False)))
        self.spin_auto_sell_interval.setValue(int(junk.get("auto_sell_interval_min", 10)))
        self.chk_sell_on_start.setChecked(bool(junk.get("sell_on_start", False)))
        for _w in (self.chk_auto_sell, self.spin_auto_sell_interval, self.chk_sell_on_start):
            _w.blockSignals(False)
        safe_x = int(junk.get("safe_zone_x", -1))
        safe_y = int(junk.get("safe_zone_y", -1))
        if safe_x >= 0:
            _pos_txt = f"X={safe_x}  Y={safe_y}" if safe_y >= 0 else f"X={safe_x}"
            self.lbl_safe_zone_x.setText(_pos_txt)
            self.lbl_safe_zone_x.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.lbl_safe_zone_x.setText("미설정")
            self.lbl_safe_zone_x.setStyleSheet("color: gray; font-size: 10px;")

        # 경로 설정 복원
        self._populate_departure_zones()
        dep_zone = (junk.get("departure_zone") or "").strip()
        if dep_zone:
            _dep_idx = self.combo_departure_zone.findText(dep_zone)
            if _dep_idx >= 0:
                self.combo_departure_zone.blockSignals(True)
                self.combo_departure_zone.setCurrentIndex(_dep_idx)
                self.combo_departure_zone.blockSignals(False)
        extra_rope = junk.get("extra_rope") or {}
        self.spin_extra_rope_x.setValue(int(extra_rope.get("x", 0)))
        _dir = extra_rope.get("direction", "up")
        self.combo_extra_rope_dir.setCurrentIndex(0 if _dir == "up" else 1)
        self.spin_extra_rope_climb.setValue(float(extra_rope.get("climb_sec", 2.5)))

        self._refresh_cash_active_tpl_label()
        self._refresh_shop_open_tpl_label()
        self._refresh_equip_sell_tpl_label()
        self._refresh_equip_confirm_tpl_label()
        self._refresh_etc_active_tpl_label()
        self._refresh_scroll_bottom_tpl_label()

    def save_to_config(self):
        title = self.edit_window_title.text().strip()
        if title:
            self.config.set("settings2", "game_window_title", title)
