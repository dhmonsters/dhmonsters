# 6 카테고리 설정 페이지 — config 키를 폼 필드로 바인딩. shell이 카테고리별로 호출
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QPushButton

from core_ui.theme import SPACING
from core_ui.widgets import (
    CheckField, TextField, IntField, ComboField, FloatField, StatusField, SliderField,
)


def _make_region_picker(config, keys_xywh, fields_xywh, label: str,
                        on_done=None) -> QPushButton:
    """'영역 선택' 버튼 — 전체화면 캡처 → 스크린샷 위 드래그 → config 4키 저장.

    keys_xywh: ((sec,..,'region_x'), y키, w키, h키)
    fields_xywh: 갱신할 IntField 4개(없으면 None) / on_done: 완료 후 콜백(상태 갱신)
    """
    btn = QPushButton("영역 지정"); btn.setMinimumWidth(78)
    btn.setObjectName("primary")
    btn.setToolTip(f"{label} 영역을 스크린샷에서 드래그")

    def on_click():
        import mss as _mss
        import numpy as np
        from core_ui.shot_selector import ScreenshotRegionSelector
        # 전체 주모니터 캡처
        with _mss.mss() as sct:
            mon = sct.monitors[1]
            raw = np.array(sct.grab(mon))[:, :, :3]   # BGRA→BGR
            origin = (mon["left"], mon["top"])
        dlg = ScreenshotRegionSelector(raw, src_origin=origin)

        def apply(x, y, w, h):
            # relative 모드 + 게임창 찾으면 클라이언트 상대 픽셀로 저장(창을 따라가게)
            if (config.get("coord_mode") or "relative") == "relative":
                from core.config_manager import cached_window_origin
                title = config.get("settings2", "game_window_title") or ""
                ox, oy, cw, ch = cached_window_origin(title)
                if cw > 0:
                    x, y = x - ox, y - oy
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
            anchor = (mon["width"] // 2, mon["height"] // 2)   # 화면 중앙=캐릭 기준
        xmn = int(config.get("attack", "atk_x_min", default=-35))
        xmx = int(config.get("attack", "atk_x_max", default=35))
        ymn = int(config.get("attack", "atk_y_min", default=-70))
        ymx = int(config.get("attack", "atk_y_max", default=70))
        init_rect = offsets_to_rect(xmn, xmx, ymn, ymx, anchor)

        # 닉네임/몬스터 감지 → 오버레이 박스 (실제 뭐가 잡히는지 보면서 조정)
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
                    name_anchor = npos   # 닉네임 위치를 실제 앵커로
                    init_rect = offsets_to_rect(xmn, xmx, ymn, ymx, name_anchor)
        # 몬스터 (현재 공격박스 안)
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
            # 닉네임 감지됐으면 그 위치 기준, 아니면 화면중앙 기준 오프셋
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
    btn.setToolTip(f"{label} 이미지를 스크린샷에서 드래그로 캡처")

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
            # 원본 절대좌표 → shot 내부 상대좌표
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
        v.addWidget(f.row)
    ex = extras or []
    for i, w in enumerate(ex):
        # fill_last면 마지막 extra에 stretch=1 부여(빈공간 채움), 나머지/일반 페이지는 0
        v.addWidget(w, 1 if (fill_last and i == len(ex) - 1) else 0)
    if not fill_last:
        v.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    return scroll


# ── 6 카테고리 빌더 (config 실제 키 매핑) ────────────────────────────
def build_pages(config) -> list[QWidget]:
    """6 카테고리 페이지 리스트. shell의 stack에 순서대로 들어감."""
    c = config
    pages = []

    # 1. 연결·인식 — 영역/캡처는 드래그 후 색상(●설정됨)으로 완료 확인 (숫자 표시 안 함)
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
    # 사냥 영역 옆에 색 허용오차 슬라이더(정수)
    tol_slider = SliderField("색 허용오차", c, ("minimap", "tolerance"),
                             lo=0, hi=255, default=30, is_int=True, label_w=74)
    ha_status = StatusField("사냥 영역",
                            lambda: int(c.get("attack", "hunt_area", "w", default=0)) > 0,
                            [hunt_area_picker], extra=tol_slider.row)
    # 몬스터 캡처 옆에 몬스터 임계값 슬라이더
    monster_cap = _make_template_capture(
        c, "templates/monster_capture.png", ("attack", "monster_template"), "몬스터",
        on_done=lambda: mon_status.refresh())
    mon_thr = SliderField("임계값", c, ("attack", "monster_accuracy"), default=0.9, label_w=52)
    mon_status = StatusField("몬스터 캡처",
                             lambda: bool(c.get("attack", "monster_template", default="")),
                             [monster_cap], extra=mon_thr.row)
    # 닉네임 캡처 옆에 닉네임 임계값 슬라이더
    name_cap = _make_template_capture(
        c, "templates/name_tag.png", ("attack", "name_template"), "닉네임",
        on_done=lambda: name_status.refresh())
    name_thr = SliderField("임계값", c, ("attack", "name_tag_threshold"), default=0.7, label_w=52)
    name_status = StatusField("닉네임 캡처",
                              lambda: bool(c.get("attack", "name_template", default="")),
                              [name_cap], extra=name_thr.row)
    pages.append(_page("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지", [
        ComboField("사냥 모드", c, ("hunt_mode",), ["key", "image", "coordinate"]),
        mm_status, ha_status, mon_status, name_status,
    ]))

    # 2. 동선·이동 — 좌표 동선은 블록 빌더로 (이동/공격/사다리 순차)
    from core_ui.block_editor import BlockEditor
    from PyQt6.QtWidgets import QLabel as _QLabel
    route_lbl = _QLabel("좌표 동선 블록 (위→아래 순서 실행)")
    route_lbl.setObjectName("subtle")
    block_editor = BlockEditor(c, ("floor_hunt", "route"))
    # 미니맵 편집 캔버스(RouteCanvas) + 블록타입 툴바. 캡처/모니터 폭 실패 시 캔버스 생략
    nav_extras = []
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
        block_editor._on_change = route_canvas.sync_unplaced   # 리스트 변경→캔버스 노출/갱신
        # 블록타입 툴바 (선택 안 함 기본)
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
        # 블록 1개 배치하면 캔버스가 _active_type을 None으로 되돌리므로, 툴바도 '선택 안 함'으로
        route_canvas.on_type_consumed = lambda b=none_btn: b.setChecked(True)
        bl.addStretch()
        nav_extras += [bar, route_canvas]
    except Exception:
        pass
    nav_extras += [route_lbl, block_editor]
    pages.append(_page("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋", [
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
        TextField("현재 사냥터", c, ("hunt_grounds", "active")),
        ComboField("좌표 기준", c, ("coord_mode",), ["relative", "absolute"], default="relative"),
    ], extras=nav_extras, fill_last=True))

    # 3. 전투 — 공격범위 박스는 드래그 후 색상(●설정됨)으로 확인 (숫자 표시 안 함)
    atk_picker = _make_attack_box_picker(c, None, on_done=lambda: atk_status.refresh())
    atk_status = StatusField(
        "공격 범위 박스",
        lambda: c.get("attack", "atk_x_max", default=None) is not None,
        [atk_picker])
    from core_ui.buff_editor import BuffEditor
    buff_editor = BuffEditor(c, ("attack", "normal_buffs"))
    # HP/MP 실시간 % 미리보기 (A Detector 고정 상대좌표). 게임 없거나 실패 시 생략
    combat_extras = []
    try:
        from core.detector import Detector
        from core.screen_reader import ScreenReader
        from core_ui.gauge_preview import GaugePreview
        combat_extras.append(GaugePreview(Detector(ScreenReader(), c)))
    except Exception:
        pass
    combat_extras.append(buff_editor)
    pages.append(_page("전투", "공격·버프·물약·펫·줍기", [
        TextField("공격 키", c, ("attack", "key"), default="ctrl"),
        atk_status,
        IntField("공격 범위(px)", c, ("attack", "range_px"), 0, 2000, default=350),
        CheckField("공격 전 점프", c, ("attack", "jump_before_attack")),
        TextField("점프 키", c, ("minimap", "jump_key"), default="alt"),
        CheckField("HP 물약 사용", c, ("recovery", "hp_potion", "enabled")),
        IntField("HP 물약 임계%", c, ("recovery", "hp_potion", "threshold"), 0, 100, default=65),
        TextField("HP 물약 키", c, ("recovery", "hp_potion", "key")),
        CheckField("MP 물약 사용", c, ("recovery", "mp_potion", "enabled")),
        IntField("MP 물약 임계%", c, ("recovery", "mp_potion", "threshold"), 0, 100, default=50),
        TextField("MP 물약 키", c, ("recovery", "mp_potion", "key")),
        CheckField("펫 먹이 사용", c, ("recovery", "pet_food", "enabled")),
        TextField("펫 먹이 키", c, ("recovery", "pet_food", "key")),
        IntField("펫 먹이 간격(분)", c, ("recovery", "pet_food", "interval_min"), 1, 120, default=10),
    ], extras=combat_extras))

    # 4. 안전·안티밴 — 거탐 알림(소리+텔레그램) 통합
    pages.append(_page("안전·안티밴", "거탐·방지몹·유저감지·자동응답·채널변경·인간화강도", [
        CheckField("거탐 감지", c, ("settings1", "lie_detector", "enabled")),
        CheckField("거탐 알림 (소리+텔레그램)", c, ("settings1", "lie_detector", "alert_enabled")),
        TextField("텔레그램 토큰", c, ("settings1", "lie_detector", "tg_token")),
        TextField("텔레그램 챗ID", c, ("settings1", "lie_detector", "tg_chat_id")),
        CheckField("투명도형 자동풀이", c, ("settings1", "transparent_shape", "enabled")),
        CheckField("다른 유저 감지", c, ("settings1", "user_detected", "enabled")),
        CheckField("방지몹 해제", c, ("anti_mob", "enabled")),
    ]))

    # 5. 자동화·운영 — 맵이탈 감지영역은 드래그 후 색상으로 확인
    mapexit_picker = _make_region_picker(
        c, [("map_exit", "region_x"), ("map_exit", "region_y"),
            ("map_exit", "width"), ("map_exit", "height")],
        None, "맵이탈 감지", on_done=lambda: mapexit_status.refresh())
    mapexit_status = StatusField(
        "맵이탈 영역", lambda: int(c.get("map_exit", "width", default=0)) > 0,
        [mapexit_picker])
    pages.append(_page("자동화·운영", "자동판매·마을귀환·예약종료·픽업·텔레그램·찰리중사", [
        CheckField("맵 이탈 감지", c, ("map_exit", "enabled")),
        mapexit_status,
        CheckField("긴급 마을귀환", c, ("town_scroll", "enabled")),
        TextField("마을귀환 키", c, ("town_scroll", "key"), default="9"),
        CheckField("픽업 타이머", c, ("pickup_timer", "enabled")),
        IntField("픽업 간격(초)", c, ("pickup_timer", "interval_sec"), 1, 3600, default=60),
        TextField("픽업 키", c, ("pickup_timer", "pickup_key")),
    ]))

    # 6. 시스템
    pages.append(_page("시스템", "라이선스·업데이트·저사양/원격·입력백엔드·YOLO캡처", [
        CheckField("공격 모듈", c, ("modules", "attack"), default=True),
        CheckField("이동 모듈", c, ("modules", "move"), default=True),
        CheckField("물약 모듈", c, ("modules", "potion"), default=True),
        CheckField("거탐 알림 모듈", c, ("modules", "lie_notify"), default=True),
        CheckField("거탐 풀이 모듈", c, ("modules", "lie_solve"), default=True),
        TextField("게임창 제목", c, ("settings2", "game_window_title"), default="MapleStory Worlds"),
    ]))

    return pages
