# config_adapter — config.json 딕셔너리를 RuntimeConfig로 매핑 (기존 설정 ↔ 신규 런타임 다리)
from __future__ import annotations

from core.runtime import RuntimeConfig
from core.navigation.block import Block
from core.navigation.floor_judge import Floor
from core.acting.combat import PotionRule
from core.acting.buff import Buff


def _potion_rule(cfg: dict) -> PotionRule:
    """recovery.hp_potion/mp_potion 딕셔너리 → PotionRule. threshold %→비율."""
    return PotionRule(
        enabled=bool(cfg.get("enabled", False)),
        key=cfg.get("key", ""),
        threshold=float(cfg.get("threshold", 70)) / 100.0,
        cooldown=float(cfg.get("cooldown_sec", 3.0)),
    )


def _buffs(attack: dict) -> list[Buff]:
    """attack.normal_buffs/toggle_buffs → Buff 리스트 (활성+키 있는 것만)."""
    out: list[Buff] = []
    for group in ("normal_buffs", "toggle_buffs"):
        for b in attack.get(group, []) or []:
            key = (b.get("key") or "").strip()
            if not b.get("enabled") or not key:
                continue
            out.append(Buff(key=key, interval=float(b.get("interval_sec", 60))))
    return out


def _floors(zones: list) -> list[Floor]:
    """zones → Floor 리스트 (Y 범위만)."""
    return [
        Floor(name=z.get("name", "구역"),
              y_min=int(z.get("y_min", 0)), y_max=int(z.get("y_max", 0)))
        for z in (zones or [])
    ]


def to_runtime_config(d: dict) -> RuntimeConfig:
    """config.json 전체 딕셔너리 → RuntimeConfig."""
    mm = d.get("minimap", {})
    minimap_region = {
        "left": int(mm.get("region_x", 0)),
        "top": int(mm.get("region_y", 0)),
        "width": int(mm.get("width", 200)),
        "height": int(mm.get("height", 120)),
    }

    recovery = d.get("recovery", {})
    hp_rule = _potion_rule(recovery.get("hp_potion", {}))
    mp_rule = _potion_rule(recovery.get("mp_potion", {}))

    attack = d.get("attack", {})
    attack_key = attack.get("key", "") or d.get("minimap", {}).get("attack_key", "")

    # 사냥 영역 (B training) — w>0이면 region dict, 아니면 None(전체화면)
    ha = attack.get("hunt_area", {})
    hunt_area_region = None
    if int(ha.get("w", 0)) > 0:
        hunt_area_region = {
            "left": int(ha.get("x", 0)), "top": int(ha.get("y", 0)),
            "width": int(ha.get("w", 0)), "height": int(ha.get("h", 0)),
        }

    # 몬스터 템플릿 수집 (단일 monster_template + monster_folder 내 png들 = B 다중방식)
    import os, glob as _glob
    monster_tpls = []
    mt = attack.get("monster_template", "")
    if mt and os.path.exists(mt):
        monster_tpls.append(mt)
    mf = attack.get("monster_folder", "")
    if mf and os.path.isdir(mf):
        monster_tpls += sorted(_glob.glob(os.path.join(mf, "*.png")))

    # 순찰: 첫 zone의 좌우 경계 + 랜덤 마진
    zones = d.get("zones", [])
    z0 = zones[0] if zones else {}
    patrol_left = int(z0.get("left_x", 0))
    patrol_right = int(z0.get("right_x", 0))
    patrol_margin = int(z0.get("random_margin_max", 0))

    # 펫 먹이 / 텔레그램 / 유저감지
    pet = recovery.get("pet_food", {})
    pet_key = pet.get("key", "") if pet.get("enabled") else ""
    pet_interval = float(pet.get("interval_min", 10)) * 60

    lie = d.get("settings1", {}).get("lie_detector", {})
    user = d.get("settings1", {}).get("user_detected", {})

    return RuntimeConfig(
        minimap_region=minimap_region,
        coord_mode=str(d.get("coord_mode", "relative")),
        game_window_title=str(d.get("settings2", {}).get("game_window_title", "")),
        floors=_floors(zones),
        route=[Block.from_dict(b) for b in (d.get("floor_hunt", {}).get("route") or [])
               if isinstance(b, dict) and "type" in b],
        route_mode=bool(d.get("floor_hunt", {}).get("route_mode", False)),
        attack_key=attack_key,
        hp_rule=hp_rule,
        mp_rule=mp_rule,
        buffs=_buffs(attack),
        minigame_type="planet",
        patrol_left_x=patrol_left,
        patrol_right_x=patrol_right,
        patrol_margin=patrol_margin,
        pet_key=pet_key,
        pet_interval=pet_interval,
        pickup_key=(d.get("pickup_timer", {}).get("pickup_key", "")
                    if d.get("pickup_timer", {}).get("enabled") else ""),
        pickup_interval=float(d.get("pickup_timer", {}).get("interval_sec", 60)),
        lie_enabled=bool(lie.get("enabled", True)),
        lie_alert=bool(lie.get("alert_enabled",
                               lie.get("play_alarm", False) or lie.get("tg_enabled", False))),
        board_roi=lie.get("board_roi"),
        transparent_enabled=bool(
            d.get("settings1", {}).get("transparent_shape", {}).get("enabled", True)),
        tg_enabled=bool(lie.get("tg_enabled", False)),
        tg_token=lie.get("tg_token", ""),
        tg_chat_id=lie.get("tg_chat_id", ""),
        user_detect_enabled=bool(user.get("enabled", False)),
        auto_reply_messages=list(user.get("messages", [])),
        hunt_area_region=hunt_area_region,
        hunt_mode=d.get("hunt_mode", "key"),
        name_template=attack.get("name_template", ""),
        monster_templates=monster_tpls,
        monster_accuracy=float(attack.get("monster_accuracy", 0.9)),
        atk_x_min=int(attack.get("atk_x_min", -35)),
        atk_x_max=int(attack.get("atk_x_max", 35)),
        atk_y_min=int(attack.get("atk_y_min", -70)),
        atk_y_max=int(attack.get("atk_y_max", 70)),
        name_threshold=float(attack.get("name_tag_threshold", 0.7)),
    )
