# 캡처한 캐릭터 마커 템플릿이 봇 시작 설정 갱신에 반영되는지 검증합니다.
from types import SimpleNamespace

import cv2
import numpy as np

import core.sensing.char_scanner as char_scanner_module
from core.runtime import BotRuntime


def test_char_scanner_reloads_marker_templates(monkeypatch):
    loaded = [[("old.png", np.zeros((8, 8, 3), dtype=np.uint8))]]
    monkeypatch.setattr(char_scanner_module, "_load_marker_templates", lambda: loaded[-1])
    scanner = char_scanner_module.CharScanner(lambda _region: None, {"width": 10, "height": 10})
    replacement_image = np.full((8, 8, 3), 255, dtype=np.uint8)
    replacement = [("y_p.png", replacement_image)]
    loaded.append(replacement)

    scanner.reload_marker_templates()

    assert scanner._marker_templates[0][0] == "y_p.png"
    assert scanner._marker_templates[0][1] is replacement_image


def test_runtime_character_filter_reload_refreshes_marker_templates():
    calls = []

    class FakeScanner:
        def reload_marker_templates(self):
            calls.append("templates")

        def set_filters(self, lower, upper, min_area=None, max_area=None):
            calls.append((lower, upper, min_area, max_area))

    runtime = SimpleNamespace(
        _cfg=SimpleNamespace(),
        char_scanner=FakeScanner(),
    )
    config = SimpleNamespace(
        char_rgb=None,
        char_h_low=20,
        char_h_high=40,
        char_h_tol=10,
        char_s_min=100,
        char_v_min=200,
        char_area_min=3.0,
        char_area_max=100.0,
    )

    BotRuntime.reload_character_filter(runtime, config)

    assert calls[0] == "templates"
    assert calls[1] == ((20, 100, 200), (40, 255, 255), 3.0, 100.0)


def test_runtime_character_filter_builds_automatic_range_from_reference_rgb():
    calls = []

    class FakeScanner:
        def reload_marker_templates(self):
            calls.append("templates")

        def set_filters(self, lower, upper, min_area=None, max_area=None):
            calls.append((lower, upper, min_area, max_area))

    runtime = SimpleNamespace(_cfg=SimpleNamespace(), char_scanner=FakeScanner())
    config = SimpleNamespace(
        char_rgb=(220, 210, 20),
        char_h_low=None,
        char_h_high=None,
        char_h_tol=10,
        char_s_min=100,
        char_v_min=200,
        char_area_min=3.0,
        char_area_max=160.0,
    )

    BotRuntime.reload_character_filter(runtime, config)

    hsv = cv2.cvtColor(np.uint8([[[20, 210, 220]]]), cv2.COLOR_BGR2HSV)[0, 0]
    assert calls[0] == "templates"
    assert calls[1] == (
        (max(0, int(hsv[0]) - 10), max(0, int(hsv[1]) - 40), max(0, int(hsv[2]) - 40)),
        (min(179, int(hsv[0]) + 10), 255, 255),
        3.0,
        160.0,
    )


def test_marker_template_loader_prefers_user_y_p_and_ignores_legacy_r_p(tmp_path, monkeypatch):
    user_templates = tmp_path / "user_templates"
    bundled_templates = tmp_path / "bundled" / "templates"
    (user_templates / "player").mkdir(parents=True)
    (bundled_templates / "player").mkdir(parents=True)
    cv2.imwrite(str(user_templates / "player" / "y_p.png"), np.full((2, 2, 3), 77, dtype=np.uint8))
    cv2.imwrite(str(bundled_templates / "player" / "y_p.png"), np.full((2, 2, 3), 11, dtype=np.uint8))
    cv2.imwrite(str(bundled_templates / "player" / "r_p.png"), np.full((2, 2, 3), 22, dtype=np.uint8))
    monkeypatch.setattr(char_scanner_module, "get_user_templates_dir", lambda: str(user_templates), raising=False)
    monkeypatch.setattr(
        char_scanner_module,
        "_resource_path",
        lambda *parts: bundled_templates.parent.joinpath(*parts),
    )

    loaded = dict(char_scanner_module._load_marker_templates())

    assert set(loaded) == {"y_p.png"}
    assert int(loaded["y_p.png"][0, 0, 0]) == 77


def test_marker_template_loader_does_not_read_missing_files(tmp_path, monkeypatch):
    user_templates = tmp_path / "user_templates"
    bundled_templates = tmp_path / "bundled" / "templates"
    read_calls = []
    monkeypatch.setattr(char_scanner_module, "get_user_templates_dir", lambda: str(user_templates), raising=False)
    monkeypatch.setattr(
        char_scanner_module,
        "_resource_path",
        lambda *parts: bundled_templates.parent.joinpath(*parts),
    )
    monkeypatch.setattr(
        char_scanner_module.cv2,
        "imread",
        lambda path, mode: read_calls.append((path, mode)) or None,
    )

    loaded = char_scanner_module._load_marker_templates()

    assert loaded == []
    assert read_calls == []
