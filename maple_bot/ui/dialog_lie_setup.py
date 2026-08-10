# 거짓말탐지기 전체 스크린샷 위에서 하위 영역을 드래그로 설정하는 다이얼로그
from __future__ import annotations
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QScrollArea, QWidget,
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, pyqtSignal


# ── 하위 영역 정의 ──────────────────────────────────────────────────────────
AREAS = [
    ("region",      "① 감지 영역 (선택)",        QColor(200, 80,  200, 90)),  # 보라
    ("puzzle_area", "② 퍼즐 영역 (빈칸 탐색)",   QColor(255, 80,  80,  90)),  # 빨강
    ("piece_area",  "③ 바  (드래그 범위)",        QColor(80,  200, 80,  90)),  # 초록
    ("next_btn",    "④ >> 버튼",                 QColor(80,  120, 255, 90)),  # 파랑
    ("confirm_btn", "⑤ 확인 버튼",               QColor(255, 200, 50,  90)),  # 노랑
    ("lie_blank",   "⑥ 빈칸 (선택)",             QColor(80,  200, 200, 90)),  # 청록
]
# 완료 팝업 확인(done_btn)은 상황마다 달라 개별 📍 버튼으로 따로 설정
AREA_KEYS   = [k for k, _, _ in AREAS]
AREA_COLORS = {k: c for k, _, c in AREAS}


