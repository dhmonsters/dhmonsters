# 봇 설정을 JSON 파일로 저장/로드하는 ConfigManager
import json
import os
import sys
import time
import copy


def _get_config_path() -> str:
    """설치(frozen) 환경은 AppData에 저장 — Program Files는 쓰기 불가."""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_dir = os.path.join(appdata, "MapleBot")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "config.json")
    return "config.json"


CONFIG_PATH = _get_config_path()

REQUIRED_HUNT_GROUND_PRESETS = {
    "초급 수련장": {
        "name": "초급 수련장",
        "mapping_completed": True,
    },
    "빨코2": {
        "name": "빨코2",
        "mapping_completed": True,
        "note": "빨코2 v5/new 전용 하드코딩 사냥터. 전용 동작값으로 실행합니다.",
    },
    "빨코3": {
        "name": "빨코3",
        "mapping_completed": True,
        "note": "텔레포트 전용 하드코딩 사냥터. 좌표 블록 없이 전용 루틴으로 실행합니다.",
    },
}

HUNT_GROUND_ALIASES = {
    "鍮⑥퐫2": "빨코2",
    "rednose2": "빨코2",
    "rednose2v5": "빨코2",
    "鍮⑥퐫3": "빨코3",
    "rednose3": "빨코3",
}


