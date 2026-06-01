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

    return RuntimeConfig(
        minimap_region=minimap_region,
        floors=_floors(d.get("zones", [])),
        route=[Block.from_dict(b) for b in (d.get("floor_hunt", {}).get("route") or [])
               if isinstance(b, dict) and "type" in b],
        attack_key=attack_key,
        hp_rule=hp_rule,
        mp_rule=mp_rule,
        buffs=_buffs(attack),
        minigame_type="planet",
    )
