# AntiMobScanner — 매크로 방지몹 감지 (B 방식: 유형별 다중 템플릿 + config on/off)
from __future__ import annotations

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner


def match_any_template(
    scene: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
) -> tuple[float, str | None]:
    """여러 템플릿 중 scene에서 가장 잘 매칭되는 것을 찾는다.

    B macro_mob 방식: 한 유형(rich)에 rich1~13 처럼 여러 템플릿이 있고,
    그 중 하나라도 임계 이상이면 감지. (name, score) 반환.
    """
    best_score = 0.0
    best_name = None
    for name, tpl in templates.items():
        if tpl is None or tpl.size == 0:
            continue
        if tpl.shape[0] > scene.shape[0] or tpl.shape[1] > scene.shape[1]:
            continue
        res = cv2.matchTemplate(scene, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, _ = cv2.minMaxLoc(res)
        if mx > best_score:
            best_score = mx
            best_name = name
    if best_score >= threshold:
        return best_score, best_name
    return best_score, None


class AntiMobScanner(Scanner):
    """매크로 방지몹(루루모/리치/일반몹)을 유형별 다중 템플릿으로 감지.

    templates: {"lulu": {"lulu1": img, ...}, "rich": {...}, "monster": {...}}
    enabled_types: {"lulu": bool, "rich": bool, ...}  (config 유형별 on/off)
    감지 시 anti_mob 이벤트 발행(data: mob_type, template, score).
    """
    interval = 0.3

    def __init__(self, screen_capture, templates: dict[str, dict[str, np.ndarray]],
                 enabled_types: dict[str, bool], threshold: float = 0.85,
                 region: dict | None = None):
        super().__init__()
        self._capture = screen_capture
        self._templates = templates
        self._enabled = enabled_types
        self._threshold = threshold
        self._region = region

    def scan_once(self) -> Event | None:
        region = self._region() if callable(self._region) else self._region
        scene = self._capture(region) if region else self._capture()
        if scene is None:
            return None
        for mob_type, tpl_set in self._templates.items():
            if not self._enabled.get(mob_type, False):
                continue   # 비활성 유형은 건너뜀
            if not tpl_set:
                continue
            score, name = match_any_template(scene, tpl_set, self._threshold)
            if name is not None:
                return Event(type="anti_mob", data={
                    "mob_type": mob_type, "template": name, "score": float(score),
                })
        return None
