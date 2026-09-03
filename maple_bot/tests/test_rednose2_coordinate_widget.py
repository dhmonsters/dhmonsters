# 빨코2 좌표 설정 카드의 저장·검증·기본값 복원을 검증한다.
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from core.config_adapter import REDNOSE2_TIMING_DEFAULTS, REDNOSE2_X_DEFAULTS
from core_ui.rednose2_coordinate_widget import Rednose2CoordinateWidget


class FakeConfig:
    def __init__(self, profile=None, active="빨코2"):
        self._data = {
            "rednose2_v5": dict(profile or {}),
            "hunt_grounds": {"active": active},
        }
        self.saved = 0

    def get(self, *keys, default=None):
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *args):
        *keys, value = args
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def save(self):
        self.saved += 1


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_loads_saved_values_and_defaults_for_missing_values(app):
    widget = Rednose2CoordinateWidget(FakeConfig({"stair7_x": 42}))
    assert widget.inputs["stair7_x"].value() == 42
    assert widget.inputs["platform24_x"].value() == REDNOSE2_X_DEFAULTS["platform24_x"]


def test_loads_defaults_for_bool_and_out_of_range_saved_values(app):
    widget = Rednose2CoordinateWidget(FakeConfig({
        "floor2_left_x": True,
        "floor2_right_x": False,
        "stair7_x": -1,
        "platform24_x": 172,
    }))

    for key in ("floor2_left_x", "floor2_right_x", "stair7_x", "platform24_x"):
        assert widget.inputs[key].value() == REDNOSE2_X_DEFAULTS[key]


def test_future_timing_default_without_ui_field_does_not_crash(app, monkeypatch):
    monkeypatch.setitem(REDNOSE2_TIMING_DEFAULTS, "future_timing_key", 0.42)

    widget = Rednose2CoordinateWidget(FakeConfig({"timing_version": 2}))
    widget.restore_timing_defaults()

    assert "future_timing_key" not in widget.timing_inputs


def test_restore_defaults_changes_fields_without_saving(app):
    config = FakeConfig({"stair7_x": 42})
    widget = Rednose2CoordinateWidget(config)
    widget.restore_defaults()
    assert widget.inputs["stair7_x"].value() == 41
    assert config.get("rednose2_v5", "stair7_x") == 42
    assert config.saved == 0


def test_valid_save_replaces_only_allowed_keys_and_saves_once(app):
    config = FakeConfig({"teleport_hold_sec": 0.3, "stair7_x": 41})
    widget = Rednose2CoordinateWidget(config)
    widget.inputs["stair7_x"].setValue(42)
    widget.inputs["stair7_x_min"].setValue(39)
    widget.inputs["stair7_x_max"].setValue(45)
    widget.save_values()
    assert config.get("rednose2_v5", "stair7_x") == 42
    assert config.get("rednose2_v5", "teleport_hold_sec") == 0.3
    assert config.saved == 1
    assert "다음 F1" in widget.status.text()


def test_invalid_range_does_not_mutate_or_save(app):
    config = FakeConfig({"stair7_x": 41})
    before = dict(config.get("rednose2_v5"))
    widget = Rednose2CoordinateWidget(config)
    widget.inputs["stair7_x_min"].setValue(45)
    widget.inputs["stair7_x"].setValue(42)
    widget.inputs["stair7_x_max"].setValue(44)
    widget.save_values()
    assert config.get("rednose2_v5") == before
    assert config.saved == 0
    assert "7번 계단" in widget.status.text()


def test_sections_start_collapsed_and_toggle_independently(app):
    widget = Rednose2CoordinateWidget(FakeConfig())

    assert widget.coordinate_content.isHidden()
    assert widget.timing_content.isHidden()

    widget.coordinate_toggle.click()
    assert not widget.coordinate_content.isHidden()
    assert widget.timing_content.isHidden()

    widget.timing_toggle.click()
    assert not widget.coordinate_content.isHidden()
    assert not widget.timing_content.isHidden()


def test_card_only_shows_for_rednose2_names(app):
    widget = Rednose2CoordinateWidget(FakeConfig(active="빨코3"))
    assert widget.isHidden()

    widget.set_hunt_ground("rednose2v5")
    assert not widget.isHidden()

    widget.set_hunt_ground("일반 사냥터")
    assert widget.isHidden()


def test_timing_save_preserves_coordinates_and_writes_version(app):
    config = FakeConfig({"stair7_x": 42, "timing_version": 2, "attack_hold_sec": 0.9})
    widget = Rednose2CoordinateWidget(config)
    widget.timing_inputs["attack_hold_sec"].setValue(0.77)
    widget.timing_inputs["floor2_hunt_teleport_interval_sec"].setValue(0.66)
    widget.timing_inputs["platform1415_attack_hold_sec"].setValue(0.81)
    widget.timing_inputs["platform27_entry_attack_hold_sec"].setValue(0.73)

    widget.save_timing_values()

    saved = config.get("rednose2_v5")
    assert saved["stair7_x"] == 42
    assert saved["timing_version"] == 2
    assert saved["attack_hold_sec"] == 0.77
    assert saved["floor2_hunt_teleport_interval_sec"] == 0.66
    assert saved["platform1415_attack_hold_sec"] == 0.81
    assert saved["platform27_entry_attack_hold_sec"] == 0.73


def test_coordinate_save_preserves_timing_values(app):
    config = FakeConfig({"timing_version": 2, "attack_hold_sec": 0.77, "stair7_x": 41})
    widget = Rednose2CoordinateWidget(config)
    widget.inputs["stair7_x"].setValue(42)

    widget.save_values()

    assert config.get("rednose2_v5", "attack_hold_sec") == 0.77


def test_y_coordinates_load_and_save_with_x_coordinates(app):
    config = FakeConfig({"floor1_y_min": 74, "platform27_y_max": 52})
    widget = Rednose2CoordinateWidget(config)

    assert widget.y_inputs["floor1_y_min"].value() == 74
    assert widget.y_inputs["platform27_y_max"].value() == 52

    widget.y_inputs["floor2_y_min"].setValue(60)
    widget.y_inputs["floor2_y_max"].setValue(64)
    widget.save_values()

    assert config.get("rednose2_v5", "floor2_y_min") == 60
    assert config.get("rednose2_v5", "floor2_y_max") == 64
    assert config.saved == 1


def test_invalid_y_range_does_not_save(app):
    config = FakeConfig()
    widget = Rednose2CoordinateWidget(config)
    widget.y_inputs["platform16_y_min"].setValue(50)
    widget.y_inputs["platform16_y_max"].setValue(49)

    widget.save_values()

    assert config.saved == 0
    assert "16번" in widget.status.text()


def test_timing_card_saves_first_two_recovery_attack_teleport_values(app):
    config = FakeConfig({"timing_version": 2})
    widget = Rednose2CoordinateWidget(config)
    expected = {
        "floor2_recovery_first_attack_hold_sec": 0.61,
        "floor2_recovery_first_teleport_hold_sec": 0.11,
        "floor2_recovery_first_interval_sec": 0.71,
        "floor2_recovery_second_attack_hold_sec": 0.62,
        "floor2_recovery_second_teleport_hold_sec": 0.12,
        "floor2_recovery_second_interval_sec": 0.72,
    }
    for key, value in expected.items():
        widget.timing_inputs[key].setValue(value)

    widget.save_timing_values()

    saved = config.get("rednose2_v5")
    for key, value in expected.items():
        assert saved[key] == value
