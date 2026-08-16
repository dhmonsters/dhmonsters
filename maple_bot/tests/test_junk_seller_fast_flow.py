# 장비 자동판매가 게임창 한정 단일 탐색으로 5초 안에 끝나는지 검증한다.
import os
import sys
from types import SimpleNamespace

import numpy as np

from core.junk_seller import _exit_shop, sell_junk


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, float(seconds))


class FakeConfig:
    def __init__(self):
        self.data = {
            "coord_mode": "relative",
            "settings2": {
                "game_window_title": "MapleStory Worlds",
                "junk_sell": {
                    "inventory_key": "i",
                    "junk_sell_enabled": False,
                    "shop_exit_btn": [700, 210],
                },
            },
        }

    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


class FakeScreen:
    def __init__(self, missing=None):
        self.capture_regions = []
        self.combined_calls = []
        self.legacy_calls = []
        self.missing = set(missing or [])

    def capture(self, region=None):
        self.capture_regions.append(region)
        return np.zeros((600, 800, 3), dtype=np.uint8)

    def find_template_match(self, scene, path, threshold=0.65):
        name = os.path.basename(path)
        self.combined_calls.append((name, threshold))
        positions = {
            "inventory.png": (300, 200),
            "cash_tab_active.png": (420, 220),
            "shop_item.png": (500, 300),
            "shop_open.png": (550, 180),
            "equip_sell_btn.png": (620, 240),
            "equip_sell_confirm.png": (400, 400),
            "shop_exit.png": (650, 100),
        }
        position = None if name in self.missing else positions.get(name)
        return (0.9, position) if position else (0.0, None)

    def find_template_score(self, scene, path):
        self.legacy_calls.append(("score", os.path.basename(path)))
        return 0.9

    def find_template(self, scene, path, threshold=0.65):
        self.legacy_calls.append(("position", os.path.basename(path)))
        return (100, 100)


class FakeInput:
    def __init__(self):
        self.events = []

    def focus_game_window(self):
        self.events.append(("focus",))

    def press_key(self, key, hold_sec=0.05):
        self.events.append(("press", key, hold_sec))

    def click(self, x, y):
        self.events.append(("click", x, y))

    def double_click(self, x, y):
        self.events.append(("double", x, y))

    def scroll(self, x, y, clicks):
        self.events.append(("scroll", x, y, clicks))


class FakeMss:
    monitors = [{"left": 0, "top": 0, "width": 800, "height": 600}]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def grab(self, _region):
        return np.zeros((600, 800, 4), dtype=np.uint8)


def test_exit_shop_uses_template_center_in_game_window_instead_of_saved_coordinate(monkeypatch):
    clock = FakeClock()
    screen = FakeScreen()
    input_ctrl = FakeInput()
    config = FakeConfig()
    monkeypatch.setattr("core.junk_seller.time.sleep", clock.sleep)
    monkeypatch.setattr("core.junk_seller.os.path.exists", lambda path: os.path.basename(path) == "shop_exit.png")
    monkeypatch.setattr("core.config_manager.get_game_window_rect", lambda _config: (100, 200, 800, 600))

    _exit_shop(config, screen, input_ctrl, lambda _message: None)

    assert ("click", 750, 300) in input_ctrl.events
    assert ("click", 700, 210) not in input_ctrl.events
    assert not [event for event in input_ctrl.events if event[0] == "press"]


def test_exit_shop_fallback_presses_both_escape_keys_for_half_second(monkeypatch):
    clock = FakeClock()
    screen = FakeScreen(missing={"shop_exit.png"})
    input_ctrl = FakeInput()
    config = FakeConfig()
    monkeypatch.setattr("core.junk_seller.time.sleep", clock.sleep)
    monkeypatch.setattr("core.junk_seller.os.path.exists", lambda path: os.path.basename(path) == "shop_exit.png")
    monkeypatch.setattr("core.config_manager.get_game_window_rect", lambda _config: (100, 200, 800, 600))

    _exit_shop(config, screen, input_ctrl, lambda _message: None)

    assert [event for event in input_ctrl.events if event[0] == "press"] == [
        ("press", "esc", 0.5),
        ("press", "esc", 0.5),
    ]
    assert not [event for event in input_ctrl.events if event[0] == "click"]


def test_equipment_sale_uses_game_window_single_match_and_finishes_within_five_seconds(monkeypatch):
    clock = FakeClock()
    screen = FakeScreen()
    input_ctrl = FakeInput()
    config = FakeConfig()
    existing = {
        "inventory.png", "cash_tab.png", "cash_tab_active.png", "shop_item.png",
        "shop_open.png", "equip_sell_btn.png", "equip_sell_confirm.png",
    }
    monkeypatch.setattr("core.junk_seller.time.time", clock.time)
    monkeypatch.setattr("core.junk_seller.time.sleep", clock.sleep)
    monkeypatch.setattr("core.junk_seller.os.path.exists", lambda path: os.path.basename(path) in existing)
    monkeypatch.setattr("core.junk_seller._item_template_paths", lambda: [])
    monkeypatch.setattr("core.config_manager.get_game_window_rect", lambda _config: (100, 200, 800, 600))
    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=FakeMss))
    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(COLOR_BGRA2BGR=0, cvtColor=lambda image, _code: image[:, :, :3]),
    )

    result = sell_junk(config, screen, input_ctrl, lambda _message: None)

    expected_region = {"left": 100, "top": 200, "width": 800, "height": 600}
    assert result is True
    assert screen.capture_regions
    assert all(region == expected_region for region in screen.capture_regions)
    assert screen.combined_calls
    assert screen.legacy_calls == []
    assert clock.now <= 5.0


def test_missing_equipment_sell_button_reports_failure(monkeypatch):
    clock = FakeClock()
    screen = FakeScreen(missing={"equip_sell_btn.png"})
    input_ctrl = FakeInput()
    config = FakeConfig()
    existing = {
        "inventory.png", "cash_tab.png", "cash_tab_active.png", "shop_item.png",
        "shop_open.png", "equip_sell_btn.png", "equip_sell_confirm.png",
    }
    monkeypatch.setattr("core.junk_seller.time.time", clock.time)
    monkeypatch.setattr("core.junk_seller.time.sleep", clock.sleep)
    monkeypatch.setattr("core.junk_seller.os.path.exists", lambda path: os.path.basename(path) in existing)
    monkeypatch.setattr("core.junk_seller._item_template_paths", lambda: [])
    monkeypatch.setattr("core.config_manager.get_game_window_rect", lambda _config: (100, 200, 800, 600))

    result = sell_junk(config, screen, input_ctrl, lambda _message: None)

    assert result is False
    assert ("click", 700, 210) not in input_ctrl.events
    assert [event for event in input_ctrl.events if event[0] == "press"][-2:] == [
        ("press", "esc", 0.5),
        ("press", "esc", 0.5),
    ]
