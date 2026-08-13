# 6 移댄뀒怨좊━ ?ㅼ젙 ?섏씠吏 ??config ?ㅻ? ???꾨뱶濡?諛붿씤?? shell??移댄뀒怨좊━蹂꾨줈 ?몄텧
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QPushButton

from core_ui.theme import SPACING
from core_ui.widgets import (
    CheckField, TextField, IntField, ComboField, FloatField, StatusField, SliderField,
)


def _capture_game_client(config, owner):
    """설정된 게임창의 클라이언트 영역을 캡처해 BGR 이미지와 화면 원점을 반환한다."""
    import time

    import mss
    import numpy as np
    import win32gui
    from PyQt6.QtWidgets import QApplication, QMessageBox

    owner_hidden = False
    try:
        title = config.get("settings2", "game_window_title") or "MapleStory Worlds"
        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            QMessageBox.warning(owner, "게임창을 찾을 수 없음", f"게임창 제목이 '{title}'인지 확인해 주세요.")
            return None

        ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        width, height = int(right - left), int(bottom - top)
        if width <= 0 or height <= 0:
            QMessageBox.warning(owner, "게임창 영역 오류", "게임창 클라이언트 영역을 확인할 수 없습니다.")
            return None

        owner.hide()
        owner_hidden = True
        QApplication.processEvents()
        win32gui.ShowWindow(hwnd, 9)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.25)
        region = {
            "left": int(ox),
            "top": int(oy),
            "width": width,
            "height": height,
        }
        with mss.mss() as sct:
            image = np.asarray(sct.grab(region))[:, :, :3].copy()
        return image, (int(ox), int(oy))
    except Exception as exc:
        QMessageBox.warning(owner, "게임창 캡처 실패", f"게임창 화면을 캡처하지 못했습니다.\n{exc}")
        return None
    finally:
        if owner_hidden:
            owner.show()
            QApplication.processEvents()


def _character_template_path(project_root):
    """CharScanner가 실제로 로드하는 노란 캐릭터 마커 템플릿 경로를 반환한다."""
    if getattr(sys, "frozen", False):
        from core.config_manager import get_user_templates_dir

        return Path(get_user_templates_dir()) / "player" / "y_p.png"
    return project_root / "templates" / "player" / "y_p.png"


def _make_region_picker(config, keys_xywh, fields_xywh, label: str,
                        on_done=None) -> QPushButton:
    """'영역 선택' 버튼 — 전체화면 캡처 → 스크린샷 위 드래그 → config 4키 저장.

    keys_xywh: ((sec,..,'region_x'), y키, w키, h키)
    fields_xywh: 갱신할 IntField 4개(없으면 None) / on_done: 완료 후 콜백(상태 갱신)
    """
    btn = QPushButton("영역 지정"); btn.setMinimumWidth(78)
    btn.setObjectName("primary")
    btn.setToolTip(f"{label} 영역을 스크린샷에서 드래그해 지정합니다.")

    def on_click():
        import mss as _mss
        import numpy as np
        from core_ui.shot_selector import ScreenshotRegionSelector
        # ?꾩껜 二쇰え?덊꽣 罹≪쿂
        with _mss.mss() as sct:
            mon = sct.monitors[1]
            raw = np.array(sct.grab(mon))[:, :, :3]   # BGRA?묪GR
            origin = (mon["left"], mon["top"])
        dlg = ScreenshotRegionSelector(raw, src_origin=origin)

        def apply(x, y, w, h):
            # ?덈?醫뚰몴濡????+ 吏???쒖젏 李??먯젏???듭빱濡?湲곕줉(?댄썑 李??대룞?됰쭔 蹂댁젙 ????諛由?
            if (config.get("coord_mode") or "relative") == "relative":
                from core.config_manager import cached_window_origin
                title = config.get("settings2", "game_window_title") or ""
                ox, oy, cw, ch = cached_window_origin(title)
                if cw > 0:
                    config.set("coord_anchor", [int(ox), int(oy)])
            for i, (key, val) in enumerate(zip(keys_xywh, (x, y, w, h))):
                config.set(*key, val)
                if fields_xywh and i < len(fields_xywh) and fields_xywh[i] is not None:
                    fields_xywh[i].widget.setValue(val)
            config.save()
            if on_done:
                on_done()
        dlg.region_selected.connect(apply)
        dlg.exec()

    btn.clicked.connect(on_click)
    return btn


