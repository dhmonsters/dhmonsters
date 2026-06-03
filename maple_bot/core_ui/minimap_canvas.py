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
        self.setMinimumHeight(340)
        self._auto_fit = True         # 가로폭 자동맞춤(배경 확대), 휠 줌 시 해제
        self._monster_provider = None  # () -> [(dx,dy)] 캐릭 기준 화면px 오프셋
        self._monsters_rel: list = []  # 최근 탐지 캐시
        self._mon_last = 0.0           # 마지막 탐지 시각(스로틀)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)

    def _region(self) -> dict:
        c = self._cfg
        left = int(c.get("minimap", "region_x", default=0))
        top = int(c.get("minimap", "region_y", default=0))
        w = int(c.get("minimap", "width", default=0))
        h = int(c.get("minimap", "height", default=0))
        from core.config_manager import resolve_window_region
        coord_mode = c.get("coord_mode") or "absolute"
        title = c.get("settings2", "game_window_title") or ""
        a = c.get("coord_anchor", default=None)
        anchor = (int(a[0]), int(a[1])) if a else None
        x, y, w, h = resolve_window_region(coord_mode, title, left, top, w, h, anchor)
        return {"left": x, "top": y, "width": w, "height": h}

    def minimap_size(self) -> tuple[int, int]:
        """미니맵 (W,H) — _region 기반이라 타이머 틱 전에도 유효(클램프용)."""
        r = self._region()
        return (r["width"], r["height"])

    def set_monster_provider(self, fn) -> None:
        """몬스터 오프셋 공급자 등록(봇 런타임). None이면 점 표시 안 함."""
        self._monster_provider = fn

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
        # 몬스터 탐지(헌트영역, 무거우니 0.3초 스로틀) → 캐릭 기준 오프셋 캐시
        if self._monster_provider is not None and self._clock() - self._mon_last > 0.3:
            self._mon_last = self._clock()
            try:
                self._monsters_rel = list(self._monster_provider() or [])
            except Exception:
                self._monsters_rel = []
        h, w = bgr.shape[:2]
        self._mm_size = (w, h)
        if self._auto_fit:
            self.fit_width()          # 캡처 폭 기준 가로 꽉 채우기(배경 확대)
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
        self._draw_monsters(p, cx, cy)
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

    def _draw_monsters(self, p: QPainter, cx: int, cy: int) -> None:
        """탐지된 몬스터를 캐릭 기준 오프셋으로 미니맵 축척 환산해 빨간 점으로 표시."""
        if not self._monsters_rel:
            return
        c = self._cfg
        W = self._mm_size[0]
        ratio = float(c.get("attack", "camera_w_ratio", default=0.5))
        z = self._zoom
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f04452"))
        for dx, dy in self._monsters_rel:
            mx = cx + screen_px_to_minimap_px(dx, W, self._screen_w, ratio) * z
            my = cy + screen_px_to_minimap_px(dy, W, self._screen_w, ratio) * z
            p.drawEllipse(int(mx) - 4, int(my) - 4, 8, 8)

    def _hint(self, p: QPainter, text: str) -> None:
        p.setPen(QColor("#8a8f98"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def set_zoom(self, zoom: float) -> None:
        """줌 배율 설정(0.5~8.0 클램프)."""
        self._zoom = max(0.5, min(8.0, zoom))
        self.update()

    def fit(self) -> None:
        """미니맵 전체가 캔버스에 들어오도록 줌 맞춤."""
        W, H = self._mm_size
        if W > 0 and H > 0 and self.width() > 0 and self.height() > 0:
            self.set_zoom(min(self.width() / W, self.height() / H))

    def fit_width(self) -> None:
        """미니맵을 캔버스 가로폭에 꽉 차게 확대(배경 크게)."""
        W = self._region()["width"] or self._mm_size[0]
        if W > 0 and self.width() > 0:
            self.set_zoom(self.width() / W)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if getattr(self, "_auto_fit", True):
            self.fit_width()
            # 캔버스 높이를 미니맵 비율에 맞춰 전체 맵이 아래까지 보이게(루프 방지 가드)
            r = self._region()
            W, H = r["width"], r["height"]
            if W > 0 and H > 0 and self.width() > 0:
                need = int(self.width() * H / W)
                if abs(self.minimumHeight() - need) > 4:
                    self.setMinimumHeight(need)

    def wheelEvent(self, ev) -> None:
        self._auto_fit = False        # 수동 줌 시작 → 자동 가로맞춤 해제
        step = 1.1 if ev.angleDelta().y() > 0 else 0.9
        self.set_zoom(self._zoom * step)


class RouteCanvas(MinimapCanvas):
    """미니맵 캔버스 위에 동선 블록을 클릭 배치·드래그 이동하는 편집 캔버스.
    config의 route(같은 키)를 편집하고 on_route_changed로 리스트와 동기화한다."""

    def __init__(self, config, screen_capture,
                 route_keys=("floor_hunt", "route"), on_route_changed=None, **kw):
        super().__init__(config, screen_capture, **kw)
        self._route_keys = route_keys
        self._on_changed = on_route_changed or (lambda: None)
        self._active_type: str | None = None
        self._dragging: int | None = None
        self._drag_last: tuple[int, int] | None = None
        self.on_type_consumed = None   # 블록 1개 배치 후 호출(툴바 '선택 안 함' 복귀용)
        self.sync_unplaced()   # 리스트로만 만든 미배치 블록을 캔버스에 끌어다 놓을 수 있게 staging

    def set_active_type(self, t: str | None) -> None:
        self._active_type = t

    def sync_unplaced(self) -> None:
        """미배치 블록(리스트로만 만든 것)을 좌상단 staging 좌표로 올려 캔버스에서 끌 수 있게 한다.
        리스트 변경(on_change) 시에도 호출 — 새로 추가된 미배치 블록을 자동 노출."""
        from core_ui.minimap_geom import autoplace_unplaced
        w, h = self.minimap_size()
        route = self._route()
        if autoplace_unplaced(route, w, h) > 0:
            self._save_route(route)
        self.update()

    # ── route 입출력 ──────────────────────────────────────────────────
    def _route(self) -> list[dict]:
        return list(self._cfg.get(*self._route_keys, default=[]) or [])

    def _save_route(self, route: list[dict]) -> None:
        from core.navigation.block import Block
        valid = []
        for b in route:
            try:
                Block.from_dict(b); valid.append(b)
            except Exception:
                pass
        self._cfg.set(*self._route_keys, valid)
        self._cfg.save()
        self._on_changed()

    # ── 마우스 로직(테스트 가능한 좌표 단위로 분리) ───────────────────
    def _place_or_select(self, mx: int, my: int) -> None:
        from core_ui.minimap_geom import hit_test, seed_block_at
        W, H = self.minimap_size()
        if W > 0:
            mx = max(0, min(W - 1, mx))
        if H > 0:
            my = max(0, min(H - 1, my))
        route = self._route()
        idx = hit_test(route, mx, my)
        if idx is not None:
            self._dragging = idx
            self._drag_last = (mx, my)
        elif self._active_type is not None:
            route.append(seed_block_at(self._active_type, mx, my))
            self._save_route(route)
            self._active_type = None
            if self.on_type_consumed is not None:   # 툴바 버튼도 '선택 안 함'으로 복귀
                self.on_type_consumed()
        self.update()

    def _drag_to(self, mx: int, my: int) -> None:
        from core_ui.minimap_geom import translate_block
        if self._dragging is None or self._drag_last is None:
            return
        dx = mx - self._drag_last[0]
        dy = my - self._drag_last[1]
        route = self._route()
        route[self._dragging] = translate_block(route[self._dragging], dx, dy)
        self._cfg.set(*self._route_keys, route)   # 드래그 중엔 메모리만(저장 스팸 방지)
        self._drag_last = (mx, my)
        self.update()

    def _end_drag(self) -> None:
        if self._dragging is not None:
            self._save_route(self._route())
            self._dragging = None
            self._drag_last = None
        self.update()

    def mousePressEvent(self, ev) -> None:
        from core_ui.minimap_geom import canvas_to_minimap
        mx, my = canvas_to_minimap(ev.position().x(), ev.position().y(), self._zoom)
        self._place_or_select(mx, my)

    def mouseMoveEvent(self, ev) -> None:
        if self._dragging is None:
            return
        from core_ui.minimap_geom import canvas_to_minimap
        mx, my = canvas_to_minimap(ev.position().x(), ev.position().y(), self._zoom)
        self._drag_to(mx, my)

    def mouseReleaseEvent(self, ev) -> None:
        self._end_drag()

    # ── 렌더 ──────────────────────────────────────────────────────────
    def paintEvent(self, ev) -> None:
        super().paintEvent(ev)        # 배경+노란점+범위
        if self._shot is None:
            return
        from core_ui.minimap_geom import block_anchor, minimap_to_canvas, block_color
        from PyQt6.QtCore import QRectF
        route = self._route()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 1) 굵은 라운드 커넥터(체인) — 실행 순서대로 배치된 앵커를 잇는다
        pts = []
        for b in route:
            a = block_anchor(b)
            if a is not None:
                pts.append(minimap_to_canvas(a[0], a[1], self._zoom))
        if len(pts) >= 2:
            pen = QPen(QColor("#5865f2"), 6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        # 2) 블록 — 이동=가로 캡슐, 사다리=세로 선, 그 외=둥근 점
        for i, b in enumerate(route):
            a = block_anchor(b)
            if a is None:
                continue
            cx, cy = minimap_to_canvas(a[0], a[1], self._zoom)
            col = QColor(block_color(b))
            sel = (i == self._dragging)
            if b.get("type") == "ladder" and int(b.get("y_top", 0)) < int(b.get("y_bot", 0)):
                # 사다리: ladder_x에서 y_top↔y_bot 세로 선
                tx, ty = minimap_to_canvas(int(b["ladder_x"]), int(b["y_top"]), self._zoom)
                _bx, by = minimap_to_canvas(int(b["ladder_x"]), int(b["y_bot"]), self._zoom)
                pen2 = QPen(QColor("#ffffff") if sel else col, 7)
                pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen2)
                p.drawLine(tx, ty, tx, by)
                continue
            p.setPen(QPen(QColor("#ffffff"), 2) if sel else Qt.PenStyle.NoPen)
            p.setBrush(col)
            if b.get("type") == "move" and int(b.get("end_x", 0)) > int(b.get("start_x", 0)):
                sx = minimap_to_canvas(int(b["start_x"]), a[1], self._zoom)[0]
                ex = minimap_to_canvas(int(b["end_x"]), a[1], self._zoom)[0]
                h = 16
                p.drawRoundedRect(QRectF(sx, cy - h / 2, max(float(h), ex - sx), h),
                                  h / 2, h / 2)
            else:
                p.drawEllipse(cx - 8, cy - 8, 16, 16)
