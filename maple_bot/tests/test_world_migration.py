# 기존 로컬 좌표 설정의 전역 좌표 변환과 백업을 검증하는 테스트
import json
from copy import deepcopy

from core.navigation.world_map import (
    ActionSpec,
    Calibration,
    NavEdge,
    NavNode,
    NavRoute,
    WorldMapModel,
    WorldPoint,
)
from core.navigation.world_migration import backup_config, migrate_legacy_data


def test_migrates_route_and_zone_once():
    source = {
        "floor_hunt": {"route": [{
            "type": "move",
            "pos_x": 10,
            "pos_y": 20,
            "start_x": 5,
            "end_x": 25,
        }]},
        "zones": [{
            "name": "1층",
            "left_x": 5,
            "right_x": 25,
            "y_min": 18,
            "y_max": 22,
        }],
        "world_map": {"migration_completed": False},
    }

    result = migrate_legacy_data(
        deepcopy(source),
        Calibration(2.0, 0.0, 0.0),
        WorldPoint(100, 40),
    )

    block = result["floor_hunt"]["route"][0]
    assert (block["pos_x"], block["pos_y"]) == (120, 80)
    assert result["world_map"]["migration_completed"] is True
    assert migrate_legacy_data(
        deepcopy(result), Calibration(2, 0, 0), WorldPoint(0, 0)
    ) == result


def test_backup_config_copies_original(tmp_path):
    source = tmp_path / "config.json"
    source.write_text(json.dumps({"value": 1}), encoding="utf-8")

    target = backup_config(str(source), "20260714_120000")

    assert target.name == "config.pre_world_map_20260714_120000.json"
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 1}


def test_world_map_model_round_trip():
    action = ActionSpec("space", 0.1, 1, 0.0, 0.0)
    model = WorldMapModel(
        enabled=True,
        image_path="maps/test.png",
        image_width=1000,
        image_height=500,
        tracking_policy="strict_confirmed",
        calibration=Calibration(2.0, 10.0, 20.0),
        nodes={
            "a": NavNode("a", "waypoint", 10, 20),
            "b": NavNode("b", "action", 30, 20, 5, "공격", action),
        },
        edges=(NavEdge("e1", "a", "b", True, "walk"),),
        routes={"r1": NavRoute("r1", "순환", ("a", "b"), True)},
    )

    restored = WorldMapModel.from_dict(model.to_dict())

    assert restored == model


def test_config_manager_backs_up_and_migrates_once(tmp_path, monkeypatch):
    from core import config_manager as module

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "floor_hunt": {"route": [{"type": "move", "pos_x": 10, "pos_y": 20}]},
        "world_map": {
            "enabled": True,
            "image_path": "map.png",
            "calibration": {"scale": 2.0, "offset": [100.0, 40.0]},
            "migration_completed": False,
        },
    }), encoding="utf-8")
    monkeypatch.setattr(module, "CONFIG_PATH", str(config_path))

    first = module.ConfigManager()
    migrated = json.loads(config_path.read_text(encoding="utf-8"))
    backup_path = migrated["world_map"]["legacy_backup_path"]

    assert first.get("floor_hunt", "route")[0]["pos_x"] == 120
    assert migrated["world_map"]["migration_completed"] is True
    assert backup_path
    assert (tmp_path / backup_path.split("\\")[-1].split("/")[-1]).exists()

    module.ConfigManager()
    assert json.loads(config_path.read_text(encoding="utf-8")) == migrated