def _make_bar_picker(config, bar_type: str, label: str) -> QPushButton:
    """게임창에서 HP/MP 바를 드래그해 게임창 기준 상대좌표로 저장한다."""
    btn = QPushButton(f"{label} 바 화면 캡처")
    btn.setObjectName("primary")
    btn.setToolTip(f"게임 화면에서 {label} 게이지 영역을 드래그해 저장합니다.")

    def on_click():
        from PyQt6.QtWidgets import QMessageBox
        import mss as _mss
        import numpy as np
        import time
        import win32gui
        from PyQt6.QtWidgets import QApplication
        from core_ui.shot_selector import ScreenshotRegionSelector

        title = config.get("settings2", "game_window_title") or "MapleStory"
        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            QMessageBox.warning(
                btn, "게임창을 찾을 수 없음",
                f"게임창 제목이 '{title}'인지 확인해 주세요.",
            )
            return

        ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        cw, ch = right - left, bottom - top
        px, py, pw, ph = int(ox), int(oy), int(cw), int(ch)
        if pw <= 0 or ph <= 0:
            QMessageBox.warning(btn, "게임창 영역 오류", "게임창 클라이언트 영역을 확인할 수 없습니다.")
            return

        owner = btn.window()
        owner.hide()
        QApplication.processEvents()
        try:
            win32gui.ShowWindow(hwnd, 9)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            time.sleep(0.25)
            with _mss.mss() as sct:
                game_region = {
                    "left": int(px), "top": int(py),
                    "width": int(pw), "height": int(ph),
                }
                raw = np.array(sct.grab(game_region))[:, :, :3]
        finally:
            owner.show()
            QApplication.processEvents()
        selector = ScreenshotRegionSelector(raw, src_origin=(px, py), parent=owner)

        def apply(x, y, width, height):
            rx = max(0, min(pw, int(x) - px))
            ry = max(0, min(ph, int(y) - py))
            rw = max(1, min(pw - rx, int(width)))
            values = {
                "x": 0,
                "y": 0,
                "width": 0,
                "x_ratio": round(rx / pw, 8),
                "y_ratio": round(ry / ph, 8),
                "width_ratio": round(rw / pw, 8),
            }
            config.set("coordinate", bar_type, values)
            config.save()
            QMessageBox.information(
                btn, f"{label} 바 저장",
                f"{label} 바 영역을 게임창 기준 상대 좌표로 저장했습니다.",
            )

        selector.region_selected.connect(apply)
        _run_character_capture_selector(selector)

    btn.clicked.connect(on_click)
    return btn


