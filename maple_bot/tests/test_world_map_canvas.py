# 오프스크린 전역 지도 캔버스의 좌표 선택을 검증하는 테스트
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from core_ui.world_map_canvas import WorldMapCanvas


def test_canvas_click_emits_world_coordinate():
    app = QApplication.instance() or QApplication([])
    canvas = WorldMapCanvas()
    canvas.resize(400, 200)
    canvas.set_world_size(800, 400)
    points = []
    canvas.selected_world_point.connect(lambda x, y: points.append((x, y)))

    canvas.select_canvas_point(QPoint(200, 100))

    assert points == [(400.0, 200.0)]