# ── 이미지 캔버스 ────────────────────────────────────────────────────────────
class ImageCanvas(QLabel):
    """스크린샷을 표시하고 드래그로 영역을 선택할 수 있는 캔버스."""

    region_dragged = pyqtSignal(int, int, int, int)   # x, y, w, h (canvas 좌표)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start = None
        self._drag_cur   = None
        self._active     = False
        self._overlays: list[tuple[int, int, int, int, QColor]] = []
        self.setMouseTracking(True)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setCursor(
            Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor
        )

    def set_overlays(self, overlays: list) -> None:
        self._overlays = overlays
        self.update()

    # ── 마우스 이벤트 ────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if self._active and e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position().toPoint()
            self._drag_cur   = self._drag_start

    def mouseMoveEvent(self, e):
        if self._active and self._drag_start:
            self._drag_cur = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if self._active and self._drag_start and e.button() == Qt.MouseButton.LeftButton:
            end = e.position().toPoint()
            x1 = min(self._drag_start.x(), end.x())
            y1 = min(self._drag_start.y(), end.y())
            x2 = max(self._drag_start.x(), end.x())
            y2 = max(self._drag_start.y(), end.y())
            if x2 - x1 > 3 and y2 - y1 > 3:
                self.region_dragged.emit(x1, y1, x2 - x1, y2 - y1)
            self._drag_start = None
            self._drag_cur   = None
            self.update()

    # ── 렌더링 ───────────────────────────────────────────────────────────
    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # 설정된 오버레이
        for ox, oy, ow, oh, color in self._overlays:
            painter.fillRect(ox, oy, ow, oh, color)
            border = QColor(color.red(), color.green(), color.blue(), 220)
            pen = QPen(border, 2)
            painter.setPen(pen)
            painter.drawRect(ox, oy, ow, oh)

        # 현재 드래그 중 점선 사각형
        if self._drag_start and self._drag_cur:
            x1 = min(self._drag_start.x(), self._drag_cur.x())
            y1 = min(self._drag_start.y(), self._drag_cur.y())
            x2 = max(self._drag_start.x(), self._drag_cur.x())
            y2 = max(self._drag_start.y(), self._drag_cur.y())
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, QColor(255, 255, 255, 50))
            pen = QPen(QColor(255, 255, 255, 220), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        painter.end()


# ── 메인 다이얼로그 ──────────────────────────────────────────────────────────
class LieDetectorSetupDialog(QDialog):
    """거짓말탐지기 캡처 이미지 안에서 하위 영역을 드래그로 한번에 설정."""

    def __init__(
        self,
        full_region: tuple[int, int, int, int],
        screenshot: np.ndarray,           # BGR numpy
        existing: dict,                    # 현재 저장된 좌표들
        parent=None,
    ):
        super().__init__(parent)
        self.full_region  = full_region   # 절대 화면 (x, y, w, h)
        self.result_coords: dict[str, list[int]] = {}  # 저장 결과
        self._img_selected: dict[str, tuple[int, int, int, int]] = {}  # canvas 좌표
        self._active_key: str | None = None

        self.setWindowTitle("거짓말탐지기 퍼즐 좌표 한번에 설정")
        self.setModal(True)

        # 캔버스 크기 계산 (최대 폭 800px)
        src_h, src_w = screenshot.shape[:2]
        CANVAS_W = min(800, src_w)
        CANVAS_H = int(src_h * CANVAS_W / src_w)
        self._scale_x = src_w / CANVAS_W
        self._scale_y = src_h / CANVAS_H

        self._build_ui(screenshot, CANVAS_W, CANVAS_H)
        self._load_existing(existing)

    # ── UI 구성 ──────────────────────────────────────────────────────────
    def _build_ui(self, screenshot: np.ndarray, cw: int, ch: int) -> None:
        self.resize(cw + 280, max(ch + 60, 500))

        outer = QHBoxLayout(self)

        # 왼쪽: 캔버스
        left = QVBoxLayout()
        guide = QLabel("① 오른쪽 버튼을 눌러 영역을 활성화한 뒤  ② 이미지 위에서 드래그하세요")
        guide.setWordWrap(True)
        left.addWidget(guide)

        self._canvas = ImageCanvas()
        self._canvas.setFixedSize(cw, ch)
        pixmap = self._bgr_to_pixmap(screenshot, cw, ch)
        self._canvas.setPixmap(pixmap)
        self._canvas.region_dragged.connect(self._on_drag)
        left.addWidget(self._canvas)
        outer.addLayout(left)

        # 오른쪽: 영역 버튼 + 상태
        right_widget = QWidget()
        right_widget.setFixedWidth(260)
        right = QVBoxLayout(right_widget)
        right.setSpacing(6)

        right.addWidget(QLabel("설정할 영역 (순서대로 진행)"))

        self._area_btns: dict[str, QPushButton] = {}
        self._area_lbls: dict[str, QLabel]      = {}

        for key, title, color in AREAS:
            btn = QPushButton(title)
            btn.setCheckable(True)
            # 버튼 배경색으로 영역 색상 표시
            r, g, b = color.red(), color.green(), color.blue()
            btn.setStyleSheet(
                f"QPushButton:checked {{ background: rgba({r},{g},{b},160); font-weight:bold; }}"
            )
            btn.clicked.connect(lambda _, k=key: self._activate_area(k))
            self._area_btns[key] = btn

            lbl = QLabel("미설정")
            lbl.setStyleSheet("color: gray; font-size: 10px; padding-left:4px;")
            self._area_lbls[key] = lbl

            right.addWidget(btn)
            right.addWidget(lbl)

        right.addStretch()

        note = QLabel("* ① 감지 영역·⑥ 빈칸은 선택 항목입니다.\n  완료 팝업 확인은 개별 📍 버튼으로 따로 설정하세요.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 10px;")
        right.addWidget(note)

        btn_save = QPushButton("저장")
        btn_save.setFixedHeight(32)
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        right.addWidget(btn_save)
        right.addWidget(btn_cancel)

        outer.addWidget(right_widget)

    # ── 기존 좌표 로드 ────────────────────────────────────────────────────
    def _load_existing(self, existing: dict) -> None:
        fx, fy, fw, fh = self.full_region
        for key in AREA_KEYS:
            if key == "lie_blank":
                # 빈칸은 좌표가 아닌 이미지 파일 — 파일 유무만 표시
                import os
                if os.path.exists("templates/lie_blank.png"):
                    self._area_lbls[key].setText("✓ 파일 저장됨 (재설정 가능)")
                    self._area_lbls[key].setStyleSheet("color: green; font-size: 10px; padding-left:4px;")
                continue
            coords = existing.get(key)
            if coords and len(coords) == 4:
                ax, ay, aw, ah = coords
                # 절대 좌표 → canvas 좌표
                ix = int((ax - fx) / self._scale_x)
                iy = int((ay - fy) / self._scale_y)
                iw = int(aw / self._scale_x)
                ih = int(ah / self._scale_y)
                self._img_selected[key] = (ix, iy, iw, ih)
                self.result_coords[key] = list(coords)
                self._area_lbls[key].setText(f"✓ X={ax} Y={ay} W={aw} H={ah}")
                self._area_lbls[key].setStyleSheet("color: green; font-size: 10px; padding-left:4px;")
        self._refresh_overlays()

    # ── 영역 활성화 ───────────────────────────────────────────────────────
    def _activate_area(self, key: str) -> None:
        for k, btn in self._area_btns.items():
            btn.setChecked(k == key)
        self._active_key = key
        self._canvas.set_active(True)

    # ── 드래그 완료 ───────────────────────────────────────────────────────
    def _on_drag(self, ix: int, iy: int, iw: int, ih: int) -> None:
        if not self._active_key:
            return
        key = self._active_key
        fx, fy = self.full_region[0], self.full_region[1]
        abs_x = fx + int(ix * self._scale_x)
        abs_y = fy + int(iy * self._scale_y)
        abs_w = max(1, int(iw * self._scale_x))
        abs_h = max(1, int(ih * self._scale_y))

        self._img_selected[key] = (ix, iy, iw, ih)
        self.result_coords[key] = [abs_x, abs_y, abs_w, abs_h]

        self._area_lbls[key].setText(f"✓ X={abs_x} Y={abs_y} W={abs_w} H={abs_h}")
        self._area_lbls[key].setStyleSheet("color: green; font-size: 10px; padding-left:4px;")

        # 다음 영역 자동 활성화
        idx = AREA_KEYS.index(key)
        if idx + 1 < len(AREA_KEYS):
            self._activate_area(AREA_KEYS[idx + 1])
        else:
            self._canvas.set_active(False)
            self._active_key = None
            for btn in self._area_btns.values():
                btn.setChecked(False)

        self._refresh_overlays()

    # ── 오버레이 갱신 ────────────────────────────────────────────────────
    def _refresh_overlays(self) -> None:
        overlays = []
        for key, (ix, iy, iw, ih) in self._img_selected.items():
            overlays.append((ix, iy, iw, ih, AREA_COLORS[key]))
        self._canvas.set_overlays(overlays)

    # ── 저장 ─────────────────────────────────────────────────────────────
    def _on_save(self) -> None:
        required = ["puzzle_area", "piece_area", "next_btn", "confirm_btn"]
        missing  = [k for k in required if k not in self.result_coords]
        if missing:
            from PyQt6.QtWidgets import QMessageBox
            names = {
                "puzzle_area": "② 퍼즐 영역",
                "piece_area":  "③ 바",
                "next_btn":    "④ >> 버튼",
                "confirm_btn": "⑤ 확인 버튼",
            }
            msg = ", ".join(names.get(k, k) for k in missing)
            QMessageBox.warning(self, "미설정 영역", f"다음 영역이 설정되지 않았습니다:\n{msg}")
            return
        self.accept()

    # ── 유틸 ─────────────────────────────────────────────────────────────
    @staticmethod
    def _bgr_to_pixmap(img: np.ndarray, w: int, h: int) -> QPixmap:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                      rgb.shape[1] * 3, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg).scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
