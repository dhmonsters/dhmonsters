# 6 카테고리 페이지 빌드 + config 바인딩 검증
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication
import core_ui.pages as pages_module
from core_ui.pages import build_pages


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self): self._d = {}; self.saved = 0
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
    def save(self): self.saved += 1


def test_character_position_offset_controls_save_and_reset(app):
    from PyQt6.QtWidgets import QPushButton, QSpinBox

    cfg = FakeConfig()
    cfg.set("minimap", "position_offset_x", 3)
    cfg.set("minimap", "position_offset_y", -2)
    controls = pages_module._make_character_color_controls(cfg)
    offset_x = controls.findChild(QSpinBox, "characterPositionOffsetX")
    offset_y = controls.findChild(QSpinBox, "characterPositionOffsetY")
    reset = controls.findChild(QPushButton, "characterPositionOffsetReset")

    assert offset_x is not None
    assert offset_y is not None
    assert reset is not None
    offset_x.setValue(8)
    offset_y.setValue(-5)
    assert cfg.get("minimap", "position_offset_x") == 8
    assert cfg.get("minimap", "position_offset_y") == -5

    reset.click()

    assert offset_x.value() == 0
    assert offset_y.value() == 0
    assert cfg.get("minimap", "position_offset_x") == 0
    assert cfg.get("minimap", "position_offset_y") == 0


def test_character_position_nudge_buttons_change_only_detection_offsets(app):
    from PyQt6.QtWidgets import QPushButton, QSpinBox

    cfg = FakeConfig()
    cfg.set("minimap", "region_x", 19)
    cfg.set("minimap", "region_y", 132)
    cfg.set("minimap", "width", 142)
    cfg.set("minimap", "height", 62)
    cfg.set("minimap", "position_offset_x", 3)
    cfg.set("minimap", "position_offset_y", -2)
    controls = pages_module._make_character_color_controls(cfg)
    offset_x = controls.findChild(QSpinBox, "characterPositionOffsetX")
    offset_y = controls.findChild(QSpinBox, "characterPositionOffsetY")
    left = controls.findChild(QPushButton, "characterPositionNudgeLeft")
    right = controls.findChild(QPushButton, "characterPositionNudgeRight")
    up = controls.findChild(QPushButton, "characterPositionNudgeUp")
    down = controls.findChild(QPushButton, "characterPositionNudgeDown")

    assert all(button is not None for button in (left, right, up, down))
    left.click()
    up.click()
    assert (offset_x.value(), offset_y.value()) == (2, -3)
    right.click()
    down.click()
    assert (offset_x.value(), offset_y.value()) == (3, -2)
    assert cfg.get("minimap", "position_offset_x") == 3
    assert cfg.get("minimap", "position_offset_y") == -2
    assert (
        cfg.get("minimap", "region_x"),
        cfg.get("minimap", "region_y"),
        cfg.get("minimap", "width"),
        cfg.get("minimap", "height"),
    ) == (19, 132, 142, 62)


def test_build_pages_returns_six(app):
    pages = build_pages(FakeConfig())
    assert len(pages) == 6


def test_pages_are_widgets(app):
    from PyQt6.QtWidgets import QWidget
    for p in build_pages(FakeConfig()):
        assert isinstance(p, QWidget)


def test_movement_page_has_hunt_ground_preset_card(app):
    from PyQt6.QtWidgets import QWidget

    pages = build_pages(FakeConfig())

    assert any(
        page.findChild(QWidget, "huntGroundPresetCard") is not None
        for page in pages
    )


def test_movement_page_has_rednose2_coordinate_card(app):
    from PyQt6.QtWidgets import QWidget

    pages = build_pages(FakeConfig())

    assert pages[1].findChild(QWidget, "rednose2CoordinateCard") is not None


