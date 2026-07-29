# 설정 화면의 공통 입력 위젯을 제공하는 UI 헬퍼입니다.
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QSpinBox, QComboBox,
    QDoubleSpinBox, QSlider,
)
from PyQt6.QtCore import Qt

from core_ui.theme import SPACING


class SliderField:
    """라벨, 슬라이더, 현재값 표시를 하나의 행으로 묶는 설정 위젯입니다."""

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
        lbl = QLabel(label)
        lbl.setFixedWidth(label_w)
        lbl.setObjectName("subtle")
        h.addWidget(lbl)
        self.widget = QSlider(Qt.Orientation.Horizontal)
        cur = config.get(*keys, default=default)
        if is_int:
            self.widget.setRange(int(lo), int(hi))
            self.widget.setValue(int(cur))
            self._val = QLabel(str(int(cur)))
        else:
            self.widget.setRange(int(lo * 100), int(hi * 100))
            self.widget.setValue(int(round(float(cur) * 100)))
            self._val = QLabel(f"{int(round(float(cur) * 100))}%")
        self._val.setFixedWidth(40)
        h.addWidget(self.widget, 1)
        h.addWidget(self._val)
        self.row._field = self
        self.widget.valueChanged.connect(lambda v: self._changed(v))
        self.widget.sliderReleased.connect(lambda: self._cfg.save())

    def _changed(self, v: int) -> None:
        if self._is_int:
            self._val.setText(str(v))
            self._cfg.set(*self._keys, int(v))
        else:
            self._val.setText(f"{v}%")
            self._cfg.set(*self._keys, round(v / 100.0, 2))
        if not self.widget.isSliderDown():
            self._cfg.save()


class StatusField:
    """라벨, 설정 상태, 동작 버튼을 하나의 행으로 묶는 설정 위젯입니다."""

    def __init__(self, label: str, is_set_fn, buttons: list,
                 extra=None, label_w: int = 130):
        self._is_set = is_set_fn
        self.row = QWidget()
        h = QHBoxLayout(self.row)
        h.setContentsMargins(0, SPACING["xxs"], 0, SPACING["xxs"])
        h.setSpacing(SPACING["sm"])
        lbl = QLabel(label)
        lbl.setFixedWidth(label_w)
        lbl.setObjectName("subtle")
        h.addWidget(lbl)
        self.status = QLabel()
        self.status.setFixedWidth(88)
        h.addWidget(self.status)
        for b in buttons:
            h.addWidget(b)
        if extra is not None:
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
            self.status.setText("설정됨")
            self.status.setStyleSheet("color:#3ada85; font-weight:600; background:transparent;")
        else:
            self.status.setText("미설정")
            self.status.setStyleSheet("color:#80848e; background:transparent;")


class _Field:
    """라벨과 입력 위젯을 하나의 행으로 묶고 config 값과 연결합니다."""

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
        s = QSpinBox()
        s.setRange(self._lo, self._hi)
        s.setFixedWidth(150)
        return s
    def _load(self):
        self.widget.setValue(int(self._cfg.get(*self._keys, default=self._default)))
    def _connect(self):
        self.widget.valueChanged.connect(lambda v: self._save(int(v)))


class FloatField(_Field):
    def __init__(self, label, config, keys, lo=0.0, hi=1.0, step=0.05, default=0.0, **kw):
        self._lo, self._hi, self._step, self._default = lo, hi, step, default
        super().__init__(label, config, keys, **kw)

    def _build(self):
        s = QDoubleSpinBox()
        s.setRange(self._lo, self._hi)
        s.setSingleStep(self._step)
        s.setDecimals(2)
        s.setFixedWidth(150)
        return s
    def _load(self):
        self.widget.setValue(float(self._cfg.get(*self._keys, default=self._default)))
    def _connect(self):
        self.widget.valueChanged.connect(lambda v: self._save(float(v)))


class ComboField(_Field):
    """표시 라벨과 실제 저장 값을 분리할 수 있는 콤보박스 위젯입니다."""

    def __init__(self, label, config, keys, options: list[str], default="",
                 labels: dict | None = None, **kw):
        self._options, self._default = options, default
        self._labels = labels or {}
        super().__init__(label, config, keys, **kw)

    def _build(self):
        c = QComboBox()
        for v in self._options:
            c.addItem(self._labels.get(v, v), v)
        return c
    def _load(self):
        cur = str(self._cfg.get(*self._keys, default=self._default or self._options[0]))
        i = self.widget.findData(cur)
        if i >= 0:
            self.widget.setCurrentIndex(i)
    def _connect(self):
        self.widget.currentIndexChanged.connect(
            lambda _i: self._save(self.widget.currentData()))
