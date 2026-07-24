# 사냥터별 인식·이동·맵이탈 설정을 하나의 프리셋으로 저장하고 복원한다.
from __future__ import annotations

from copy import deepcopy


PRESET_SETTING_KEYS = (
    "minimap",
    "attack",
    "hunt_mode",
    "world_map",
    "navigation",
    "map_exit",
    "zones",
    "floor_hunt",
)


def _active_name(config, name: str | None = None) -> str:
    resolved = name if name is not None else config.get(
        "hunt_grounds", "active", default=""
    )
    resolved = str(resolved or "").strip()
    if not resolved:
        raise ValueError("사냥터 이름을 먼저 입력해 주세요.")
    return resolved


def save_active_preset(config, mapping_completed: bool = True) -> dict:
    """현재 사냥터와 관련된 설정만 복사해 이름별 프리셋으로 저장한다."""
    name = _active_name(config)
    snapshot = {}
    for key in PRESET_SETTING_KEYS:
        value = config.get(key, default=None)
        if value is not None:
            snapshot[key] = deepcopy(value)
    snapshot["mapping_completed"] = bool(mapping_completed)

    presets = deepcopy(config.get("hunt_grounds", "presets", default={}) or {})
    presets[name] = snapshot
    config.set("hunt_grounds", "active", name)
    config.set("hunt_grounds", "presets", presets)
    config.save()
    return deepcopy(snapshot)


def load_preset(config, name: str | None = None) -> dict:
    """선택한 사냥터 프리셋을 관련 설정에만 병합한다."""
    resolved = _active_name(config, name)
    preset = config.get("hunt_grounds", "presets", resolved, default=None)
    if not isinstance(preset, dict):
        raise ValueError(f"'{resolved}'에 저장된 설정이 없습니다.")

    for key in PRESET_SETTING_KEYS:
        if key in preset:
            config.set(key, deepcopy(preset[key]))
    config.set("hunt_grounds", "active", resolved)
    config.save()
    return deepcopy(preset)
