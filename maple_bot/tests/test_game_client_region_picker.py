# 영역 선택기가 게임창 클라이언트 화면만 사용하는지 검증한다.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

import core_ui.pages as pages_module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self):
        self.data = {"coord_mode": "absolute"}
        self.saved = 0

    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *args):
        *keys, value = args
        node = self.data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def save(self):
        self.saved += 1


def test_region_picker_uses_game_client_image_and_screen_origin(app, monkeypatch):
    game_image = np.full((60, 80, 3), 17, dtype=np.uint8)
    selected = {}

    class FakeSignal:
        def connect(self, callback):
            self.callback = callback

    class FakeSelector:
        def __init__(self, image, src_origin):
            selected["image"] = image
            selected["origin"] = src_origin
            self.region_selected = FakeSignal()

        def exec(self):
            self.region_selected.callback(130, 260, 25, 30)

    class FullMonitorMss:
        monitors = [None, {"left": -500, "top": 0, "width": 1920, "height": 1080}]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def grab(self, monitor):
            return np.zeros((monitor["height"], monitor["width"], 4), dtype=np.uint8)

    cfg = FakeConfig()
    monkeypatch.setattr(
        pages_module,
        "_capture_game_client",
        lambda config, owner: (game_image, (120, 240)),
    )
    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=FullMonitorMss))
    monkeypatch.setitem(
        sys.modules,
        "core_ui.shot_selector",
        SimpleNamespace(ScreenshotRegionSelector=FakeSelector),
    )

    button = pages_module._make_region_picker(
        cfg,
        (("attack", "hunt_area", "x"),
         ("attack", "hunt_area", "y"),
         ("attack", "hunt_area", "w"),
         ("attack", "hunt_area", "h")),
        None,
        "사냥영역",
    )
    button.click()

    assert selected["image"] is game_image
    assert selected["origin"] == (120, 240)
    assert cfg.data["attack"]["hunt_area"] == {
        "x": 130,
        "y": 260,
        "w": 25,
        "h": 30,
    }
    assert cfg.saved == 1

