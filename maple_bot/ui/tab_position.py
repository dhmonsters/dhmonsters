# 위치 탭 - 매크로방지몹 해제 / 마을 귀환 주문서 / 사냥터 복귀
from __future__ import annotations
import glob
import os

import cv2
import mss
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QSpinBox, QComboBox, QScrollArea, QMessageBox,
)
from PyQt6.QtCore import Qt

from ui.region_selector import RegionSelector


class TabPosition(QWidget):
    def __init__(self, config, hotkey_manager=None):
        super().__init__()
        self.config = config
        self._hk = hotkey_manager
        self._pending_anti_mob_key: str = ""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        layout.addWidget(self._build_map_exit_group())
        layout.addWidget(self._build_anti_mob_group())
        layout.addWidget(self._build_town_scroll_group())
        layout.addWidget(self._build_hunting_return_group())
        layout.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.load_from_config()

    # ── 사냥터 이탈 감지 ──────────────────────────────────────────────
    def _build_map_exit_group(self) -> QGroupBox:
        group = QGroupBox("사냥터 이탈 감지 설정")
        layout = QVBoxLayout(group)

        self.chk_map_exit = QCheckBox("이탈 감지 활성화 (미니맵 이름이 바뀌면 봇 정지/알림)")
        layout.addWidget(self.chk_map_exit)

        # 맵 이름 기준 이미지 행
        ref_row = QHBoxLayout()
        self.lbl_map_name_ref = QLabel("❌ 기준 이미지 없음")
        self.lbl_map_name_ref.setStyleSheet("color: red;")
        ref_row.addWidget(self.lbl_map_name_ref)
        ref_row.addStretch()
        btn_capture_name = QPushButton("📷 현재 맵 이름 저장")
        btn_capture_name.setFixedWidth(150)
        btn_capture_name.setToolTip(
            "사냥터에서 미니맵 이름 텍스트 부분만 드래그로 선택하세요.\n"
            "기준 이미지로 저장되며, 다른 맵으로 이동하면 감지됩니다."
        )
        btn_capture_name.clicked.connect(self._capture_map_name_ref)
        ref_row.addWidget(btn_capture_name)
        layout.addLayout(ref_row)

        # 판정 횟수 행
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("판정 횟수"))
        self.spin_map_exit_grace = QSpinBox()
        self.spin_map_exit_grace.setRange(1, 30)
        self.spin_map_exit_grace.setValue(3)
        self.spin_map_exit_grace.setFixedWidth(55)
        row1.addWidget(self.spin_map_exit_grace)
        row1.addWidget(QLabel("회 연속 불일치 시 이탈로 판정 (1회=약 1초)"))
        row1.addStretch()
        layout.addLayout(row1)

        # 감지 시 동작 행
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("감지 시 동작"))
        self.combo_map_exit_action = QComboBox()
        self.combo_map_exit_action.addItems(["봇 정지", "텔레그램 알림", "봇 정지 + 텔레그램"])
        self.combo_map_exit_action.setFixedWidth(170)
        row2.addWidget(self.combo_map_exit_action)
        row2.addWidget(QLabel("(텔레그램은 설정1 거탐 설정의 토큰/Chat ID 공유)"))
        row2.addStretch()
        layout.addLayout(row2)

        btn_save = QPushButton("💾 저장")
        btn_save.setFixedWidth(70)
        btn_save.clicked.connect(self._save_map_exit_settings)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignRight)

        self._refresh_map_name_ref_label()
        return group

    def _refresh_map_name_ref_label(self) -> None:
        from core.config_manager import get_user_templates_dir
        ref_path = os.path.join(get_user_templates_dir(), "map_name_ref.png")
        if os.path.exists(ref_path):
            me = self.config.get("map_exit") or {}
            nr = me.get("name_region")
            if isinstance(nr, dict):
                self.lbl_map_name_ref.setText("✅ 기준 이미지 저장됨 (비율)")
            elif isinstance(nr, list) and len(nr) == 4:
                w, h = nr[2], nr[3]
                self.lbl_map_name_ref.setText(f"✅ 기준 이미지 저장됨 ({w}×{h} px)")
            else:
                self.lbl_map_name_ref.setText("✅ 기준 이미지 저장됨")
            self.lbl_map_name_ref.setStyleSheet("color: green;")
        else:
            self.lbl_map_name_ref.setText("❌ 기준 이미지 없음 — '📷 현재 맵 이름 저장' 클릭")
            self.lbl_map_name_ref.setStyleSheet("color: red;")

    def _capture_map_name_ref(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_map_name_ref)
        self._map_name_selector = sel
        sel.show()

    def _save_map_name_ref(self, x: int, y: int, w: int, h: int) -> None:
        from core.config_manager import get_user_templates_dir, get_game_window_rect, logical_to_physical_coords
        from ui.region_selector import logical_to_physical
        px, py, pw, ph = logical_to_physical(x, y, w, h)
        ref_path = os.path.join(get_user_templates_dir(), "map_name_ref.png")
        try:
            with mss.mss() as sct:
                raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
                img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(ref_path, img)
        except Exception as exc:
            QMessageBox.critical(self, "저장 실패", f"이미지 저장 오류: {exc}")
            return
        ox, oy, cw, ch = get_game_window_rect(self.config)
        if cw > 0 and ch > 0:
            region = {
                "x_ratio": (x - ox) / cw,
                "y_ratio": (y - oy) / ch,
                "w_ratio": w / cw,
                "h_ratio": h / ch,
            }
            mode = "비율"
        else:
            region = [x, y, w, h]
            mode = "절대"
        self.config.set("map_exit", "name_region", region)
        self.config.save()
        self._refresh_map_name_ref_label()
        QMessageBox.information(self, "저장 완료", f"맵 이름 기준 이미지 저장 완료 ({pw}×{ph} px, {mode})")

    def _save_map_exit_settings(self) -> None:
        action_map = {"봇 정지": "stop", "텔레그램 알림": "telegram", "봇 정지 + 텔레그램": "both"}
        action = action_map.get(self.combo_map_exit_action.currentText(), "stop")
        self.config.set("map_exit", "enabled",     self.chk_map_exit.isChecked())
        self.config.set("map_exit", "grace_count", self.spin_map_exit_grace.value())
        self.config.set("map_exit", "action",      action)
        self.config.save()
        QMessageBox.information(self, "저장 완료", "사냥터 이탈 감지 설정이 저장되었습니다.")

    # ── 매크로방지몹 해제 ─────────────────────────────────────────────
    def _build_anti_mob_group(self) -> QGroupBox:
        group = QGroupBox("매크로방지몹 해제")
        layout = QVBoxLayout(group)

        self.chk_anti_mob = QCheckBox("감지 활성화 (방지몹 발견 시 공격 정지 후 해제 동작)")
        layout.addWidget(self.chk_anti_mob)

        # 탐지 이미지
        layout.addWidget(QLabel("── 탐지 이미지 ─────────────────────"))
        tpl_row = QHBoxLayout()
        self.lbl_anti_mob_tpl = QLabel("없음")
        self.lbl_anti_mob_tpl.setStyleSheet("color: gray;")
        btn_tpl_add = QPushButton("+ 추가 캡처")
        btn_tpl_add.setFixedWidth(90)
        btn_tpl_add.setToolTip("방지몹 이미지 부분을 드래그해서 등록합니다. 여러 장 등록 가능.")
        btn_tpl_add.clicked.connect(self._capture_anti_mob_template)
        btn_tpl_del = QPushButton("전체 삭제")
        btn_tpl_del.setFixedWidth(70)
        btn_tpl_del.clicked.connect(self._clear_anti_mob_templates)
        tpl_row.addWidget(self.lbl_anti_mob_tpl)
        tpl_row.addStretch()
        tpl_row.addWidget(btn_tpl_add)
        tpl_row.addWidget(btn_tpl_del)
        layout.addLayout(tpl_row)

        # 탐지 영역
        region_row = QHBoxLayout()
        self.lbl_anti_mob_region = QLabel("탐지 영역: 전체 화면")
        self.lbl_anti_mob_region.setStyleSheet("color: gray;")
        btn_set_region = QPushButton("📍 영역 설정")
        btn_set_region.setFixedWidth(90)
        btn_set_region.setToolTip("방지몹이 나타나는 화면 영역만 좁게 지정하면 오탐이 줄어듭니다.")
        btn_set_region.clicked.connect(self._set_anti_mob_region)
        btn_rst_region = QPushButton("초기화")
        btn_rst_region.setFixedWidth(55)
        btn_rst_region.clicked.connect(self._reset_anti_mob_region)
        region_row.addWidget(self.lbl_anti_mob_region)
        region_row.addStretch()
        region_row.addWidget(btn_set_region)
        region_row.addWidget(btn_rst_region)
        layout.addLayout(region_row)

        # 이동 목표 + 해제 방식
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("이동 목표 (미니맵X)"))
        self.spin_anti_mob_x = QSpinBox()
        self.spin_anti_mob_x.setRange(0, 500)
        self.spin_anti_mob_x.setValue(100)
        self.spin_anti_mob_x.setFixedWidth(65)
        self.spin_anti_mob_x.setToolTip("방지몹 해제 동작을 수행할 미니맵 X 좌표.")
        row1.addWidget(self.spin_anti_mob_x)
        row1.addSpacing(16)
        row1.addWidget(QLabel("해제 방식"))
        self.combo_anti_mob_type = QComboBox()
        self.combo_anti_mob_type.addItems(["클릭형", "아이템 뿌리기형", "기본 공격형"])
        self.combo_anti_mob_type.setFixedWidth(140)
        row1.addWidget(self.combo_anti_mob_type)
        row1.addStretch()
        layout.addLayout(row1)

        # ── 클릭형 패널 ──────────────────────────────────────────────
        self._anti_mob_click_panel = QWidget()
        cp_lay = QVBoxLayout(self._anti_mob_click_panel)
        cp_lay.setContentsMargins(0, 4, 0, 0)
        cp_lay.addWidget(QLabel("── 클릭형: 키 시퀀스 ──────────────────"))
        ck_row = QHBoxLayout()
        ck_row.addWidget(QLabel("키 (쉼표 구분)"))
        self.edit_anti_mob_keys = QLineEdit()
        self.edit_anti_mob_keys.setPlaceholderText("예: space,right,enter")
        ck_row.addWidget(self.edit_anti_mob_keys)
        cp_lay.addLayout(ck_row)
        layout.addWidget(self._anti_mob_click_panel)

        # ── 아이템 뿌리기형 패널 ─────────────────────────────────────
        self._anti_mob_item_panel = QWidget()
        ip_lay = QVBoxLayout(self._anti_mob_item_panel)
        ip_lay.setContentsMargins(0, 4, 0, 0)
        ip_lay.addWidget(QLabel("── 아이템 뿌리기형 좌표 ──────────────"))
        self._anti_mob_item_coords: dict[str, QLabel] = {}
        for key, title in [("item_inv_tab", "인벤토리 기타탭"), ("item_slot", "버릴 아이템 슬롯")]:
            row = QHBoxLayout()
            lbl_t = QLabel(title)
            lbl_t.setFixedWidth(130)
            lbl_v = QLabel("미설정")
            lbl_v.setStyleSheet("color: gray; font-size: 10px;")
            self._anti_mob_item_coords[key] = lbl_v
            btn_s = QPushButton("📍 드래그")
            btn_s.setFixedWidth(78)
            btn_s.clicked.connect(lambda _, k=key: self._set_anti_mob_coord(k))
            btn_r = QPushButton("✕")
            btn_r.setFixedWidth(24)
            btn_r.clicked.connect(lambda _, k=key: self._reset_anti_mob_coord(k))
            row.addWidget(lbl_t)
            row.addWidget(lbl_v)
            row.addStretch()
            row.addWidget(btn_s)
            row.addWidget(btn_r)
            ip_lay.addLayout(row)
        layout.addWidget(self._anti_mob_item_panel)

        # ── 기본 공격형 패널 ──────────────────────────────────────────
        self._anti_mob_basic_panel = QWidget()
        bp_lay = QVBoxLayout(self._anti_mob_basic_panel)
        bp_lay.setContentsMargins(0, 4, 0, 0)
        bp_lay.addWidget(QLabel("── 기본 공격형 ──────────────────────"))
        bc_row = QHBoxLayout()
        bc_row.addWidget(QLabel("공격 횟수"))
        self.spin_anti_mob_count = QSpinBox()
        self.spin_anti_mob_count.setRange(1, 50)
        self.spin_anti_mob_count.setValue(5)
        self.spin_anti_mob_count.setFixedWidth(65)
        bc_row.addWidget(self.spin_anti_mob_count)
        bc_row.addWidget(QLabel("회 (attack 탭의 공격키 사용)"))
        bc_row.addStretch()
        bp_lay.addLayout(bc_row)
        layout.addWidget(self._anti_mob_basic_panel)

        # 저장 버튼
        btn_save = QPushButton("💾 저장")
        btn_save.setFixedWidth(70)
        btn_save.clicked.connect(self._save_anti_mob_settings)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignRight)

        # 방식 변경 시 패널 전환
        self.combo_anti_mob_type.currentIndexChanged.connect(self._on_anti_mob_type_changed)
        self._on_anti_mob_type_changed(0)

        return group

    def _on_anti_mob_type_changed(self, idx: int) -> None:
        self._anti_mob_click_panel.setVisible(idx == 0)
        self._anti_mob_item_panel.setVisible(idx == 1)
        self._anti_mob_basic_panel.setVisible(idx == 2)

    def _refresh_anti_mob_tpl_label(self) -> None:
        from core.config_manager import get_user_templates_dir
        tpl_dir = get_user_templates_dir()
        count = len(glob.glob(os.path.join(tpl_dir, "anti_mob_*.png")))
        if count:
            self.lbl_anti_mob_tpl.setText(f"✅ {count}개 등록됨")
            self.lbl_anti_mob_tpl.setStyleSheet("color: green;")
        else:
            self.lbl_anti_mob_tpl.setText("없음 (+ 추가 캡처로 등록하세요)")
            self.lbl_anti_mob_tpl.setStyleSheet("color: gray;")

    def _capture_anti_mob_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_anti_mob_template)
        self._anti_mob_tpl_selector = sel
        sel.show()

    def _save_anti_mob_template(self, x: int, y: int, w: int, h: int) -> None:
        from core.config_manager import get_user_templates_dir
        from ui.region_selector import logical_to_physical
        px, py, pw, ph = logical_to_physical(x, y, w, h)
        tpl_dir = get_user_templates_dir()
        existing = sorted(glob.glob(os.path.join(tpl_dir, "anti_mob_*.png")))
        next_num = len(existing) + 1
        path = os.path.join(tpl_dir, f"anti_mob_{next_num}.png")
        with mss.mss() as sct:
            raw = sct.grab({"left": px, "top": py, "width": pw, "height": ph})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite(path, img)
        self._refresh_anti_mob_tpl_label()
        QMessageBox.information(self, "완료", f"방지몹 템플릿 {next_num}번 저장 완료 ({pw}×{ph}px)")

    def _clear_anti_mob_templates(self) -> None:
        from core.config_manager import get_user_templates_dir
        tpl_dir = get_user_templates_dir()
        files = glob.glob(os.path.join(tpl_dir, "anti_mob_*.png"))
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
        self._refresh_anti_mob_tpl_label()

    def _set_anti_mob_region(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_anti_mob_region)
        self._anti_mob_region_selector = sel
        sel.show()

    def _save_anti_mob_region(self, x: int, y: int, w: int, h: int) -> None:
        from ui.region_selector import logical_to_physical
        from core.config_manager import get_game_window_origin
        gx, gy = logical_to_physical(x, y, 0, 0)[:2]
        ox, oy = get_game_window_origin(self.config)
        rx, ry = gx - ox, gy - oy
        self.config.set("anti_mob", "detect_region", [rx, ry, w, h])
        self.config.save()
        self.lbl_anti_mob_region.setText(f"탐지 영역: X={rx} Y={ry} W={w} H={h}")
        self.lbl_anti_mob_region.setStyleSheet("color: green;")

    def _reset_anti_mob_region(self) -> None:
        self.config.set("anti_mob", "detect_region", None)
        self.config.save()
        self.lbl_anti_mob_region.setText("탐지 영역: 전체 화면")
        self.lbl_anti_mob_region.setStyleSheet("color: gray;")

    def _set_anti_mob_coord(self, key: str) -> None:
        self._pending_anti_mob_key = key
        sel = RegionSelector()
        sel.region_selected.connect(self._save_anti_mob_coord)
        self._anti_mob_coord_selector = sel
        sel.show()

    def _save_anti_mob_coord(self, x: int, y: int, w: int, h: int) -> None:
        from ui.region_selector import logical_to_physical
        gx, gy = logical_to_physical(x, y, 0, 0)[:2]
        key = self._pending_anti_mob_key
        val = [gx, gy, w, h]
        self.config.set("anti_mob", key, val)
        self.config.save()
        lbl = self._anti_mob_item_coords.get(key)
        if lbl:
            lbl.setText(f"X={gx} Y={gy} W={w} H={h}")
            lbl.setStyleSheet("color: green; font-size: 10px;")

    def _reset_anti_mob_coord(self, key: str) -> None:
        self.config.set("anti_mob", key, None)
        self.config.save()
        lbl = self._anti_mob_item_coords.get(key)
        if lbl:
            lbl.setText("미설정")
            lbl.setStyleSheet("color: gray; font-size: 10px;")

    def _save_anti_mob_settings(self) -> None:
        type_map = {"클릭형": "click", "아이템 뿌리기형": "item", "기본 공격형": "basic"}
        self.config.set("anti_mob", "enabled",     self.chk_anti_mob.isChecked())
        self.config.set("anti_mob", "type",        type_map.get(self.combo_anti_mob_type.currentText(), "click"))
        self.config.set("anti_mob", "target_x",    self.spin_anti_mob_x.value())
        self.config.set("anti_mob", "click_keys",  self.edit_anti_mob_keys.text().strip())
        self.config.set("anti_mob", "basic_count", self.spin_anti_mob_count.value())
        self.config.save()
        QMessageBox.information(self, "저장 완료", "매크로방지몹 해제 설정이 저장되었습니다.")

    # ── 긴급 마을 귀환 ───────────────────────────────────────────────
    def _build_town_scroll_group(self) -> QGroupBox:
        group = QGroupBox("긴급 마을 귀환")
        layout = QVBoxLayout(group)

        note = QLabel(
            "봇 내부에서 귀환 명령 시 설정된 키를 눌러 마을로 귀환합니다.\n"
            "HP 또는 MP가 설정 퍼센트 미만이 되면 자동으로 귀환 키를 발동합니다."
        )
        note.setStyleSheet("color: gray; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # 기본 설정 행
        row = QHBoxLayout()
        self.chk_town_scroll = QCheckBox("활성화")
        row.addWidget(self.chk_town_scroll)
        row.addSpacing(16)
        row.addWidget(QLabel("귀환 키"))
        self.edit_town_scroll_key = QLineEdit("9")
        self.edit_town_scroll_key.setFixedWidth(55)
        self.edit_town_scroll_key.setToolTip("귀환 주문서가 등록된 단축키 (예: 9, 0, F1)")
        row.addWidget(self.edit_town_scroll_key)
        row.addStretch()
        layout.addLayout(row)

        # HP 발동 조건
        hp_row = QHBoxLayout()
        self.chk_ts_hp = QCheckBox("HP")
        self.spin_ts_hp_pct = QSpinBox()
        self.spin_ts_hp_pct.setRange(1, 99)
        self.spin_ts_hp_pct.setValue(10)
        self.spin_ts_hp_pct.setFixedWidth(65)
        self.spin_ts_hp_pct.setSuffix(" % 미만시 발동")
        hp_row.addWidget(self.chk_ts_hp)
        hp_row.addWidget(self.spin_ts_hp_pct)
        hp_row.addStretch()
        layout.addLayout(hp_row)

        # MP 발동 조건
        mp_row = QHBoxLayout()
        self.chk_ts_mp = QCheckBox("MP")
        self.spin_ts_mp_pct = QSpinBox()
        self.spin_ts_mp_pct.setRange(1, 99)
        self.spin_ts_mp_pct.setValue(10)
        self.spin_ts_mp_pct.setFixedWidth(65)
        self.spin_ts_mp_pct.setSuffix(" % 미만시 발동")
        mp_row.addWidget(self.chk_ts_mp)
        mp_row.addWidget(self.spin_ts_mp_pct)
        mp_row.addStretch()
        layout.addLayout(mp_row)

        btn_save = QPushButton("💾 저장")
        btn_save.setFixedWidth(70)
        btn_save.clicked.connect(self._save_town_scroll_settings)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignRight)

        return group

    def _save_town_scroll_settings(self) -> None:
        key = self.edit_town_scroll_key.text().strip()
        self.config.set("town_scroll", "enabled",          self.chk_town_scroll.isChecked())
        self.config.set("town_scroll", "key",              key)
        self.config.set("town_scroll", "hp_trigger",       self.chk_ts_hp.isChecked())
        self.config.set("town_scroll", "hp_trigger_pct",   self.spin_ts_hp_pct.value())
        self.config.set("town_scroll", "mp_trigger",       self.chk_ts_mp.isChecked())
        self.config.set("town_scroll", "mp_trigger_pct",   self.spin_ts_mp_pct.value())
        self.config.save()
        QMessageBox.information(self, "저장 완료", "긴급 마을 귀환 설정이 저장되었습니다.")

    # ── 사냥터 복귀 (플레이스홀더) ───────────────────────────────────
    def _build_hunting_return_group(self) -> QGroupBox:
        group = QGroupBox("사냥터 복귀")
        layout = QVBoxLayout(group)

        self.chk_hunting_return = QCheckBox("활성화")
        layout.addWidget(self.chk_hunting_return)

        note = QLabel("(기능 구현 예정)\n마을 귀환 후 사냥터로 자동 복귀합니다.")
        note.setStyleSheet("color: gray; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        return group

    # ── 핫키 매니저 주입 ─────────────────────────────────────────────
    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk

    # ── config 연동 ───────────────────────────────────────────────────
    def load_from_config(self) -> None:
        # 사냥터 이탈 감지
        me = self.config.get("map_exit") or {}
        self.chk_map_exit.setChecked(bool(me.get("enabled", False)))
        self.spin_map_exit_grace.setValue(int(me.get("grace_count", 3)))
        action_labels = {"stop": "봇 정지", "telegram": "텔레그램 알림", "both": "봇 정지 + 텔레그램"}
        label = action_labels.get(me.get("action", "stop"), "봇 정지")
        idx = self.combo_map_exit_action.findText(label)
        if idx >= 0:
            self.combo_map_exit_action.setCurrentIndex(idx)
        self._refresh_map_name_ref_label()

        # 매크로방지몹
        am = self.config.get("anti_mob") or {}
        self.chk_anti_mob.setChecked(bool(am.get("enabled", False)))
        type_map = {"click": 0, "item": 1, "basic": 2}
        self.combo_anti_mob_type.setCurrentIndex(type_map.get(am.get("type", "click"), 0))
        self.spin_anti_mob_x.setValue(int(am.get("target_x", 100)))
        self.edit_anti_mob_keys.setText(am.get("click_keys", "space,enter"))
        self.spin_anti_mob_count.setValue(int(am.get("basic_count", 5)))
        region = am.get("detect_region")
        if region and len(region) == 4:
            x, y, w, h = region
            self.lbl_anti_mob_region.setText(f"탐지 영역: X={x} Y={y} W={w} H={h}")
            self.lbl_anti_mob_region.setStyleSheet("color: green;")
        for key, lbl in self._anti_mob_item_coords.items():
            v = am.get(key)
            if v and len(v) == 4:
                lbl.setText(f"X={v[0]} Y={v[1]} W={v[2]} H={v[3]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
        self._refresh_anti_mob_tpl_label()

        # 긴급 마을 귀환
        ts = self.config.get("town_scroll") or {}
        self.chk_town_scroll.setChecked(bool(ts.get("enabled", False)))
        self.edit_town_scroll_key.setText(ts.get("key", "9"))
        self.chk_ts_hp.setChecked(bool(ts.get("hp_trigger", False)))
        self.spin_ts_hp_pct.setValue(int(ts.get("hp_trigger_pct", 10)))
        self.chk_ts_mp.setChecked(bool(ts.get("mp_trigger", False)))
        self.spin_ts_mp_pct.setValue(int(ts.get("mp_trigger_pct", 10)))

    def save_to_config(self) -> None:
        # 긴급 마을 귀환
        self.config.set("town_scroll", "enabled",        self.chk_town_scroll.isChecked())
        self.config.set("town_scroll", "key",            self.edit_town_scroll_key.text().strip())
        self.config.set("town_scroll", "hp_trigger",     self.chk_ts_hp.isChecked())
        self.config.set("town_scroll", "hp_trigger_pct", self.spin_ts_hp_pct.value())
        self.config.set("town_scroll", "mp_trigger",     self.chk_ts_mp.isChecked())
        self.config.set("town_scroll", "mp_trigger_pct", self.spin_ts_mp_pct.value())
        self.config.save()
