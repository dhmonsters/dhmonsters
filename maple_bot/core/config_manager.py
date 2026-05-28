# 봇 설정을 JSON 파일로 저장/로드하는 ConfigManager
import json
import os
import sys


def _get_config_path() -> str:
    """설치(frozen) 환경은 AppData에 저장 — Program Files는 쓰기 불가."""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_dir = os.path.join(appdata, "MapleBot")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "config.json")
    return "config.json"


CONFIG_PATH = _get_config_path()


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
            # ── 고정 기본값: 거짓말탐지기 감지 영역 (절대좌표 — 항상 동일) ──
            "region": [1126, 297, 296, 130],
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
    "attack": {
        "key":               "ctrl",
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
    },
    "hunt_mode": "key",   # "key" | "image" | "coordinate"
    "hunt_grounds": {
        "active": "",       # 현재 활성 프리셋 이름
        "presets": {},      # name → {minimap, zones, ropes, attack_key, monster_template}
    },
    "minimap": {
        "region_x": 0, "region_y": 0, "width": 200, "height": 120,
        "char_r": 255, "char_g": 255, "char_b": 255, "tolerance": 30,
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
            "cooldown_sec": 3.0,
        },
        "mp_potion": {
            "enabled": False,
            "threshold": 50,
            "key": "0",
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


class ConfigManager:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        # 구버전 마이그레이션: exe 폴더 config.json → AppData (권한 문제 해결)
        if getattr(sys, "frozen", False) and not os.path.exists(CONFIG_PATH):
            old = "config.json"   # main.py의 os.chdir로 exe 폴더 = cwd
            if os.path.exists(old):
                try:
                    import shutil
                    shutil.copy2(old, CONFIG_PATH)
                except Exception:
                    pass

        import copy
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 저장된 값을 기본값 위에 덮어씌움 — 새 기본값 키는 자동으로 추가됨
            _deep_merge(self._data, saved)

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
