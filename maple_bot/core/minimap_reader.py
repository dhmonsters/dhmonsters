# 미니맵에서 캐릭터 도트 위치를 감지하는 모듈
from __future__ import annotations
import numpy as np
import logging
from dataclasses import dataclass
try:
    import cv2
except Exception:
    cv2 = None

from core.screen_reader import ScreenReader

logger = logging.getLogger(__name__)


@dataclass
class MinimapConfig:
    """미니맵 화면 영역 및 캐릭터 도트 색상 설정."""
    region_x: int = 0          # 미니맵 좌상단 절대 화면 좌표
    region_y: int = 0
    width: int = 200
    height: int = 120
    char_r: int = 255           # 캐릭터 도트 RGB 색상 (기본 흰색)
    char_g: int = 255
    char_b: int = 255
    tolerance: int = 30         # 색상 허용 오차
    jump_key: str = "alt"       # 밧줄 점프 키 (메이플 기본 alt)


@dataclass
class RopePoint:
    """밧줄/사다리 위치 및 점프 접근 설정."""
    name: str = "밧줄"
    x: int = 0                  # 미니맵 기준 X 좌표
    approach: str = "both"      # "left" | "right" | "both"
    jump_offset: int = 5        # 밧줄에서 몇 픽셀 옆에서 점프할지
    climb_sec: float = 2.5      # 밧줄 오르는 데 걸리는 시간 (초)

    def to_dict(self, mm_w: int = 0) -> dict:
        """mm_w > 0 이면 x_ratio 도 함께 저장."""
        d = {"name": self.name, "x": self.x,
             "approach": self.approach, "jump_offset": self.jump_offset,
             "climb_sec": self.climb_sec}
        if mm_w > 0:
            d["x_ratio"] = self.x / mm_w
        return d

    @classmethod
    def from_dict(cls, d: dict, mm_w: int = 0) -> "RopePoint":
        """mm_w > 0 이고 x_ratio 가 있으면 비율로부터 픽셀값 계산."""
        if mm_w > 0 and d.get("x_ratio") is not None:
            x = max(0, int(d["x_ratio"] * mm_w))
        else:
            x = int(d.get("x", 0))
        return cls(
            name=d.get("name", "밧줄"),
            x=x,
            approach=d.get("approach", "both"),
            jump_offset=int(d.get("jump_offset", 15)),
            climb_sec=float(d.get("climb_sec", 2.5)),
        )

    def label(self) -> str:
        approach_kor = {"left": "왼쪽", "right": "오른쪽", "both": "양쪽"}.get(self.approach, self.approach)
        return f"{self.name}  X={self.x}  접근={approach_kor}  점프거리={self.jump_offset}px  오르기={self.climb_sec:.1f}s"


