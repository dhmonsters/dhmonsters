# 배포용 설정 생성 시 개인 인증정보가 제거되는지 검증한다.
import json

from build_release_config import build_release_config


def test_release_config_removes_sensitive_values_and_preserves_settings(tmp_path):
    source = tmp_path / "config.json"
    destination = tmp_path / "release.json"
    source.write_text(
        json.dumps({
            "settings1": {
                "lie_detector": {
                    "enabled": True,
                    "tg_token": "private-token",
                    "tg_chat_id": "private-chat",
                },
            },
            "junk_sell": {
                "password1": "first",
                "password2": "second",
                "enabled": True,
            },
        }),
        encoding="utf-8",
    )

    build_release_config(source, destination)

    released = json.loads(destination.read_text(encoding="utf-8"))
    lie = released["settings1"]["lie_detector"]
    assert lie["tg_token"] == ""
    assert lie["tg_chat_id"] == ""
    assert released["junk_sell"]["password1"] == ""
    assert released["junk_sell"]["password2"] == ""
    assert lie["enabled"] is True
    assert released["junk_sell"]["enabled"] is True


def test_release_config_makes_project_paths_relative_and_drops_external_paths(tmp_path):
    source = tmp_path / "config.json"
    destination = tmp_path / "release.json"
    source.write_text(
        json.dumps({
            "world_map": {"image_path": str(tmp_path / "maps" / "world.png")},
            "yolo": {"model_path": str(tmp_path.parent / "training" / "best.pt")},
        }),
        encoding="utf-8",
    )

    build_release_config(source, destination)

    released = json.loads(destination.read_text(encoding="utf-8"))
    assert released["world_map"]["image_path"] == "maps/world.png"
    assert released["yolo"]["model_path"] == ""