def get_user_templates_dir() -> str:
    """사용자가 생성하는 템플릿 파일 저장 디렉토리.

    설치(frozen) 환경은 AppData\\MapleBot\\templates — Program Files는 쓰기 불가.
    개발 환경은 상대경로 templates/ 그대로 사용.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        d = os.path.join(appdata, "MapleBot", "templates")
        os.makedirs(d, exist_ok=True)
        return d
    d = "templates"
    os.makedirs(d, exist_ok=True)
    return d

DEFAULT_CONFIG = {
    "settings1": {
        "lie_detector": {
            "enabled": False,
            "play_alarm": False,
            "close_maple": False,
            "shutdown_pc": False,
            "reconnect_after": False,
            # ── 고정 기본값: 거짓말탐지기 감지 영역 (게임창 기준 상대좌표) ──
            "region": {
                "x_ratio": 0.724219,
                "y_ratio": 0.491959,
                "w_ratio": 0.250781,
                "h_ratio": 0.453947,
                "source": "00409.png game-client relative lie detector panel",
            },
            "template_path": "templates\\lie_detector\\title.png",
            "threshold": 0.65,
            "check_interval_sec": 0.2,
            "cooldown_sec": 10.0,
            "alert_enabled": False,
            "tg_enabled": False,
            "tg_token": "",
            "tg_chat_id": "",
        },
        "transparent_shape": {
            "enabled": False,
            "debug_overlay": False,
            # ── 고정 기본값: 투명 도형 게임판 영역 (비율 좌표, 2560×1369 기준 중앙 추정값) ──
            "board_roi": {"x_ratio": 0.286, "y_ratio": 0.183, "w_ratio": 0.428, "h_ratio": 0.575},
        },
        "user_detected": {
            "enabled": False,
            "interval_minutes": 5,
            "messages": ["자리입니다.^^", "비켜주시겠어요?", "다른곳에서 사냥해주세요~"],
        },
        "level_stop": {
            "enabled": False,
            "target_level": 50,
        },
        "stat_assign": {
            "enabled": False,
            "STR": 0,
            "INT": 0,
            "DEX": 0,
            "LUK": 0,
        },
    },
    "hotkeys": {
        "start": "f1",
        "stop":  "f2",
    },
    "world_map": {
        "enabled": False,
        "image_path": "",
        "image_width": 0,
        "image_height": 0,
        "calibration": None,
        "tracking_policy": "continue_estimated",
        "migration_completed": False,
        "legacy_backup_path": "",
    },
    "navigation": {"nodes": [], "edges": [], "routes": []},
    "attack": {
        "key":               "ctrl",
        "sequences":         [],
        "monster_template":  "",
        "monster_folder":    "",     # 몬스터 이미지 폴더 경로 (비우면 monsters/ 루트 사용)
        "jump_before_attack": False,
        "riding_on_rope":     False,
        "range_px":           150,    # 오버레이 공격 범위 박스 좌/우 픽셀
        # ── ScreenPositionResolver 파라미터 ─────────────────────────
        "camera_w_ratio":     0.5,    # 미니맵 폭 대비 카메라 가시 폭 비율 (0.0~1.0)
        "char_y_ratio":       0.6,    # 화면 높이 대비 캐릭터 Y 비율 (0.0~1.0)
        "char_offset_x":      0,      # 변환 결과 X 미세 보정 픽셀
        "char_offset_y":      0,      # 변환 결과 Y 미세 보정 픽셀
        "floor_profiles":     [],     # [{minimap_y, screen_y, name}, ...] 층별 Y 보정
        "box_h":              120,    # 공격 박스 높이 (픽셀)
        "monster_range_h":       120,   # 몬스터 인식 범위 박스 높이 (픽셀)
        "monster_range_px":      600,   # 몬스터 인식 범위 박스 좌/우 픽셀 (0=화면 전체)
        "monster_range_y_offset": 0,   # 몬스터 인식 범위 Y 오프셋 (양수=위로, 공격박스와 독립)
        "local_window_size":   80,    # 디버그 미니맵 패널 크롭 범위 (미니맵 픽셀, 작을수록 더 확대)
        "deadzone_ratio":      0.0,   # DeadZone 비율 (0=항상 중앙, 0.3=중앙 30% 고정 영역)
        "name_tag_threshold":  0.70,  # 이름표 템플릿 매칭 신뢰도 임계값 (0.3~1.0)
        "name_tag_y_offset":   0,     # 이름표 중앙에서 위로 이동할 픽셀 (양수=위쪽)
        # 공격 타이밍 (홀드 = 목표 방수 × 스킬1회 시간, 각 값에 −5%~0 랜덤)
        "hits_to_kill":        1,     # 몹 처치에 필요한 타격 수(몇 방)
        "skill_cast_sec":      0.6,   # 스킬 1회 시전 시간(초) — 1방 나가는 시간
        "delay_sec":           0.4,   # 공격키 재누름 최소 간격(초) — 스킬 딜레이/도배 방지
        # 밀집 사냥(시간당 처치 최적화): 사냥영역 몹 개수로 멈춰사냥↔이동
        "density_stay":        3,     # 이 마리수 이상이면 멈춰 사냥(밀집)
        "density_leave":       1,     # 이 마리수 이하로 줄면 이동(희소)
        "density_max_dwell_sec": 8.0, # 한 자리 최대 체류(밀집이어도 초과 시 강제 이동)
        "hunt_area": {"x": 0, "y": 0, "w": 0, "h": 0},
        "image_trigger": {
            "enabled": False,
            "template_path": "",
            "threshold": 0.8,
            "check_interval_sec": 0.1,
            "cooldown_sec": 2.0,
            "action": {
                "key": "space",
                "hold_sec": 0.1,
                "repeat": 1,
                "repeat_interval_sec": 0.0,
                "wait_after_sec": 0.0,
            },
        },
    },
    "hunt_mode": "key",   # "key" | "image"
    "hunt_grounds": {
        "active": "",       # 현재 활성 프리셋 이름
        "presets": {},      # name → {minimap, zones, ropes, attack_key, monster_template}
    },
    "minimap": {
        "region_x": 0, "region_y": 0, "width": 200, "height": 120,
        "char_r": 255, "char_g": 255, "char_b": 255, "tolerance": 30,
        "char_h_tol": 10, "char_s_min": 100, "char_v_min": 200,
        "char_area_min": 3, "char_area_max": 100,
        "attack_key": "ctrl", "monster_template": "",
    },
    "zones": [],   # Zone.to_dict() 목록
    "patterns": {
        "active": None,     # HuntPattern.to_dict() 결과 (이미지 인식 모드)
    },
    "key_patterns": {
        "active": None,     # KeyPattern.to_dict() 결과 (키 반복 모드)
        "presets": {},      # name → KeyPattern.to_dict() (층별 패턴 선택용)
    },
    "coordinate": {
        # ── 고정 기본값: HP/MP 상대좌표 비율 (항상 동일) ──
        "hp": {"x": 0, "y": 0, "width": 0,
               "x_ratio": 0.216015625, "y_ratio": 1.127100073046019, "width_ratio": 0.105078125},
        "mp": {"x": 0, "y": 0, "width": 0,
               "x_ratio": 0.3234375,   "y_ratio": 1.127100073046019, "width_ratio": 0.105078125},
    },
    "recovery": {
        "hp_potion": {
            "enabled": False,
            "threshold": 70,
            "key": "9",
            "secondary_key": "",
            "cooldown_sec": 3.0,
        },
        "mp_potion": {
            "enabled": False,
            "threshold": 50,
            "key": "0",
            "secondary_key": "",
            "cooldown_sec": 3.0,
        },
        "potion_count": {
            "hp_region": None,      # [x, y, w, h] — HP 포션 슬롯 영역
            "mp_region": None,      # [x, y, w, h] — MP 포션 슬롯 영역
            "zero_return": False,   # 수량 0 시 마을 귀환 활성화
        },
    },
    "map_exit": {
        "enabled": False,
        "action": "stop",       # "stop" | "telegram" | "both"
        "name_region": None,    # [x, y, w, h] — 미니맵 맵 이름 텍스트 영역
        "threshold": 0.75,      # 이미지 유사도 임계값 (미만이면 다른 맵으로 판정)
        "grace_count": 3,       # 연속 N회 불일치 시 이탈 판정
    },
    "anti_mob": {
        "enabled":        False,
        "type":           "click",      # "click" | "item" | "basic"
        "detect_region":  None,         # [x, y, w, h]
        "target_x":       100,          # 미니맵 X 이동 목표
        "click_keys":     "space,enter",# 쉼표 구분 키 시퀀스
        "item_inv_tab":   None,         # [x, y, w, h] — 인벤토리 기타탭
        "item_slot":      None,         # [x, y, w, h] — 버릴 아이템 슬롯
        "basic_count":    5,            # 기본공격형 공격 횟수
    },
    "town_scroll": {
        "enabled":          False,
        "key":              "9",        # 긴급 마을 귀환 키
        "hp_trigger":       False,      # HP % 미만 발동 여부
        "hp_trigger_pct":   10,         # HP 발동 퍼센트
        "mp_trigger":       False,      # MP % 미만 발동 여부
        "mp_trigger_pct":   10,         # MP 발동 퍼센트
    },
    "hunting_return": {
        "enabled":  False,
    },
    "pickup_timer": {
        "enabled":      False,
        "interval_sec": 110,    # 수집 주기 (초) — 아이템 소멸 2분보다 10초 여유
        "pickup_key":   "z",    # 아이템 줍기 키
        "key_hold_sec": 1.5,    # 각 구역에서 픽업 키 유지 시간
        "route":        [],     # [{to_zone: str, rope: str}, ...]
    },
    "coord_mode": "relative",   # "absolute" | "relative" (게임 창 클라이언트 기준 상대 좌표)
    "settings2": {
        "shutdown": {
            "on_death": False,
            "scheduled": False,
            "hours": 0,
            "minutes": 0,
        },
        "pause": {
            "mode": "reconnect",
            "pause_time": "",
            "resume_time": "",
        },
        "macro_schedule": {
            "start_time": "",
        },
        "connection": {
            "server": "스카니아",
            "channel": 1,
            "char_slot": 1,
            "account_index": 1,
            "email": "",
            "password1": "",
            "password2": "",
        },
        # ── 고정 기본값: 잡템 자동 판매 좌표 (항상 동일) ──
        "junk_sell": {
            "inventory_key":          "i",
            "cash_tab":               [2084, 627],
            "cash_tab_active_anchor": [1211, 587],
            "cash_tab_offset":        [173, 27],
            "first_slot":             [1753, 710],
            "first_slot_offset":      [-334, 86],
            "inventory_anchor":       [1039, 559],
            "equip_sell_btn":         [1749, 555],
            "equip_sell_confirm":     [1439, 1141],
            "shop_etc_tab":           [1682, 548],
            "shop_exit_btn":          [1156, 333],
            "shop_area":              [1288, 590, 516, 514],
            "scroll_pos":             [1822, 845],
            # 아래는 사용자별 설정 (기본값만)
            "junk_sell_enabled":      False,
            "auto_sell_enabled":      False,
            "auto_sell_interval_min": 10,
            "sell_on_start":          False,
            "safe_zone_x":            -1,
            "safe_zone_y":            -1,
            "departure_zone":         "",
            "extra_rope":             {},
        },
    },
    # ── YOLO11 몬스터 감지 ─────────────────────────────────────────────
    "yolo": {
        "enabled":        False,          # True = YOLO 파이프라인 활성화
        "model_path":     "",             # .pt 파일 경로 (비면 폴백)
        "confidence":     0.5,            # 감지 신뢰도 임계값
        "iou":            0.45,           # NMS IoU 임계값
        "max_det":        20,             # 최대 감지 수
        "every_n_frame":  2,              # N 프레임마다 1회 추론 (1=매 프레임)
        # 몬스터 인지 ROI — 프레임 크기 대비 비율 [left, top, right, bottom]
        "roi_ratio":      [0.1, 0.1, 0.9, 0.9],
        # 공격 범위 박스 (캐릭터 중심 기준 픽셀)
        "attack_range": {
            "left":     300,
            "right":    300,
            "vertical": 180,
            "y_offset": -40,
        },
        "dev_mode":       False,          # True = 드래그/편집 UI 표시 (배포 시 False)
    },
}


def _deep_merge(base: dict, override: dict) -> None:
    """override의 값을 base에 재귀적으로 덮어씌운다.
    base에만 있는 키(새 기본값)는 그대로 유지된다."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _get_bundled_config_path() -> str:
    """EXE 또는 개발 폴더에 포함된 기본 config.json 경로를 찾는다."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "config.json"))
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, "config.json"))
    else:
        candidates.append("config.json")
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


def _load_json_safe(path: str) -> dict:
    """설정 파일을 읽되 실패하면 빈 dict를 돌려준다."""
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _ensure_required_presets(data: dict) -> bool:
    """배포 필수 사냥터 프리셋만 유지하고 깨진 이름을 정상 이름으로 보정한다."""
    bundled = _load_json_safe(_get_bundled_config_path())
    bundled_presets = ((bundled.get("hunt_grounds") or {}).get("presets") or {})
    if not isinstance(bundled_presets, dict):
        return False

    changed = False
    hunt_grounds = data.setdefault("hunt_grounds", {})
    presets = hunt_grounds.setdefault("presets", {})
    if not isinstance(presets, dict):
        presets = {}
        hunt_grounds["presets"] = presets
        changed = True

    for bad_name, good_name in HUNT_GROUND_ALIASES.items():
        if bad_name in presets:
            if good_name not in presets:
                presets[good_name] = presets[bad_name]
            presets.pop(bad_name, None)
            changed = True

    allowed_names = set(REQUIRED_HUNT_GROUND_PRESETS)
    for name in list(presets.keys()):
        if name not in allowed_names:
            presets.pop(name, None)
            changed = True

    if "rednose2_v5" in bundled and "rednose2_v5" not in data:
        data["rednose2_v5"] = copy.deepcopy(bundled["rednose2_v5"])
        changed = True

    for name, preset in REQUIRED_HUNT_GROUND_PRESETS.items():
        if name not in presets:
            presets[name] = copy.deepcopy(preset)
            changed = True
        elif isinstance(presets[name], dict):
            for key, value in preset.items():
                if presets[name].get(key) != value:
                    presets[name][key] = copy.deepcopy(value)
                    changed = True

    active = str(hunt_grounds.get("active") or "").strip()
    normalized_active = HUNT_GROUND_ALIASES.get(active, active)
    if normalized_active not in allowed_names:
        normalized_active = "빨코2"
    if hunt_grounds.get("active") != normalized_active:
        hunt_grounds["active"] = normalized_active
        changed = True

    attack = data.setdefault("attack", {})
    bundled_attack = bundled.get("attack") or {}
    if not attack.get("normal_buffs") and bundled_attack.get("normal_buffs"):
        attack["normal_buffs"] = copy.deepcopy(bundled_attack["normal_buffs"])
        changed = True
    if "toggle_buffs" not in attack and "toggle_buffs" in bundled_attack:
        attack["toggle_buffs"] = copy.deepcopy(bundled_attack.get("toggle_buffs") or [])
        changed = True

    lie_detector = data.setdefault("settings1", {}).setdefault("lie_detector", {})
    lie_template = str(lie_detector.get("template_path") or "")
    lie_template_name = lie_template.replace("\\", "/").rsplit("/", 1)[-1]
    if not lie_template or lie_template_name == "transparent_shape_title.png":
        lie_detector["template_path"] = "templates\\lie_detector\\title.png"
        changed = True
    fixed_lie_region = copy.deepcopy(DEFAULT_CONFIG["settings1"]["lie_detector"]["region"])
    if lie_detector.get("region") != fixed_lie_region:
        lie_detector["region"] = fixed_lie_region
        changed = True

    return changed


class ConfigManager:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        # 구버전 마이그레이션: exe 폴더 config.json -> AppData (권한 문제 해결)
        if getattr(sys, "frozen", False) and not os.path.exists(CONFIG_PATH):
            old = "config.json"
            if os.path.exists(old):
                try:
                    import shutil
                    shutil.copy2(old, CONFIG_PATH)
                except Exception:
                    pass

        self._data = copy.deepcopy(DEFAULT_CONFIG)
        changed = False
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                    saved = json.load(f)
            except Exception:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                broken_path = f"{CONFIG_PATH}.broken_{timestamp}"
                try:
                    import shutil
                    shutil.copy2(CONFIG_PATH, broken_path)
                except Exception:
                    pass
                saved = {}
                changed = True
            world = saved.get("world_map", {})
            calibration_data = world.get("calibration")
            if calibration_data and not world.get("migration_completed"):
                from datetime import datetime
                from core.navigation.world_map import Calibration, WorldPoint
                from core.navigation.world_migration import backup_config, migrate_legacy_data

                offset = calibration_data.get("offset", [0.0, 0.0])
                calibration = Calibration(
                    float(calibration_data["scale"]),
                    float(offset[0]),
                    float(offset[1]),
                )
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_config(CONFIG_PATH, timestamp)
                saved = migrate_legacy_data(
                    saved,
                    calibration,
                    WorldPoint(calibration.offset_x, calibration.offset_y),
                )
                saved["world_map"]["legacy_backup_path"] = str(backup_path)
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(saved, f, ensure_ascii=False, indent=2)
            # 저장된 값을 기본값 위에 덮어쓰며, 새 기본값은 자동으로 유지한다.
            _deep_merge(self._data, saved)
            changed = _ensure_required_presets(self._data)
        else:
            changed = _ensure_required_presets(self._data)
        if changed:
            self.save()
    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, *keys, default=None):
        node = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set(self, *args):
        *keys, value = args
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value


def get_game_window_origin(config: "ConfigManager") -> tuple[int, int]:
    """coord_mode == 'relative'일 때 게임 창 클라이언트 좌상단 절대 좌표를 반환.

    absolute 모드이거나 창을 찾지 못하면 (0, 0) 반환.
    """
    ox, oy, _, _ = get_game_window_rect(config)
    return (ox, oy)


def resolve_minimap_coords(config: "ConfigManager", mm: dict) -> tuple[int, int, int, int]:
    """미니맵 화면 좌표 (region_x, region_y, width, height) 를 절대 픽셀로 반환.

    비율 키가 있고 게임 창을 찾은 경우 → 비율 × 창 크기로 계산 (창 이동/리사이즈 모두 대응).
    그 외 → 저장된 픽셀값 + 창 origin (기존 absolute 방식).
    """
    ox, oy, cw, ch = get_game_window_rect(config)

    if cw > 0 and ch > 0 and mm.get("region_x_ratio") is not None:
        region_x = ox + int(mm["region_x_ratio"] * cw)
        region_y = oy + int(mm["region_y_ratio"] * ch)
        width    = max(1, int(mm.get("width_ratio",  0.1)  * cw))
        height   = max(1, int(mm.get("height_ratio", 0.07) * ch))
    else:
        region_x = ox + int(mm.get("region_x", 0))
        region_y = oy + int(mm.get("region_y", 0))
        width    = max(1, int(mm.get("width",  200)))
        height   = max(1, int(mm.get("height", 120)))

    return (region_x, region_y, width, height)


def resolve_region_coords(config: "ConfigManager", region_cfg) -> tuple[int, int, int, int] | None:
    """감지 영역 설정(dict 비율 or list 픽셀)을 절대 화면 좌표 (x, y, w, h)로 변환.

    지원 포맷.
    - {x_ratio, y_ratio, w_ratio, h_ratio} — 게임 창 크기 대비 비율
    - {client_x, client_y, w, h}           — 게임 창 클라이언트 기준 픽셀 (구버전)
    - [x, y, w, h]                          — 절대 픽셀 (레거시)
    """
    if not region_cfg:
        return None
    ox, oy, cw, ch = get_game_window_rect(config)

    if isinstance(region_cfg, dict):
        if region_cfg.get("x_ratio") is not None and cw > 0:
            x = ox + int(region_cfg["x_ratio"] * cw)
            y = oy + int(region_cfg["y_ratio"] * ch)
            w = max(1, int(region_cfg["w_ratio"] * cw))
            h = max(1, int(region_cfg["h_ratio"] * ch))
        else:
            # 구버전 client_x/client_y 또는 x/y 픽셀 형식
            x = ox + int(region_cfg.get("client_x", region_cfg.get("x", 0)))
            y = oy + int(region_cfg.get("client_y", region_cfg.get("y", 0)))
            w = max(1, int(region_cfg.get("w", region_cfg.get("width", 0))))
            h = max(1, int(region_cfg.get("h", region_cfg.get("height", 0))))
    elif isinstance(region_cfg, list) and len(region_cfg) == 4:
        # 레거시 [x, y, w, h] — 절대 픽셀
        x, y, w, h = int(region_cfg[0]), int(region_cfg[1]), int(region_cfg[2]), int(region_cfg[3])
    else:
        return None

    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def _query_window_origin(window_title: str) -> tuple[int, int, int, int]:
    """win32로 게임창 클라이언트 (ox, oy, cw, ch). 못 찾거나 win32 미가용이면 (0,0,0,0)."""
    try:
        import win32gui
        hwnd = win32gui.FindWindow(None, window_title or "MapleStory")
        if hwnd:
            ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            if right - left > 0 and bottom - top > 0:
                return (ox, oy, right - left, bottom - top)
    except Exception:
        pass
    return (0, 0, 0, 0)


_origin_cache = {"title": None, "ts": 0.0, "rect": (0, 0, 0, 0)}


def cached_window_origin(window_title: str, ttl: float = 0.2,
                         _now=time.monotonic) -> tuple[int, int, int, int]:
    """게임창 클라이언트 (ox,oy,cw,ch) — win32 조회를 ttl초 캐시(매 캡처 폭주 방지)."""
    c = _origin_cache
    now = _now()
    if c["title"] == window_title and (now - c["ts"]) < ttl:
        return c["rect"]
    rect = _query_window_origin(window_title)
    c.update(title=window_title, ts=now, rect=rect)
    return rect


def resolve_window_region(coord_mode: str, window_title: str,
                          left: int, top: int, w: int, h: int,
                          anchor: tuple[int, int] | None = None) -> tuple[int, int, int, int]:
    """저장된 절대 영역(left,top)+w,h를 창 이동량만큼 보정해 (x,y,w,h) 반환.

    앵커=영역 지정 시점의 창 클라이언트 원점. 현재 원점이 앵커와 같거나(창 안 움직임)
    창을 못 찾거나 앵커가 없으면 절대좌표 그대로(=안 밀림). 창을 옮겼을 때만 그 delta만큼 따라감.
    coord_mode != 'relative'이면 항상 절대 그대로."""
    if (coord_mode or "absolute") != "relative":
        return (left, top, w, h)
    if not anchor:
        return (left, top, w, h)
    ox, oy, cw, ch = cached_window_origin(window_title)
    if cw <= 0:
        return (left, top, w, h)
    return (left + (ox - anchor[0]), top + (oy - anchor[1]), w, h)


def logical_to_physical_coords(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    """논리 픽셀(Qt/win32 좌표계) → mss 물리 픽셀 변환.

    DPI 배율이 100%가 아닌 시스템에서 mss.grab()에 논리 좌표를 그대로 전달하면
    잘못된 영역을 캡처한다. 이 함수로 변환 후 전달해야 한다.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QRect
        import mss as _mss
        app = QApplication.instance()
        if app is None:
            return x, y, w, h
        total = QRect()
        for s in app.screens():
            total = total.united(s.geometry())
        with _mss.mss() as sct:
            mon = sct.monitors[0]
            phys_w, phys_h = mon["width"], mon["height"]
        sx = phys_w / max(1, total.width())
        sy = phys_h / max(1, total.height())
        abs_x = x + total.x()
        abs_y = y + total.y()
        return int(abs_x * sx), int(abs_y * sy), int(w * sx), int(h * sy)
    except Exception:
        return x, y, w, h


def get_game_window_rect(config: "ConfigManager") -> tuple[int, int, int, int]:
    """게임 창 클라이언트 영역의 (left, top, width, height) 를 반환.

    coord_mode == 'relative'이고 창을 찾은 경우에만 실제 값을 반환한다.
    그 외에는 (0, 0, 0, 0) 반환 — 호출부에서 width/height == 0 이면
    절대 좌표 모드로 처리한다.
    """
    if (config.get("coord_mode") or "absolute") != "relative":
        return (0, 0, 0, 0)
    title = config.get("settings2", "game_window_title") or "MapleStory"
    try:
        import win32gui
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            cw = right - left
            ch = bottom - top
            if cw > 0 and ch > 0:
                return (ox, oy, cw, ch)
    except Exception:
        pass
    return (0, 0, 0, 0)


