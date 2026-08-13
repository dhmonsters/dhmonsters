# config_adapter ??config.json ?뺤뀛?덈━瑜?RuntimeConfig濡?留ㅽ븨 (湲곗〈 ?ㅼ젙 ???좉퇋 ?고????ㅻ━)
from __future__ import annotations

import math
from dataclasses import fields

try:
    from core.runtime import RuntimeConfig
except ModuleNotFoundError:
    import importlib.util
    import sys
    from pathlib import Path

    def _load_runtime_config_fallback():
        candidates = []
        here = Path(__file__).resolve()
        candidates.append(here.with_name("runtime.py"))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "core" / "runtime.py")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "core" / "runtime.py")
        candidates.append(exe_dir / "_internal" / "core" / "runtime.py")

        for path in candidates:
            if not path.exists():
                continue
            spec = importlib.util.spec_from_file_location("core.runtime", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["core.runtime"] = module
                spec.loader.exec_module(module)
                return module.RuntimeConfig
        raise

    RuntimeConfig = _load_runtime_config_fallback()
from core.navigation.block import Block
from core.navigation.route_state import RouteStep
from core.navigation.floor_judge import Floor
from core.acting.combat import PotionRule
from core.acting.attack_sequence import AttackSequence
from core.acting.buff import Buff
from core.navigation.image_trigger import ImageTriggerSpec
from core.navigation.world_map import ActionSpec, WorldMapModel


class _DictConfigView:
    """dict ?ㅼ젙??ConfigManager.get ?뺥깭濡??쎄쾶 ?댁＜???먮룞?먮ℓ???대뙌??"""

    def __init__(self, data: dict):
        self._data = data

    def get(self, *keys, default=None):
        cur = self._data
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                return default
            cur = cur[key]
        return cur


def _resolve_window_ratio_region(region_cfg: dict, window_title: str) -> dict | None:
    """寃뚯엫李?湲곗? 鍮꾩쑉 ?곸뿭???꾩옱 寃뚯엫李??붾㈃ 醫뚰몴濡?蹂?섑븳??"""
    try:
        from core.puzzle.game_window import (
            find_game_hwnd,
            find_window_hwnd_by_title,
            get_game_client_rect_screen,
        )

        hwnd = None
        if window_title:
            hwnd = find_window_hwnd_by_title(window_title)
        if not hwnd:
            hwnd = find_game_hwnd()
        if not hwnd:
            return None

        left, top, width, height = get_game_client_rect_screen(hwnd)
        if width <= 0 or height <= 0:
            return None

        return {
            "left": left + int(float(region_cfg["x_ratio"]) * width),
            "top": top + int(float(region_cfg["y_ratio"]) * height),
            "width": max(1, int(float(region_cfg["w_ratio"]) * width)),
            "height": max(1, int(float(region_cfg["h_ratio"]) * height)),
        }
    except Exception:
        return None


def _legacy_absolute_region_to_window_ratio(region_cfg, window_title: str) -> dict | None:
    """예전 절대좌표 거탐 영역을 현재 게임창 기준 상대좌표로 변환한다."""
    x, y, w, h = [int(v) for v in region_cfg]
    try:
        from core.puzzle.game_window import (
            find_game_hwnd,
            find_window_hwnd_by_title,
            get_game_client_rect_screen,
        )

        hwnd = None
        if window_title:
            hwnd = find_window_hwnd_by_title(window_title)
        if not hwnd:
            hwnd = find_game_hwnd()
        if not hwnd:
            return None

        left, top, width, height = get_game_client_rect_screen(hwnd)
        if width <= 0 or height <= 0:
            return None

        return {
            "x_ratio": max(0.0, min(1.0, (x - left) / width)),
            "y_ratio": max(0.0, min(1.0, (y - top) / height)),
            "w_ratio": max(0.001, min(1.0, w / width)),
            "h_ratio": max(0.001, min(1.0, h / height)),
            "legacy_region": [x, y, w, h],
        }
    except Exception:
        pass
    return {
        "x_ratio": max(0.0, min(1.0, x / 1920.0)),
        "y_ratio": max(0.0, min(1.0, y / 1080.0)),
        "w_ratio": max(0.001, min(1.0, w / 1920.0)),
        "h_ratio": max(0.001, min(1.0, h / 1080.0)),
        "legacy_region": [x, y, w, h],
        "fallback_base": [1920, 1080],
    }

def _potion_rule(cfg: dict) -> PotionRule:
    """recovery.hp_potion/mp_potion ?뺤뀛?덈━ ??PotionRule. threshold %?믩퉬??"""
    kwargs = {
        "enabled": bool(cfg.get("enabled", False)),
        "key": cfg.get("key", ""),
        "secondary_key": cfg.get("secondary_key", ""),
        "threshold": float(cfg.get("threshold", 70)) / 100.0,
        "cooldown": (
            1.0 if float(cfg.get("cooldown_sec", 1.0)) == 3.0
            else float(cfg.get("cooldown_sec", 1.0))
        ),
        "verify_delay": float(cfg.get("verify_delay_sec", 0.2)),
        "min_recovery": float(cfg.get("min_recovery_percent", 1.0)) / 100.0,
    }
    allowed = {field.name for field in fields(PotionRule)}
    return PotionRule(**{key: value for key, value in kwargs.items() if key in allowed})


def _attack_sequences(attack: dict) -> list[AttackSequence]:
    return [
        AttackSequence.from_dict(data)
        for data in (attack.get("sequences") or [])
        if isinstance(data, dict)
    ]


def _minimap_region_profile(mm: dict) -> dict:
    """현재 UI에 저장된 미니맵 영역을 게임창 기준 상대좌표로 전달한다."""
    region = {
        "base_region": [
            int(mm.get("region_x", 38)),
            int(mm.get("region_y", 129)),
            int(mm.get("width", 172)),
            int(mm.get("height", 103)),
        ],
    }
    ratio_keys = ("region_x_ratio", "region_y_ratio", "width_ratio", "height_ratio")
    if all(mm.get(key) is not None for key in ratio_keys):
        region.update({
            "x_ratio": float(mm.get("region_x_ratio")),
            "y_ratio": float(mm.get("region_y_ratio")),
            "w_ratio": float(mm.get("width_ratio")),
            "h_ratio": float(mm.get("height_ratio")),
        })
    else:
        region.update({
            "left": int(mm.get("region_x", 38)),
            "top": int(mm.get("region_y", 129)),
            "width": int(mm.get("width", 172)),
            "height": int(mm.get("height", 103)),
        })
    return region


def _with_minimap_ratios(profile: dict, x_keys: tuple[str, ...], y_keys: tuple[str, ...]) -> dict:
    """고정 좌표를 기준 미니맵 내부 비율로 함께 저장한다."""
    base_w = max(1.0, float(profile.get("base_minimap_width", 172)))
    base_h = max(1.0, float(profile.get("base_minimap_height", 103)))
    for key in x_keys:
        if key in profile and f"{key}_ratio" not in profile:
            profile[f"{key}_ratio"] = float(profile[key]) / base_w
    for key in y_keys:
        if key in profile and f"{key}_ratio" not in profile:
            profile[f"{key}_ratio"] = float(profile[key]) / base_h
    return profile


def _platforms_with_minimap_ratios(profile: dict) -> dict:
    """빨코3 발판 범위를 기준 미니맵 내부 비율로 함께 저장한다."""
    base_w = max(1.0, float(profile.get("base_minimap_width", 172)))
    base_h = max(1.0, float(profile.get("base_minimap_height", 103)))
    for data in (profile.get("platforms") or {}).values():
        if not isinstance(data, dict):
            continue
        for key in ("x", "x_min", "x_max"):
            if key in data and f"{key}_ratio" not in data:
                data[f"{key}_ratio"] = float(data[key]) / base_w
        for key in ("y", "y_min", "y_max"):
            if key in data and f"{key}_ratio" not in data:
                data[f"{key}_ratio"] = float(data[key]) / base_h
    return profile


def _route_blocks_with_minimap_ratios(blocks: list, mm: dict) -> list:
    """레거시 동선 픽셀 좌표를 저장 당시 미니맵 내부 비율로 한 번만 변환한다."""
    base_w = max(1.0, float(mm.get("width", 172)))
    base_h = max(1.0, float(mm.get("height", 103)))
    converted = []
    for source in blocks:
        if not isinstance(source, dict):
            continue
        block = dict(source)
        for key in (
            "target_x", "start_x", "end_x", "pos_x", "ladder_x",
            "rand_margin", "jump_offset",
        ):
            ratio_key = f"{key}_ratio"
            if block.get(ratio_key) is None and block.get(key) is not None:
                block[ratio_key] = float(block[key]) / base_w
        for key in ("pos_y", "y_top", "y_bot"):
            ratio_key = f"{key}_ratio"
            value = block.get(key)
            if block.get(ratio_key) is None and value is not None and float(value) >= 0:
                block[ratio_key] = float(value) / base_h
        converted.append(block)
    return converted


REDNOSE2_X_DEFAULTS = {
    "floor2_left_x": 55,
    "floor2_right_x": 124,
    "floor2_right_safe_x": 124,
    "stair7_x": 41,
    "stair7_x_min": 38,
    "stair7_x_max": 44,
    "platform24_approach_x": 43,
    "platform24_x": 30,
    "platform1415_16_approach_x": 95,
    "platform1415_x_min": 94,
    "platform1415_x_max": 96,
    "platform27_approach_x": 91,
    "platform27_bypass_approach_x": 80,
    "platform27_bypass_x_min": 72,
    "platform27_bypass_x_max": 89,
}

REDNOSE2_TIMING_VERSION = 2
REDNOSE2_TIMING_DEFAULTS = {
    "teleport_hold_sec": 0.30,
    "attack_hold_sec": 0.90,
    "floor2_hunt_teleport_interval_sec": 0.72,
    "stair7_right_teleport_hold_sec": 0.10,
    "floor2_right_edge_teleport_interval_sec": 0.90,
}


def rednose2_x_validation_error(values: dict) -> str | None:
    for key in REDNOSE2_X_DEFAULTS:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 171:
            return "모든 X 좌표는 0~171 사이의 정수여야 합니다."
    if values["floor2_left_x"] > values["floor2_right_x"]:
        return "2층 사냥 범위의 왼쪽 X는 오른쪽 X보다 클 수 없습니다."
    if not values["stair7_x_min"] <= values["stair7_x"] <= values["stair7_x_max"]:
        return "7번 계단 목표 X는 허용 범위 안에 있어야 합니다."
    if not values["platform1415_x_min"] <= values["platform1415_16_approach_x"] <= values["platform1415_x_max"]:
        return "14/15번과 16번 공통 접근 X는 14/15 허용 범위 안에 있어야 합니다."
    if not values["platform27_bypass_x_min"] <= values["platform27_bypass_approach_x"] <= values["platform27_bypass_x_max"]:
        return "27번 우회 접근 X는 우회 허용 범위 안에 있어야 합니다."
    return None


def _valid_rednose2_x(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 171


def _rednose2_group_is_valid(keys: tuple[str, ...], values: dict) -> bool:
    if not all(_valid_rednose2_x(values[key]) for key in keys):
        return False
    if keys == ("floor2_left_x", "floor2_right_x"):
        return values["floor2_left_x"] <= values["floor2_right_x"]
    if keys == ("stair7_x_min", "stair7_x", "stair7_x_max"):
        return values["stair7_x_min"] <= values["stair7_x"] <= values["stair7_x_max"]
    if keys == ("platform1415_x_min", "platform1415_16_approach_x", "platform1415_x_max"):
        return values["platform1415_x_min"] <= values["platform1415_16_approach_x"] <= values["platform1415_x_max"]
    if keys == ("platform27_bypass_x_min", "platform27_bypass_approach_x", "platform27_bypass_x_max"):
        return values["platform27_bypass_x_min"] <= values["platform27_bypass_approach_x"] <= values["platform27_bypass_x_max"]
    return False


def _merge_rednose2_x_settings(raw: dict | None) -> dict[str, int]:
    raw = raw if isinstance(raw, dict) else {}
    merged = dict(REDNOSE2_X_DEFAULTS)
    simple_keys = (
        "floor2_right_safe_x",
        "platform24_approach_x",
        "platform24_x",
        "platform27_approach_x",
    )
    for key in simple_keys:
        if _valid_rednose2_x(raw.get(key)):
            merged[key] = int(raw[key])

    groups = (
        ("floor2_left_x", "floor2_right_x"),
        ("stair7_x_min", "stair7_x", "stair7_x_max"),
        ("platform1415_x_min", "platform1415_16_approach_x", "platform1415_x_max"),
        ("platform27_bypass_x_min", "platform27_bypass_approach_x", "platform27_bypass_x_max"),
    )
    for keys in groups:
        candidate = dict(merged)
        for key in keys:
            if key in raw:
                candidate[key] = raw[key]
        if _rednose2_group_is_valid(keys, candidate):
            merged.update({key: int(candidate[key]) for key in keys})
    return merged


def _valid_rednose2_timing(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 10.0
    )


def _merge_rednose2_timing_settings(raw: dict | None) -> dict[str, float | int]:
    merged: dict[str, float | int] = {
        "timing_version": REDNOSE2_TIMING_VERSION,
        **REDNOSE2_TIMING_DEFAULTS,
    }
    if not isinstance(raw, dict) or raw.get("timing_version") != REDNOSE2_TIMING_VERSION:
        return merged
    for key in REDNOSE2_TIMING_DEFAULTS:
        if _valid_rednose2_timing(raw.get(key)):
            merged[key] = float(raw[key])
    return merged


def _rednose2_v5_profile(d: dict, attack: dict) -> dict:
    """Build RedNose2 v5 runtime profile from one fixed source."""
    mm = d.get("minimap", {}) or {}
    forced = {
        "enabled": True,
        "use_fixed_minimap_region": True,
        "fixed_minimap_region": _minimap_region_profile(mm),
        "attack_key": "end",
        "teleport_key": "x",
        "attack_hold_sec": 0.9,
        "retry_attack_hold_sec": 1.5,
        "teleport_hold_sec": 0.3,
        "teleport_step_px": 13.0,
        "teleport_interval_sec": 0.4,
        "attack_to_teleport_sec": 0.5,
        "floor2_hunt_teleport_interval_sec": 0.4,
        "floor2_right_edge_teleport_interval_sec": 1.8,
        "close_walk_px": 8,
        "arrival_tolerance": 3,
        "max_step_sec": 18.0,
        **REDNOSE2_X_DEFAULTS,
        "auto_sell_entry_x_min": 123,
        "auto_sell_entry_x_max": 136,
        "auto_sell_entry_x": 129.5,
        "floor2_y_min": 61,
        "floor2_y_max": 63,
        "floor1_y_min": 75,
        "floor1_y_max": 77,
        "floor3_y_min": 47,
        "floor3_y_max": 51,
        "stair7_y": 67,
        "stair7_return_y_min": 66,
        "stair7_return_y_max": 68,
        "stair7_right_bias_x": 45,
        "stair7_right_bias_correct_sec": 0.0,
        "stair7_right_teleport_hold_sec": 0.1,
        "stair7_right_teleport_lead_sec": 0.02,
        "platform24_y": 61,
        "platform1415_y_min": 54,
        "platform1415_y_max": 55,
        "platform16_y_min": 47,
        "platform16_y_max": 48,
        "platform27_y_min": 50,
        "platform27_y_max": 50,
        "pickup_route_enabled": True,
        "hunt_cycle_min_sec": 92.83,
        "hunt_cycle_max_sec": 102.483,
        "base_minimap_width": 172,
        "base_minimap_height": 103,
    }
    forced["minimap_width"] = int(mm.get("width", forced["base_minimap_width"]))
    forced["minimap_height"] = int(mm.get("height", forced["base_minimap_height"]))
    forced.update(_merge_rednose2_x_settings(d.get("rednose2_v5")))
    forced.update(_merge_rednose2_timing_settings(d.get("rednose2_v5")))
    return _with_minimap_ratios(
        forced,
        x_keys=(
            "floor2_left_x", "floor2_right_x", "floor2_right_safe_x",
            "auto_sell_entry_x_min", "auto_sell_entry_x_max", "auto_sell_entry_x",
            "stair7_x", "stair7_x_min", "stair7_x_max", "stair7_right_bias_x",
            "platform24_approach_x", "platform24_x",
            "platform1415_16_approach_x", "platform1415_x_min", "platform1415_x_max",
            "platform27_approach_x", "platform27_bypass_approach_x",
            "platform27_bypass_x_min", "platform27_bypass_x_max",
        ),
        y_keys=(
            "floor2_y_min", "floor2_y_max",
            "floor1_y_min", "floor1_y_max",
            "floor3_y_min", "floor3_y_max",
            "stair7_y", "stair7_return_y_min", "stair7_return_y_max",
            "platform24_y",
            "platform1415_y_min", "platform1415_y_max",
            "platform16_y_min", "platform16_y_max",
            "platform27_y_min", "platform27_y_max",
        ),
    )


def _rednose3_profile(d: dict, attack: dict) -> dict:
    """Build RedNose3 teleport-only runtime profile from one fixed source."""
    mm = d.get("minimap", {}) or {}
    forced = {
        "enabled": True,
        "use_fixed_minimap_region": True,
        "fixed_minimap_region": _minimap_region_profile(mm),
        "attack_key": "end",
        "teleport_key": "x",
        "jump_key": str(mm.get("jump_key", "alt") or "alt"),
        "attack_hold_sec": 0.9,
        "attack_gap_sec": 0.05,
        "teleport_hold_sec": 0.07,
        "teleport_lead_sec": 0.09,
        "left_direction_hold_sec": 0.15,
        "right_direction_hold_sec": 0.13,
        "vertical_teleport_lead_sec": 0.02,
        "after_teleport_wait_sec": 0.12,
        "down_jump_lead_sec": 0.03,
        "down_jump_hold_sec": 0.12,
        "after_down_jump_wait_sec": 0.25,
        "platform1_attack_count": 16,
        "platform2_attack_count": 4,
        "hunt_cycle_min_sec": 92.83,
        "hunt_cycle_max_sec": 102.483,
        "fall_y_threshold": 70,
        "confirm_timeout_sec": 0.55,
        "step_attempts": 5,
        "recover_attempts": 10,
        "platforms": {
            "1": {"x_min": 54, "x_max": 59, "y_min": 68, "y_max": 70},
            "2": {"x_min": 41, "x_max": 45, "y_min": 63, "y_max": 65},
            "3": {"x_min": 30, "x_max": 34, "y_min": 63, "y_max": 65},
            "4": {"x_min": 30, "x_max": 34, "y_min": 52, "y_max": 54},
            "5": {"x_min": 30, "x_max": 34, "y_min": 40, "y_max": 42},
            "6": {"x_min": 30, "x_max": 34, "y_min": 45, "y_max": 47},
        },
        "base_minimap_width": 172,
        "base_minimap_height": 103,
    }
    forced["minimap_width"] = int(mm.get("width", forced["base_minimap_width"]))
    forced["minimap_height"] = int(mm.get("height", forced["base_minimap_height"]))
    forced["fall_y_threshold_ratio"] = (
        float(forced["fall_y_threshold"]) / float(forced["base_minimap_height"])
    )
    return _platforms_with_minimap_ratios(forced)


def _hunt_ground_matches(active: str, canonical: str) -> bool:
    """깨진 인코딩으로 저장된 사냥터 이름까지 전용 루틴 선택에 포함한다."""
    value = str(active or "").strip()
    aliases = {
        "빨코2": {"빨코2", "鍮⑥퐫2", "rednose2", "rednose2v5"},
        "빨코3": {"빨코3", "鍮⑥퐫3", "rednose3"},
    }
    return value in aliases.get(canonical, {canonical})

def _buffs(attack: dict) -> list[Buff]:
    """attack.normal_buffs/toggle_buffs ??Buff 由ъ뒪??(?쒖꽦+???덈뒗 寃껊쭔)."""
    out: list[Buff] = []
    for group in ("normal_buffs", "toggle_buffs"):
        for b in attack.get(group, []) or []:
            key = (b.get("key") or "").strip()
            if not b.get("enabled") or not key:
                continue
            out.append(Buff(
                key=key,
                interval=float(b.get("interval_sec", 60)),
                hold_sec=float(b.get("hold_sec", 0.8)),
            ))
    return out


def _floors(zones: list) -> list[Floor]:
    """zones ??Floor 由ъ뒪??(Y 踰붿쐞留?."""
    return [
        Floor(name=z.get("name", "援ъ뿭"),
              y_min=int(z.get("y_min", 0)), y_max=int(z.get("y_max", 0)))
        for z in (zones or [])
    ]


def to_runtime_config(d: dict) -> RuntimeConfig:
    """config.json ?꾩껜 ?뺤뀛?덈━ ??RuntimeConfig."""
    mm = d.get("minimap", {})
    minimap_region = {
        "left": int(mm.get("region_x", 0)),
        "top": int(mm.get("region_y", 0)),
        "width": int(mm.get("width", 200)),
        "height": int(mm.get("height", 120)),
    }
    if all(mm.get(key) is not None for key in ("region_x_ratio", "region_y_ratio", "width_ratio", "height_ratio")):
        minimap_region.update({
            "x_ratio": float(mm.get("region_x_ratio")),
            "y_ratio": float(mm.get("region_y_ratio")),
            "w_ratio": float(mm.get("width_ratio")),
            "h_ratio": float(mm.get("height_ratio")),
            "base_region": [
                int(mm.get("region_x", 0)),
                int(mm.get("region_y", 0)),
                int(mm.get("width", 200)),
                int(mm.get("height", 120)),
            ],
        })
    raw_reference_rgb = mm.get("reference_color_rgb")
    reference_rgb = None
    if isinstance(raw_reference_rgb, (list, tuple)) and len(raw_reference_rgb) == 3:
        try:
            reference_rgb = tuple(max(0, min(255, int(value))) for value in raw_reference_rgb)
        except (TypeError, ValueError):
            reference_rgb = None
    raw_char_rgb = (
        (int(mm["char_r"]), int(mm["char_g"]), int(mm["char_b"]))
        if all(k in mm for k in ("char_r", "char_g", "char_b"))
        else None
    )
    # ?몃? 罹먮┃????湲곗?: 鍮④컯/?곗깋 ???섎せ ??λ맂 ?됱긽? ?몃??됱쑝濡?蹂댁젙?쒕떎.
    char_rgb = reference_rgb or (
        raw_char_rgb
        if raw_char_rgb is not None
        and raw_char_rgb[0] >= 180
        and raw_char_rgb[1] >= 180
        and raw_char_rgb[2] <= 100
        else (225, 225, 0)
    )

    recovery = d.get("recovery", {})
    hp_rule = _potion_rule(recovery.get("hp_potion", {}))
    mp_rule = _potion_rule(recovery.get("mp_potion", {}))

    attack = d.get("attack", {})
    ladder_profile = d.get("ladder_profile", {}) or {}
    attack_key = attack.get("key", "") or d.get("minimap", {}).get("attack_key", "")

    # ?щ깷 ?곸뿭 (B training) ??w>0?대㈃ region dict, ?꾨땲硫?None(?꾩껜?붾㈃)
    ha = attack.get("hunt_area", {})
    hunt_area_region = None
    if int(ha.get("w", 0)) > 0:
        hunt_area_region = {
            "left": int(ha.get("x", 0)), "top": int(ha.get("y", 0)),
            "width": int(ha.get("w", 0)), "height": int(ha.get("h", 0)),
        }

    world_map = None
    world_data = d.get("world_map", {})
    if (world_data.get("enabled") and world_data.get("image_path")
            and world_data.get("calibration")):
        world_map = WorldMapModel.from_dict(d)

    image_trigger_spec = None
    trigger_data = attack.get("image_trigger", {})
    if trigger_data.get("enabled") and trigger_data.get("template_path"):
        action_data = trigger_data.get("action", {})
        image_trigger_spec = ImageTriggerSpec(
            template_path=str(trigger_data["template_path"]),
            threshold=float(trigger_data.get("threshold", 0.8)),
            check_interval_sec=float(trigger_data.get("check_interval_sec", 0.1)),
            cooldown_sec=float(trigger_data.get("cooldown_sec", 2.0)),
            action=ActionSpec(
                key=str(action_data.get("key", "space")),
                hold_sec=float(action_data.get("hold_sec", 0.1)),
                repeat=int(action_data.get("repeat", 1)),
                repeat_interval_sec=float(action_data.get("repeat_interval_sec", 0.0)),
                wait_after_sec=float(action_data.get("wait_after_sec", 0.0)),
                action_type=str(action_data.get("action_type", "key")),
                click_x=action_data.get("click_x"),
                click_y=action_data.get("click_y"),
            ),
        )

    # 紐ъ뒪???쒗뵆由??섏쭛 (?⑥씪 monster_template + monster_folder ??png??= B ?ㅼ쨷諛⑹떇)
    import os, glob as _glob
    monster_tpls = []
    mt = attack.get("monster_template", "")
    if mt and os.path.exists(mt):
        monster_tpls.append(mt)
    mf = attack.get("monster_folder", "")
    if mf and os.path.isdir(mf):
        monster_tpls += sorted(_glob.glob(os.path.join(mf, "*.png")))

    # ?쒖같: 泥?zone??醫뚯슦 寃쎄퀎 + ?쒕뜡 留덉쭊
    zones = d.get("zones", [])
    z0 = zones[0] if zones else {}
    patrol_left = int(z0.get("left_x", 0))
    patrol_right = int(z0.get("right_x", 0))
    patrol_margin = int(z0.get("random_margin_max", 0))

    # ??癒뱀씠 / ?붾젅洹몃옩 / ?좎?媛먯?
    pet = recovery.get("pet_food", {})
    pet_key = pet.get("key", "") if pet.get("enabled") else ""
    pet_interval = float(pet.get("interval_min", 10)) * 60
    pet_count = int(pet.get("pet_count", 1))

    lie = d.get("settings1", {}).get("lie_detector", {})
    user = d.get("settings1", {}).get("user_detected", {})
    lie_region = lie.get("region")
    lie_detect_region = None
    game_window_title = str(d.get("settings2", {}).get("game_window_title", ""))
    if isinstance(lie_region, dict) and lie_region.get("x_ratio") is not None:
        lie_detect_region = dict(lie_region)
    elif isinstance(lie_region, (list, tuple)) and len(lie_region) == 4:
        lie_detect_region = _legacy_absolute_region_to_window_ratio(lie_region, game_window_title)
        if lie_detect_region is None:
            lie_detect_region = None

    active_hunt_ground = str(d.get("hunt_grounds", {}).get("active", "") or "").strip()
    rednose2_profile = _rednose2_v5_profile(d, attack)
    rednose3_profile = _rednose3_profile(d, attack)
    rednose2_profile["enabled"] = _hunt_ground_matches(active_hunt_ground, "빨코2")
    rednose3_profile["enabled"] = _hunt_ground_matches(active_hunt_ground, "빨코3")
    runtime_hunt_ground_active = active_hunt_ground
    if bool(rednose2_profile.get("enabled", False)):
        runtime_hunt_ground_active = "빨코2"
    elif bool(rednose3_profile.get("enabled", False)):
        runtime_hunt_ground_active = "빨코3"
    fixed_rednose_mm = (
        rednose2_profile.get("fixed_minimap_region")
        if bool(rednose2_profile.get("enabled", False))
        else rednose3_profile.get("fixed_minimap_region")
    )
    fixed_rednose_enabled = (
        bool(rednose2_profile.get("enabled", False))
        and bool(rednose2_profile.get("use_fixed_minimap_region", False))
    ) or (
        bool(rednose3_profile.get("enabled", False))
        and bool(rednose3_profile.get("use_fixed_minimap_region", False))
    )
    if (
        fixed_rednose_enabled
        and isinstance(fixed_rednose_mm, dict)
    ):
        if fixed_rednose_mm.get("x_ratio") is not None:
            minimap_region = dict(fixed_rednose_mm)
        else:
            minimap_region = {
                "left": int(fixed_rednose_mm.get("left", minimap_region["left"])),
                "top": int(fixed_rednose_mm.get("top", minimap_region["top"])),
                "width": int(fixed_rednose_mm.get("width", minimap_region["width"])),
                "height": int(fixed_rednose_mm.get("height", minimap_region["height"])),
            }
            rednose2_profile["minimap_width"] = minimap_region["width"]
            rednose2_profile["minimap_height"] = minimap_region["height"]
            rednose3_profile["minimap_width"] = minimap_region["width"]
            rednose3_profile["minimap_height"] = minimap_region["height"]
    junk_sell = d.get("settings2", {}).get("junk_sell", {}) or {}

    return RuntimeConfig(
        minimap_region=minimap_region,
        coord_mode=str(d.get("coord_mode", "relative")),
        game_window_title=game_window_title,
        coord_anchor=d.get("coord_anchor"),
        char_rgb=char_rgb,
        char_h_low=None,
        char_h_high=None,
        char_h_tol=int(mm.get("char_h_tol", 10)),
        char_s_min=int(mm.get("char_s_min", 100)),
        char_v_min=int(mm.get("char_v_min", 200)),
        char_area_min=float(mm.get("char_area_min", 3)),
        char_area_max=float(mm.get("char_area_max", 160)),
        floors=_floors(zones),
        route=[Block.from_dict(b) for b in _route_blocks_with_minimap_ratios(
                   d.get("floor_hunt", {}).get("route") or [], mm)
               if isinstance(b, dict) and "type" in b],
        route_steps=[RouteStep.from_dict(s) for s in
                     (d.get("floor_hunt", {}).get("route_steps") or [])
                     if isinstance(s, dict) and ("step_type" in s or "type" in s)],
        route_mode=bool(d.get("floor_hunt", {}).get("route_mode", False)),
        hunt_ground_active=runtime_hunt_ground_active,
        rednose2_v5=rednose2_profile,
        rednose3=rednose3_profile,
        attack_key=attack_key,
        attack_sequences=_attack_sequences(attack),
        hp_rule=hp_rule,
        mp_rule=mp_rule,
        buffs=_buffs(attack),
        minigame_type="planet",
        patrol_left_x=patrol_left,
        patrol_right_x=patrol_right,
        patrol_margin=patrol_margin,
        junk_config=_DictConfigView(d),
        auto_sell_enabled=bool(junk_sell.get("auto_sell_enabled", False)),
        auto_sell_interval_min=float(junk_sell.get("auto_sell_interval_min", 10)),
        auto_sell_on_start=bool(junk_sell.get("sell_on_start", False)),
        pet_key=pet_key,
        pet_interval=pet_interval,
        pet_count=pet_count,
        attack_interval=float(attack.get("delay_sec") if attack.get("delay_sec") is not None else 0.4),
        jump_key=str(mm.get("jump_key", "alt") or "alt"),
        jump_while_move=bool(attack.get("jump_while_move", False)),
        ladder_launch_distance=(
            5.0 if float(ladder_profile.get("launch_distance", 5.0)) == 8.0
            else float(ladder_profile.get("launch_distance", 5.0))
        ),
        ladder_launch_distance_right=float(
            ladder_profile.get("launch_distance_right", 7.0)
        ),
        ladder_launch_distance_left=float(
            ladder_profile.get("launch_distance_left", 2.0)
        ),
        ladder_jump_hold_sec=float(ladder_profile.get("jump_hold_sec", 0.10)),
        ladder_up_delay_sec=(
            0.125
            if float(ladder_profile.get("up_delay_sec", 0.125)) in (0.01, 0.03, 0.15, 0.245, 0.30)
            else float(ladder_profile.get("up_delay_sec", 0.125))
        ),
        ladder_direction_hold_sec=float(ladder_profile.get("direction_hold_sec", 0.08)),
        ladder_stable_tolerance=int(ladder_profile.get("stable_tolerance", 2)),
        ladder_stable_samples=int(ladder_profile.get("stable_samples", 3)),
        ladder_position_max_age_sec=float(ladder_profile.get("position_max_age_sec", 0.60)),
        ladder_grab_confirm_sec=(
            1.00 if float(ladder_profile.get("grab_confirm_sec", 1.00)) == 0.60
            else float(ladder_profile.get("grab_confirm_sec", 1.00))
        ),
        hits_to_kill=int(attack.get("hits_to_kill", 1)),
        skill_cast_sec=float(attack.get("skill_cast_sec") if attack.get("skill_cast_sec") is not None else 0.6),
        hunt_stay_threshold=int(attack.get("density_stay", 3)),
        hunt_leave_threshold=int(attack.get("density_leave", 1)),
        hunt_max_dwell_sec=float(attack.get("density_max_dwell_sec", 8.0)),
        pickup_key=(d.get("pickup_timer", {}).get("pickup_key", "")
                    if (d.get("pickup_timer", {}).get("enabled")
                        or d.get("pickup_timer", {}).get("always_enabled")) else ""),
        pickup_interval=float(d.get("pickup_timer", {}).get("interval_sec", 60)),
        pickup_always=bool(d.get("pickup_timer", {}).get("always_enabled", False)),
        lie_enabled=bool(lie.get("enabled", True)),
        lie_alert=bool(lie.get("alert_enabled",
                               lie.get("play_alarm", False) or lie.get("tg_enabled", False))),
        lie_title_template=str(lie.get("template_path") or "templates/lie_detector/title.png"),
        lie_threshold=float(lie.get("threshold", 0.65)),
        lie_detect_region=lie_detect_region,
        board_roi=lie.get("board_roi"),
        transparent_enabled=bool(
            d.get("settings1", {}).get("transparent_shape", {}).get("enabled", True)),
        tg_enabled=bool(lie.get("tg_enabled", False)),
        tg_token=lie.get("tg_token", ""),
        tg_chat_id=lie.get("tg_chat_id", ""),
        user_detect_enabled=bool(user.get("enabled", False)),
        auto_reply_messages=list(user.get("messages", [])),
        hunt_area_region=hunt_area_region,
        world_map=world_map,
        image_trigger_spec=image_trigger_spec,
        anti_mob_profile=d.get("anti_mob", {}) or {},
        hunt_mode="image" if d.get("hunt_mode") == "image" else "key",
        name_template=attack.get("name_template", ""),
        monster_templates=monster_tpls,
        monster_accuracy=float(attack.get("monster_accuracy", 0.9)),
        atk_x_min=int(attack.get("atk_x_min", -35)),
        atk_x_max=int(attack.get("atk_x_max", 35)),
        atk_y_min=int(attack.get("atk_y_min", -70)),
        atk_y_max=int(attack.get("atk_y_max", 70)),
        name_threshold=float(attack.get("name_tag_threshold", 0.7)),
    )

