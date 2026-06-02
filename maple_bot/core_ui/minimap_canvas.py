# 미니맵을 실시간 캡처해 배경으로 깔고 캐릭터·공격/사냥 범위를 투영하는 캔버스 위젯
from __future__ import annotations

import math
import time

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPen, QColor

from core.sensing.char_scanner import find_char_in_hsv
from core_ui.minimap_geom import (
    minimap_to_canvas, screen_px_to_minimap_px, char_track_state,
)


class MinimapCanvas(QWidget):
    """미니맵 영역을 주기 캡처해 배경(흐리게)·캐릭터(노란 점)·공격/사냥 범위를 그린다.
    좌표는 미니맵 픽셀 기준, 화면 표시 시 줌 배율을 곱한다(범위도 줌 비례).
    캐릭터 검출 끊김은 tracking→lost(깜빡임)→stale(점 숨김+배지) 상태로 표현한다."""

    def __init__(self, config, screen_capture, char_finder=find_char_in_hsv,
                 interval_ms: int = 80, screen_w: int = 1920, clock=time.time):
        super().__init__()
        self._cfg = config
        self._capture = screen_capture
        self._find = char_finder
        self._screen_w = screen_w
        self._clock = clock
        self._zoom = 1.0
        self._last_char: tuple[int, int] | None = None
        self._last_seen: float | None = None    # 마지막 성공 검출 시각
        self._shot: QImage | None = None
        self._mm_size = (0, 0)        # (W_mm, H_mm)
        self.setMinimumHeight(220)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)

    def _region(self) -> dict:
        c = self._cfg
        return {"left": int(c.get("minimap", "region_x", default=0)),
                "top": int(c.get("minimap", "region_y", default=0)),
                "width": int(c.get("minimap", "width", default=0)),
                "height": int(c.get("minimap", "height", default=0))}

    def minimap_size(self) -> tuple[int, int]:
        """미니맵 (W,H) — _region 기반이라 타이머 틱 전에도 유효(클램프용)."""
        r = self._region()
        return (r["width"], r["height"])

    def track_state(self) -> str:
        """현재 캐릭터 추적 상태: tracking | lost | stale (한 번도 검출 전이면 stale)."""
        if self._last_seen is None:
            return "stale"
        return char_track_state(self._clock() - self._last_seen)

    def _tick(self) -> None:
        r = self._region()
        if r["width"] <= 0:
            self._shot = None
            self.update()
            return
        try:
            bgr = self._capture(r)
        except Exception:
            return
        if bgr is None:
            return
        pos = self._find(bgr, (20, 100, 200), (40, 255, 255), 6, 4000)
        if pos is not None:
            self._last_char = pos
            self._last_seen = self._clock()
        h, w = bgr.shape[:2]
        self._mm_size = (w, h)
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        self._shot = QImage(rgb.data, w, h, 3 * w,
                            QImage.Format.Format_RGB888).copy()
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0d0e10"))
        if self._shot is None:
            self._hint(p, "연결·인식에서 미니맵 영역을 먼저 지정하세요")
            return
        W, H = self._mm_size
        p.setOpacity(0.30)
        p.drawImage(QRectF(0, 0, W * self._zoom, H * self._zoom), self._shot)
        p.setOpacity(1.0)
        state = self.track_state()
        if self._last_char is None or state == "stale":
            self._hint(p, "캐릭터 미검출")
            return
        cx, cy = minimap_to_canvas(self._last_char[0], self._last_char[1], self._zoom)
        self._draw_ranges(p, cx, cy)
        if state == "lost":
            # 천천히 깜빡임(0.8초 주기) — '일시적 끊김' 상황 인지
            phase = (self._clock() % 0.8) / 0.8
            p.setOpacity(0.35 + 0.45 * abs(math.sin(phase * math.pi)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffd33d"))
        p.drawEllipse(cx - 7, cy - 7, 14, 14)
        p.setOpacity(1.0)

    def _draw_ranges(self, p: QPainter, cx: int, cy: int) -> None:
        c = self._cfg
        W = self._mm_size[0]
        ratio = float(c.get("attack", "camera_w_ratio", default=0.5))
        z = self._zoom

        def conv(key, dft):
            v = abs(int(c.get("attack", key, default=dft)))
            return screen_px_to_minimap_px(v, W, self._screen_w, ratio) * z

        axw = max(3.0, conv("atk_x_max", 35))
        ayh = max(3.0, conv("atk_y_max", 70))
        hxw = max(4.0, conv("monster_range_px", 600))
        hyh = max(4.0, conv("monster_range_h", 120))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#4d7cff"), 1.4, Qt.PenStyle.DashLine))   # 사냥
        p.drawRect(int(cx - hxw), int(cy - hyh), int(hxw * 2), int(hyh * 2))
        p.setPen(QPen(QColor("#f04452"), 1.4, Qt.PenStyle.DashLine))   # 공격
        p.drawRect(int(cx - axw), int(cy - ayh), int(axw * 2), int(ayh * 2))

    def _hint(self, p: QPainter, text: str) -> None:
        p.setPen(QColor("#8a8f98"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def set_zoom(self, zoom: float) -> None:
        """줌 배율 설정(0.5~4.0 클램프)."""
        self._zoom = max(0.5, min(4.0, zoom))
        self.update()

    def fit(self) -> None:
        """미니맵 전체가 캔버스에 들어오도록 줌 맞춤."""
        W, H = self._mm_size
        if W > 0 and H > 0 and self.width() > 0 and self.height() > 0:
            self.set_zoom(min(self.width() / W, self.height() / H))

    def wheelEvent(self, ev) -> None:
        step = 1.1 if ev.angleDelta().y() > 0 else 0.9
        self.set_zoom(self._zoom * step)