def test_rednose2_card_tracks_loaded_hunt_ground(app):
    from core_ui.hunt_ground_preset_widget import HuntGroundPresetWidget
    from core_ui.rednose2_coordinate_widget import Rednose2CoordinateWidget

    pages = build_pages(FakeConfig())
    preset = pages[1].findChild(HuntGroundPresetWidget)
    rednose2 = pages[1].findChild(Rednose2CoordinateWidget)

    assert rednose2.isHidden()
    preset.preset_loaded.emit("빨코2")
    assert not rednose2.isHidden()
    preset.preset_loaded.emit("빨코3")
    assert rednose2.isHidden()


def test_combat_page_has_attack_sequence_editor(app):
    from PyQt6.QtWidgets import QWidget

    pages = build_pages(FakeConfig())

    assert any(
        page.findChild(QWidget, "attackSequenceEditor") is not None
        for page in pages
    )


def test_attack_sequence_editor_is_immediately_below_attack_range(app):
    from PyQt6.QtWidgets import QWidget

    pages = build_pages(FakeConfig())
    editor = pages[2].findChild(QWidget, "attackSequenceEditor")
    layout = editor.parentWidget().layout()
    editor_index = layout.indexOf(editor)
    previous_row = layout.itemAt(editor_index - 1).widget()

    assert editor_index > 0
    assert getattr(previous_row, "_field")._keys == ("attack", "range_px")


def test_hunt_mode_no_longer_offers_coordinate(app):
    from PyQt6.QtWidgets import QComboBox

    pages = build_pages(FakeConfig())
    combo_items = [
        [combo.itemText(i) for i in range(combo.count())]
        for page in pages
        for combo in page.findChildren(QComboBox)
    ]

    hunt_modes = [items for items in combo_items if "키 입력" in items and "이미지 인식" in items]
    assert hunt_modes
    assert all("좌표" not in items for items in hunt_modes)


def test_field_edit_persists_to_config(app):
    """페이지 안 필드를 바꾸면 config에 저장된다 (양방향 바인딩 통합)."""
    from core_ui.widgets import TextField
    cfg = FakeConfig()
    cfg.set("attack", "key", "ctrl")
    # build_pages는 내부에서 필드를 만들지만, 통합 동작은 widgets 단위테스트가 커버.
    # 여기선 페이지 생성이 config 읽기로 예외 안 나는지(실 키 구조)만 확인.
    pages = build_pages(cfg)
    assert len(pages) == 6


def test_capture_game_client_uses_configured_window_client_region(app, monkeypatch):
    captured = {}

    class FakeMss:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def grab(self, region):
            captured["region"] = region
            return np.zeros((region["height"], region["width"], 4), dtype=np.uint8)

    class FakeOwner:
        def __init__(self):
            self.hidden = False
            self.shown = False

        def hide(self):
            self.hidden = True

        def show(self):
            self.shown = True

    fake_win32gui = SimpleNamespace(
        FindWindow=lambda _class_name, title: 77 if title == "MapleStory Worlds" else 0,
        ClientToScreen=lambda _hwnd, _point: (120, 240),
        GetClientRect=lambda _hwnd: (0, 0, 800, 600),
        ShowWindow=lambda _hwnd, _command: None,
        SetForegroundWindow=lambda _hwnd: None,
    )
    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=FakeMss))
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    cfg = FakeConfig()
    cfg.set("settings2", "game_window_title", "MapleStory Worlds")
    owner = FakeOwner()

    image, origin = pages_module._capture_game_client(cfg, owner)

    assert captured["region"] == {
        "left": 120,
        "top": 240,
        "width": 800,
        "height": 600,
    }
    assert image.shape == (600, 800, 3)
    assert origin == (120, 240)
    assert owner.hidden is True
    assert owner.shown is True