def _make_attack_box_picker(config, fields4, on_done=None) -> QPushButton:
    """공격범위 박스 픽커 — 스크린샷 위에 기존범위 미리보기 + 드래그로 갱신.
    화면 중앙을 캐릭(앵커) 기준점으로 가정해 상대 오프셋(atk_x/y_min/max) 환산.
    fields4: 갱신할 IntField [x_min, x_max, y_min, y_max](없으면 None) / on_done: 완료 콜백."""
    btn = QPushButton("🎯 공격 범위 박스 드래그 (기존범위 표시)")
    btn.setObjectName("primary")

    def on_click():
        import mss as _mss
        import numpy as np
        from core_ui.shot_selector import (
            ScreenshotRegionSelector, rect_to_offsets, offsets_to_rect,
        )
        with _mss.mss() as sct:
            mon = sct.monitors[1]
            raw = np.array(sct.grab(mon))[:, :, :3]
            origin = (mon["left"], mon["top"])
            anchor = (mon["width"] // 2, mon["height"] // 2)   # ?붾㈃ 以묒븰=罹먮┃ 湲곗?
        xmn = int(config.get("attack", "atk_x_min", default=-35))
        xmx = int(config.get("attack", "atk_x_max", default=35))
        ymn = int(config.get("attack", "atk_y_min", default=-70))
        ymx = int(config.get("attack", "atk_y_max", default=70))
        init_rect = offsets_to_rect(xmn, xmx, ymn, ymx, anchor)

        # ?됰꽕??紐ъ뒪??媛먯? ???ㅻ쾭?덉씠 諛뺤뒪 (?ㅼ젣 萸먭? ?≫엳?붿? 蹂대㈃??議곗젙)
        from core.sensing import monster_vision as _mv
        overlays = []
        name_path = config.get("attack", "name_template", default="")
        name_anchor = anchor
        if name_path:
            nt = _mv.load_template(name_path)
            if nt is not None:
                npos = _mv.find_template_pos(raw, nt, threshold=0.6)
                if npos:
                    nh, nw = nt.shape[:2]
                    overlays.append((npos[0]-nw//2, npos[1]-nh//2, nw, nh,
                                     "#cba258", "닉네임"))
                    name_anchor = npos   # ?됰꽕???꾩튂瑜??ㅼ젣 ?듭빱濡?
                    init_rect = offsets_to_rect(xmn, xmx, ymn, ymx, name_anchor)
        # 紐ъ뒪??(?꾩옱 怨듦꺽諛뺤뒪 ??
        mon_tpls = {}
        mt = config.get("attack", "monster_template", default="")
        if mt:
            t = _mv.load_template(mt)
            if t is not None:
                mon_tpls["m"] = t
        if mon_tpls:
            cur_box = (name_anchor[0]+xmn, name_anchor[1]+ymn, xmx-xmn, ymx-ymn)
            for (mx_, my_, mw_, mh_) in _mv.monster_boxes_in_box(
                    raw, mon_tpls, cur_box, threshold=float(
                        config.get("attack", "monster_accuracy", default=0.9))):
                overlays.append((mx_, my_, mw_, mh_, "#f04452", "몬스터"))

        dlg = ScreenshotRegionSelector(raw, src_origin=origin,
                                       initial_rect=init_rect, anchor=name_anchor,
                                       overlays=overlays)

        def apply(x, y, w, h):
            # ?됰꽕??媛먯??먯쑝硫?洹??꾩튂 湲곗?, ?꾨땲硫??붾㈃以묒븰 湲곗? ?ㅽ봽??
            o = rect_to_offsets(x - origin[0], y - origin[1], w, h, name_anchor)
            for i, (key, val) in enumerate(zip(
                    ["atk_x_min", "atk_x_max", "atk_y_min", "atk_y_max"], o)):
                config.set("attack", key, val)
                if fields4 and i < len(fields4) and fields4[i] is not None:
                    fields4[i].widget.setValue(val)
            config.save()
            if on_done:
                on_done()
        dlg.region_selected.connect(apply)
        dlg.exec()

    btn.clicked.connect(on_click)
    return btn


def _make_template_capture(config, save_path, config_key, label: str,
                           on_done=None) -> QPushButton:
    """'이미지 캡처' 버튼 — 스크린샷에서 영역 드래그 → 그 부분을 잘라 png 저장 + config에 경로.

    save_path: 저장할 png 경로(templates/...). config_key: 경로 저장할 config 키. on_done: 완료 콜백.
    """
    btn = QPushButton("캡처"); btn.setMinimumWidth(64)
    btn.setToolTip(f"{label} 이미지를 스크린샷에서 드래그해 캡처합니다.")

    def on_click():
        import os
        import mss as _mss
        import numpy as np
        import cv2
        from core_ui.shot_selector import ScreenshotRegionSelector
        with _mss.mss() as sct:
            mon = sct.monitors[1]
            shot = np.array(sct.grab(mon))[:, :, :3]   # BGR
            origin = (mon["left"], mon["top"])
        dlg = ScreenshotRegionSelector(shot, src_origin=origin)

        def crop_save(x, y, w, h):
            # ?먮낯 ?덈?醫뚰몴 ??shot ?대? ?곷?醫뚰몴
            rx, ry = x - origin[0], y - origin[1]
            crop = shot[ry:ry + h, rx:rx + w]
            if crop.size == 0:
                return
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            cv2.imwrite(save_path, crop)
            config.set(*config_key, save_path)
            config.save()
            if on_done:
                on_done()
        dlg.region_selected.connect(crop_save)
        dlg.exec()

    btn.clicked.connect(on_click)
    return btn


def _page(title: str, desc: str, fields: list, buttons: list | None = None,
          extras: list | None = None, fill_last: bool = False) -> QWidget:
    """제목 + 설명 + (버튼들) + 폼 필드들 + (임의 위젯 extras)를 담은 스크롤 페이지.
    fill_last=True면 마지막 extra가 남은 세로 공간을 채운다(블록 리스트가 창에 꽉 차게)."""
    inner = QWidget()
    v = QVBoxLayout(inner)
    v.setContentsMargins(SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"])
    v.setSpacing(SPACING["xs"])

    h = QLabel(title); h.setObjectName("h1")
    sub = QLabel(desc); sub.setObjectName("subtle"); sub.setWordWrap(True)
    v.addWidget(h); v.addWidget(sub)
    v.addSpacing(SPACING["md"])
    for b in (buttons or []):
        v.addWidget(b)
    if buttons:
        v.addSpacing(SPACING["sm"])
    for f in fields:
        v.addWidget(getattr(f, "row", f))
    ex = extras or []
    for i, w in enumerate(ex):
        # fill_last硫?留덉?留?extra??stretch=1 遺??鍮덇났媛?梨꾩?), ?섎㉧吏/?쇰컲 ?섏씠吏??0
        v.addWidget(w, 1 if (fill_last and i == len(ex) - 1) else 0)
    if not fill_last:
        v.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    return scroll


# ?? 6 移댄뀒怨좊━ 鍮뚮뜑 (config ?ㅼ젣 ??留ㅽ븨) ????????????????????????????
def _make_current_position_checker(config) -> QWidget:
    """현재 미니맵에서 감지한 캐릭터 좌표를 픽셀/상대좌표로 보여주는 행."""
    row = QWidget()
    row.setObjectName("currentPositionChecker")
    row._character_provider = None
    row._minimap_size_provider = None
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(SPACING["sm"])

    btn = QPushButton("현재 위치 좌표 확인")
    btn.setObjectName("primary")
    btn.setMinimumWidth(140)
    lbl = QLabel("현재 위치: -")
    lbl.setObjectName("subtle")
    lbl.setMinimumWidth(360)

    def set_character_provider(fn, size_fn=None):
        row._character_provider = fn
        row._minimap_size_provider = size_fn

    def on_click():
        try:
            from PyQt6.QtWidgets import QApplication
            from core.config_manager import resolve_minimap_coords
            from core.minimap_reader import MinimapConfig, MinimapReader
            from core.screen_reader import ScreenReader

            stored_mm = config.get("minimap") or {}
            region_x, region_y, width, height = resolve_minimap_coords(config, stored_mm)
            pos = None
            provider = getattr(row, "_character_provider", None)
            if callable(provider):
                provided = provider()
                if (
                    isinstance(provided, tuple)
                    and len(provided) == 2
                    and isinstance(provided[0], tuple)
                ):
                    pos, observed_at = provided
                    if observed_at is not None:
                        import time
                        if time.monotonic() - float(observed_at) > 1.0:
                            pos = None
                else:
                    pos = provided
                size_provider = getattr(row, "_minimap_size_provider", None)
                if callable(size_provider):
                    width, height = size_provider()
            if not pos:
                reader = MinimapReader(ScreenReader())
                reader.set_config(MinimapConfig(
                    region_x=region_x,
                    region_y=region_y,
                    width=width,
                    height=height,
                    char_r=int(stored_mm.get("char_r", 255)),
                    char_g=int(stored_mm.get("char_g", 255)),
                    char_b=int(stored_mm.get("char_b", 0)),
                    tolerance=int(stored_mm.get("tolerance", 40)),
                ))
                pos = reader.get_character_pos()
            if not pos:
                lbl.setText("현재 위치: 감지 실패 - 미니맵 영역/캐릭터 색 확인 필요")
                return

            x, y = int(pos[0]), int(pos[1])
            rx = x / max(1, int(width))
            ry = y / max(1, int(height))
            text = f"현재 위치: X={x}  Y={y} / 상대 X={rx:.4f}, Y={ry:.4f}"
            lbl.setText(text)
            QApplication.clipboard().setText(
                f"X={x}, Y={y}, x_ratio={rx:.4f}, y_ratio={ry:.4f}"
            )
        except Exception as exc:
            lbl.setText(f"현재 위치 확인 오류: {exc}")

    btn.clicked.connect(on_click)
    row.set_character_provider = set_character_provider
    lay.addWidget(btn)
    lay.addWidget(lbl)
    lay.addStretch()
    return row




def _make_character_color_controls(config) -> QWidget:
    """미니맵 캐릭터 노란점의 HSV와 점 크기 필터를 조절하는 영역."""
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, SPACING["xs"], 0, SPACING["xs"])
    v.setSpacing(SPACING["xxs"])

    title = QLabel("캐릭터 색검출 조절")
    title.setObjectName("subtle")
    desc = QLabel(
        "노란점이 안 잡히면 밝기 최소값을 낮추고, "
        "배경 노란색을 잡으면 밝기/채도 최소값을 올려주세요. "
        "점 크기 범위는 작은 노란 캐릭터 마크만 남기기 위한 필터입니다."
    )
    desc.setObjectName("subtle")
    desc.setWordWrap(True)
    v.addWidget(title)
    v.addWidget(desc)

    fields = {
        "h_low": SliderField("색상 시작 H", config, ("minimap", "hsv_h_low"), lo=0, hi=179, default=20, is_int=True, label_w=120),
        "h_high": SliderField("색상 끝 H", config, ("minimap", "hsv_h_high"), lo=0, hi=179, default=40, is_int=True, label_w=120),
        "s_low": SliderField("채도 최소 S", config, ("minimap", "hsv_s_low"), lo=0, hi=255, default=100, is_int=True, label_w=120),
        "v_low": SliderField("밝기 최소 V", config, ("minimap", "hsv_v_low"), lo=0, hi=255, default=200, is_int=True, label_w=120),
        "area_min": SliderField("점 크기 최소", config, ("minimap", "char_area_min"), lo=1, hi=80, default=3, is_int=True, label_w=120),
        "area_max": SliderField("점 크기 최대", config, ("minimap", "char_area_max"), lo=10, hi=500, default=160, is_int=True, label_w=120),
    }
    for field in fields.values():
        v.addWidget(field.row)

    capture_row = QHBoxLayout()
    def _run_character_capture_selector(selector):
        """영역 선택 신호를 기존 동기식 캡처 처리와 연결한다."""
        from PyQt6.QtCore import QEventLoop

        loop = QEventLoop()

        def apply_selection(x, y, width, height):
            selector.selected_rect = (x, y, width, height)
            loop.quit()

        selector.region_selected.connect(apply_selection)
        selector.show()
        loop.exec()
    color_button = QPushButton("기준색 캡처")
    template_button = QPushButton("캐릭터 템플릿 캡처")
    capture_status = QLabel("게임 화면에서 캐릭터 마커를 작게 드래그해 선택하세요.")
    capture_status.setObjectName("subtle")
    capture_status.setWordWrap(True)
    capture_row.addWidget(color_button)
    capture_row.addWidget(template_button)
    capture_row.addWidget(capture_status, 1)
    v.addLayout(capture_row)

    def _set_slider(field, value: int) -> bool:
        for name in ("slider", "control", "widget", "input"):
            control = getattr(field, name, None)
            if control is not None and hasattr(control, "setValue"):
                control.setValue(int(value))
                return True
        for control in field.row.findChildren(QSlider):
            control.setValue(int(value))
            return True
        return False

    def _capture_selection():
        from core_ui.shot_selector import ScreenshotRegionSelector

        captured = _capture_game_client(config, box.window())
        if captured is None:
            return None
        image, origin = captured
        selector = ScreenshotRegionSelector(image, src_origin=origin, parent=box.window())
        selected = {}

        def remember_selection(x, y, width, height):
            selected["value"] = (x, y, width, height)

        selector.region_selected.connect(remember_selection)
        selector.exec()
        if "value" not in selected:
            return None

        x, y, width, height = selected["value"]
        x, y, width, height = map(int, (x, y, width, height))
        x -= origin[0]
        y -= origin[1]
        x = max(0, min(x, image.shape[1] - 1))
        y = max(0, min(y, image.shape[0] - 1))
        width = max(1, min(width, image.shape[1] - x))
        height = max(1, min(height, image.shape[0] - y))
        return image[y:y + height, x:x + width].copy()

    def capture_reference_color():
        import cv2
        import numpy as np

        crop = _capture_selection()
        if crop is None or not crop.size:
            capture_status.setText("기준색 선택을 취소했습니다.")
            return
        bgr = cv2.cvtColor(crop, cv2.COLOR_BGRA2BGR) if crop.shape[2] == 4 else crop[:, :, :3]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        h, s, value = (int(round(v)) for v in np.median(hsv.reshape(-1, 3), axis=0))
        h_low, h_high = max(0, h - 10), min(179, h + 10)
        s_low, v_low = max(0, s - 40), max(0, value - 40)
        _set_slider(fields["h_low"], h_low)
        _set_slider(fields["h_high"], h_high)
        _set_slider(fields["s_low"], s_low)
        _set_slider(fields["v_low"], v_low)
        config.set("minimap", "hsv_h_low", h_low)
        config.set("minimap", "hsv_h_high", h_high)
        config.set("minimap", "hsv_s_low", s_low)
        config.set("minimap", "hsv_v_low", v_low)
        config.save()
        capture_status.setText(
            f"기준색 HSV({h}, {s}, {value})를 적용했습니다. "
            f"범위 H {h_low}~{h_high}, S {s_low} 이상, V {v_low} 이상."
        )

    def capture_character_template():
        import cv2
        from pathlib import Path

        crop = _capture_selection()
        if crop is None or not crop.size:
            capture_status.setText("캐릭터 템플릿 선택을 취소했습니다.")
            return
        project_root = Path(__file__).resolve().parents[1]
        template_path = _character_template_path(project_root)
        template_dir = template_path.parent
        template_dir.mkdir(parents=True, exist_ok=True)
        pending_path = template_path.with_name(".y_p.pending.png")
        if not cv2.imwrite(str(pending_path), crop):
            capture_status.setText("캐릭터 템플릿 저장에 실패했습니다.")
            return
        try:
            os.replace(pending_path, template_path)
        except OSError:
            try:
                pending_path.unlink(missing_ok=True)
            except OSError:
                pass
            capture_status.setText("캐릭터 템플릿 저장에 실패했습니다.")
            return
        capture_status.setText(f"캐릭터 템플릿을 저장했습니다. {template_path}")

    color_button.clicked.connect(capture_reference_color)
    template_button.clicked.connect(capture_character_template)
    return box


def build_pages(config) -> list[QWidget]:
    """6 카테고리 페이지 리스트. shell의 stack에 순서대로 들어감."""
    c = config
    pages = []

    # 1. ?곌껐쨌?몄떇 ???곸뿭/罹≪쿂???쒕옒洹????됱긽(?륁꽕?뺣맖)?쇰줈 ?꾨즺 ?뺤씤 (?レ옄 ?쒖떆 ????
    minimap_picker = _make_region_picker(
        c, [("minimap", "region_x"), ("minimap", "region_y"),
            ("minimap", "width"), ("minimap", "height")],
        None, "미니맵", on_done=lambda: mm_status.refresh())
    mm_status = StatusField("미니맵 영역",
                            lambda: int(c.get("minimap", "width", default=0)) > 0,
                            [minimap_picker])
    hunt_area_picker = _make_region_picker(
        c, [("attack", "hunt_area", "x"), ("attack", "hunt_area", "y"),
            ("attack", "hunt_area", "w"), ("attack", "hunt_area", "h")],
        None, "사냥", on_done=lambda: ha_status.refresh())
    # ?щ깷 ?곸뿭 ?놁뿉 ???덉슜?ㅼ감 ?щ씪?대뜑(?뺤닔)
    tol_slider = SliderField("색 허용오차", c, ("minimap", "tolerance"),
                             lo=0, hi=255, default=30, is_int=True, label_w=74)
    char_controls = _make_character_color_controls(c)
    ha_status = StatusField("사냥 영역",
                            lambda: int(c.get("attack", "hunt_area", "w", default=0)) > 0,
                            [hunt_area_picker], extra=tol_slider.row)
    # 紐ъ뒪??罹≪쿂 ?놁뿉 紐ъ뒪???꾧퀎媛??щ씪?대뜑
    monster_cap = _make_template_capture(
        c, "templates/monster_capture.png", ("attack", "monster_template"), "몬스터",
        on_done=lambda: mon_status.refresh())
    mon_thr = SliderField("임계값", c, ("attack", "monster_accuracy"), default=0.9, label_w=52)
    mon_status = StatusField("몬스터 캡처",
                             lambda: bool(c.get("attack", "monster_template", default="")),
                             [monster_cap], extra=mon_thr.row)
    # ?됰꽕??罹≪쿂 ?놁뿉 ?됰꽕???꾧퀎媛??щ씪?대뜑
    name_cap = _make_template_capture(
        c, "templates/name_tag.png", ("attack", "name_template"), "닉네임",
        on_done=lambda: name_status.refresh())
    name_thr = SliderField("임계값", c, ("attack", "name_tag_threshold"), default=0.7, label_w=52)
    name_status = StatusField("닉네임 캡처",
                              lambda: bool(c.get("attack", "name_template", default="")),
                              [name_cap], extra=name_thr.row)
    pages.append(_page("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지", [
        ComboField("사냥 모드", c, ("hunt_mode",), ["key", "image"],
                   labels={"key": "키 입력", "image": "이미지 인식"}),
        mm_status, char_controls, ha_status, mon_status, name_status,
    ]))

    # 2. ?숈꽑쨌?대룞 ??醫뚰몴 ?숈꽑? 釉붾줉 鍮뚮뜑濡?(?대룞/怨듦꺽/?щ떎由??쒖감)
    from core_ui.block_editor import BlockEditor
    from PyQt6.QtWidgets import QLabel as _QLabel
    route_lbl = _QLabel("좌표 동선 블록 (위→아래 순서 실행)")
    route_lbl.setObjectName("subtle")
    block_editor = BlockEditor(c, ("floor_hunt", "route_steps"))
    # 誘몃땲留??몄쭛 罹붾쾭??RouteCanvas) + 釉붾줉????대컮. 罹≪쿂/紐⑤땲?????ㅽ뙣 ??罹붾쾭???앸왂
    hunt_name_field = TextField("현재 사냥터", c, ("hunt_grounds", "active"))
    current_position_checker = _make_current_position_checker(c)
    nav_extras = []
    from core_ui.hunt_ground_preset_widget import HuntGroundPresetWidget
    from core_ui.rednose2_coordinate_widget import Rednose2CoordinateWidget
    hunt_ground_preset = HuntGroundPresetWidget(c, name_field=hunt_name_field)
    rednose2_settings = Rednose2CoordinateWidget(c)
    hunt_ground_preset.preset_loaded.connect(rednose2_settings.set_hunt_ground)
    hunt_name_field.widget.editingFinished.connect(
        lambda: rednose2_settings.set_hunt_ground(hunt_name_field.widget.text())
    )
    nav_extras.append(hunt_ground_preset)
    nav_extras.append(rednose2_settings)
    try:
        import mss as _mss
        from PyQt6.QtWidgets import QWidget as _QWidget, QHBoxLayout as _QHBox, \
            QPushButton as _QBtn, QButtonGroup as _QBtnGroup
        from core.screen_reader import ScreenReader
        from core_ui.minimap_canvas import RouteCanvas
        with _mss.mss() as _s:
            _sw = int(_s.monitors[1]["width"])
        route_canvas = RouteCanvas(c, ScreenReader().capture, screen_w=_sw,
                                   on_route_changed=block_editor.reload)
        block_editor._on_change = route_canvas.sync_unplaced   # 由ъ뒪??蹂寃썩넂罹붾쾭???몄텧/媛깆떊
        # 釉붾줉????대컮 (?좏깮 ????湲곕낯)
        bar = _QWidget(); bl = _QHBox(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        grp = _QBtnGroup(bar); grp.setExclusive(True)
        none_btn = None
        for label, typ in [("선택 안 함", None), ("이동", "move"), ("공격", "attack"),
                           ("사다리", "ladder"), ("점프", "jump"), ("텔포", "teleport")]:
            btn = _QBtn(label); btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, t=typ: route_canvas.set_active_type(t))
            grp.addButton(btn); bl.addWidget(btn)
            if typ is None:
                btn.setChecked(True); none_btn = btn
        # 釉붾줉 1媛?諛곗튂?섎㈃ 罹붾쾭?ㅺ? _active_type??None?쇰줈 ?섎룎由щ?濡? ?대컮??'?좏깮 ?????쇰줈
        route_canvas.on_type_consumed = lambda b=none_btn: b.setChecked(True)
        bl.addStretch()
        nav_extras += [bar, route_canvas]
    except Exception:
        pass
    nav_extras += [route_lbl, block_editor]
    pages.append(_page("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋", [
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
        hunt_name_field,
        current_position_checker,
        ComboField("좌표 기준", c, ("coord_mode",), ["relative", "absolute"], default="relative",
                   labels={"relative": "게임창 기준(상대)", "absolute": "화면 기준(절대)"}),
    ], extras=nav_extras, fill_last=True))

    # 3. ?꾪닾 ??怨듦꺽踰붿쐞 諛뺤뒪???쒕옒洹????됱긽(?륁꽕?뺣맖)?쇰줈 ?뺤씤 (?レ옄 ?쒖떆 ????
    atk_picker = _make_attack_box_picker(c, None, on_done=lambda: atk_status.refresh())
    atk_status = StatusField(
        "공격 범위 박스",
        lambda: c.get("attack", "atk_x_max", default=None) is not None,
        [atk_picker])
    from core_ui.buff_editor import BuffEditor
    buff_editor = BuffEditor(c, ("attack", "normal_buffs"))
    # HP/MP ?ㅼ떆媛?% 誘몃━蹂닿린 (A Detector 怨좎젙 ?곷?醫뚰몴). 寃뚯엫 ?녾굅???ㅽ뙣 ???앸왂
    from core_ui.attack_sequence_editor import AttackSequenceEditor
    attack_sequence_editor = AttackSequenceEditor(c)
    combat_extras = []
    combat_extras.append(_make_bar_picker(c, "hp", "HP"))
    combat_extras.append(_make_bar_picker(c, "mp", "MP"))
    try:
        from core.detector import Detector
        from core.screen_reader import ScreenReader
        from core_ui.gauge_preview import GaugePreview
        combat_extras.append(GaugePreview(Detector(ScreenReader(), c)))
    except Exception:
        pass
    combat_extras.append(buff_editor)
    pages.append(_page("전투", "공격·버프·물약·펫·줍기", [
        atk_status,
        IntField("공격 범위(px)", c, ("attack", "range_px"), 0, 2000, default=350),
        attack_sequence_editor,
        CheckField("공격 전 점프", c, ("attack", "jump_before_attack")),
        TextField("점프 키", c, ("minimap", "jump_key"), default="alt"),
        CheckField("이동 시 점프 (걷는 동안 점프키 홀드)", c, ("attack", "jump_while_move")),
        CheckField("HP 물약 사용", c, ("recovery", "hp_potion", "enabled")),
        IntField("HP 물약 임계%", c, ("recovery", "hp_potion", "threshold"), 0, 100, default=65),
        TextField("HP 물약 키", c, ("recovery", "hp_potion", "key")),
        TextField("HP 2차 물약 키", c, ("recovery", "hp_potion", "secondary_key")),
        CheckField("MP 물약 사용", c, ("recovery", "mp_potion", "enabled")),
        IntField("MP 물약 임계%", c, ("recovery", "mp_potion", "threshold"), 0, 100, default=50),
        TextField("MP 물약 키", c, ("recovery", "mp_potion", "key")),
        TextField("MP 2차 물약 키", c, ("recovery", "mp_potion", "secondary_key")),
        CheckField("펫 먹이 사용", c, ("recovery", "pet_food", "enabled")),
        TextField("펫 먹이 키", c, ("recovery", "pet_food", "key")),
        IntField("펫 먹이 간격(분)", c, ("recovery", "pet_food", "interval_min"), 1, 120, default=10),
    ], extras=combat_extras))

    # 4. ?덉쟾쨌?덊떚諛???嫄고깘 ?뚮┝(?뚮━+?붾젅洹몃옩) ?듯빀
    anti_mob_widget = None
    try:
        from core_ui.anti_mob_profile_widget import AntiMobProfileWidget
        anti_mob_widget = AntiMobProfileWidget(c)
    except Exception:
        pass
    pages.append(_page("안전·안티밴", "거탐·방지몹·유저감지·자동응답·채널변경·인간화강도", [
        CheckField("거탐 감지", c, ("settings1", "lie_detector", "enabled")),
        CheckField("거탐 알림 (소리+텔레그램)", c, ("settings1", "lie_detector", "alert_enabled")),
        TextField("텔레그램 토큰", c, ("settings1", "lie_detector", "tg_token")),
        TextField("텔레그램 챗ID", c, ("settings1", "lie_detector", "tg_chat_id")),
        CheckField("투명도형 자동탐지", c, ("settings1", "transparent_shape", "enabled")),
        CheckField("다른 유저 감지", c, ("settings1", "user_detected", "enabled")),
        CheckField("방지몹 해제", c, ("anti_mob", "enabled")),
    ], extras=[anti_mob_widget] if anti_mob_widget is not None else None))

    # 5. ?먮룞?붋룹슫????留듭씠??媛먯??곸뿭? ?쒕옒洹????됱긽?쇰줈 ?뺤씤
    mapexit_picker = _make_region_picker(
        c, [("map_exit", "region_x"), ("map_exit", "region_y"),
            ("map_exit", "width"), ("map_exit", "height")],
        None, "맵이탈 감지", on_done=lambda: mapexit_status.refresh())
    mapexit_status = StatusField(
        "맵이탈 영역", lambda: int(c.get("map_exit", "width", default=0)) > 0,
        [mapexit_picker])
    auto_sell_manual_row = QWidget()
    auto_sell_manual_layout = QHBoxLayout(auto_sell_manual_row)
    auto_sell_manual_layout.setContentsMargins(0, 0, 0, 0)
    auto_sell_manual_layout.setSpacing(SPACING["sm"])
    auto_sell_manual_label = QLabel("수동 자동판매")
    auto_sell_manual_label.setFixedWidth(130)
    auto_sell_manual_label.setObjectName("subtle")
    auto_sell_manual_layout.addWidget(auto_sell_manual_label)
    auto_sell_run_btn = QPushButton("판매 실행")
    auto_sell_run_btn.setObjectName("autoSellRunButton")
    auto_sell_run_btn.setMinimumWidth(96)
    auto_sell_stop_btn = QPushButton("판매 중단")
    auto_sell_stop_btn.setObjectName("autoSellStopButton")
    auto_sell_stop_btn.setMinimumWidth(96)
    auto_sell_manual_layout.addWidget(auto_sell_run_btn)
    auto_sell_manual_layout.addWidget(auto_sell_stop_btn)
    auto_sell_manual_layout.addStretch(1)
    pages.append(_page("자동화·운영", "자동판매·마을귀환·예약종료·픽업·텔레그램·찰리교환", [
        CheckField("자동판매 사용", c, ("settings2", "junk_sell", "auto_sell_enabled")),
        IntField("자동판매 주기(분)", c, ("settings2", "junk_sell", "auto_sell_interval_min"), 1, 240, default=10),
        CheckField("시작 시 자동판매", c, ("settings2", "junk_sell", "sell_on_start")),
        CheckField("기타템 판매", c, ("settings2", "junk_sell", "junk_sell_enabled")),
        auto_sell_manual_row,
        CheckField("맵 이탈 감지", c, ("map_exit", "enabled")),
        mapexit_status,
        CheckField("긴급 마을귀환", c, ("town_scroll", "enabled")),
        TextField("마을귀환 키", c, ("town_scroll", "key"), default="9"),
        CheckField("픽업 타이머", c, ("pickup_timer", "enabled")),
        CheckField("항시 픽업 (2초 주기)", c, ("pickup_timer", "always_enabled")),
        IntField("픽업 간격(초)", c, ("pickup_timer", "interval_sec"), 1, 3600, default=60),
        TextField("픽업 키", c, ("pickup_timer", "pickup_key")),
    ]))

    # 6. ?쒖뒪??
    pages.append(_page("시스템", "라이선스·업데이트·리소스·입력 백엔드·YOLO 캡처", [
        CheckField("공격 모듈", c, ("modules", "attack"), default=True),
        CheckField("이동 모듈", c, ("modules", "move"), default=True),
        CheckField("물약 모듈", c, ("modules", "potion"), default=True),
        CheckField("거탐 알림 모듈", c, ("modules", "lie_notify"), default=True),
        CheckField("거탐 풀이 모듈", c, ("modules", "lie_solve"), default=True),
        TextField("게임창 제목", c, ("settings2", "game_window_title"), default="MapleStory Worlds"),
    ]))

    return pages
