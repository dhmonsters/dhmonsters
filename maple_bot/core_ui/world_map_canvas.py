# 큰 지도 위에 전역 노드와 현재 뷰포트 및 캐릭터 위치를 표시하는 캔버스
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class WorldMapCanvas(QWidget):
    selected_world_point = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._world_size = (0, 0)
        self._tool = None
        self._viewport = None
        self._character = None
        self._nodes = []
        self._edges = []
        self._zones = []
        self.setMinimumHeight(180)

    def set_image(self, path: str):
        self._pixmap = QPixmap(path)
        if not self._pixmap.isNull():
            self.set_world_size(self._pixmap.width(), self._pixmap.height())
        self.update()

    def set_world_size(self, width: int, height: int):
        self._world_size = (width, height)
        self.update()

    def set_tool(self, tool: str | None):
        self._tool = tool

    def set_data(self, nodes, edges, zones):
        self._nodes = list(nodes or [])
        self._edges = list(edges or [])
        self._zones = list(zones or [])
        self.update()

    def set_viewport(self, origin, size, state):
        self._viewport = (origin, size, state)
        self.update()

    def set_character(self, position):
        self._character = position
        self.update()

    def _point(self, x, y):
        width, height = self._world_size
        if width <= 0 or height <= 0:
            return QPointF()
        return QPointF(x * self.width() / width, y * self.height() / height)

    def select_canvas_point(self, point):
        width, height = self._world_size
        if width <= 0 or height <= 0 or self.width() <= 0 or self.height() <= 0:
            return
        self.selected_world_point.emit(
            point.x() * width / self.width(),
            point.y() * height / self.height(),
        )

    def mousePressEvent(self, event):
        self.select_canvas_point(event.position().toPoint())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#17212b"))
        if not self._pixmap.isNull():
            painter.drawPixmap(self.rect(), self._pixmap)
        node_by_id = {node.get("id"): node for node in self._nodes}
        painter.setPen(QPen(QColor("#66c2a5"), 2))
        for edge in self._edges:
            left = node_by_id.get(edge.get("from_id"))
            right = node_by_id.get(edge.get("to_id"))
            if left and right:
                painter.drawLine(
                    self._point(left["x"], left["y"]),
                    self._point(right["x"], right["y"]),
                )
        for node in self._nodes:
            color = QColor("#ff9f43") if node.get("kind") == "action" else QColor("#5dade2")
            painter.setBrush(color)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawEllipse(self._point(node["x"], node["y"]), 5, 5)
        if self._viewport is not None:
            origin, size, state = self._viewport
            top_left = self._point(origin[0], origin[1])
            bottom_right = self._point(origin[0] + size[0], origin[1] + size[1])
            pen = QPen(QColor("#2ecc71") if state == "confirmed" else QColor("#f1c40f"), 2)
            pen.setStyle(Qt.PenStyle.SolidLine if state == "confirmed" else Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(
                int(top_left.x()), int(top_left.y()),
                int(bottom_right.x() - top_left.x()),
                int(bottom_right.y() - top_left.y()),
            )
        if self._character is not None:
            painter.setBrush(QColor("#e74c3c"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self._point(*self._character), 6, 6)
