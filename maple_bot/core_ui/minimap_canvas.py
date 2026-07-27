# 誘몃땲留듭쓣 ?ㅼ떆媛?罹≪쿂??諛곌꼍?쇰줈 源붽퀬 罹먮┃?걔룰났寃??щ깷 踰붿쐞瑜??ъ쁺?섎뒗 罹붾쾭???꾩젽
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
    """誘몃땲留??곸뿭??二쇨린 罹≪쿂??諛곌꼍(?먮━寃?쨌罹먮┃???몃? ??쨌怨듦꺽/?щ깷 踰붿쐞瑜?洹몃┛??
    醫뚰몴??誘몃땲留??쎌? 湲곗?, ?붾㈃ ?쒖떆 ??以?諛곗쑉??怨깊븳??踰붿쐞??以?鍮꾨?).
    罹먮┃??寃異??딄?? tracking?뭠ost(源쒕묀???뭩tale(???④?+諛곗?) ?곹깭濡??쒗쁽?쒕떎."""

    def __init__(self, config, screen_capture, char_finder=find_char_in_hsv,
                 interval_ms: int = 40, screen_w: int = 1920, clock=time.time):
        super().__init__()
        self._cfg = config
        self._capture = screen_capture
        self._find = char_finder
        self._screen_w = screen_w
        self._clock = clock
        self._zoom = 1.0
        self._last_char: tuple[int, int] | None = None
        self._last_seen: float | None = None    # 留덉?留??깃났 寃異??쒓컖
        self._shot: QImage | None = None
        self._mm_size = (0, 0)        # (W_mm, H_mm)
        self.setMinimumHeight(340)
        self._auto_fit = True         # 媛濡쒗룺 ?먮룞留욎땄(諛곌꼍 ?뺣?), ??以????댁젣
        self._monster_provider = None  # () -> [(dx,dy)] 罹먮┃ 湲곗? ?붾㈃px ?ㅽ봽??
        self._character_provider = None
        self._monsters_rel: list = []  # 理쒓렐 ?먯? 罹먯떆
        self._mon_last = 0.0           # 留덉?留??먯? ?쒓컖(?ㅻ줈?)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)

    def _char_hsv(self):
        """?ㅼ젙 罹먮┃?곗깋(char_r/g/b)?믩뒓?⑦븳 HSV 踰붿쐞. ?놁쑝硫?湲곕낯 ?몃옉."""
        c = self._cfg
        r = c.get("minimap", "char_r", default=None)
        g = c.get("minimap", "char_g", default=None)
        b = c.get("minimap", "char_b", default=None)
        if None in (r, g, b) or (int(r), int(g), int(b)) == (255, 255, 255):
            r, g, b = 255, 255, 0
        if None in (r, g, b):
            return ((20, 100, 200), (40, 255, 255))
        from core.sensing.char_scanner import hsv_range_from_rgb
        return hsv_range_from_rgb(int(r), int(g), int(b))

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
        """誘몃땲留?(W,H) ??_region 湲곕컲?대씪 ??대㉧ ???꾩뿉???좏슚(?대옩?꾩슜)."""
        r = self._region()
        return (r["width"], r["height"])

    def set_monster_provider(self, fn) -> None:
        """紐ъ뒪???ㅽ봽??怨듦툒???깅줉(遊??고???. None?대㈃ ???쒖떆 ????"""
        self._monster_provider = fn

    def set_character_provider(self, fn) -> None:
        """실행 스캐너가 보관한 최신 캐릭터 좌표를 미리보기에 공급한다."""
        self._character_provider = fn

    def track_state(self) -> str:
        """?꾩옱 罹먮┃??異붿쟻 ?곹깭: tracking | lost | stale (??踰덈룄 寃異??꾩씠硫?stale)."""
        if self._last_seen is None:
            return "stale"
        return char_track_state(self._clock() - self._last_seen)

    def _tick(self) -> None:
        if self._character_provider is not None:
            try:
                live_pos = self._character_provider()
            except Exception:
                live_pos = None
            if live_pos is not None:
                self._last_char = live_pos
                self._last_seen = self._clock()

        # 활성화된 설정 창을 다시 캡처해 노란 표시를 캐릭터로 오인하지 않는다.
        if self.window().isActiveWindow():
            self.update()
            return
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
        if self._character_provider is None:
            lo, hi = self._char_hsv()
            pos = self._find(bgr, lo, hi, 6, 4000)
            if pos is not None:
                self._last_char = pos
                self._last_seen = self._clock()
        # 紐ъ뒪???먯?(?뚰듃?곸뿭, 臾닿굅?곕땲 0.3珥??ㅻ줈?) ??罹먮┃ 湲곗? ?ㅽ봽??罹먯떆
        if self._monster_provider is not None and self._clock() - self._mon_last > 0.3:
            self._mon_last = self._clock()
            try:
                self._monsters_rel = list(self._monster_provider() or [])
            except Exception:
                self._monsters_rel = []
        h, w = bgr.shape[:2]
        self._mm_size = (w, h)
        if self._auto_fit:
            self.fit_width()          # 罹≪쿂 ??湲곗? 媛濡?苑?梨꾩슦湲?諛곌꼍 ?뺣?)
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        self._shot = QImage(rgb.data, w, h, 3 * w,
                            QImage.Format.Format_RGB888).copy()
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0d0e10"))
        if self._shot is None:
            self._hint(p, "?곌껐쨌?몄떇?먯꽌 誘몃땲留??곸뿭??癒쇱? 吏?뺥븯?몄슂")
            return
        W, H = self._mm_size
        p.setOpacity(0.30)
        p.drawImage(QRectF(0, 0, W * self._zoom, H * self._zoom), self._shot)
        p.setOpacity(1.0)
        state = self.track_state()
        if self._last_char is None or state == "stale":
            self._hint(p, "캐릭터를 아직 감지하지 못했습니다")
            return
        cx, cy = minimap_to_canvas(self._last_char[0], self._last_char[1], self._zoom)
        self._draw_ranges(p, cx, cy)
        self._draw_monsters(p, cx, cy)
        if state == "lost":
            # 泥쒖쿇??源쒕묀??0.8珥?二쇨린) ??'?쇱떆???딄?' ?곹솴 ?몄?
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
        p.setPen(QPen(QColor("#4d7cff"), 1.4, Qt.PenStyle.DashLine))   # ?щ깷
        p.drawRect(int(cx - hxw), int(cy - hyh), int(hxw * 2), int(hyh * 2))
        p.setPen(QPen(QColor("#f04452"), 1.4, Qt.PenStyle.DashLine))   # 怨듦꺽
        p.drawRect(int(cx - axw), int(cy - ayh), int(axw * 2), int(ayh * 2))

    def _draw_monsters(self, p: QPainter, cx: int, cy: int) -> None:
        """?먯???紐ъ뒪?곕? 罹먮┃ 湲곗? ?ㅽ봽?뗭쑝濡?誘몃땲留?異뺤쿃 ?섏궛??鍮④컙 ?먯쑝濡??쒖떆."""
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
        """以?諛곗쑉 ?ㅼ젙(0.5~8.0 ?대옩??."""
        self._zoom = max(0.5, min(8.0, zoom))
        self.update()

    def fit(self) -> None:
        """誘몃땲留??꾩껜媛 罹붾쾭?ㅼ뿉 ?ㅼ뼱?ㅻ룄濡?以?留욎땄."""
        W, H = self._mm_size
        if W > 0 and H > 0 and self.width() > 0 and self.height() > 0:
            self.set_zoom(min(self.width() / W, self.height() / H))

    def fit_width(self) -> None:
        """誘몃땲留듭쓣 罹붾쾭??媛濡쒗룺??苑?李④쾶 ?뺣?(諛곌꼍 ?ш쾶)."""
        W = self._region()["width"] or self._mm_size[0]
        if W > 0 and self.width() > 0:
            self.set_zoom(self.width() / W)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if getattr(self, "_auto_fit", True):
            self.fit_width()
            # 罹붾쾭???믪씠瑜?誘몃땲留?鍮꾩쑉??留욎떠 ?꾩껜 留듭씠 ?꾨옒源뚯? 蹂댁씠寃?猷⑦봽 諛⑹? 媛??
            r = self._region()
            W, H = r["width"], r["height"]
            if W > 0 and H > 0 and self.width() > 0:
                need = int(self.width() * H / W)
                if abs(self.minimumHeight() - need) > 4:
                    self.setMinimumHeight(need)

    def wheelEvent(self, ev) -> None:
        self._auto_fit = False        # ?섎룞 以??쒖옉 ???먮룞 媛濡쒕쭪異??댁젣
        step = 1.1 if ev.angleDelta().y() > 0 else 0.9
        self.set_zoom(self._zoom * step)


