# 거탐 제목 템플릿을 화면에서 주기적으로 감지하는 스캐너
from __future__ import annotations

import time
from collections.abc import Callable

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner


def _to_gray(image: np.ndarray) -> np.ndarray:
    """BGR/BGRA 이미지를 템플릿 매칭용 흑백 이미지로 변환한다."""
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _match_score(scene: np.ndarray, template: np.ndarray) -> float:
    """scene 안에서 template의 최고 매칭 점수를 반환한다."""
    if scene is None or template is None or template.size == 0:
        return 0.0
    if template.shape[0] > scene.shape[0] or template.shape[1] > scene.shape[1]:
        return 0.0
    res = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    _, mx, _, _ = cv2.minMaxLoc(res)
    return float(mx)


def _best_scaled_match_score(
    scene: np.ndarray,
    template: np.ndarray,
    scales: tuple[float, ...],
) -> tuple[float, float]:
    """여러 템플릿 크기 중 가장 높은 점수와 사용된 스케일을 반환한다."""
    best_score = 0.0
    best_scale = 1.0
    for scale in scales:
        if abs(scale - 1.0) < 0.0001:
            scaled = template
        else:
            width = max(1, int(round(template.shape[1] * scale)))
            height = max(1, int(round(template.shape[0] * scale)))
            scaled = cv2.resize(template, (width, height), interpolation=cv2.INTER_AREA)
        score = _match_score(scene, scaled)
        if score > best_score:
            best_score = score
            best_scale = scale
    return best_score, best_scale


class LieScanner(Scanner):
    """거탐 제목 이미지가 나타나는 순간 lie 이벤트를 1회 발행한다."""

    interval = 0.2
    scales = (0.90, 0.925, 0.95, 0.975, 1.0, 1.025, 1.05, 1.075, 1.10)

    def __init__(
        self,
        screen_capture,
        title_template,
        threshold: float = 0.65,
        region: dict | Callable[[], dict | None] | None = None,
        debug_log_fn=None,
        debug_interval: float = 3.0,
    ):
        super().__init__()
        self._capture = screen_capture
        self._threshold = threshold
        self._region = region
        self._debug_log_fn = debug_log_fn
        self._debug_interval = max(0.5, float(debug_interval))
        self._last_debug_at = 0.0
        self._present = False
        self._tpl = cv2.imread(title_template) if isinstance(title_template, str) else title_template
        if self._tpl is not None:
            self._tpl = _to_gray(self._tpl)

    def scan_once(self) -> Event | None:
        try:
            region = self._region() if callable(self._region) else self._region
            scene = self._capture(region) if region else self._capture()
        except Exception as exc:
            self._debug_log(f"거탐 스캔 오류: {exc}")
            return None
        if scene is None or self._tpl is None:
            self._debug_log("거탐 스캔 실패: 캡처 또는 템플릿 없음")
            return None

        scene_gray = _to_gray(scene)
        score, scale = _best_scaled_match_score(scene_gray, self._tpl, self.scales)
        detected = score >= self._threshold
        self._debug_log(
            f"거탐 감시중: score={score:.3f}, scale={scale:.3f}, threshold={self._threshold:.3f}, "
            f"region={region or '전체화면'}"
        )

        if detected and not self._present:
            self._present = True
            return Event(type="lie", data={"score": score, "scale": scale})
        if not detected and self._present:
            self._present = False
        return None

    def _debug_log(self, message: str) -> None:
        if self._debug_log_fn is None:
            return
        now = time.monotonic()
        if now - self._last_debug_at < self._debug_interval:
            return
        self._last_debug_at = now
        try:
            self._debug_log_fn(message)
        except Exception:
            pass
