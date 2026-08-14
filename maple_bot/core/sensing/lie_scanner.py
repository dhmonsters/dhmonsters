# 거탐 제목 템플릿을 화면에서 주기적으로 감지하는 스캐너.
from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner
from core.internal_trace import trace_event


def _to_gray(image: np.ndarray) -> np.ndarray:
    """BGR/BGRA 이미지를 템플릿 매칭용 흑백 이미지로 변환한다."""
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _match_score(scene: np.ndarray, template: np.ndarray) -> tuple[float, tuple[int, int]]:
    """scene 안에서 template의 최고 매칭 점수와 위치를 반환한다."""
    if scene is None or template is None or template.size == 0:
        return 0.0, (0, 0)
    if template.shape[0] > scene.shape[0] or template.shape[1] > scene.shape[1]:
        return 0.0, (0, 0)
    result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    _, max_score, _, max_loc = cv2.minMaxLoc(result)
    return float(max_score), (int(max_loc[0]), int(max_loc[1]))


def _best_scaled_match(
    scene: np.ndarray,
    templates: list[np.ndarray],
    scales: tuple[float, ...],
) -> tuple[float, float, tuple[int, int], tuple[int, int]]:
    """여러 템플릿과 스케일 중 가장 높은 매칭 결과를 반환한다."""
    best_score = 0.0
    best_scale = 1.0
    best_loc = (0, 0)
    best_size = (0, 0)
    for template in templates:
        for scale in scales:
            if abs(scale - 1.0) < 0.0001:
                scaled = template
            else:
                width = max(1, int(round(template.shape[1] * scale)))
                height = max(1, int(round(template.shape[0] * scale)))
                scaled = cv2.resize(template, (width, height), interpolation=cv2.INTER_AREA)
            score, loc = _match_score(scene, scaled)
            if score > best_score:
                best_score = score
                best_scale = scale
                best_loc = loc
                best_size = (int(scaled.shape[1]), int(scaled.shape[0]))
    return best_score, best_scale, best_loc, best_size


class LieScanner(Scanner):
    """거탐 제목 이미지가 감지되면 lie 이벤트를 한 번 발행한다."""

    interval = 0.2
    scales = (0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 1.0, 1.025, 1.05, 1.075, 1.10, 1.15, 1.20)

    def __init__(
        self,
        screen_capture,
        title_template,
        threshold: float = 0.65,
        region: dict | Callable[[], dict | None] | None = None,
        debug_log_fn=None,
        debug_interval: float = 3.0,
        debug_dir: str | os.PathLike[str] | None = None,
        debug_image_interval: float = 10.0,
    ):
        super().__init__()
        self._capture = screen_capture
        self._threshold = threshold
        self._region = region
        self._debug_log_fn = debug_log_fn
        self._debug_interval = max(0.5, float(debug_interval))
        self._debug_image_interval = max(1.0, float(debug_image_interval))
        self._debug_dir = Path(debug_dir) if debug_dir else None
        self._last_debug_at = 0.0
        self._last_debug_image_at = 0.0
        self._present = False
        self._templates = self._load_templates(title_template)

    def _load_templates(self, title_template) -> list[np.ndarray]:
        paths: list[str] = []
        if isinstance(title_template, str):
            path = Path(title_template)
            if path.is_dir():
                paths = [str(p) for p in sorted(path.glob("*.png"))]
            elif path.is_file():
                paths = [str(path)]
                extra_dir = path.parent
                paths.extend(
                    str(p) for p in sorted(extra_dir.glob("*.png"))
                    if str(p) not in paths
                )
        templates = []
        for path in paths:
            template = cv2.imread(path)
            if template is not None:
                templates.append(_to_gray(template))
        if not templates and not isinstance(title_template, str) and title_template is not None:
            templates.append(_to_gray(title_template))
        return templates

    def scan_once(self) -> Event | None:
        total_started = time.perf_counter()
        capture_started = total_started
        try:
            region = self._region() if callable(self._region) else self._region
            scene = self._capture(region) if region else self._capture()
        except Exception as exc:
            self._debug_log(f"거탐 감시 오류: {exc}")
            return None
        capture_finished = time.perf_counter()
        if scene is None or not self._templates:
            self._debug_log("거탐 감시 실패: 캡처 또는 템플릿 없음")
            return None

        scene_gray = _to_gray(scene)
        match_started = time.perf_counter()
        score, scale, loc, size = _best_scaled_match(scene_gray, self._templates, self.scales)
        match_finished = time.perf_counter()
        capture_ms = (capture_finished - capture_started) * 1000.0
        match_ms = (match_finished - match_started) * 1000.0
        total_ms = (match_finished - total_started) * 1000.0
        detected = score >= self._threshold
        trace_event(
            "lie_scan",
            "complete",
            capture_ms=round(capture_ms, 3),
            match_ms=round(match_ms, 3),
            total_ms=round(total_ms, 3),
            score=round(score, 4),
            detected=detected,
        )
        self._debug_log(
            f"거탐 감시중: score={score:.3f}, scale={scale:.3f}, "
            f"threshold={self._threshold:.3f}, region={region or '전체화면'}, "
            f"capture={capture_ms:.1f}ms, match={match_ms:.1f}ms, total={total_ms:.1f}ms"
        )
        if not detected:
            self._save_debug_images(scene, loc, size, score, scale)

        if detected and not self._present:
            self._present = True
            return Event(type="lie", data={"score": score, "scale": scale})
        if not detected and self._present:
            self._present = False
        return None

    def is_present(self) -> bool:
        """최근 스캔에서 거탐 제목이 화면에 남아 있는지 반환한다."""
        return self._present

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

    def _save_debug_images(
        self,
        scene: np.ndarray,
        loc: tuple[int, int],
        size: tuple[int, int],
        score: float,
        scale: float,
    ) -> None:
        if self._debug_dir is None:
            return
        now = time.monotonic()
        if now - self._last_debug_image_at < self._debug_image_interval:
            return
        self._last_debug_image_at = now
        try:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            region_img = scene.copy()
            x, y = loc
            w, h = size
            if w > 0 and h > 0:
                cv2.rectangle(region_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.imwrite(str(self._debug_dir / "latest_region.png"), region_img)
            meta = f"score={score:.4f}, scale={scale:.4f}, loc={loc}, size={size}\n"
            (self._debug_dir / "latest_score.txt").write_text(meta, encoding="utf-8")
        except Exception:
            pass
