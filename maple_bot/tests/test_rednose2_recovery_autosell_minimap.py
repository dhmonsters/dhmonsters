# 빨코2 미검출 복구와 자동판매·미니맵 영역 동기화를 검증한다.
from __future__ import annotations

import copy
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from core.navigation.rednose2_runner import RedNose2RouteRunner
from core_ui import pages as pages_module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def perf_counter(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class RecordingInputs:
    def __init__(self, clock):
        self.clock = clock
        self.direction = None
        self.direction_events = []
        self.action_events = []

    def hold_direction(self, direction):
        self.direction = direction
        self.direction_events.append(("hold", direction, self.clock.now))

    def release_direction(self):
        self.direction_events.append(("release", self.direction, self.clock.now))
        self.direction = None

    def hold_action(self, key):
        self.action_events.append(("down", key, self.clock.now))

    def release_action(self, key):
        self.action_events.append(("up", key, self.clock.now))

    def press_action(self, key, hold_sec=0.05):
        self.action_events.append(("press", key, hold_sec, self.clock.now))
        self.clock.sleep(hold_sec)


def make_runner(clock, inputs, profile=None):
    block_runner = SimpleNamespace(
        _route_inputs=inputs,
        release_inputs=lambda: None,
        _stop=lambda: False,
    )
    return RedNose2RouteRunner(
        block_runner,
        get_blocks=lambda: [],
        is_active=lambda: True,
        profile={
            "attack_key": "end",
            "teleport_key": "x",
            "teleport_hold_sec": 0.3,
            "teleport_step_px": 13.0,
            "arrival_tolerance": 3,
            "max_step_sec": 20.0,
            "base_minimap_width": 172,
            "base_minimap_height": 103,
            "minimap_width": 172,
            "minimap_height": 103,
            "floor2_y_min": 61,
            "floor2_y_max": 63,
            "floor3_y_min": 47,
            "floor3_y_max": 51,
            **(profile or {}),
        },
        sleep_fn=clock.sleep,
    )


def test_move_keeps_last_direction_during_short_position_loss(monkeypatch):
    clock = FakeClock()
    inputs = RecordingInputs(clock)
    runner = make_runner(clock, inputs)
    teleported = False
    missed_reads = 0

    def current_pos():
        nonlocal missed_reads
        if not teleported:
            return (0.0, 62.0)
        missed_reads += 1
        if missed_reads <= 2:
            return None
        return (40.0, 62.0)

    def teleport(_direction):
        nonlocal teleported
        teleported = True
        inputs.release_direction()

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.perf_counter", clock.perf_counter)
    monkeypatch.setattr(runner, "_current_pos", current_pos)
    monkeypatch.setattr(runner, "_fresh_sample", lambda: (None, None))
    monkeypatch.setattr(runner, "_teleport_attack", teleport)

    assert runner._move_to_target_v5(40.0, attack=True)

    release_index = next(i for i, event in enumerate(inputs.direction_events) if event[0] == "release")
    assert any(
        event[:2] == ("hold", "right")
        for event in inputs.direction_events[release_index + 1:]
    )


def test_next_move_keeps_previous_horizontal_intent_when_position_starts_missing(monkeypatch):
    clock = FakeClock()
    inputs = RecordingInputs(clock)
    runner = make_runner(clock, inputs)
    reads = 0

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.perf_counter", clock.perf_counter)
    runner._teleport_once("left")
    previous_event_count = len(inputs.direction_events)

    def current_pos():
        nonlocal reads
        reads += 1
        if reads <= 3:
            return None
        return (-40.0, 62.0)

    monkeypatch.setattr(runner, "_current_pos", current_pos)

    assert runner._move_to_target_v5(-40.0, attack=False)
    assert any(
        event[:2] == ("hold", "left")
        for event in inputs.direction_events[previous_event_count:]
    )


def test_auto_sell_does_not_start_when_shop_entry_teleport_never_lands(monkeypatch):
    clock = FakeClock()
    inputs = RecordingInputs(clock)
    runner = make_runner(clock, inputs)
    position = [129.0, 62.0]
    teleports = []

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_teleport_once", lambda direction: teleports.append(direction))

    assert runner.prepare_auto_sell_from_floor2() is False
    assert teleports == ["up", "up", "up"]


def test_auto_sell_retries_entry_teleport_until_shop_entry_is_confirmed(monkeypatch):
    clock = FakeClock()
    inputs = RecordingInputs(clock)
    runner = make_runner(clock, inputs)
    position = [129.0, 62.0]
    teleports = []

    def teleport(direction):
        teleports.append(direction)
        if teleports.count("up") == 2:
            position[1] = 49.0

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_teleport_once", teleport)

    assert runner.prepare_auto_sell_from_floor2() is True
    assert teleports == ["up", "up"]


def test_auto_sell_return_holds_down_for_point_three_seconds_before_teleport(monkeypatch):
    clock = FakeClock()
    inputs = RecordingInputs(clock)
    runner = make_runner(clock, inputs)

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr(runner, "_wait_floor", lambda _predicate, _timeout: True)

    assert runner.return_floor2_after_auto_sell() is True
    teleport_events = [
        event for event in inputs.action_events
        if len(event) >= 2 and event[1] in {"down", "x"}
    ]
    assert teleport_events == [
        ("down", "down", 0.0),
        ("press", "x", 0.3, 0.3),
        ("up", "down", 0.6),
    ]


class FakeConfig:
    def __init__(self, data=None):
        self._data = copy.deepcopy(data or {})
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


class FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback

    def emit(self, *args):
        self.callback(*args)


class FakeSelector:
    def __init__(self, *_args, **_kwargs):
        self.region_selected = FakeSignal()

    def exec(self):
        self.region_selected.emit(19, 132, 142, 62)


def make_minimap_picker(app, monkeypatch, config):
    import core.config_manager as config_manager
    import core_ui.shot_selector as shot_selector

    game_image = np.zeros((720, 1280, 3), dtype=np.uint8)
    monkeypatch.setattr(
        pages_module,
        "_capture_game_client",
        lambda _config, _owner: (game_image, (1, 31)),
    )
    monkeypatch.setattr(shot_selector, "ScreenshotRegionSelector", FakeSelector)
    monkeypatch.setattr(
        config_manager,
        "cached_window_origin",
        lambda _title: (1, 31, 1280, 720),
    )
    return pages_module._make_region_picker(
        config,
        [
            ("minimap", "region_x"),
            ("minimap", "region_y"),
            ("minimap", "width"),
            ("minimap", "height"),
        ],
        None,
        "미니맵",
    )


def test_minimap_picker_syncs_new_region_and_ratios_to_active_preset(app, monkeypatch):
    config = FakeConfig({
        "coord_mode": "relative",
        "settings2": {"game_window_title": "MapleStory Worlds"},
        "minimap": {},
        "hunt_grounds": {
            "active": "빨코2",
            "presets": {"빨코2": {"minimap": {"region_x": 38, "width": 172}}},
        },
    })
    button = make_minimap_picker(app, monkeypatch, config)

    button.click()

    saved = config.get("hunt_grounds", "presets", "빨코2", "minimap")
    assert saved["region_x"] == 19
    assert saved["region_y"] == 132
    assert saved["width"] == 142
    assert saved["height"] == 62
    assert saved["region_x_ratio"] == pytest.approx(18 / 1280)
    assert saved["region_y_ratio"] == pytest.approx(101 / 720)


def test_minimap_picker_notifies_runtime_binding_after_region_is_saved(app, monkeypatch):
    config = FakeConfig({
        "coord_mode": "relative",
        "settings2": {"game_window_title": "MapleStory Worlds"},
        "minimap": {},
    })
    button = make_minimap_picker(app, monkeypatch, config)
    applied = []
    signal = getattr(button, "region_applied", None)
    if signal is not None:
        signal.connect(lambda: applied.append(copy.deepcopy(config.get("minimap"))))

    button.click()

    assert applied == [config.get("minimap")]


def test_minimap_runtime_binding_applies_latest_saved_region(app, monkeypatch):
    import run_integrated

    config = FakeConfig({
        "coord_mode": "relative",
        "settings2": {"game_window_title": "MapleStory Worlds"},
        "minimap": {},
    })
    button = make_minimap_picker(app, monkeypatch, config)
    button.setProperty("regionRole", "minimap")
    shell = SimpleNamespace(findChildren=lambda _type: [button])
    applied = []
    runtime = SimpleNamespace(update_minimap_region=lambda region: applied.append(region))
    binder = getattr(run_integrated, "bind_minimap_region_controls", None)

    assert callable(binder)
    binder(shell, runtime, config)
    button.click()

    assert applied == [config.get("minimap")]
