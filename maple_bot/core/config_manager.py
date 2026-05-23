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
        },
        "transparent_shape": {
            "enabled": False,
            "debug_overlay": False,
            "board_roi": None,   # {"client_x":..., "client_y":..., "w":..., "h":...}
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
        "hp":  {"x": 0, "y": 0, "width": 0},
        "mp":  {"x": 0, "y": 0, "width": 0},
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
    "coord_mode": "absolute",   # "absolute" | "relative" (게임 창 클라이언트 기준 상대 좌표)
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
    드래그로 영역을 선택할 때 이 값을 빼서 상대 좌표로 저장하고,
    화면 캡처 시에는 이 값을 더해 절대 좌표로 복원한다.
    """
    if (config.get("coord_mode") or "absolute") != "relative":
        return (0, 0)
    title = config.get("settings2", "game_window_title") or "MapleStory"
    try:
        import win32gui
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            return win32gui.ClientToScreen(hwnd, (0, 0))
    except Exception:
        pass
    return (0, 0)
