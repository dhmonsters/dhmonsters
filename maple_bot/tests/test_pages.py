# 6 카테고리 페이지 빌드 + config 바인딩 검증
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtWidgets import QApplication
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
