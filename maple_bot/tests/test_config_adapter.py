# config_adapter — 실제 config.json 딕셔너리를 RuntimeConfig로 매핑하는 어댑터 검증
import json
import os
import pytest
from core.config_adapter import to_runtime_config
from core.navigation.block import Block
from core.acting.combat import PotionRule


def _sample_config():
    return {
        "minimap": {"region_x": 13, "region_y": 136, "width": 256, "height": 104,
                    "char_r": 225, "char_g": 225, "char_b": 0, "tolerance": 30,
                    "jump_key": "alt"},
        "recovery": {
            "hp_potion": {"enabled": True, "threshold": 65, "key": "pgup", "cooldown_sec": 1.0},
            "mp_potion": {"enabled": True, "threshold": 50, "key": "pgdn", "cooldown_sec": 3.0},
            "pet_food": {"enabled": True, "key": "=", "interval_min": 10},
        },
        "attack": {"key": "ctrl",
                   "normal_buffs": [{"key": "1", "interval_sec": 60, "enabled": True}],
                   "toggle_buffs": []},
        "zones": [{"name": "1층", "left_x": 60, "right_x": 202, "y_min": 66, "y_max": 79}],
    }


def test_minimap_region_mapped():
    rc = to_runtime_config(_sample_config())
    assert rc.minimap_region == {"left": 13, "top": 136, "width": 256, "height": 104}


def test_potion_rules_mapped():
    rc = to_runtime_config(_sample_config())
    assert rc.hp_rule.key == "pgup"
    assert rc.hp_rule.threshold == 0.65   # 65% → 0.65
    assert rc.hp_rule.cooldown == 1.0
    assert rc.mp_rule.key == "pgdn"
    assert rc.mp_rule.threshold == 0.50


def test_attack_key_mapped():
    rc = to_runtime_config(_sample_config())
    assert rc.attack_key == "ctrl"


def test_buffs_mapped():
    rc = to_runtime_config(_sample_config())
    assert len(rc.buffs) == 1
    assert rc.buffs[0].key == "1"
    assert rc.buffs[0].interval == 60


def test_zones_to_floors():
    rc = to_runtime_config(_sample_config())
    assert len(rc.floors) == 1
    assert rc.floors[0].name == "1층"
    assert rc.floors[0].y_min == 66 and rc.floors[0].y_max == 79


def test_disabled_potion_yields_disabled_rule():
    cfg = _sample_config()
    cfg["recovery"]["hp_potion"]["enabled"] = False
    rc = to_runtime_config(cfg)
    assert rc.hp_rule.enabled is False


def test_real_config_json_loads():
    """실제 config.json 이 어댑터를 통과한다(스모크)."""
    path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    if not os.path.exists(path):
        pytest.skip("config.json 없음")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    rc = to_runtime_config(d)
    assert "left" in rc.minimap_region
    assert rc.attack_key  # 비어있지 않음


def test_maps_enabled_world_map_and_image_trigger():
    from core.config_adapter import to_runtime_config

    data = {
        "world_map": {
            "enabled": True,
            "image_path": "maps/test.png",
            "image_width": 1000,
            "image_height": 500,
            "calibration": {"scale": 2.0, "offset": [10.0, 20.0]},
            "tracking_policy": "continue_estimated",
        },
        "navigation": {"nodes": [], "edges": [], "routes": []},
        "attack": {
            "hunt_area": {"x": 3, "y": 286, "w": 300, "h": 200},
            "image_trigger": {
                "enabled": True,
                "template_path": "templates/target.png",
                "threshold": 0.85,
                "check_interval_sec": 0.2,
                "cooldown_sec": 3.0,
                "action": {
                    "key": "space",
                    "hold_sec": 0.1,
                    "repeat": 1,
                    "repeat_interval_sec": 0.0,
                    "wait_after_sec": 0.0,
                },
            },
        },
    }

    runtime = to_runtime_config(data)

    assert runtime.world_map.enabled is True
    assert runtime.world_map.calibration.scale == 2.0
    assert runtime.hunt_area_region == {"left": 3, "top": 286, "width": 300, "height": 200}
    assert runtime.image_trigger_spec.template_path == "templates/target.png"
    assert runtime.image_trigger_spec.action.key == "space"