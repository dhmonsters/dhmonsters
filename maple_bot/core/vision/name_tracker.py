# 캐릭터 이름표 템플릿 매칭 + 미니맵 델타 데드레코닝 위치 추정 모듈
from __future__ import annotations

import os

import cv2
import numpy as np

_TEMPLATE_FILE = "char_name_tag.png"


class NameTagTracker:
    """이름표 템플릿 매칭으로 절대 위치를 앵커링하고, 실패 시 미니맵 델타로 데드레코닝한다.

    동작 흐름:
        1. 게임 화면에서 이름표 템플릿 매칭 시도.
        2. 매칭 성공(conf ≥ threshold) → 절대 앵커 갱신.
        3. 매칭 실패 + 앵커 존재 → 미니맵 (mx,my) 변화량을 화면 픽셀로 환산해 위치 추정.
        4. 템플릿 없음 + 앵커 없음 → None 반환 (상위에서 공식 방식 폴백).

    source 값:
        "template"      이번 프레임 직접 감지
        "deadreckoning" 앵커 + 미니맵 델타 추정
    """

    def __init__(self, templates_dir: str) -> None:
        self._templates_dir = templates_dir
        self._template: np.ndarray | None = None
        self._threshold: float = 0.70
        self._anchor_screen: tuple[int, int] | None = None  # (gx, gy)
        self._anchor_mm:     tuple[int, int] | None = None  # (mx, my)
        self._load_template()

    # ── 템플릿 관리 ───────────────────────────────────────────────────────────
    def _template_path(self) -> str:
        return os.path.join(self._templates_dir, _TEMPLATE_FILE)

    def _load_template(self) -> None:
        path = self._template_path()
        if os.path.exists(path):
            buf = np.fromfile(path, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is not None:
                self._template = img

    def set_template(self, bgr: np.ndarray) -> None:
        """이름표 이미지를 설정하고 디스크에 저장한다. 앵커는 초기화."""
        os.makedirs(self._templates_dir, exist_ok=True)
        self._template = bgr.copy()
        cv2.imwrite(self._template_path(), bgr)
        self.reset()

    def clear_template(self) -> None:
        """템플릿과 앵커를 모두 초기화한다."""
        self._template = None
        self.reset()
        path = self._template_path()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def set_threshold(self, value: float) -> None:
        self._threshold = max(0.3, min(1.0, float(value)))

    def has_template(self) -> bool:
        return self._template is not None

    @property
    def template_shape(self) -> tuple[int, int] | None:
        """(height, width) 또는 None."""
        if self._template is None:
            return None
        return self._template.shape[:2]

    # ROI 검색 반경 (anchor 주변 탐색 픽셀 — 클수록 안전하나 느림)
    _ROI_RADIUS_X = 250
    _ROI_RADIUS_Y = 150

    def _match_template(
        self,
        game_frame: np.ndarray,
        th: int, tw: int,
        fh: int, fw: int,
    ) -> tuple[float, tuple[int, int]] | None:
        """ROI 우선 탐색 후 전체 프레임 폴백으로 템플릿 매칭을 수행한다.

        Returns:
            (max_val, absolute_max_loc) 또는 None.
        """
        if self._anchor_screen is not None:
            ax, ay = self._anchor_screen
            x1 = max(0, ax - self._ROI_RADIUS_X)
            y1 = max(0, ay - self._ROI_RADIUS_Y)
            x2 = min(fw, ax + self._ROI_RADIUS_X + tw)
            y2 = min(fh, ay + self._ROI_RADIUS_Y + th)
            if x2 - x1 >= tw and y2 - y1 >= th:
                roi = game_frame[y1:y2, x1:x2]
                res = cv2.matchTemplate(roi, self._template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= self._threshold:
                    return float(max_val), (x1 + max_loc[0], y1 + max_loc[1])

        res = cv2.matchTemplate(game_frame, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= self._threshold:
            return float(max_val), (int(max_loc[0]), int(max_loc[1]))
        return None

    # ── 매 프레임 호출 ────────────────────────────────────────────────────────
    def update(
        self,
        game_frame: np.ndarray | None,
        mx: int, my: int,
        cam_left: int, cam_right: int,
        cam_top: int,  cam_bottom: int,
        screen_w: int, screen_h: int,
    ) -> dict | None:
        """이름표 위치를 추정한다.

        Returns:
            {"gx": int, "gy": int, "source": str, "conf": float}
            또는 None (템플릿/앵커 없음).
        """
        cam_w = max(1, cam_right  - cam_left)
        cam_h = max(1, cam_bottom - cam_top)

        # ── 1. 템플릿 매칭 ───────────────────────────────────────────────
        if self._template is not None and game_frame is not None:
            th, tw = self._template.shape[:2]
            fh, fw = game_frame.shape[:2]
            if fw >= tw and fh >= th:
                result = self._match_template(game_frame, th, tw, fh, fw)
                if result is not None:
                    max_val, max_loc = result
                    gx = max_loc[0] + tw // 2
                    gy = max_loc[1] + th
                    self._anchor_screen = (gx, gy)
                    self._anchor_mm     = (mx, my)
                    return {"gx": gx, "gy": gy,
                            "source": "template", "conf": float(max_val),
                            "tw": tw, "th": th, "tx": max_loc[0], "ty": max_loc[1]}

        # ── 2. 데드레코닝 (앵커 존재 시) ────────────────────────────────
        if (self._anchor_screen is not None and self._anchor_mm is not None
                and screen_w > 0 and screen_h > 0):
            dmx = mx - self._anchor_mm[0]
            dmy = my - self._anchor_mm[1]
            gx = int(self._anchor_screen[0] + dmx / cam_w * screen_w)
            gy = int(self._anchor_screen[1] + dmy / cam_h * screen_h)
            return {"gx": gx, "gy": gy,
                    "source": "deadreckoning", "conf": 0.0,
                    "tw": self.template_shape[1] if self.template_shape else 0,
                    "th": self.template_shape[0] if self.template_shape else 0,
                    "tx": gx - (self.template_shape[1] // 2 if self.template_shape else 0),
                    "ty": gy - (self.template_shape[0] if self.template_shape else 0)}

        return None

    # ── 초기화 ───────────────────────────────────────────────────────────────
    def reload_from_disk(self) -> bool:
        """디스크에서 템플릿을 다시 로드하고 앵커를 초기화한다. 성공 시 True 반환."""
        self._load_template()
        self.reset()
        return self._template is not None

    def reset(self) -> None:
        """앵커를 초기화한다. 맵 전환·봇 재시작 시 호출."""
        self._anchor_screen = None
        self._anchor_mm     = None

