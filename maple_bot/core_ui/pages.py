# 6 카테고리 설정 페이지 — config 키를 폼 필드로 바인딩. shell이 카테고리별로 호출
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QPushButton

from core_ui.theme import SPACING
from core_ui.widgets import CheckField, TextField, IntField, ComboField, FloatField


def _make_region_picker(config, keys_xywh, fields_xywh, label: str) -> QPushButton:
    """'영역 선택' 버튼 — 전체화면 캡처 → 스크린샷 위 드래그 → config 4키 저장 + 필드 갱신.

    keys_xywh: ((sec,..,'region_x'), y키, w키, h키)
    fields_xywh: 갱신할 IntField 4개 (드래그 결과를 위젯에 반영)
    """
    btn = QPushButton(f"📐 {label} 영역 선택 (게임 스크린샷에서 드래그)")
    btn.setObjectName("primary")

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
            for key, fld, val in zip(keys_xywh, fields_xywh, (x, y, w, h)):
                config.set(*key, val)
                fld.widget.setValue(val)   # IntField 위젯 갱신
            config.save()
        dlg.region_selected.connect(apply)
        dlg.exec()

    btn.clicked.connect(on_click)
    return btn


def _make_attack_box_picker(config, fields4) -> QPushButton:
    """공격범위 박스 픽커 — 스크린샷 위에 기존범위 미리보기 + 드래그로 갱신.
    화면 중앙을 캐릭(앵커) 기준점으로 가정해 상대 오프셋(atk_x/y_min/max) 환산.
    fields4: 갱신할 IntField [x_min, x_max, y_min, y_max]."""
    btn = QPushButton("🎯 공격 범위 박스 (스크린샷 드래그, 기존범위 표시)")
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
            for key, fld, val in zip(
                ["atk_x_min", "atk_x_max", "atk_y_min", "atk_y_max"], fields4, o):
                config.set("attack", key, val)
                fld.widget.setValue(val)
            config.save()
        dlg.region_selected.connect(apply)
        dlg.exec()

    btn.clicked.connect(on_click)
    return btn


def _make_template_capture(config, save_path, config_key, label: str) -> QPushButton:
    """'이미지 캡처' 버튼 — 스크린샷에서 영역 드래그 → 그 부분을 잘라 png 저장 + config에 경로.

    save_path: 저장할 png 경로(templates/...). config_key: 경로 저장할 config 키.
    """
    btn = QPushButton(f"📷 {label} 캡처 (스크린샷에서 드래그)")

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
        dlg.region_selected.connect(crop_save)
        dlg.exec()

    btn.clicked.connect(on_click)
    return btn