class RouteCanvas(MinimapCanvas):
    """誘몃땲留?罹붾쾭???꾩뿉 ?숈꽑 釉붾줉???대┃ 諛곗튂쨌?쒕옒洹??대룞?섎뒗 ?몄쭛 罹붾쾭??
    config??route(媛숈? ??瑜??몄쭛?섍퀬 on_route_changed濡?由ъ뒪?몄? ?숆린?뷀븳??"""

    def __init__(self, config, screen_capture,
                 route_keys=("floor_hunt", "route_steps"), on_route_changed=None, **kw):
        super().__init__(config, screen_capture, **kw)
        self._route_keys = route_keys
        self._on_changed = on_route_changed or (lambda: None)
        self._active_type: str | None = None
        self._dragging: int | None = None
        self._drag_last: tuple[int, int] | None = None
        self.on_type_consumed = None
        self._ladder_state_provider = None
        self.sync_unplaced()

    def set_ladder_state_provider(self, fn) -> None:
        self._ladder_state_provider = fn

    def set_active_type(self, t: str | None) -> None:
        self._active_type = t

    def sync_unplaced(self) -> None:
        """誘몃같移?釉붾줉(由ъ뒪?몃줈留?留뚮뱺 寃???醫뚯긽??staging 醫뚰몴濡??щ젮 罹붾쾭?ㅼ뿉???????덇쾶 ?쒕떎.
        由ъ뒪??蹂寃?on_change) ?쒖뿉???몄텧 ???덈줈 異붽???誘몃같移?釉붾줉???먮룞 ?몄텧."""
        from core_ui.minimap_geom import autoplace_unplaced
        w, h = self.minimap_size()
        route = self._route()
        if autoplace_unplaced(route, w, h) > 0:
            self._save_route(route)
        self.update()

    # ?? route ?낆텧????????????????????????????????????????????????????
    def _route(self) -> list[dict]:
        return list(self._cfg.get(*self._route_keys, default=[]) or [])

    def _save_route(self, route: list[dict]) -> None:
        from core.navigation.route_state import RouteStep
        valid = []
        for b in route:
            try:
                valid.append(RouteStep.from_dict(b).to_dict())
            except Exception:
                pass
        self._cfg.set(*self._route_keys, valid)
        self._cfg.save()
        self._on_changed()

    # ?? 留덉슦??濡쒖쭅(?뚯뒪??媛?ν븳 醫뚰몴 ?⑥쐞濡?遺꾨━) ???????????????????
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
            if self.on_type_consumed is not None:   # ?대컮 踰꾪듉??'?좏깮 ?????쇰줈 蹂듦?
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
        self._cfg.set(*self._route_keys, route)   # ?쒕옒洹?以묒뿏 硫붾え由щ쭔(????ㅽ뙵 諛⑹?)
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

    # ?? ?뚮뜑 ??????????????????????????????????????????????????????????
    def paintEvent(self, ev) -> None:
        super().paintEvent(ev)        # 諛곌꼍+?몃???踰붿쐞
        if self._shot is None:
            return
        from core_ui.minimap_geom import block_anchor, minimap_to_canvas, block_color
        from PyQt6.QtCore import QRectF
        route = self._route()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ladder_state = None
        if self._ladder_state_provider is not None:
            try:
                ladder_state = self._ladder_state_provider()
            except Exception:
                ladder_state = None
        if ladder_state and ladder_state.get("character_x") is not None:
            character_y = int(ladder_state.get("character_y", 0))
            lx, ly = minimap_to_canvas(int(ladder_state["ladder_x"]), character_y, self._zoom)
            cx, cy = minimap_to_canvas(int(ladder_state["character_x"]), character_y, self._zoom)
            phase = str(ladder_state.get("phase", "APPROACH"))
            color = "#35d07f" if phase in ("JUMP_GRAB", "VERIFY_GRAB", "CLIMB") else (
                "#ffd33d" if phase == "STABILIZE" else "#f0a43c")
            p.setPen(QPen(QColor(color), 3))
            p.drawLine(cx, cy, lx, ly)
        # 1) 援듭? ?쇱슫??而ㅻ꽖??泥댁씤) ???ㅽ뻾 ?쒖꽌?濡?諛곗튂???듭빱瑜??뉖뒗??
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
        # 2) 釉붾줉 ???대룞=媛濡?罹≪뒓, ?щ떎由??몃줈 ?? 洹????κ렐 ??
        for i, b in enumerate(route):
            a = block_anchor(b)
            if a is None:
                continue
            cx, cy = minimap_to_canvas(a[0], a[1], self._zoom)
            col = QColor(block_color(b))
            sel = (i == self._dragging)
            if b.get("type") == "ladder" and int(b.get("y_top", 0)) < int(b.get("y_bot", 0)):
                # ?щ떎由? ladder_x?먯꽌 y_top?봸_bot ?몃줈 ??
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


