# 미니맵에서 캐릭터 도트 위치를 감지하는 모듈
from __future__ import annotations
import numpy as np
import logging
from dataclasses import dataclass

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
    jump_offset: int = 15       # 밧줄에서 몇 픽셀 옆에서 점프할지

    def to_dict(self) -> dict:
        return {"name": self.name, "x": self.x,
                "approach": self.approach, "jump_offset": self.jump_offset}

    @classmethod
    def from_dict(cls, d: dict) -> "RopePoint":
        return cls(
            name=d.get("name", "밧줄"),
            x=int(d.get("x", 0)),
            approach=d.get("approach", "both"),
            jump_offset=int(d.get("jump_offset", 15)),
        )

    def label(self) -> str:
        approach_kor = {"left": "왼쪽", "right": "오른쪽", "both": "양쪽"}.get(self.approach, self.approach)
        return f"{self.name}  X={self.x}  접근={approach_kor}  점프거리={self.jump_offset}px"


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
    sweeps: int = 2             # 층별 사냥 시 왕복 횟수 (0 = 무제한)
    key_pattern: str = ""       # 층별 공격 패턴 프리셋 이름 (빈 문자열 = 기본 패턴 유지)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "left_x": self.left_x,
            "right_x": self.right_x,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "rope_x": self.rope_x,
            "random_margin_min": self.random_margin_min,
            "random_margin_max": self.random_margin_max,
            "sweeps": self.sweeps,
            "key_pattern": self.key_pattern,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Zone":
        return cls(
            name=d.get("name", "구역"),
            left_x=int(d.get("left_x", 0)),
            right_x=int(d.get("right_x", 200)),
            y_min=int(d.get("y_min", 0)),
            y_max=int(d.get("y_max", 120)),
            rope_x=int(d.get("rope_x", -1)),
            random_margin_min=int(d.get("random_margin_min", 0)),
            random_margin_max=int(d.get("random_margin_max", 0)),
            sweeps=int(d.get("sweeps", 2)),
            key_pattern=d.get("key_pattern", ""),
        )

    def label(self) -> str:
        rope = f"  로프 X={self.rope_x}" if self.rope_x >= 0 else "  로프 없음"
        rnd = (f"  랜덤 {self.random_margin_min}~{self.random_margin_max}px"
               if self.random_margin_max > 0 else "")
        sw = f"  왕복 {self.sweeps}회" if self.sweeps > 0 else "  왕복 무제한"
        pat = f"  패턴:{self.key_pattern}" if self.key_pattern else ""
        return f"{self.name}: X {self.left_x}~{self.right_x}  Y {self.y_min}~{self.y_max}{rope}{rnd}{sw}{pat}"


class MinimapReader:
    def __init__(self, screen_reader: ScreenReader):
        self._screen = screen_reader
        self._cfg: MinimapConfig = MinimapConfig()

    def set_config(self, cfg: MinimapConfig) -> None:
        self._cfg = cfg

    @property
    def config(self) -> MinimapConfig:
        return self._cfg

    # ── 캐릭터 위치 감지 ──────────────────────────────────────────────
    def get_character_pos(self) -> tuple[int, int] | None:
        """
        미니맵 내 캐릭터 도트의 상대 좌표 (x, y)를 반환.
        미니맵 영역이 설정되지 않았거나 도트를 찾지 못하면 None.
        """
        cfg = self._cfg
        if cfg.width <= 0 or cfg.height <= 0:
            return None

        region = {
            "left": cfg.region_x,
            "top":  cfg.region_y,
            "width": cfg.width,
            "height": cfg.height,
        }
        minimap = self._screen.capture(region)

        target = np.array([cfg.char_b, cfg.char_g, cfg.char_r], dtype=np.int32)
        diff = np.abs(minimap.astype(np.int32) - target)
        mask = np.all(diff <= cfg.tolerance, axis=2)   # (H, W) bool 배열

        ys, xs = np.where(mask)
        if len(xs) == 0:
            return None

        # 무게중심으로 위치 계산
        cx = int(np.mean(xs))
        cy = int(np.mean(ys))
        return cx, cy

    def capture_minimap(self) -> np.ndarray:
        """미니맵 영역 이미지를 반환 (디버그/미리보기용)."""
        cfg = self._cfg
        region = {
            "left": cfg.region_x,
            "top":  cfg.region_y,
            "width": max(1, cfg.width),
            "height": max(1, cfg.height),
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