@dataclass
class Zone:
    """사냥 구역 정의 — 미니맵 기준 상대 좌표."""
    name: str
    left_x: int
    right_x: int
    y_min: int
    y_max: int
    rope_x: int = -1           # 로프/사다리 X 좌표 (-1 = 없음)
    random_margin_min: int = 0  # 경계 전환 랜덤 여유 최솟값 (px)
    random_margin_max: int = 0  # 경계 전환 랜덤 여유 최댓값 (px)
    sweeps: float = 2.0         # 층별 사냥 시 왕복 횟수 (0 = 무제한, 0.5 단위 가능)
    key_pattern: str = ""       # 층별 공격 패턴 프리셋 이름 (빈 문자열 = 기본 패턴 유지)

    def to_dict(self, mm_w: int = 0, mm_h: int = 0) -> dict:
        """mm_w/mm_h > 0 이면 비율 키도 함께 저장."""
        d = {
            "name": self.name,
            "left_x": self.left_x, "right_x": self.right_x,
            "y_min": self.y_min,   "y_max": self.y_max,
            "rope_x": self.rope_x,
            "random_margin_min": self.random_margin_min,
            "random_margin_max": self.random_margin_max,
            "sweeps": float(self.sweeps),
            "key_pattern": self.key_pattern,
        }
        if mm_w > 0 and mm_h > 0:
            d.update({
                "left_x_ratio":  self.left_x  / mm_w,
                "right_x_ratio": self.right_x / mm_w,
                "y_min_ratio":   self.y_min   / mm_h,
                "y_max_ratio":   self.y_max   / mm_h,
                "rope_x_ratio":  self.rope_x  / mm_w if self.rope_x >= 0 else -1.0,
            })
        return d

    @classmethod
    def from_dict(cls, d: dict, mm_w: int = 0, mm_h: int = 0) -> "Zone":
        """mm_w/mm_h > 0 이고 비율 키가 있으면 비율로부터 픽셀값 계산."""
        if mm_w > 0 and mm_h > 0 and d.get("left_x_ratio") is not None:
            left_x  = max(0, int(d["left_x_ratio"]  * mm_w))
            right_x = max(0, int(d["right_x_ratio"] * mm_w))
            y_min   = max(0, int(d["y_min_ratio"]   * mm_h))
            y_max   = max(0, int(d["y_max_ratio"]   * mm_h))
            rx_r    = d.get("rope_x_ratio", -1.0)
            rope_x  = int(rx_r * mm_w) if rx_r >= 0 else -1
        else:
            left_x  = int(d.get("left_x", 0))
            right_x = int(d.get("right_x", 200))
            y_min   = int(d.get("y_min", 0))
            y_max   = int(d.get("y_max", 120))
            rope_x  = int(d.get("rope_x", -1))
        return cls(
            name=d.get("name", "구역"),
            left_x=left_x, right_x=right_x,
            y_min=y_min,   y_max=y_max,
            rope_x=rope_x,
            random_margin_min=int(d.get("random_margin_min", 0)),
            random_margin_max=int(d.get("random_margin_max", 0)),
            sweeps=float(d.get("sweeps", 2.0)),
            key_pattern=d.get("key_pattern", ""),
        )

    def label(self) -> str:
        rope = f"  로프 X={self.rope_x}" if self.rope_x >= 0 else "  로프 없음"
        rnd = (f"  랜덤 {self.random_margin_min}~{self.random_margin_max}px"
               if self.random_margin_max > 0 else "")
        sw = f"  왕복 {self.sweeps}회" if self.sweeps > 0 else "  왕복 통과"
        pat = f"  패턴:{self.key_pattern}" if self.key_pattern else ""
        return f"{self.name}: X {self.left_x}~{self.right_x}  Y {self.y_min}~{self.y_max}{rope}{rnd}{sw}{pat}"


