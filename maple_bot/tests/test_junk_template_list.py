# 기타템 템플릿 동적 목록과 판매 대상 파일 탐색을 검증한다.
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

import core_ui.pages as pages_module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self):
        self._data = {}
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


def _button(widget, name):
    button = widget.findChild(QPushButton, name)
    assert button is not None
    return button


def test_plus_adds_persistent_rows_one_at_a_time(app, tmp_path):
    config = FakeConfig()
    widget = pages_module._make_junk_template_list(config, tmp_path)

    assert widget.findChild(QPushButton, "junkTemplateSet1") is None

    _button(widget, "junkTemplateAddButton").click()
    assert _button(widget, "junkTemplateSet1").text() == "템플릿 설정"
    assert config.get("settings2", "junk_sell", "item_template_count") == 1

    _button(widget, "junkTemplateAddButton").click()
    assert _button(widget, "junkTemplateSet2").text() == "템플릿 설정"
    assert config.get("settings2", "junk_sell", "item_template_count") == 2


def test_setting_template_uses_game_client_crop_and_overwrites_same_slot(
    app, monkeypatch, tmp_path,
):
    config = FakeConfig()
    widget = pages_module._make_junk_template_list(config, tmp_path)
    _button(widget, "junkTemplateAddButton").click()
    images = [
        np.arange(6 * 6 * 3, dtype=np.uint8).reshape(6, 6, 3),
        np.full((6, 6, 3), 177, dtype=np.uint8),
    ]
    capture_calls = []

    def capture(_config, _owner):
        capture_calls.append(True)
        return images[len(capture_calls) - 1], (100, 200)

    class FakeSignal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

    class FakeSelector:
        def __init__(self, image, src_origin, parent=None):
            assert image is images[len(capture_calls) - 1]
            assert src_origin == (100, 200)
            self.region_selected = FakeSignal()

        def exec(self):
            self.region_selected.callback(101, 202, 2, 2)

    monkeypatch.setattr(pages_module, "_capture_game_client", capture)
    monkeypatch.setitem(
        sys.modules,
        "core_ui.shot_selector",
        SimpleNamespace(ScreenshotRegionSelector=FakeSelector),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: None)

    set_button = _button(widget, "junkTemplateSet1")
    set_button.click()
    template_path = tmp_path / "item_1.png"
    assert np.array_equal(cv2.imread(str(template_path)), images[0][2:4, 1:3])

    set_button.click()
    assert len(list(tmp_path.glob("item_*.png"))) == 1
    assert np.array_equal(cv2.imread(str(template_path)), images[1][2:4, 1:3])


def test_minus_deletes_template_and_compacts_following_numbers(
    app, monkeypatch, tmp_path,
):
    config = FakeConfig()
    config.set("settings2", "junk_sell", "item_template_count", 3)
    colors = (30, 90, 150)
    for index, color in enumerate(colors, start=1):
        cv2.imwrite(
            str(tmp_path / f"item_{index}.png"),
            np.full((2, 2, 3), color, dtype=np.uint8),
        )
    widget = pages_module._make_junk_template_list(config, tmp_path)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    _button(widget, "junkTemplateRemove2").click()

    assert config.get("settings2", "junk_sell", "item_template_count") == 2
    assert _button(widget, "junkTemplateSet2") is not None
    assert widget.findChild(QPushButton, "junkTemplateSet3") is None
    assert not (tmp_path / "item_3.png").exists()
    assert np.all(cv2.imread(str(tmp_path / "item_1.png")) == colors[0])
    assert np.all(cv2.imread(str(tmp_path / "item_2.png")) == colors[2])


def test_seller_includes_item_one_and_orders_templates_numerically(tmp_path):
    from core.junk_seller import _item_template_paths

    for name in ("item_10.png", "item_2.png", "item_1.png", "shop.png"):
        (tmp_path / name).write_bytes(b"template")

    assert [path.name for path in _item_template_paths(tmp_path)] == [
        "item_1.png",
        "item_2.png",
        "item_10.png",
    ]
