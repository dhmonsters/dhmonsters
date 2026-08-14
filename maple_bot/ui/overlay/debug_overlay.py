# 게임 화면 위에 띄우는 클릭 통과 투명 디버그 오버레이
from __future__ import annotations

import ctypes

from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtWidgets import QWidget

# Windows API 상수
_WDA_EXCLUDEFROMCAPTURE = 0x00000011   # Win10 2004+ — 화면 캡처에서 창을 제외
_WDA_NONE               = 0x00000000   # 기본값 (캡처 포함)


class DebugOverlay(QWidget):
    """게임 화면 위에 고정되는 클릭 통과 투명 오버레이.

    GameState를 30ms 주기로 읽어 미니맵 위치, HUD 텍스트, 몬스터 박스를 그린다.

    Args:
        game_state: BotLoop.game_state (공유 상태 객체).
        config:     ConfigManager 인스턴스 (게임 창 영역 설정 참조).
        parent:     부모 위젯 (기본 None).
    """

    _REFRESH_MS = 33   # ~30 FPS

    def __init__(self, game_state, config, parent=None) -> None:
        super().__init__(parent)
        self._gs = game_state
        self._config = config
        self._roi_manager = None   # 선택적 ROIManager (set_roi_manager로 주입)
        self._alpha = 220          # 텍스트/선 기본 불투명도
        self._show_minimap = True
        self._show_hud = True
        self._show_monster = True
        self._show_roi = True             # ROI 경계 박스 표시 여부
        self._show_attack_range = True    # 공격 범위 박스 표시 여부

        # ── 윈도우 플래그: 클릭 통과 + 항상 위 + 제목 없음 ──────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # ── 타이머 → repaint ─────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(self._REFRESH_MS)

        self._update_geometry()

    # ── 공개 제어 ──────────────────────────────────────────────────────────
    def set_alpha(self, value: int) -> None:
        """오버레이 불투명도 설정 (0~255)."""
        self._alpha = max(0, min(255, value))

    def set_show(self, *, minimap: bool | None = None,
                 hud: bool | None = None, monster: bool | None = None,
                 roi: bool | None = None,
                 attack_range: bool | None = None) -> None:
        """표시 항목 ON/OFF."""
        if minimap is not None:
            self._show_minimap = minimap
        if hud is not None:
            self._show_hud = hud
        if monster is not None:
            self._show_monster = monster
        if roi is not None:
            self._show_roi = roi
        if attack_range is not None:
            self._show_attack_range = attack_range

    def set_roi_manager(self, roi_manager) -> None:
        """ROIManager를 주입해 ROI 경계 박스 표시를 활성화한다."""
        self._roi_manager = roi_manager

    def refresh_geometry(self) -> None:
        """게임 창 위치가 변경되었을 때 오버레이 크기·위치를 갱신한다."""
        self._update_geometry()

    # ── Qt 이벤트 ──────────────────────────────────────────────────────────
    def showEvent(self, event) -> None:  # noqa: N802
        """창이 표시될 때 화면 캡처 제외 플래그를 적용한다."""
        super().showEvent(event)
        self._apply_capture_exclusion()

    # ── 그리기 ────────────────────────────────────────────────────────────
    def paintEvent(self, _) -> None:  # noqa: N802
        # snapshot()으로 락 보유 중 한 번에 읽어 동시성 문제 방지
        snap = self._gs.snapshot()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._show_roi and self._roi_manager is not None:
            self._draw_roi_boxes(p)
        if self._show_hud:
            self._draw_hud(p, snap)
        if self._show_minimap:
            self._draw_minimap_panel(p, snap)
        if self._show_monster:
            self._draw_monsters(p, snap)
        if self._show_attack_range:
            self._draw_attack_range(p, snap)

        p.end()

    # ── HUD 텍스트 (좌상단) ───────────────────────────────────────────────
    def _draw_hud(self, p: QPainter, snap: dict) -> None:
        font = QFont("Consolas", 10, QFont.Weight.Bold)
        p.setFont(font)

        det_fps  = snap.get("detection_fps", 0.0)
        det_conf = snap.get("detection_confidence", 0.0)
        route_action = snap.get("route_action", "")

        lines = [
            f"Cap FPS: {snap.get('capture_fps', 0.0):.0f}  Det FPS: {det_fps:.0f}",
            f"State: {snap.get('bot_state', '-')}  Nav: {snap.get('nav_state', '-')}",
            f"HP: {snap.get('hp_ratio', 0.0):.0%}  MP: {snap.get('mp_ratio', 0.0):.0%}",
            f"Pos: {snap.get('char_pos')}  Conf: {det_conf:.2f}",
            f"Action: {route_action[:50]}" if route_action else "",
        ]

        x, y = 10, 20
        for line in lines:
            if not line:
                y += 4
                continue
            # 그림자
            p.setPen(QColor(0, 0, 0, self._alpha))
            p.drawText(x + 1, y + 1, line)
            # 본문
            p.setPen(QColor(255, 255, 80, self._alpha))
            p.drawText(x, y, line)
            y += 18

    # ── 미니맵 패널 (우상단) ──────────────────────────────────────────────
    def _draw_minimap_panel(self, p: QPainter, snap: dict) -> None:
        mm_cfg = self._get_minimap_config()
        if mm_cfg is None:
            return

        rx, ry, rw, rh = mm_cfg
        if rw <= 0 or rh <= 0:
            return

        # 미니맵 영역 테두리
        pen = QPen(QColor(100, 200, 255, self._alpha), 1)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(0, 0, 0, 60)))
        p.drawRect(rx, ry, rw, rh)

        # ── 카메라 가시 범위 (노란 반투명 박스 + 경계 수직선) ─────────
        cam_rect = snap.get("camera_rect_on_minimap")
        if cam_rect is not None:
            cam_left, cam_right = cam_rect
            cam_l = rx + cam_left
            cam_r = rx + cam_right
            # 반투명 배경
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 220, 0, 18)))
            p.drawRect(cam_l, ry, cam_r - cam_l, rh)
            # 경계 수직선 (노란 점선)
            pen_cam = QPen(QColor(255, 220, 0, 160), 1, Qt.PenStyle.DashLine)
            p.setPen(pen_cam)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(cam_l, ry, cam_l, ry + rh)
            p.drawLine(cam_r, ry, cam_r, ry + rh)

        # ── 이동 경로 trail (밝은 파란 선) ───────────────────────────
        path = snap.get("char_path", [])
        if len(path) >= 2:
            pen_trail = QPen(QColor(100, 180, 255, 150), 1)
            p.setPen(pen_trail)
            for i in range(1, len(path)):
                ax, ay = rx + path[i - 1][0], ry + path[i - 1][1]
                bx, by = rx + path[i][0],     ry + path[i][1]
                p.drawLine(ax, ay, bx, by)

        # ── 캐릭터 위치 — 부드러운 좌표 우선, 없으면 원시 좌표 ────────
        pos = snap.get("char_pos_smooth") or snap.get("char_pos")
        if pos:
            cx = rx + pos[0]
            cy = ry + pos[1]
            # 빨간 점 (반지름 3)
            p.setPen(QPen(QColor(255, 60, 60, self._alpha), 2))
            p.setBrush(QBrush(QColor(255, 60, 60, self._alpha)))
            p.drawEllipse(QPoint(cx, cy), 3, 3)

    # ── 몬스터 박스 ───────────────────────────────────────────────────────
    def _draw_monsters(self, p: QPainter, snap: dict) -> None:
        positions = snap.get("monster_positions") or []
        if not positions:
            return

        font = QFont("Consolas", 8, QFont.Weight.Bold)
        p.setFont(font)
        pen = QPen(QColor(80, 255, 80, self._alpha), 2)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(80, 255, 80, 20)))

        for x, y in positions:
            p.drawEllipse(QPoint(x, y), 6, 6)

    # ── 공격 범위 박스 ────────────────────────────────────────────────────
    def _draw_attack_range(self, p: QPainter, snap: dict) -> None:
        """char_y_ratio 기준으로 공격 범위를 그린다."""
        atk_cfg   = self._config.get("attack") or {}
        atk_range = int(atk_cfg.get("range_px", 150))
        box_h     = int(atk_cfg.get("box_h",    120))

        # 캐릭터 화면 좌표
        char_screen = snap.get("character_screen_pos")
        if char_screen is not None:
            gx = int(char_screen[0])
            gy = int(char_screen[1])
        else:
            ov_w = self.width()
            ov_h = self.height()
            gx = ov_w // 2 + int(atk_cfg.get("char_offset_x", 0))
            gy = int(ov_h * float(atk_cfg.get("char_y_ratio", 0.6))) + int(atk_cfg.get("char_offset_y", 0))

        p.setPen(QPen(QColor(255, 60, 60, self._alpha), 1, Qt.PenStyle.DashLine))
        p.setBrush(QBrush(QColor(255, 60, 60, 30)))
        p.drawRect(gx - atk_range, gy - box_h // 2, atk_range, box_h)
        p.drawRect(gx,             gy - box_h // 2, atk_range, box_h)
        p.setPen(QPen(QColor(255, 200, 0, self._alpha), 1))
        p.drawLine(gx, gy - box_h // 2, gx, gy + box_h // 2)

    # ── ROI 경계 박스 ─────────────────────────────────────────────────────
    def _draw_roi_boxes(self, p: QPainter) -> None:
        """등록된 모든 ROI를 색상별 점선 사각형으로 표시한다.
        오버레이 좌표계는 game_region 좌상단이 (0,0)이므로 offset을 빼서 변환한다.
        """
        # game_region offset 계산
        try:
            region = self._config.get("settings1", "game_region")
            ox = int(region[0]) if region and len(region) == 4 else 0
            oy = int(region[1]) if region and len(region) == 4 else 0
        except Exception:
            ox, oy = 0, 0

        # ROI 이름별 색상
        _color_map = {
            "game_screen": QColor(255, 255, 0, 180),   # 노란색
            "minimap":     QColor(100, 200, 255, 200),  # 파란색
            "hp_bar":      QColor(255, 80, 80, 200),    # 빨간색
            "mp_bar":      QColor(80, 80, 255, 200),    # 파란색
        }
        _default_color = QColor(200, 200, 200, 160)

        for name in self._roi_manager.all_names():
            rect = self._roi_manager.get_roi(name)
            if rect is None or not rect.valid:
                continue
            color = _color_map.get(name, _default_color)
            pen = QPen(color, 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            # 오버레이 기준 좌표로 변환
            draw_x = rect.left  - ox
            draw_y = rect.top   - oy
            p.drawRect(draw_x, draw_y, rect.width, rect.height)
            # 이름 라벨
            p.setPen(QPen(color, 1))
            p.drawText(draw_x + 2, draw_y - 2, name)

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────
    def _apply_capture_exclusion(self) -> None:
        """오버레이 창을 mss/BitBlt 화면 캡처에서 제외한다 (Win10 2004+).
        이를 적용하면 오버레이가 게임 화면 캡처(미니맵 색상 감지 등)에 영향을 주지 않는다.
        """
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass  # 구버전 Windows에서는 무시

    def _update_geometry(self) -> None:
        """오버레이를 게임 창 영역에 맞춘다."""
        try:
            region = self._config.get("settings1", "game_region")
        except Exception:
            region = None

        if region and len(region) == 4:
            self.setGeometry(int(region[0]), int(region[1]),
                             int(region[2]), int(region[3]))
        else:
            # 설정 없으면 주 모니터 전체
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                self.setGeometry(geo)

    def _get_minimap_config(self):
        """(region_x, region_y, width, height) 또는 None 반환."""
        try:
            mm = self._config.get("minimap") or {}
            rx = int(mm.get("region_x", 0))
            ry = int(mm.get("region_y", 0))
            rw = int(mm.get("width", 0))
            rh = int(mm.get("height", 0))
            if rw > 0 and rh > 0:
                return rx, ry, rw, rh
        except Exception:
            pass
        return None
