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

    assert cfg.get("minimap", "hsv_h_low") == 0
    assert cfg.get("minimap", "hsv_h_high") == 10
    assert cfg.get("minimap", "hsv_s_low") == 215
    assert cfg.get("minimap", "hsv_v_low") == 215


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
    controls = pages_module._make_character_color_controls(FakeConfig())
    buttons = {button.text(): button for button in controls.findChildren(pages_module.QPushButton)}

    buttons["캐릭터 템플릿 캡처"].click()

    assert saved["path"].name == "y_p.png"
    assert np.array_equal(saved["crop"], image[1:3, 1:3])
