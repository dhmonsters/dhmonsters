# 설정 폼 위젯 — config 양방향 바인딩(로드/변경시 자동저장). 6페이지가 선언적으로 짧아지게
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QSpinBox, QComboBox,
    QDoubleSpinBox, QSlider,
)
from PyQt6.QtCore import Qt

from core_ui.theme import SPACING


class SliderField:
    """라벨 + 드래그 슬라이더 + 값. config 양방향. self.row=QWidget.
    is_int=False면 0.1~1.0 비율(%표시), is_int=True면 정수 그대로(예 색 허용오차 0~255)."""

    def __init__(self, label: str, config, keys: tuple,
                 lo: float = 0.1, hi: float = 1.0, default: float = 0.9,
                 is_int: bool = False, label_w: int = 130):
        self._cfg = config
        self._keys = keys
        self._is_int = is_int
        self.row = QWidget()
        h = QHBoxLayout(self.row)
        h.setContentsMargins(0, SPACING["xxs"], 0, SPACING["xxs"])
        h.setSpacing(SPACING["xs"])
        lbl = QLabel(label); lbl.setFixedWidth(label_w); lbl.setObjectName("subtle")
        h.addWidget(lbl)
        self.widget = QSlider(Qt.Orientation.Horizontal)
        cur = config.get(*keys, default=default)
        if is_int:
            self.widget.setRange(int(lo), int(hi)); self.widget.setValue(int(cur))
            self._val = QLabel(str(int(cur)))
        else:
            self.widget.setRange(int(lo * 100), int(hi * 100))
            self.widget.setValue(int(round(float(cur) * 100)))
            self._val = QLabel(f"{int(round(float(cur) * 100))}%")
        self._val.setFixedWidth(40)
        h.addWidget(self.widget, 1)
        h.addWidget(self._val)
        # 라벨·메모리값은 매 변경마다 실시간 갱신(가벼움), 디스크 저장은 드래그 끝에 1회만.
        # 연결은 반드시 lambda로 — bound method(self._changed)로 연결하면 PyQt6가 슬롯을
        # 약참조로 들어, 이 객체가 GC될 때 연결이 끊겨 드래그해도 숫자가 안 바뀌었음.
        # (다른 _Field들은 lambda를 써서 클로저가 self를 잡아 살아있다.)
        self.row._field = self   # .row 위젯이 이 객체를 강참조로 유지(GC 방지)
        self.widget.valueChanged.connect(lambda v: self._changed(v))
        self.widget.sliderReleased.connect(lambda: self._cfg.save())

    def _changed(self, v: int) -> None:
        if self._is_int:
            self._val.setText(str(v)); self._cfg.set(*self._keys, int(v))
        else:
            self._val.setText(f"{v}%"); self._cfg.set(*self._keys, round(v / 100.0, 2))
        if not self.widget.isSliderDown():   # 드래그가 아니면(키보드/클릭) 즉시 저장
            self._cfg.save()


class StatusField:
    """라벨 + 상태표시(● 설정됨 / ○ 미설정 색상) + 액션 버튼들.
    숫자 대신 색으로 입력 완료를 확인한다. refresh()로 상태 갱신, self.row=QWidget."""

    def __init__(self, label: str, is_set_fn, buttons: list,
                 extra=None, label_w: int = 130):
        self._is_set = is_set_fn
        self.row = QWidget()
        h = QHBoxLayout(self.row)
        h.setContentsMargins(0, SPACING["xxs"], 0, SPACING["xxs"])
        h.setSpacing(SPACING["sm"])
        lbl = QLabel(label); lbl.setFixedWidth(label_w); lbl.setObjectName("subtle")
        h.addWidget(lbl)
        self.status = QLabel(); self.status.setFixedWidth(72)
        h.addWidget(self.status)
        for b in buttons:
            h.addWidget(b)
        if extra is not None:        # 옆에 슬라이더 등 동반 위젯(남은 폭 채움)
            h.addWidget(extra, 1)
        else:
            h.addStretch()
        self.refresh()

    def refresh(self) -> None:
        ok = False
        try:
            ok = bool(self._is_set())
        except Exception:
            ok = False
        if ok:
            self.status.setText("● 설정됨")
            self.status.setStyleSheet("color:#3ada85; font-weight:600; background:transparent;")
        else:
            self.status.setText("○ 미설정")
            self.status.setStyleSheet("color:#80848e; background:transparent;")