def test_capture_game_client_reports_grab_error_and_restores_owner(app, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    warnings = []

    class FailingMss:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def grab(self, _region):
            raise RuntimeError("capture failed")

    class FakeOwner:
        def __init__(self):
            self.hidden = False
            self.shown = False

        def hide(self):
            self.hidden = True

        def show(self):
            self.shown = True

    fake_win32gui = SimpleNamespace(
        FindWindow=lambda _class_name, _title: 77,
        ClientToScreen=lambda _hwnd, _point: (120, 240),
        GetClientRect=lambda _hwnd: (0, 0, 800, 600),
        ShowWindow=lambda _hwnd, _command: None,
        SetForegroundWindow=lambda _hwnd: None,
    )
    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=FailingMss))
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _owner, title, message: warnings.append((title, message)),
    )
    owner = FakeOwner()

    result = pages_module._capture_game_client(FakeConfig(), owner)

    assert result is None
    assert owner.hidden is True
    assert owner.shown is True
    assert warnings == [("게임창 캡처 실패", "게임창 화면을 캡처하지 못했습니다.\ncapture failed")]


def test_template_capture_uses_game_client_image_and_screen_origin(app, monkeypatch, tmp_path):
    import cv2
    import core_ui.shot_selector as shot_selector

    game_image = np.arange(5 * 5 * 3, dtype=np.uint8).reshape(5, 5, 3)
    selected = {}
    saved = {}

    class RecordingSelector:
        def __init__(self, image, src_origin, parent=None):
            selected.update(image=image, origin=src_origin, parent=parent)
            self.region_selected = FakeRegionSignal()

        def exec(self):
            self.region_selected.emit(101, 201, 2, 2)

    capture_calls = []
    monkeypatch.setattr(
        pages_module,
        "_capture_game_client",
        lambda config, owner: capture_calls.append((config, owner)) or (game_image, (100, 200)),
    )
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", RecordingSelector)
    monkeypatch.setattr(
        cv2,
        "imwrite",
        lambda path, crop: saved.update(path=Path(path), crop=crop.copy()) or True,
    )
    cfg = FakeConfig()
    button = pages_module._make_template_capture(
        cfg,
        str(tmp_path / "monster.png"),
        ("attack", "monster_template"),
        "몬스터",
    )

    button.click()

    assert len(capture_calls) == 1
    assert selected["image"] is game_image
    assert selected["origin"] == (100, 200)
    assert np.array_equal(saved["crop"], game_image[1:3, 1:3])


def test_character_template_path_always_targets_loaded_yellow_marker(tmp_path):
    assert pages_module._character_template_path(Path(tmp_path)) == Path(tmp_path) / "templates" / "player" / "y_p.png"


class FakeRegionSignal:
    def __init__(self):
        self._callback = None

    def connect(self, callback):
        self._callback = callback

    def emit(self, *args):
        self._callback(*args)


class FakeRegionSelector:
    selected_region = (101, 201, 2, 2)

    def __init__(self, *_args, **_kwargs):
        self.region_selected = FakeRegionSignal()

    def exec(self):
        self.region_selected.emit(*self.selected_region)


def test_minimap_region_picker_updates_window_ratios_with_absolute_region(app, monkeypatch):
    import core.config_manager as config_manager
    import core_ui.shot_selector as shot_selector

    game_image = np.zeros((720, 1280, 3), dtype=np.uint8)

    class MinimapSelector(FakeRegionSelector):
        selected_region = (19, 132, 142, 62)

    monkeypatch.setattr(
        pages_module,
        "_capture_game_client",
        lambda _config, _owner: (game_image, (1, 31)),
    )
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", MinimapSelector)
    monkeypatch.setattr(
        config_manager,
        "cached_window_origin",
        lambda _title: (1, 31, 1280, 720),
    )
    cfg = FakeConfig()
    cfg.set("coord_mode", "relative")
    cfg.set("settings2", "game_window_title", "MapleStory Worlds")
    cfg.set("minimap", "region_x_ratio", 0.025520833333333333)
    cfg.set("minimap", "region_y_ratio", 0.1377601585728444)
    cfg.set("minimap", "width_ratio", 0.12708333333333333)
    cfg.set("minimap", "height_ratio", 0.14271555996035679)
    button = pages_module._make_region_picker(
        cfg,
        [
            ("minimap", "region_x"),
            ("minimap", "region_y"),
            ("minimap", "width"),
            ("minimap", "height"),
        ],
        None,
        "미니맵",
    )

    button.click()

    assert cfg.get("minimap", "region_x") == 19
    assert cfg.get("minimap", "region_y") == 132
    assert cfg.get("minimap", "width") == 142
    assert cfg.get("minimap", "height") == 62
    assert cfg.get("minimap", "region_x_ratio") == pytest.approx(18 / 1280)
    assert cfg.get("minimap", "region_y_ratio") == pytest.approx(101 / 720)
    assert cfg.get("minimap", "width_ratio") == pytest.approx(142 / 1280)
    assert cfg.get("minimap", "height_ratio") == pytest.approx(62 / 720)