def _page(title: str, desc: str, fields: list, buttons: list | None = None,
          extras: list | None = None) -> QWidget:
    """제목 + 설명 + (버튼들) + 폼 필드들 + (임의 위젯 extras)를 담은 스크롤 페이지."""
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
    for w in (extras or []):
        v.addWidget(w)
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

    # 1. 연결·인식 — 미니맵 영역은 스크린샷 드래그로 실측
    mm_x = IntField("미니맵 X", c, ("minimap", "region_x"), 0, 4000)
    mm_y = IntField("미니맵 Y", c, ("minimap", "region_y"), 0, 4000)
    mm_w = IntField("미니맵 W", c, ("minimap", "width"), 0, 4000)
    mm_h = IntField("미니맵 H", c, ("minimap", "height"), 0, 4000)
    minimap_picker = _make_region_picker(
        c,
        [("minimap", "region_x"), ("minimap", "region_y"),
         ("minimap", "width"), ("minimap", "height")],
        [mm_x, mm_y, mm_w, mm_h],
        "미니맵",
    )
    monster_cap = _make_template_capture(
        c, "templates/monster_capture.png", ("attack", "monster_template"), "몬스터",
    )
    name_cap = _make_template_capture(
        c, "templates/name_tag.png", ("attack", "name_template"), "닉네임",
    )
    # 사냥 영역 (B training 방식) — 이 사각형 안에서만 닉네임/몬스터 감지 (전체화면 대비 빠름)
    ha_x = IntField("사냥영역 X", c, ("attack", "hunt_area", "x"), 0, 4000)
    ha_y = IntField("사냥영역 Y", c, ("attack", "hunt_area", "y"), 0, 4000)
    ha_w = IntField("사냥영역 W", c, ("attack", "hunt_area", "w"), 0, 4000)
    ha_h = IntField("사냥영역 H", c, ("attack", "hunt_area", "h"), 0, 4000)
    hunt_area_picker = _make_region_picker(
        c,
        [("attack", "hunt_area", "x"), ("attack", "hunt_area", "y"),
         ("attack", "hunt_area", "w"), ("attack", "hunt_area", "h")],
        [ha_x, ha_y, ha_w, ha_h],
        "사냥",
    )
    pages.append(_page("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지", [
        ComboField("사냥 모드", c, ("hunt_mode",), ["key", "image", "coordinate"]),
        mm_x, mm_y, mm_w, mm_h,
        IntField("색 허용오차", c, ("minimap", "tolerance"), 0, 255, default=30),
        TextField("점프 키", c, ("minimap", "jump_key"), default="alt"),
        # 사냥 영역 (B training: 이 영역 안에서만 감지)
        ha_x, ha_y, ha_w, ha_h,
        FloatField("몬스터 임계값", c, ("attack", "monster_accuracy"), 0.1, 1.0, default=0.9),
        FloatField("닉네임 임계값", c, ("attack", "name_tag_threshold"), 0.1, 1.0, default=0.7),
    ], buttons=[minimap_picker, hunt_area_picker, monster_cap, name_cap]))

    # 2. 동선·이동 — 좌표 동선은 블록 빌더로 (이동/공격/사다리 순차)
    from core_ui.block_editor import BlockEditor
    from PyQt6.QtWidgets import QLabel as _QLabel
    route_lbl = _QLabel("좌표 동선 블록 (위→아래 순서 실행)")
    route_lbl.setObjectName("subtle")
    block_editor = BlockEditor(c, ("floor_hunt", "route"))
    pages.append(_page("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋", [
        CheckField("층별 사냥 사용", c, ("floor_hunt", "enabled")),
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
        TextField("현재 사냥터", c, ("hunt_grounds", "active")),
        ComboField("좌표 기준", c, ("coord_mode",), ["relative", "absolute"], default="relative"),
    ], extras=[route_lbl, block_editor]))

    # 3. 전투 — 공격범위 박스(닉네임 기준 상대 오프셋, 드래그로 설정)
    atk_xmn = IntField("공격범위 ←(px)", c, ("attack", "atk_x_min"), -1000, 0, default=-35)
    atk_xmx = IntField("공격범위 →(px)", c, ("attack", "atk_x_max"), 0, 1000, default=35)
    atk_ymn = IntField("공격범위 ↑(px)", c, ("attack", "atk_y_min"), -1000, 0, default=-70)
    atk_ymx = IntField("공격범위 ↓(px)", c, ("attack", "atk_y_max"), 0, 1000, default=70)
    atk_picker = _make_attack_box_picker(c, [atk_xmn, atk_xmx, atk_ymn, atk_ymx])
    from core_ui.buff_editor import BuffEditor
    buff_editor = BuffEditor(c, ("attack", "normal_buffs"))
    pages.append(_page("전투", "공격·버프·물약·펫·줍기", [
        TextField("공격 키", c, ("attack", "key"), default="ctrl"),
        atk_xmn, atk_xmx, atk_ymn, atk_ymx,
        IntField("공격 범위(px)", c, ("attack", "range_px"), 0, 2000, default=350),
        CheckField("공격 전 점프", c, ("attack", "jump_before_attack")),
        CheckField("HP 물약 사용", c, ("recovery", "hp_potion", "enabled")),
        IntField("HP 물약 임계%", c, ("recovery", "hp_potion", "threshold"), 0, 100, default=65),
        TextField("HP 물약 키", c, ("recovery", "hp_potion", "key")),
        CheckField("MP 물약 사용", c, ("recovery", "mp_potion", "enabled")),
        IntField("MP 물약 임계%", c, ("recovery", "mp_potion", "threshold"), 0, 100, default=50),
        TextField("MP 물약 키", c, ("recovery", "mp_potion", "key")),
        CheckField("펫 먹이 사용", c, ("recovery", "pet_food", "enabled")),
        TextField("펫 먹이 키", c, ("recovery", "pet_food", "key")),
        IntField("펫 먹이 간격(분)", c, ("recovery", "pet_food", "interval_min"), 1, 120, default=10),
    ], buttons=[atk_picker], extras=[buff_editor]))

    # 4. 안전·안티밴
    pages.append(_page("안전·안티밴", "거탐·방지몹·유저감지·자동응답·채널변경·인간화강도", [
        CheckField("거탐 감지", c, ("settings1", "lie_detector", "enabled")),
        CheckField("거탐 알림음", c, ("settings1", "lie_detector", "play_alarm")),
        CheckField("투명도형 자동풀이", c, ("settings1", "transparent_shape", "enabled")),
        CheckField("다른 유저 감지", c, ("settings1", "user_detected", "enabled")),
        CheckField("방지몹 해제", c, ("anti_mob", "enabled")),
    ]))

    # 5. 자동화·운영
    pages.append(_page("자동화·운영", "자동판매·마을귀환·예약종료·레벨정지·텔레그램·찰리중사", [
        CheckField("맵 이탈 감지", c, ("map_exit", "enabled")),
        CheckField("긴급 마을귀환", c, ("town_scroll", "enabled")),
        TextField("마을귀환 키", c, ("town_scroll", "key"), default="9"),
        CheckField("픽업 타이머", c, ("pickup_timer", "enabled")),
        IntField("픽업 간격(초)", c, ("pickup_timer", "interval_sec"), 1, 3600, default=60),
        TextField("픽업 키", c, ("pickup_timer", "pickup_key")),
        CheckField("텔레그램 알림", c, ("settings1", "lie_detector", "tg_enabled")),
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
