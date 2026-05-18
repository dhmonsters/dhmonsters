# HP/MP 픽셀 감지 및 몬스터 템플릿 매칭 모듈
from __future__ import annotations
import os
import numpy as np
import cv2

from core.screen_reader import ScreenReader
from core.config_manager import ConfigManager


class Detector:
    def __init__(self, screen_reader: ScreenReader, config: ConfigManager):
        self._screen = screen_reader
        self._config = config
        # 템플릿 캐시 (경로 → cv2 이미지)
        self._template_cache: dict[str, np.ndarray | None] = {}

    # ── 몬스터 감지 ───────────────────────────────────────────────────
    def has_monster(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.75,
    ) -> bool:
        """screenshot 안에 template_path 몬스터 이미지가 있으면 True."""
        template = self._load_template(template_path)
        if template is None:
            return False
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= threshold

    def find_monsters(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.75,
    ) -> list[tuple[int, int]]:
        """화면에서 몬스터 위치(중심 좌표) 목록을 반환."""
        template = self._load_template(template_path)
        if template is None:
            return []

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        th, tw = template.shape[:2]
        locations = np.where(result >= threshold)
        positions = []
        for y, x in zip(*locations):
            positions.append((int(x + tw // 2), int(y + th // 2)))
        return positions

    # ── HP / MP 감지 ──────────────────────────────────────────────────
    def hp_ratio(self) -> float:
        """HP 바의 현재 비율(0.0~1.0)을 반환. 좌표 미설정 시 1.0."""
        return self._bar_ratio("hp")

    def mp_ratio(self) -> float:
        """MP 바의 현재 비율(0.0~1.0)을 반환. 좌표 미설정 시 1.0."""
        return self._bar_ratio("mp")

    def _bar_ratio(self, bar_type: str) -> float:
        """바 영역을 한 번에 캡처 후 numpy HSV로 처리 — 개별 픽셀 API 호출 없음."""
        coord = self._config.get("coordinate", bar_type) or {}
        x = coord.get("x")
        y = coord.get("y")
        width = coord.get("width")

        # x=0이나 y=0은 유효한 좌표일 수 있으므로 None 또는 width=0만 미설정으로 판단
        if x is None or y is None or not width:
            return 1.0

        x, y, width = int(x), int(y), int(width)
        scan_h = 17  # ±8행

        # 바 영역 한 번에 캡처 (mss 개별 호출 없음)
        region = {"left": x, "top": max(0, y - 8), "width": width, "height": scan_h}
        img = self._screen.capture(region)   # BGR numpy (H, W, 3)

        # numpy 벡터 연산으로 HSV 마스크 계산
        f = img.astype(np.float32) / 255.0
        r, g, b = f[:, :, 2], f[:, :, 1], f[:, :, 0]

        maxc = np.maximum(r, np.maximum(g, b))
        minc = np.minimum(r, np.minimum(g, b))
        delta = maxc - minc

        v = maxc
        # maxc=0인 픽셀의 0÷0 RuntimeWarning 억제
        with np.errstate(divide='ignore', invalid='ignore'):
            s = np.where(maxc > 1e-6, delta / maxc, 0.0)

        # 채도·명도 기본 필터 (흰색 텍스트·회색 빈칸·검정 제외)
        base = (s >= 0.35) & (v >= 0.25)

        # Hue 계산
        hue = np.zeros_like(r)
        d = delta + 1e-9  # 0 나눔 방지
        mr = (delta > 1e-6) & (maxc == r)
        mg = (delta > 1e-6) & (maxc == g)
        mb = (delta > 1e-6) & (maxc == b)
        hue[mr] = ((g[mr] - b[mr]) / d[mr]) % 6
        hue[mg] = (b[mg] - r[mg]) / d[mg] + 2
        hue[mb] = (r[mb] - g[mb]) / d[mb] + 4
        hue_deg = hue * 60

        if bar_type == "hp":
            color_mask = (hue_deg <= 20) | (hue_deg >= 340)
        else:
            color_mask = (hue_deg >= 180) & (hue_deg <= 260)

        final_mask = base & color_mask   # shape (H, W)

        # 색상 픽셀이 존재하는 가장 오른쪽 열 = 채워진 비율
        col_has_match = final_mask.any(axis=0)   # shape (W,)
        cols = np.where(col_has_match)[0]
        if len(cols) == 0:
            return 0.0
        return (int(cols[-1]) + 1) / width

    # ── 템플릿 캐시 ───────────────────────────────────────────────────
    def _load_template(self, path: str) -> np.ndarray | None:
        if path not in self._template_cache:
            if os.path.exists(path):
                self._template_cache[path] = cv2.imread(path)
            else:
                self._template_cache[path] = None
        return self._template_cache[path]

    def clear_cache(self) -> None:
        self._template_cache.clear()

    # ── monsters/ 폴더 이미지 목록 ────────────────────────────────────
    @staticmethod
    def list_monster_templates(folder: str = "monsters") -> list[str]:
        """monsters/ 폴더의 이미지 파일 목록을 반환."""
        if not os.path.isdir(folder):
            return []
        exts = {".png", ".jpg", ".bmp"}
        return [
            os.path.join(folder, f)
            for f in sorted(os.listdir(folder))
            if os.path.splitext(f)[1].lower() in exts
        ]