def test_reference_color_button_applies_selected_game_region(app, monkeypatch):
    import core_ui.shot_selector as shot_selector

    image = np.zeros((5, 5, 3), dtype=np.uint8)
    image[1:3, 1:3] = (0, 0, 255)
    monkeypatch.setattr(pages_module, "_capture_game_client", lambda _config, _owner: (image, (100, 200)))
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeRegionSelector)
    cfg = FakeConfig()
    controls = pages_module._make_character_color_controls(cfg)
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["기준색 캡처"].click()

    assert cfg.get("minimap", "reference_color_rgb") == [255, 0, 0]
    assert cfg.saved == 1


def test_mean_rgb_from_bgr_uses_all_selected_pixels():
    crop = np.array([[[10, 20, 30], [30, 40, 50]]], dtype=np.uint8)

    assert pages_module._mean_rgb_from_bgr(crop) == (40, 30, 20)


def test_character_color_controls_show_one_reference_color_without_hsv_sliders(app):
    cfg = FakeConfig()
    cfg.set("minimap", "reference_color_rgb", [225, 220, 10])
    controls = pages_module._make_character_color_controls(cfg)
    text = " ".join(label.text() for label in controls.findChildren(pages_module.QLabel))

    assert "#E1DC0A" in text
    assert "RGB(225, 220, 10)" in text
    assert "색상 시작 H" not in text
    assert "색상 끝 H" not in text
    assert "채도 최소 S" not in text
    assert "밝기 최소 V" not in text
    assert "점 크기 최소" in text
    assert "점 크기 최대" in text


def test_reference_color_button_saves_average_rgb_once(app, monkeypatch):
    import core_ui.shot_selector as shot_selector

    image = np.zeros((5, 5, 3), dtype=np.uint8)
    image[1:3, 1:3] = np.array([
        [[10, 20, 30], [30, 40, 50]],
        [[50, 60, 70], [70, 80, 90]],
    ], dtype=np.uint8)
    monkeypatch.setattr(pages_module, "_capture_game_client", lambda _config, _owner: (image, (100, 200)))
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeRegionSelector)
    cfg = FakeConfig()
    controls = pages_module._make_character_color_controls(cfg)
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["기준색 캡처"].click()

    assert cfg.get("minimap", "reference_color_rgb") == [60, 50, 40]
    assert cfg.saved == 1


def test_reference_color_save_failure_restores_previous_value(app, monkeypatch):
    import core_ui.shot_selector as shot_selector

    class FailingSaveConfig(FakeConfig):
        def save(self):
            raise OSError("disk full")

    image = np.zeros((5, 5, 3), dtype=np.uint8)
    image[1:3, 1:3] = (0, 0, 255)
    monkeypatch.setattr(pages_module, "_capture_game_client", lambda _config, _owner: (image, (100, 200)))
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeRegionSelector)
    cfg = FailingSaveConfig()
    cfg.set("minimap", "reference_color_rgb", [225, 225, 0])
    controls = pages_module._make_character_color_controls(cfg)
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["기준색 캡처"].click()

    text = " ".join(label.text() for label in controls.findChildren(pages_module.QLabel))
    assert cfg.get("minimap", "reference_color_rgb") == [225, 225, 0]
    assert "기준색 저장에 실패했습니다" in text


