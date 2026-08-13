# 화면 템플릿의 점수와 위치를 한 번의 멀티스케일 탐색으로 얻는지 검증한다.
import numpy as np

from core.screen_reader import ScreenReader


def test_find_template_match_calculates_score_and_position_once(monkeypatch):
    reader = ScreenReader()
    calls = []
    screenshot = np.zeros((20, 20, 3), dtype=np.uint8)
    template = np.zeros((5, 5, 3), dtype=np.uint8)
    monkeypatch.setattr("core.screen_reader.cv2.imread", lambda _path: template)
    monkeypatch.setattr(
        reader,
        "_match_multiscale",
        lambda image, loaded: calls.append((image, loaded)) or (0.82, (7, 9)),
    )

    score, position = reader.find_template_match(screenshot, "template.png", threshold=0.7)

    assert score == 0.82
    assert position == (7, 9)
    assert len(calls) == 1
