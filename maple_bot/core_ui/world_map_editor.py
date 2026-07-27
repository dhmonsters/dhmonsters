# 큰 지도 보정과 노드·루트·이미지 트리거 설정을 관리하는 편집 패널
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.navigation.world_map import WorldPoint, calibrate_two_points
from core_ui.world_map_canvas import WorldMapCanvas


class WorldMapEditor(QWidget):
    destination_requested = pyqtSignal(str)
    route_start_requested = pyqtSignal(str)

    def __init__(self, config, screen_capture=None, parent=None):
        super().__init__(parent)
        self.setObjectName("worldMapEditor")
        self._cfg = config
        self._capture = screen_capture
        self._world_points = []
        self._local_points = []
        self._edit_tool = "calibration"
        self._connect_from_id = None
        self._position_fn = lambda: None
        self._tracking_state_fn = lambda: "unavailable"
        self._viewport_fn = lambda: None
        self._runtime_timer = QTimer(self)
        self._runtime_timer.timeout.connect(self._refresh_runtime)
        self._local_timer = QTimer(self)
        self._local_timer.timeout.connect(self._refresh_local_capture)
        self._build_ui()
        self.reload()
        if self._capture is not None:
            self._refresh_local_capture()
            self._local_timer.start(250)

    def _build_ui(self):
        root = QHBoxLayout(self)
        self._canvas = WorldMapCanvas(self)
        self._canvas.selected_world_point.connect(self._on_world_point)
        root.addWidget(self._canvas, 3)

        side = QVBoxLayout()
        choose_map = QPushButton("큰 지도 이미지 선택")
        choose_map.setObjectName("worldMapImageButton")
        choose_map.clicked.connect(self._choose_world_map_image)
        side.addWidget(choose_map)
        tool_row = QHBoxLayout()
        for label, tool in (
            ("보정점", "calibration"),
            ("이동점", "waypoint"),
            ("액션점", "action"),
            ("연결", "connect"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, name=tool: self.set_edit_tool(name))
            tool_row.addWidget(button)
        side.addLayout(tool_row)
        side.addWidget(QLabel("전역 지도 편집"))
        self._calibration_status = QLabel("보정 순서 · 큰 지도 점 → 같은 미니맵 점을 2회 선택")
        side.addWidget(self._calibration_status)
        side.addWidget(QLabel("미니맵 미리보기"))
        self._local_preview = QLabel("미니맵 영역을 먼저 설정하세요")
        self._local_preview.setMinimumSize(240, 120)
        self._local_preview.setMaximumHeight(180)
        self._local_preview.setScaledContents(True)
        self._local_preview.mousePressEvent = self._local_preview_clicked
        side.addWidget(self._local_preview)
        apply_calibration = QPushButton("2점 보정 적용")
        apply_calibration.clicked.connect(self._apply_calibration_from_ui)
        side.addWidget(apply_calibration)
        self._nodes = QListWidget()
        self._routes = QListWidget()
        side.addWidget(QLabel("노드"))
        side.addWidget(self._nodes)
        side.addWidget(QLabel("루트"))
        side.addWidget(self._routes)
        go = QPushButton("선택 노드로 이동")
        go.clicked.connect(self._request_destination)
        run = QPushButton("선택 루트 시작")
        run.clicked.connect(self._request_route)
        side.addWidget(go)
        side.addWidget(run)

        form = QFormLayout()
        self._trigger_enabled = QCheckBox()
        self._template_path = QLineEdit()
        template_row = QHBoxLayout()
        template_row.addWidget(self._template_path, 1)
        capture_template = QPushButton("화면 캡처")
        capture_template.clicked.connect(self._capture_trigger_template)
        template_row.addWidget(capture_template)
        choose_template = QPushButton("찾기")
        choose_template.clicked.connect(self._choose_trigger_template)
        template_row.addWidget(choose_template)
        self._threshold = QDoubleSpinBox(); self._threshold.setRange(0, 1); self._threshold.setValue(0.8)
        self._check_interval = QDoubleSpinBox(); self._check_interval.setRange(0, 60); self._check_interval.setValue(0.1)
        self._cooldown = QDoubleSpinBox(); self._cooldown.setRange(0, 3600); self._cooldown.setValue(2.0)
        self._action_type = QComboBox()
        self._action_type.addItem("키 입력", "key")
        self._action_type.addItem("마우스 클릭", "click")
        self._action_key = QLineEdit("space")
        self._click_x = QSpinBox(); self._click_x.setRange(-10000, 10000)
        self._click_y = QSpinBox(); self._click_y.setRange(-10000, 10000)
        self._hold_sec = QDoubleSpinBox(); self._hold_sec.setRange(0, 30); self._hold_sec.setValue(0.1)
        self._repeat = QSpinBox(); self._repeat.setRange(1, 100); self._repeat.setValue(1)
        self._repeat_interval = QDoubleSpinBox(); self._repeat_interval.setRange(0, 60)
        self._wait_after = QDoubleSpinBox(); self._wait_after.setRange(0, 60)
        form.addRow("이미지 감지", self._trigger_enabled)
        form.addRow("템플릿", template_row)
        form.addRow("유사도", self._threshold)
        form.addRow("감지 주기", self._check_interval)
        form.addRow("쿨다운", self._cooldown)
        form.addRow("액션 방식", self._action_type)
        form.addRow("액션 키", self._action_key)
        form.addRow("화면 X", self._click_x)
        form.addRow("화면 Y", self._click_y)
        form.addRow("누름 시간", self._hold_sec)
        form.addRow("반복", self._repeat)
        form.addRow("반복 간격", self._repeat_interval)
        form.addRow("실행 후 대기", self._wait_after)
        side.addLayout(form)
        save_trigger = QPushButton("이미지 액션 저장")
        save_trigger.clicked.connect(self._save_trigger_from_ui)
        side.addWidget(save_trigger)
        root.addLayout(side, 1)

    def reload(self):
        world = self._cfg.get("world_map", default={}) or {}
        if world.get("image_path"):
            self._canvas.set_image(world["image_path"])
        else:
            self._canvas.set_world_size(
                int(world.get("image_width", 0)), int(world.get("image_height", 0))
            )
        nodes = self._cfg.get("navigation", "nodes", default=[]) or []
        edges = self._cfg.get("navigation", "edges", default=[]) or []
        routes = self._cfg.get("navigation", "routes", default=[]) or []
        zones = self._cfg.get("zones", default=[]) or []
        self._canvas.set_data(nodes, edges, zones)
        self._nodes.clear()
        for node in nodes:
            self._nodes.addItem(f"{node.get('id')} · {node.get('label', node.get('kind'))}")
            self._nodes.item(self._nodes.count() - 1).setData(0x0100, node.get("id"))
        self._routes.clear()
        for route in routes:
            self._routes.addItem(route.get("name", route.get("id")))
            self._routes.item(self._routes.count() - 1).setData(0x0100, route.get("id"))
        trigger = self._cfg.get("attack", "image_trigger", default={}) or {}
        action = trigger.get("action", {}) or {}
        self._trigger_enabled.setChecked(bool(trigger.get("enabled", False)))
        self._template_path.setText(str(trigger.get("template_path", "")))
        self._threshold.setValue(float(trigger.get("threshold", 0.8)))
        self._check_interval.setValue(float(trigger.get("check_interval_sec", 0.1)))
        self._cooldown.setValue(float(trigger.get("cooldown_sec", 2.0)))
        action_index = self._action_type.findData(action.get("action_type", "key"))
        self._action_type.setCurrentIndex(max(0, action_index))
        self._action_key.setText(str(action.get("key", "space")))
        self._click_x.setValue(int(action.get("click_x", 0) or 0))
        self._click_y.setValue(int(action.get("click_y", 0) or 0))
        self._hold_sec.setValue(float(action.get("hold_sec", 0.1)))
        self._repeat.setValue(int(action.get("repeat", 1)))
        self._repeat_interval.setValue(float(action.get("repeat_interval_sec", 0.0)))
        self._wait_after.setValue(float(action.get("wait_after_sec", 0.0)))

    def _choose_trigger_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 템플릿 선택", "", "이미지 (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self._template_path.setText(path)

    def _capture_trigger_template(self):
        try:
            import os
            import cv2
            import mss
            import numpy as np
            from core_ui.shot_selector import ScreenshotRegionSelector

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                frame = np.array(sct.grab(monitor))[:, :, :3]
                origin = (int(monitor["left"]), int(monitor["top"]))

            selector = ScreenshotRegionSelector(frame, src_origin=origin, parent=self)

            def save_template(x, y, width, height):
                try:
                    left = max(0, int(x - origin[0]))
                    top = max(0, int(y - origin[1]))
                    right = min(frame.shape[1], left + int(width))
                    bottom = min(frame.shape[0], top + int(height))
                    crop = frame[top:bottom, left:right]
                    if crop.size == 0:
                        raise ValueError("캡처 영역이 비어 있습니다.")
                    folder = os.path.join("templates", "image_actions")
                    os.makedirs(folder, exist_ok=True)
                    index = 1
                    while True:
                        path = os.path.join(folder, f"trigger_{index:03d}.png")
                        if not os.path.exists(path):
                            break
                        index += 1
                    ok, encoded = cv2.imencode(".png", crop)
                    if not ok:
                        raise ValueError("이미지 변환에 실패했습니다.")
                    encoded.tofile(path)
                    self._template_path.setText(os.path.abspath(path))
                except Exception as exc:
                    QMessageBox.warning(self, "액션 템플릿 저장 오류", str(exc))

            selector.region_selected.connect(save_template)
            selector.exec()
        except Exception as exc:
            QMessageBox.warning(self, "액션 템플릿 캡처 오류", str(exc))

    def _choose_world_map_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "큰 지도 이미지 선택", "", "이미지 (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.set_world_map_image(path)

    def set_world_map_image(self, path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError("큰 지도 이미지를 읽을 수 없습니다.")
        self._cfg.set("world_map", "enabled", True)
        self._cfg.set("world_map", "image_path", str(path))
        self._cfg.set("world_map", "image_width", pixmap.width())
        self._cfg.set("world_map", "image_height", pixmap.height())
        self._cfg.save()
        self.reload()

    def set_edit_tool(self, tool):
        if tool not in {"calibration", "waypoint", "action", "connect"}:
            raise ValueError(f"지원하지 않는 지도 편집 도구입니다. {tool}")
        self._edit_tool = tool
        self._connect_from_id = None
        self._canvas.set_tool(tool)

    @staticmethod
    def _next_id(prefix, items):
        used = {item.get("id") for item in items}
        index = 1
        while f"{prefix}-{index:03d}" in used:
            index += 1
        return f"{prefix}-{index:03d}"

    def add_waypoint_node(self, x, y):
        nodes = list(self._cfg.get("navigation", "nodes", default=[]) or [])
        nodes.append({
            "id": self._next_id("node", nodes),
            "kind": "waypoint",
            "x": float(x),
            "y": float(y),
            "arrival_radius": 4.0,
            "label": "이동점",
        })
        self._cfg.set("navigation", "nodes", nodes)
        self._cfg.save()
        self.reload()

    def _nearest_node_id(self, x, y):
        nodes = self._cfg.get("navigation", "nodes", default=[]) or []
        if not nodes:
            return None
        node = min(nodes, key=lambda item: (item["x"] - x) ** 2 + (item["y"] - y) ** 2)
        return node.get("id")

    def _connect_node_at(self, x, y):
        node_id = self._nearest_node_id(x, y)
        if node_id is None:
            return
        if self._connect_from_id is None:
            self._connect_from_id = node_id
            return
        if node_id == self._connect_from_id:
            return
        edges = list(self._cfg.get("navigation", "edges", default=[]) or [])
        edges.append({
            "id": self._next_id("edge", edges),
            "from_id": self._connect_from_id,
            "to_id": node_id,
            "traversal": "walk",
        })
        self._connect_from_id = None
        self._cfg.set("navigation", "edges", edges)
        self._cfg.save()
        self.reload()

    def add_action_node(self, x, y, label, key, hold_sec, repeat,
                        repeat_interval_sec, wait_after_sec):
        nodes = list(self._cfg.get("navigation", "nodes", default=[]) or [])
        nodes.append({
            "id": self._next_id("node", nodes),
            "kind": "action",
            "x": float(x),
            "y": float(y),
            "arrival_radius": 4.0,
            "label": label,
            "action": {
                "key": key,
                "hold_sec": hold_sec,
                "repeat": repeat,
                "repeat_interval_sec": repeat_interval_sec,
                "wait_after_sec": wait_after_sec,
            },
        })
        self._cfg.set("navigation", "nodes", nodes)
        self._cfg.save()
        self.reload()

    def save_image_trigger(self, enabled, template_path, threshold,
                           check_interval_sec, cooldown_sec, key, hold_sec,
                           repeat, repeat_interval_sec, wait_after_sec,
                           action_type="key", click_x=None, click_y=None):
        self._cfg.set("attack", "image_trigger", {
            "enabled": bool(enabled),
            "template_path": str(template_path),
            "threshold": float(threshold),
            "check_interval_sec": float(check_interval_sec),
            "cooldown_sec": float(cooldown_sec),
            "action": {
                "key": str(key),
                "action_type": str(action_type),
                "click_x": None if click_x is None else int(click_x),
                "click_y": None if click_y is None else int(click_y),
                "hold_sec": float(hold_sec),
                "repeat": int(repeat),
                "repeat_interval_sec": float(repeat_interval_sec),
                "wait_after_sec": float(wait_after_sec),
            },
        })
        self._cfg.save()

    def _save_trigger_from_ui(self):
        self.save_image_trigger(
            self._trigger_enabled.isChecked(), self._template_path.text(),
            self._threshold.value(), self._check_interval.value(),
            self._cooldown.value(), self._action_key.text(), self._hold_sec.value(),
            self._repeat.value(), self._repeat_interval.value(), self._wait_after.value(),
            self._action_type.currentData(), self._click_x.value(), self._click_y.value(),
        )

    def apply_calibration(self):
        if len(self._world_points) != 2 or len(self._local_points) != 2:
            raise ValueError("보정에는 큰 지도와 미니맵 기준점이 각각 2개 필요합니다")
        calibration = calibrate_two_points(
            self._world_points[0], self._world_points[1],
            self._local_points[0], self._local_points[1],
        )
        self._cfg.set("world_map", "calibration", {
            "scale": calibration.scale,
            "offset": [calibration.offset_x, calibration.offset_y],
        })
        self._cfg.save()
        if hasattr(self._cfg, "load"):
            self._cfg.load()
        return calibration

    def _apply_calibration_from_ui(self):
        try:
            calibration = self.apply_calibration()
        except ValueError as exc:
            self._calibration_status.setText(str(exc))
            QMessageBox.warning(self, "보정 실패", str(exc))
            return None
        self._calibration_status.setText("2점 보정이 적용되었습니다")
        return calibration

    def _on_world_point(self, x, y):
        tool = self._edit_tool
        if tool == "waypoint":
            self.add_waypoint_node(x, y)
            return
        if tool == "action":
            self.add_action_node(
                x, y, "액션", self._action_key.text(), self._hold_sec.value(),
                self._repeat.value(), self._repeat_interval.value(), self._wait_after.value(),
            )
            return
        if tool == "connect":
            self._connect_node_at(x, y)
            return
        if len(self._world_points) > len(self._local_points):
            self._calibration_status.setText("먼저 대응하는 미니맵 점을 선택하세요")
            return
        if len(self._world_points) >= 2:
            self._world_points.clear()
            self._local_points.clear()
        self._world_points.append(WorldPoint(float(x), float(y)))
        self._calibration_status.setText("같은 위치의 미니맵 점을 선택하세요")

    def _local_preview_clicked(self, event):
        if not hasattr(self, "_local_frame_size"):
            return
        width, height = self._local_frame_size
        x = event.position().x() * width / max(1, self._local_preview.width())
        y = event.position().y() * height / max(1, self._local_preview.height())
        self._on_local_point(x, y)

    def _on_local_point(self, x, y):
        if len(self._world_points) != len(self._local_points) + 1:
            self._calibration_status.setText("먼저 큰 지도 점을 선택하세요")
            return
        self._local_points.append(WorldPoint(float(x), float(y)))
        count = len(self._local_points)
        self._calibration_status.setText(
            "2점 보정 적용을 누르세요" if count == 2 else "두 번째 큰 지도 점을 선택하세요"
        )

    def _refresh_local_capture(self):
        minimap = self._cfg.get("minimap", default={}) or {}
        region = {
            "left": int(minimap.get("region_x", 0)),
            "top": int(minimap.get("region_y", 0)),
            "width": int(minimap.get("width", 0)),
            "height": int(minimap.get("height", 0)),
        }
        if region["width"] <= 0 or region["height"] <= 0:
            return
        frame = self._capture(region)
        if frame is None:
            return
        height, width = frame.shape[:2]
        self._local_frame_size = (width, height)
        image = QImage(
            frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888
        ).copy()
        self._local_preview.setPixmap(QPixmap.fromImage(image))

    def set_runtime_state_provider(self, position_fn, tracking_state_fn, viewport_fn):
        self._position_fn = position_fn
        self._tracking_state_fn = tracking_state_fn
        self._viewport_fn = viewport_fn
        self._runtime_timer.start(100)

    def _refresh_runtime(self):
        viewport = self._viewport_fn()
        if viewport is not None:
            origin, size = viewport
            self._canvas.set_viewport(origin, size, self._tracking_state_fn())
        self._canvas.set_character(self._position_fn())

    def _request_destination(self):
        item = self._nodes.currentItem()
        if item:
            self.destination_requested.emit(item.data(0x0100))

    def _request_route(self):
        item = self._routes.currentItem()
        if item:
            self.route_start_requested.emit(item.data(0x0100))