class _Field:
    """라벨 + 입력위젯 한 행. config 키에 양방향 바인딩.
    self.row = QWidget(레이아웃 포함), self.widget = 입력위젯."""

    def __init__(self, label: str, config, keys: tuple, label_w: int = 130):
        self._cfg = config
        self._keys = keys
        self.row = QWidget()
        h = QHBoxLayout(self.row)
        h.setContentsMargins(0, SPACING["xxs"], 0, SPACING["xxs"])
        h.setSpacing(SPACING["sm"])
        lbl = QLabel(label)
        lbl.setFixedWidth(label_w)
        lbl.setObjectName("subtle")
        h.addWidget(lbl)
        self.widget = self._build()
        h.addWidget(self.widget, 1)
        self._load()
        self._connect()

    # 하위 클래스 구현
    def _build(self) -> QWidget: ...
    def _load(self) -> None: ...
    def _connect(self) -> None: ...

    def _save(self, value) -> None:
        self._cfg.set(*self._keys, value)
        self._cfg.save()


class CheckField(_Field):
    def __init__(self, label, config, keys, default=False, **kw):
        self._default = default
        super().__init__(label, config, keys, **kw)

    def _build(self): return QCheckBox()
    def _load(self):
        self.widget.setChecked(bool(self._cfg.get(*self._keys, default=self._default)))
    def _connect(self):
        self.widget.toggled.connect(lambda v: self._save(bool(v)))


class TextField(_Field):
    def __init__(self, label, config, keys, default="", **kw):
        self._default = default
        super().__init__(label, config, keys, **kw)

    def _build(self): return QLineEdit()
    def _load(self):
        self.widget.setText(str(self._cfg.get(*self._keys, default=self._default)))
    def _connect(self):
        self.widget.textChanged.connect(lambda v: self._save(v))


class IntField(_Field):
    def __init__(self, label, config, keys, lo=0, hi=9999, default=0, **kw):
        self._lo, self._hi, self._default = lo, hi, default
        super().__init__(label, config, keys, **kw)

    def _build(self):
        s = QSpinBox(); s.setRange(self._lo, self._hi); s.setFixedWidth(120); return s
    def _load(self):
        self.widget.setValue(int(self._cfg.get(*self._keys, default=self._default)))
    def _connect(self):
        self.widget.valueChanged.connect(lambda v: self._save(int(v)))


class FloatField(_Field):
    def __init__(self, label, config, keys, lo=0.0, hi=1.0, step=0.05, default=0.0, **kw):
        self._lo, self._hi, self._step, self._default = lo, hi, step, default
        super().__init__(label, config, keys, **kw)

    def _build(self):
        s = QDoubleSpinBox(); s.setRange(self._lo, self._hi)
        s.setSingleStep(self._step); s.setDecimals(2); s.setFixedWidth(120); return s
    def _load(self):
        self.widget.setValue(float(self._cfg.get(*self._keys, default=self._default)))
    def _connect(self):
        self.widget.valueChanged.connect(lambda v: self._save(float(v)))


class ComboField(_Field):
    """options=저장값(영문). labels={저장값: 한글표시}를 주면 화면엔 한글, 저장은 영문."""

    def __init__(self, label, config, keys, options: list[str], default="",
                 labels: dict | None = None, **kw):
        self._options, self._default = options, default
        self._labels = labels or {}
        super().__init__(label, config, keys, **kw)

    def _build(self):
        c = QComboBox()
        for v in self._options:
            c.addItem(self._labels.get(v, v), v)   # 표시=한글(있으면), userData=저장값
        return c
    def _load(self):
        cur = str(self._cfg.get(*self._keys, default=self._default or self._options[0]))
        i = self.widget.findData(cur)
        if i >= 0:
            self.widget.setCurrentIndex(i)
    def _connect(self):
        self.widget.currentIndexChanged.connect(
            lambda _i: self._save(self.widget.currentData()))
