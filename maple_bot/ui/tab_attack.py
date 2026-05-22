# 공격 탭 - 공격 키, 점프 공격, 라이딩 옵션, 동적 버프 설정
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QFileDialog, QCheckBox, QSpinBox,
)


class TabAttack(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._normal_rows: list[dict] = []   # 일반버프 행 리스트
        self._toggle_rows: list[dict] = []   # 온오프버프 행 리스트

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_group())
        layout.addWidget(self._build_buff_group())
        layout.addStretch()
        self.load_from_config()

    def _build_group(self) -> QGroupBox:
        group = QGroupBox("공격 설정")
        layout = QVBoxLayout(group)

        # 공격 키
        row_key = QHBoxLayout()
        row_key.addWidget(QLabel("공격 키"))
        self.edit_attack_key = QLineEdit("ctrl")
        self.edit_attack_key.setFixedWidth(60)
        row_key.addWidget(self.edit_attack_key)
        row_key.addSpacing(12)
        row_key.addWidget(QLabel("몬스터 이미지"))
        self.edit_monster = QLineEdit()
        self.edit_monster.setPlaceholderText("monsters/slime.png  (비우면 무조건 공격)")
        btn_browse = QPushButton("찾기")
        btn_browse.setFixedWidth(50)
        btn_browse.clicked.connect(self._browse_monster)
        row_key.addWidget(self.edit_monster)
        row_key.addWidget(btn_browse)
        row_key.addStretch()
        layout.addLayout(row_key)

        # 몬스터 폴더
        row_folder = QHBoxLayout()
        row_folder.addWidget(QLabel("몬스터 폴더"))
        self.edit_monster_folder = QLineEdit()
        self.edit_monster_folder.setPlaceholderText(
            "monsters/슬라임사냥터  (비우면 monsters/ 전체 사용)")
        btn_browse_folder = QPushButton("폴더 선택")
        btn_browse_folder.setFixedWidth(70)
        btn_browse_folder.clicked.connect(self._browse_monster_folder)
        row_folder.addWidget(self.edit_monster_folder)
        row_folder.addWidget(btn_browse_folder)
        row_folder.addStretch()
        layout.addLayout(row_folder)

        # 옵션 체크박스
        row_opt = QHBoxLayout()
        self.chk_jump_attack = QCheckBox("공격 전 점프 (스킬 직전 스페이스)")
        self.chk_riding = QCheckBox("밧줄 탈 때 라이딩 해제/재탑승")
        self.chk_riding.setToolTip("밧줄 접근 전 라이딩 해제, 오르기 완료 후 재탑승")
        row_opt.addWidget(self.chk_jump_attack)
        row_opt.addSpacing(16)
        row_opt.addWidget(self.chk_riding)
        row_opt.addStretch()
        layout.addLayout(row_opt)

        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_to_config)
        layout.addWidget(btn_save)

        return group

    # ── 버프 그룹 (동적) ─────────────────────────────────────────────
    def _build_buff_group(self) -> QGroupBox:
        group = QGroupBox("버프 설정 (일정 시간마다 자동 사용)")
        outer = QVBoxLayout(group)

        # ── 일반 버프 섹션
        lbl_normal = QLabel("일반 버프  (지속 시간마다 키를 눌러 유지)")
        lbl_normal.setStyleSheet("font-weight: bold;")
        outer.addWidget(lbl_normal)

        self._normal_layout = QVBoxLayout()
        self._normal_layout.setSpacing(4)
        outer.addLayout(self._normal_layout)

        btn_add_normal = QPushButton("+ 일반 버프 추가")
        btn_add_normal.setFixedWidth(130)
        btn_add_normal.clicked.connect(lambda: self._add_buff_row("normal"))
        outer.addWidget(btn_add_normal)

        outer.addSpacing(8)

        # ── 온오프 버프 섹션
        lbl_toggle = QLabel("온오프 버프  (인터벌마다 키를 눌러 ON→OFF→ON 전환)")
        lbl_toggle.setStyleSheet("font-weight: bold;")
        outer.addWidget(lbl_toggle)

        self._toggle_layout = QVBoxLayout()
        self._toggle_layout.setSpacing(4)
        outer.addLayout(self._toggle_layout)

        btn_add_toggle = QPushButton("+ 온오프 버프 추가")
        btn_add_toggle.setFixedWidth(140)
        btn_add_toggle.clicked.connect(lambda: self._add_buff_row("toggle"))
        outer.addWidget(btn_add_toggle)

        outer.addSpacing(4)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.save_to_config)
        outer.addWidget(btn_save)

        return group

    def _add_buff_row(self, buff_type: str, data: dict | None = None) -> None:
        """버프 행 위젯을 동적으로 추가한다."""
        if data is None:
            data = {}

        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)

        chk = QCheckBox("사용")
        chk.setFixedWidth(55)
        chk.setChecked(data.get("enabled", False))

        row.addWidget(QLabel("키"))
        edit = QLineEdit()
        edit.setPlaceholderText("예: f3")
        edit.setFixedWidth(55)
        edit.setText(data.get("key", ""))

        row.addWidget(QLabel("간격"))
        spin = QSpinBox()
        spin.setRange(10, 9999)
        spin.setValue(int(data.get("interval_sec", 180)))
        spin.setSuffix(" 초")
        spin.setFixedWidth(80)

        btn_del = QPushButton("🗑")
        btn_del.setFixedWidth(28)
        btn_del.setToolTip("이 버프 행 삭제")

        row.addWidget(chk)
        row.addWidget(edit)
        row.addWidget(spin)
        row.addStretch()
        row.addWidget(btn_del)

        row_dict = {
            "widget": row_widget,
            "chk": chk,
            "edit": edit,
            "spin": spin,
        }

        if buff_type == "normal":
            self._normal_rows.append(row_dict)
            self._normal_layout.addWidget(row_widget)
            btn_del.clicked.connect(lambda: self._remove_buff_row("normal", row_dict))
        else:
            self._toggle_rows.append(row_dict)
            self._toggle_layout.addWidget(row_widget)
            btn_del.clicked.connect(lambda: self._remove_buff_row("toggle", row_dict))

    def _remove_buff_row(self, buff_type: str, row_dict: dict) -> None:
        """버프 행을 삭제한다."""
        row_dict["widget"].setVisible(False)
        row_dict["widget"].deleteLater()
        if buff_type == "normal":
            self._normal_rows.remove(row_dict)
        else:
            self._toggle_rows.remove(row_dict)

    def _clear_buff_rows(self, buff_type: str) -> None:
        """해당 타입의 모든 버프 행을 초기화한다."""
        rows = self._normal_rows if buff_type == "normal" else self._toggle_rows
        for rd in list(rows):
            rd["widget"].setVisible(False)
            rd["widget"].deleteLater()
        rows.clear()

    # ── 파일 찾기 ────────────────────────────────────────────────────
    def _browse_monster(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "몬스터 이미지 선택", "monsters", "이미지 (*.png *.jpg *.bmp)")
        if path:
            self.edit_monster.setText(path)

    def _browse_monster_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "몬스터 폴더 선택", "monsters")
        if folder:
            self.edit_monster_folder.setText(folder)

    # ── 저장/로드 ─────────────────────────────────────────────────────
    def save_to_config(self) -> None:
        self.config.set("attack", "key",              self.edit_attack_key.text().strip() or "ctrl")
        self.config.set("attack", "monster_template", self.edit_monster.text().strip())
        self.config.set("attack", "monster_folder",
                        self.edit_monster_folder.text().strip())
        self.config.set("attack", "jump_before_attack", self.chk_jump_attack.isChecked())
        self.config.set("attack", "riding_on_rope",     self.chk_riding.isChecked())

        self.config.set("attack", "normal_buffs", [
            {"enabled": rd["chk"].isChecked(),
             "key":     rd["edit"].text().strip(),
             "interval_sec": rd["spin"].value()}
            for rd in self._normal_rows
        ])
        self.config.set("attack", "toggle_buffs", [
            {"enabled": rd["chk"].isChecked(),
             "key":     rd["edit"].text().strip(),
             "interval_sec": rd["spin"].value()}
            for rd in self._toggle_rows
        ])
        self.config.save()

    def load_from_config(self) -> None:
        a = self.config.get("attack") or {}
        self.edit_attack_key.setText(a.get("key", "ctrl"))
        self.edit_monster.setText(a.get("monster_template", ""))
        self.edit_monster_folder.setText(a.get("monster_folder", ""))
        self.chk_jump_attack.setChecked(a.get("jump_before_attack", False))
        self.chk_riding.setChecked(a.get("riding_on_rope", False))

        self._clear_buff_rows("normal")
        for item in (a.get("normal_buffs") or []):
            self._add_buff_row("normal", item)

        self._clear_buff_rows("toggle")
        for item in (a.get("toggle_buffs") or []):
            self._add_buff_row("toggle", item)
