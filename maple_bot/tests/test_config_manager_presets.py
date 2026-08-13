# 배포 필수 사냥터와 사용자 생성 프리셋이 함께 보존되는지 검증한다.
from copy import deepcopy
import json

from core import config_manager
from core.config_manager import REQUIRED_HUNT_GROUND_PRESETS, _ensure_required_presets


def test_required_presets_keep_user_map_and_active_selection():
    user_preset = {
        "mapping_completed": True,
        "floor_hunt": {
            "route_mode": True,
            "route_steps": [{"id": "move_1", "step_type": "move"}],
        },
    }
    data = {
        "hunt_grounds": {
            "active": "사용자맵",
            "presets": {"사용자맵": deepcopy(user_preset)},
        }
    }

    changed = _ensure_required_presets(data)

    assert changed is True
    assert data["hunt_grounds"]["presets"]["사용자맵"] == user_preset
    assert data["hunt_grounds"]["active"] == "사용자맵"
    assert set(REQUIRED_HUNT_GROUND_PRESETS).issubset(
        data["hunt_grounds"]["presets"]
    )


def test_rednose_alias_merges_without_overwriting_canonical_profile():
    canonical = {"mapping_completed": True, "floor_hunt": {"route_steps": []}}
    data = {
        "hunt_grounds": {
            "active": "rednose2",
            "presets": {
                "rednose2": {"mapping_completed": False},
                "빨코2": deepcopy(canonical),
            },
        }
    }

    _ensure_required_presets(data)

    assert "rednose2" not in data["hunt_grounds"]["presets"]
    assert data["hunt_grounds"]["presets"]["빨코2"]["floor_hunt"] == {
        "route_steps": []
    }
    assert data["hunt_grounds"]["active"] == "빨코2"


def test_config_manager_reload_preserves_saved_user_map(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "hunt_grounds": {
                    "active": "새 사냥터",
                    "presets": {
                        "새 사냥터": {
                            "mapping_completed": True,
                            "floor_hunt": {
                                "route_mode": True,
                                "route_steps": [
                                    {"id": "move_1", "step_type": "move"}
                                ],
                            },
                        }
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(path))
    monkeypatch.setattr(config_manager, "_get_bundled_config_path", lambda: "")

    loaded = config_manager.ConfigManager()

    assert loaded.get("hunt_grounds", "active") == "새 사냥터"
    assert loaded.get("hunt_grounds", "presets", "새 사냥터", "floor_hunt") == {
        "route_mode": True,
        "route_steps": [{"id": "move_1", "step_type": "move"}],
    }