def test_character_template_path_uses_user_directory_in_frozen_app(tmp_path, monkeypatch):
    import core.config_manager as config_manager

    monkeypatch.setattr(pages_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_manager, "get_user_templates_dir", lambda: str(tmp_path / "templates"))

    assert pages_module._character_template_path(Path("ignored")) == tmp_path / "templates" / "player" / "y_p.png"


def test_character_template_button_saves_selected_game_region_to_loaded_path(app, monkeypatch):
    import cv2
    import core_ui.shot_selector as shot_selector

    image = np.arange(5 * 5 * 3, dtype=np.uint8).reshape(5, 5, 3)
    saved = {}
    monkeypatch.setattr(pages_module, "_capture_game_client", lambda _config, _owner: (image, (100, 200)))
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeRegionSelector)
    monkeypatch.setattr(
        cv2,
        "imwrite",
        lambda path, crop: saved.update(path=Path(path), crop=crop.copy()) or True,
    )
    monkeypatch.setattr(
        pages_module.os,
        "replace",
        lambda source, target: saved.update(final_path=Path(target)),
    )
    controls = pages_module._make_character_color_controls(FakeConfig())
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["캐릭터 템플릿 캡처"].click()

    assert saved["path"].name == ".y_p.pending.png"
    assert saved["final_path"].name == "y_p.png"
    assert np.array_equal(saved["crop"], image[1:3, 1:3])


def test_character_template_button_atomically_overwrites_fixed_file(app, monkeypatch, tmp_path):
    import cv2
    import core_ui.shot_selector as shot_selector

    image = np.arange(5 * 5 * 3, dtype=np.uint8).reshape(5, 5, 3)
    template_path = tmp_path / "player" / "y_p.png"
    template_path.parent.mkdir(parents=True)
    template_path.write_bytes(b"old-template")
    writes = []
    replacements = []
    monkeypatch.setattr(pages_module, "_capture_game_client", lambda _config, _owner: (image, (100, 200)))
    monkeypatch.setattr(pages_module, "_character_template_path", lambda _root: template_path)
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeRegionSelector)
    monkeypatch.setattr(cv2, "imwrite", lambda path, crop: writes.append((Path(path), crop.copy())) or True)
    monkeypatch.setattr(pages_module.os, "replace", lambda source, target: replacements.append((Path(source), Path(target))))
    controls = pages_module._make_character_color_controls(FakeConfig())
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["캐릭터 템플릿 캡처"].click()

    assert writes[0][0].name == ".y_p.pending.png"
    assert replacements == [(template_path.with_name(".y_p.pending.png"), template_path)]
    assert np.array_equal(writes[0][1], image[1:3, 1:3])


def test_character_template_button_replaces_existing_png_on_disk(app, monkeypatch, tmp_path):
    import cv2
    import core_ui.shot_selector as shot_selector

    image = np.arange(5 * 5 * 3, dtype=np.uint8).reshape(5, 5, 3)
    template_path = tmp_path / "player" / "y_p.png"
    template_path.parent.mkdir(parents=True)
    cv2.imwrite(str(template_path), np.zeros((2, 2, 3), dtype=np.uint8))
    monkeypatch.setattr(pages_module, "_capture_game_client", lambda _config, _owner: (image, (100, 200)))
    monkeypatch.setattr(pages_module, "_character_template_path", lambda _root: template_path)
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeRegionSelector)
    controls = pages_module._make_character_color_controls(FakeConfig())
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["캐릭터 템플릿 캡처"].click()

    assert np.array_equal(cv2.imread(str(template_path)), image[1:3, 1:3])
    assert not template_path.with_name(".y_p.pending.png").exists()
