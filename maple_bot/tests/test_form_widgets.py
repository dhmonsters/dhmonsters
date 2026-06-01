# 설정 폼 위젯 — config 양방향 바인딩(로드/저장) 검증
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.widgets import CheckField, TextField, IntField, ComboField, FloatField


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    """get(*keys)/set(*keys,value)/save() 만 흉내내는 가짜 config."""
    def __init__(self, data): self._d = data; self.saved = False
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node: return default
            node = node[k]
        return node
    def set(self, *args):
        *keys, val = args; node = self._d
        for k in keys[:-1]: node = node.setdefault(k, {})
        node[keys[-1]] = val
    def save(self): self.saved = True


def test_check_field_loads_value(app):
    cfg = FakeConfig({"settings1": {"lie_detector": {"enabled": True}}})
    f = CheckField("거탐", cfg, ("settings1", "lie_detector", "enabled"))
    assert f.widget.isChecked() is True


def test_check_field_writes_on_change(app):
    cfg = FakeConfig({"a": {"b": False}})
    f = CheckField("X", cfg, ("a", "b"))
    f.widget.setChecked(True)            # 사용자 토글
    assert cfg.get("a", "b") is True     # config 즉시 반영
    assert cfg.saved is True             # save 호출


def test_text_field_roundtrip(app):
    cfg = FakeConfig({"attack": {"key": "ctrl"}})
    f = TextField("공격키", cfg, ("attack", "key"))
    assert f.widget.text() == "ctrl"
    f.widget.setText("a")
    assert cfg.get("attack", "key") == "a"


def test_int_field_roundtrip(app):
    cfg = FakeConfig({"recovery": {"hp_potion": {"threshold": 65}}})
    f = IntField("HP%", cfg, ("recovery", "hp_potion", "threshold"), 0, 100)
    assert f.widget.value() == 65
    f.widget.setValue(80)
    assert cfg.get("recovery", "hp_potion", "threshold") == 80


def test_float_field_roundtrip(app):
    cfg = FakeConfig({"attack": {"camera_w_ratio": 0.5}})
    f = FloatField("카메라폭", cfg, ("attack", "camera_w_ratio"), 0.0, 1.0, step=0.05)
    assert abs(f.widget.value() - 0.5) < 1e-6
    f.widget.setValue(0.7)
    assert abs(cfg.get("attack", "camera_w_ratio") - 0.7) < 1e-6


def test_combo_field_roundtrip(app):
    cfg = FakeConfig({"hunt_mode": "key"})
    f = ComboField("모드", cfg, ("hunt_mode",), ["key", "coord"])
    assert f.widget.currentText() == "key"
    f.widget.setCurrentText("coord")
    assert cfg.get("hunt_mode") == "coord"


def test_missing_key_uses_default(app):
    cfg = FakeConfig({})
    f = CheckField("X", cfg, ("nope", "missing"), default=False)
    assert f.widget.isChecked() is False
