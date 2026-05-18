# 봇 설정을 JSON 파일로 저장/로드하는 ConfigManager
import json
import os

CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "settings1": {
        "lie_detector": {
            "enabled": False,
            "play_alarm": False,
            "close_maple": False,
            "shutdown_pc": False,
            "reconnect_after": False,
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
        "jump_before_attack": False,
        "riding_on_rope":     False,
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
    },
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


class ConfigManager:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            import copy
            self._data = copy.deepcopy(DEFAULT_CONFIG)

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
