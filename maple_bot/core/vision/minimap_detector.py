# 誘몃땲留??꾨젅?꾩뿉??罹먮┃???꾩튂瑜?HSV ?됱긽 媛먯?濡?異붿쟻?섎뒗 紐⑤뱢
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    pass

# 湲곕낯 HSV 踰붿쐞 ???몃???罹먮┃???꾪듃 (255, 255, 0)
_DEFAULT_HSV_LOWER = (20, 100, 200)
_DEFAULT_HSV_UPPER = (40, 255, 255)

# ?대룞?됯퇏 ?덈룄???ш린
_SMOOTH_WINDOW = 5

# 寃쎈줈 湲곕줉 理쒕? 湲몄씠
_PATH_MAX = 30

# 理쒖냼 而⑦닾??硫댁쟻 (?몄씠利??쒓굅)
_MIN_AREA = 2
_MAX_AREA = 500


class MinimapDetector:
    """誘몃땲留?ROI ?대?吏?먯꽌 罹먮┃???꾪듃瑜?媛먯??섍퀬 ?대룞?됯퇏?쇰줈 異붿쟻?쒕떎.

    Args:
        config:       ConfigManager ?몄뒪?댁뒪 (hsv ?됱긽 踰붿쐞 ?쎄린).
        frame_buffer: FrameBuffer ?몄뒪?댁뒪 (?좏깮). ?덉쑝硫?cached ROI ?곗꽑 ?ъ슜.
    """

    def __init__(self, config, frame_buffer=None) -> None:
        self._config = config
        self._frame_buffer = frame_buffer
        self._smooth_buf: deque[tuple[int, int]] = deque(maxlen=_SMOOTH_WINDOW)
        self._path: list[tuple[int, int]] = []
        self._last_raw: tuple[int, int] | None = None
        self._last_smooth: tuple[int, int] | None = None
        self._last_confidence: float = 0.0

    # ?? 怨듦컻 API ??????????????????????????????????????????????????????????
    def detect(
        self, minimap_frame: "np.ndarray | None" = None
    ) -> tuple[
        "tuple[int,int] | None",
        "tuple[int,int] | None",
        float,
    ]:
        """誘몃땲留??꾨젅?꾩뿉??罹먮┃???꾩튂瑜?媛먯??쒕떎.

        Args:
            minimap_frame: 誘몃땲留?BGR ?대?吏. None?대㈃ frame_buffer?먯꽌 ?쎈뒗??

        Returns:
            (raw_pos, smooth_pos, confidence)
            - raw_pos    : 媛먯????먯떆 ?쎌? 醫뚰몴 (誘몃땲留?湲곗?)
            - smooth_pos : ?대룞?됯퇏 醫뚰몴
            - confidence : 0.0 ~ 1.0 (硫댁쟻 湲곕컲 ?좊ː??
        """
        frame = minimap_frame
        if frame is None and self._frame_buffer is not None:
            frame = self._frame_buffer.get_roi("minimap")

        if frame is None or frame.size == 0:
            self._last_confidence = 0.0
            return None, None, 0.0

        raw_pos, confidence = self._find_dot(frame)

        if raw_pos is not None:
            self._smooth_buf.append(raw_pos)
            smooth_pos = self._calc_smooth()
            self._last_raw = raw_pos
            self._last_smooth = smooth_pos
            self._last_confidence = confidence
            # 寃쎈줈 湲곕줉 (?댁쟾 ?꾩튂? ?ㅻ? ?뚮쭔)
            if not self._path or self._path[-1] != smooth_pos:
                self._path.append(smooth_pos)
                if len(self._path) > _PATH_MAX:
                    self._path = self._path[-_PATH_MAX:]
        else:
            self._last_confidence = 0.0

        return self._last_raw, self._last_smooth, self._last_confidence

    def get_char_path(self) -> list[tuple[int, int]]:
        """理쒓렐 ?대룞 寃쎈줈 醫뚰몴 紐⑸줉 諛섑솚 (誘몃땲留?湲곗? ?쎌?)."""
        return list(self._path)

    def reset(self) -> None:
        """異붿쟻 ?곹깭瑜?珥덇린?뷀븳??"""
        self._smooth_buf.clear()
        self._path.clear()
        self._last_raw = None
        self._last_smooth = None
        self._last_confidence = 0.0

    # ?? ?대? ?ы띁 ?????????????????????????????????????????????????????????
    def _get_hsv_range(self) -> tuple[tuple, tuple]:
        """config?먯꽌 HSV 踰붿쐞瑜??쎈뒗?? ?놁쑝硫?湲곕낯媛??ъ슜."""
        try:
            mm = self._config.get("minimap") or {}
            lower = (
                int(mm.get("hsv_h_low",  _DEFAULT_HSV_LOWER[0])),
                int(mm.get("hsv_s_low",  _DEFAULT_HSV_LOWER[1])),
                int(mm.get("hsv_v_low",  _DEFAULT_HSV_LOWER[2])),
            )
            upper = (
                int(mm.get("hsv_h_high", _DEFAULT_HSV_UPPER[0])),
                int(mm.get("hsv_s_high", _DEFAULT_HSV_UPPER[1])),
                int(mm.get("hsv_v_high", _DEFAULT_HSV_UPPER[2])),
            )
            return lower, upper
        except Exception:
            return _DEFAULT_HSV_LOWER, _DEFAULT_HSV_UPPER

    def _get_area_range(self) -> tuple[int, int]:
        """config에서 캐릭터 점 크기 범위를 읽는다."""
        try:
            mm = self._config.get("minimap") or {}
            area_min = int(mm.get("char_area_min", _MIN_AREA))
            area_max = int(mm.get("char_area_max", _MAX_AREA))
            return max(1, area_min), max(area_min + 1, area_max)
        except Exception:
            return _MIN_AREA, _MAX_AREA

    def _find_dot(
        self, frame: "np.ndarray"
    ) -> tuple["tuple[int,int] | None", float]:
        """HSV 留덉뒪??+ 而⑦닾?대줈 罹먮┃???꾪듃 ?꾩튂? ?좊ː?꾨? 諛섑솚."""
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower, upper = self._get_hsv_range()
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))

            # ?몄씠利??쒓굅 (morphology opening)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return None, 0.0

            # 硫댁쟻 ?꾪꽣 ??媛????而⑦닾???좏깮
            valid = [
                c for c in contours
                if _MIN_AREA <= cv2.contourArea(c) <= _MAX_AREA
            ]
            if not valid:
                return None, 0.0

            best = max(valid, key=cv2.contourArea)
            area = cv2.contourArea(best)

            M = cv2.moments(best)
            if M["m00"] == 0:
                return None, 0.0

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # ?좊ː?? 硫댁쟻??[2, 50] 踰붿쐞濡??뺢퇋??(0~1)
            confidence = min(1.0, (area - _MIN_AREA) / (50 - _MIN_AREA))
            return (cx, cy), round(confidence, 3)

        except Exception:
            return None, 0.0

    def _calc_smooth(self) -> tuple[int, int]:
        """deque ??醫뚰몴???대룞?됯퇏 諛섑솚."""
        xs = [p[0] for p in self._smooth_buf]
        ys = [p[1] for p in self._smooth_buf]
        return int(sum(xs) / len(xs)), int(sum(ys) / len(ys))




