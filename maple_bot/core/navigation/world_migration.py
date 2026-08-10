from __future__ import annotations
# 기존 로컬 좌표 설정을 백업하고 전역 지도 좌표로 한 번만 변환하는 도구

import shutil
from copy import deepcopy
from pathlib import Path

from core.navigation.world_map import WorldPoint


def backup_config(config_path: str, timestamp: str) -> Path:
    source = Path(config_path)
    target = source.with_name(f"config.pre_world_map_{timestamp}.json")
    shutil.copy2(source, target)
    return target


def migrate_legacy_data(data: dict, calibration, viewport_origin: WorldPoint) -> dict:
    result = deepcopy(data)
    world = result.setdefault("world_map", {})
    if world.get("migration_completed"):
        return result

    def point(x, y):
        return WorldPoint(
            viewport_origin.x + float(x) * calibration.scale,
            viewport_origin.y + float(y) * calibration.scale,
        )

    for block in result.get("floor_hunt", {}).get("route", []):
        if int(block.get("pos_x", -1)) >= 0 and int(block.get("pos_y", -1)) >= 0:
            converted = point(block["pos_x"], block["pos_y"])
            block["pos_x"] = round(converted.x)
            block["pos_y"] = round(converted.y)
        for key in ("target_x", "start_x", "end_x", "ladder_x"):
            if key in block:
                block[key] = round(
                    viewport_origin.x + float(block[key]) * calibration.scale
                )
        for key in ("y_top", "y_bot"):
            if key in block:
                block[key] = round(
                    viewport_origin.y + float(block[key]) * calibration.scale
                )

    for zone in result.get("zones", []):
        zone["left_x"] = round(
            viewport_origin.x + float(zone["left_x"]) * calibration.scale
        )
        zone["right_x"] = round(
            viewport_origin.x + float(zone["right_x"]) * calibration.scale
        )
        zone["y_min"] = round(
            viewport_origin.y + float(zone["y_min"]) * calibration.scale
        )
        zone["y_max"] = round(
            viewport_origin.y + float(zone["y_max"]) * calibration.scale
        )
    world["migration_completed"] = True
    return result