class MinimapReader:
    def __init__(self, screen_reader: ScreenReader):
        self._screen = screen_reader
        self._cfg: MinimapConfig = MinimapConfig()
        # 창모드↔전체화면 전환 대응: config+mm_dict 저장 시 매 호출마다 위치 재계산
        self._dyn_config = None   # ConfigManager
        self._dyn_mm: dict = {}   # 미니맵 설정 dict
        self._last_char_pos: tuple[int, int] | None = None
        self._ccv2_available = cv2 is not None

    def set_config(self, cfg: MinimapConfig) -> None:
        self._cfg = cfg

    def set_dynamic_source(self, config, mm: dict) -> None:
        """창 이동·전체화면 전환 시 region_x/y를 매 호출마다 재계산하도록 설정.

        config: ConfigManager 인스턴스
        mm:     minimap 설정 dict (region_x_ratio 등 포함)
        """
        self._dyn_config = config
        self._dyn_mm = mm

    def _resolve_region(self) -> tuple[int, int, int, int]:
        """현재 창 위치 기준으로 미니맵 region (x, y, w, h) 를 반환.

        set_dynamic_source 가 설정된 경우 매번 재계산 → 창 이동/전체화면 전환 대응.
        그 외에는 set_config 로 저장된 값 사용.
        """
        if self._dyn_config is not None:
            from core.config_manager import resolve_minimap_coords
            rx, ry, rw, rh = resolve_minimap_coords(self._dyn_config, self._dyn_mm)
            if rw > 0 and rh > 0:
                return rx, ry, rw, rh
        cfg = self._cfg
        return cfg.region_x, cfg.region_y, cfg.width, cfg.height

    @property
    def config(self) -> MinimapConfig:
        return self._cfg

    # ── 캐릭터 위치 감지 ──────────────────────────────────────────────
    def get_character_pos(self) -> tuple[int, int] | None:
        """
        캐릭터 위치를 미니맵 상에서 추정한 (x, y)를 반환한다.
        미검출 시 None을 반환한다.
        """
        cfg = self._cfg
        rx, ry, rw, rh = self._resolve_region()
        if rw <= 0 or rh <= 0:
            return None

        region = {
            "left": rx,
            "top":  ry,
            "width": rw,
            "height": rh,
        }
        minimap = self._screen.capture(region)

        target = np.array([cfg.char_b, cfg.char_g, cfg.char_r], dtype=np.int32)
        diff = np.abs(minimap.astype(np.int32) - target)
        mask = np.all(diff <= cfg.tolerance, axis=2)

        ys, xs = np.where(mask)
        if len(xs) < 2:
            self._last_char_pos = None
            return None

        h, w = mask.shape
        cx_prev, cy_prev = self._last_char_pos or (w * 0.5, h * 0.5)

        cx, cy = int(np.mean(xs)), int(np.mean(ys))

        if self._ccv2_available:
            try:
                num_labels, labels, stats, cent = cv2.connectedComponentsWithStats(
                    mask.astype(np.uint8),
                    connectivity=8,
                )
            except Exception:
                self._ccv2_available = False
                num_labels = 0

            if num_labels > 1:
                # 캐릭터 점은 미니맵에서 작고 둥근 노란 덩어리다.
                # tolerance는 색상 허용값이므로 면적 기준으로 쓰면 실제 캐릭터 점이 빠질 수 있다.
                min_area = 5
                max_area = max(40, min(180, int(w * h * 0.03)))
                candidates = []
                for label in range(1, num_labels):
                    area = int(stats[label, cv2.CC_STAT_AREA])
                    if area < min_area or area > max_area:
                        continue

                    x = int(stats[label, cv2.CC_STAT_LEFT])
                    y = int(stats[label, cv2.CC_STAT_TOP])
                    bw = int(stats[label, cv2.CC_STAT_WIDTH])
                    bh = int(stats[label, cv2.CC_STAT_HEIGHT])
                    if bw <= 0 or bh <= 0:
                        continue
                    if bw < 3 or bh < 3 or bw > 18 or bh > 18:
                        continue

                    ratio = bw / bh
                    if ratio > 1.65 or ratio < 0.60:
                        continue

                    fill_ratio = area / float(bw * bh)
                    if fill_ratio < 0.25 or fill_ratio > 0.95:
                        continue

                    c_x, c_y = cent[label]
                    dist2 = (float(c_x) - cx_prev) ** 2 + (float(c_y) - cy_prev) ** 2
                    shape_penalty = abs(1.0 - ratio) * 20.0
                    fill_penalty = abs(0.68 - fill_ratio) * 12.0
                    area_penalty = abs(45.0 - area) / 10.0
                    continuity_penalty = dist2 * 0.04 if self._last_char_pos else 0.0
                    score = shape_penalty + fill_penalty + area_penalty + continuity_penalty
                    candidates.append((score, dist2, float(c_x), float(c_y), area, x, y, bw, bh, fill_ratio))

                if candidates:
                    candidates.sort(key=lambda v: v[0])
                    score, dist2, c_x, c_y, area, x, y, bw, bh, fill_ratio = candidates[0]
                    cx, cy = int(round(c_x)), int(round(c_y))
                    cx = max(0, min(w - 1, cx))
                    cy = max(0, min(h - 1, cy))
                    if self._last_char_pos:
                        d2 = (cx - self._last_char_pos[0]) ** 2 + (cy - self._last_char_pos[1]) ** 2
                        if d2 > max(900, (rw * rw + rh * rh) * 0.08):
                            logger.warning(
                                "[미니맵 추적] 캐릭터 좌표 급변 후보를 감지했습니다 (x,y=%d,%d, prev=%s, dist2=%.1f, area=%d, bbox=(%d,%d,%d,%d), fill=%.2f, candidates=%d)",
                                cx,
                                cy,
                                self._last_char_pos,
                                d2,
                                area,
                                x,
                                y,
                                bw,
                                bh,
                                fill_ratio,
                                len(candidates),
                            )
                    self._last_char_pos = (cx, cy)
                    logger.debug(
                        "[미니맵 추적] 원형 후보 선택 x=%d y=%d area=%d bbox=%s fill=%.2f score=%.2f candidates=%d",
                        cx,
                        cy,
                        area,
                        (x, y, bw, bh),
                        fill_ratio,
                        score,
                        len(candidates),
                    )
                    return cx, cy

        logger.debug("[미니맵 추적] 폴백 사용 x=%d y=%d total=%d", cx, cy, len(xs))
        self._last_char_pos = (cx, cy)
        return cx, cy

    def capture_minimap(self) -> np.ndarray:
        """미니맵 영역 이미지를 반환 (디버그/미리보기용)."""
        rx, ry, rw, rh = self._resolve_region()
        region = {
            "left": rx,
            "top":  ry,
            "width": max(1, rw),
            "height": max(1, rh),
        }
        return self._screen.capture(region)

    # ── 구역 판별 ─────────────────────────────────────────────────────
    @staticmethod
    def find_zone(pos: tuple[int, int], zones: list[Zone]) -> Zone | None:
        """현재 위치가 속하는 구역을 반환."""
        x, y = pos
        for zone in zones:
            if zone.left_x <= x <= zone.right_x and zone.y_min <= y <= zone.y_max:
                return zone
        return None
