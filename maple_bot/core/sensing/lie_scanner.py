# LieScanner — 거탐(투명도형 타이틀) 출현을 템플릿 매칭으로 감지 → "lie" 이벤트
# C MinigameWatcher 방식: _on_appear(출현 순간 1회 발행) / _on_disappear(사라지면 리셋)
from __future__ import annotations

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner


def _match_score(scene: np.ndarray, template: np.ndarray) -> float:
    """scene 안 template 최고 매칭 점수 (TM_CCOEFF_NORMED)."""
    if template is None or template.size == 0:
        return 0.0
    if template.shape[0] > scene.shape[0] or template.shape[1] > scene.shape[1]:
        return 0.0
    res = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    _, mx, _, _ = cv2.minMaxLoc(res)
    return float(mx)


class LieScanner(Scanner):
    """거탐 미니게임 타이틀 출현 감지.

    title_template: 타이틀 이미지(ndarray) 또는 파일경로(str).
    출현 순간에만 "lie" 이벤트 1회 발행(중복 방지). 사라지면 상태 리셋 → 재출현 시 또 발행.
    """
    interval = 0.2

    def __init__(self, screen_capture, title_template, threshold: float = 0.65,
                 region: dict | None = None):
        super().__init__()
        self._capture = screen_capture
        self._threshold = threshold
        self._region = region
        self._present = False   # 현재 떠있는지 (appear/disappear 추적)
        # 템플릿: 경로면 로드, ndarray면 그대로
        if isinstance(title_template, str):
            self._tpl = cv2.imread(title_template)
        else:
            self._tpl = title_template

    def scan_once(self) -> Event | None:
        scene = self._capture(self._region) if self._region else self._capture()
        if scene is None or self._tpl is None:
            return None
        score = _match_score(scene, self._tpl)
        detected = score >= self._threshold

        if detected and not self._present:
            # 출현 순간 (_on_appear)
            self._present = True
            return Event(type="lie", data={"score": score})
        if not detected and self._present:
            # 사라짐 (_on_disappear) — 상태 리셋, 이벤트는 없음
            self._present = False
        return None
