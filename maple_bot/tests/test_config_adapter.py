# config_adapter — 실제 config.json 딕셔너리를 RuntimeConfig로 매핑하는 어댑터 검증
import json
import os
import pytest
from core.config_manager import DEFAULT_CONFIG
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


def test_default_reference_color_is_deployed_yellow_rgb():
    assert DEFAULT_CONFIG["minimap"]["reference_color_rgb"] == [225, 225, 0]


def test_reference_color_rgb_overrides_legacy_hsv_fields():
    data = _sample_config()
    data["minimap"].update({
        "reference_color_rgb": [220, 210, 20],
        "hsv_h_low": 1,
        "hsv_h_high": 2,
        "hsv_s_low": 3,
        "hsv_v_low": 4,
    })

    result = to_runtime_config(data)

    assert result.char_rgb == (220, 210, 20)
    assert result.char_h_low is None
    assert result.char_h_high is None


def test_legacy_char_rgb_is_used_when_reference_color_is_absent():
    result = to_runtime_config(_sample_config())

    assert result.char_rgb == (225, 225, 0)
    assert result.char_h_low is None
    assert result.char_h_high is None


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
    absolute_keys = {"left", "top", "width", "height"}
    relative_keys = {"base_region", "x_ratio", "y_ratio", "w_ratio", "h_ratio"}
    assert absolute_keys <= rc.minimap_region.keys() or relative_keys <= rc.minimap_region.keys()
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


def test_maps_attack_sequences_secondary_potions_and_legacy_coordinate_mode():
    data = {
        "hunt_mode": "coordinate",
        "attack": {
            "key": "ctrl",
            "sequences": [{
                "enabled": True,
                "name": "연속기 1",
                "keys": ["ctrl", "a"],
                "key_interval_sec": 0.15,
                "repeat_interval_sec": 5.0,
            }],
        },
        "recovery": {
            "hp_potion": {"enabled": True, "key": "9", "secondary_key": "8"},
            "mp_potion": {"enabled": True, "key": "0", "secondary_key": "7"},
        },
    }

    runtime = to_runtime_config(data)

    assert runtime.hunt_mode == "key"
    assert runtime.attack_sequences[0].keys == ("ctrl", "a")
    assert runtime.attack_sequences[0].repeat_interval_sec == 5.0
    assert runtime.hp_rule.secondary_key == "8"
    assert runtime.mp_rule.secondary_key == "7"


def test_rednose2_user_x_settings_override_defaults_and_rebuild_ratios():
    data = _sample_config()
    data["hunt_grounds"] = {"active": "빨코2"}
    data["rednose2_v5"] = {
        "floor2_left_x": 58,
        "floor2_right_x": 121,
        "floor2_right_safe_x": 120,
        "stair7_x": 42,
        "stair7_x_min": 39,
        "stair7_x_max": 45,
        "platform24_approach_x": 44,
        "platform24_x": 31,
        "platform1415_16_approach_x": 97,
        "platform1415_x_min": 96,
        "platform1415_x_max": 98,
        "platform27_approach_x": 92,
        "platform27_bypass_approach_x": 81,
        "platform27_bypass_x_min": 73,
        "platform27_bypass_x_max": 90,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["floor2_left_x"] == 58
    assert profile["stair7_x"] == 42
    assert profile["platform1415_16_approach_x"] == 97
    assert profile["platform27_bypass_x_max"] == 90
    assert profile["floor2_left_x_ratio"] == pytest.approx(58 / 172)
    assert profile["platform27_bypass_x_max_ratio"] == pytest.approx(90 / 172)


def test_rednose2_user_y_settings_override_defaults_and_rebuild_ratios():
    data = _sample_config()
    data["hunt_grounds"] = {"active": "빨코2"}
    data["rednose2_v5"] = {
        "floor2_y_min": 60,
        "floor2_y_max": 64,
        "floor1_y_min": 74,
        "floor1_y_max": 78,
        "floor3_y_min": 46,
        "floor3_y_max": 52,
        "stair7_y": 69,
        "platform24_y": 62,
        "platform1415_y_min": 53,
        "platform1415_y_max": 56,
        "platform16_y_min": 46,
        "platform16_y_max": 49,
        "platform27_y_min": 49,
        "platform27_y_max": 51,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["floor2_y_min"] == 60
    assert profile["stair7_y"] == 69
    assert profile["platform27_y_max"] == 51
    assert profile["floor2_y_min_ratio"] == pytest.approx(60 / 103)
    assert profile["platform27_y_max_ratio"] == pytest.approx(51 / 103)


def test_rednose2_invalid_external_ranges_fall_back_by_group():
    data = _sample_config()
    data["rednose2_v5"] = {
        "floor2_left_x": 130,
        "floor2_right_x": 120,
        "platform24_approach_x": 46,
        "stair7_x_min": 44,
        "stair7_x": 40,
        "stair7_x_max": 42,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["floor2_left_x"] == 55
    assert profile["floor2_right_x"] == 124
    assert profile["stair7_x_min"] == 38
    assert profile["stair7_x"] == 41
    assert profile["stair7_x_max"] == 44
    assert profile["platform24_approach_x"] == 46


def test_rednose2_x_overrides_do_not_change_rednose3_profile():
    baseline = to_runtime_config(_sample_config()).rednose3
    data = _sample_config()
    data["rednose2_v5"] = {"floor2_left_x": 58, "floor2_right_x": 121}

    assert to_runtime_config(data).rednose3 == baseline


def test_legacy_rednose2_timing_uses_completion_interval_compatibility_defaults():
    data = _sample_config()
    data["rednose2_v5"] = {
        "attack_hold_sec": 0.9,
        "floor2_hunt_teleport_interval_sec": 0.4,
        "floor2_right_edge_teleport_interval_sec": 1.8,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["timing_version"] == 2
    assert profile["floor2_hunt_teleport_interval_sec"] == 0.72
    assert profile["floor2_right_edge_teleport_interval_sec"] == 0.90


def test_versioned_rednose2_timing_preserves_valid_saved_values():
    data = _sample_config()
    data["rednose2_v5"] = {
        "timing_version": 2,
        "teleport_hold_sec": 0.21,
        "attack_hold_sec": 0.77,
        "floor2_hunt_teleport_interval_sec": 0.66,
        "stair7_right_teleport_hold_sec": 0.08,
        "floor2_right_edge_teleport_interval_sec": 0.88,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["teleport_hold_sec"] == 0.21
    assert profile["attack_hold_sec"] == 0.77
    assert profile["floor2_hunt_teleport_interval_sec"] == 0.66
    assert profile["stair7_right_teleport_hold_sec"] == 0.08
    assert profile["floor2_right_edge_teleport_interval_sec"] == 0.88
