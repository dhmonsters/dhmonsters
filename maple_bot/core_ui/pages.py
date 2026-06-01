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


def _page(title: str, desc: str, fields: list, buttons: list | None = None) -> QWidget:
    """제목 + 설명 + (버튼들) + 폼 필드들을 담은 스크롤 페이지."""
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
    pages.append(_page("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지", [
        ComboField("사냥 모드", c, ("hunt_mode",), ["key", "image", "coordinate"]),
        mm_x, mm_y, mm_w, mm_h,
        IntField("색 허용오차", c, ("minimap", "tolerance"), 0, 255, default=30),
        TextField("점프 키", c, ("minimap", "jump_key"), default="alt"),
        # 사냥 영역 (몬스터 탐색 범위)
        IntField("공격 범위(px)", c, ("attack", "range_px"), 0, 2000, default=350),
        FloatField("카메라 폭 비율", c, ("attack", "camera_w_ratio"), 0.1, 1.0, default=0.5),
        FloatField("캐릭터 Y 비율", c, ("attack", "char_y_ratio"), 0.1, 1.0, default=0.6),
        # 닉네임 인식 (이미지 모드에서 본인 식별)
        FloatField("닉네임 임계값", c, ("attack", "name_tag_threshold"), 0.1, 1.0, default=0.7),
        IntField("닉네임 Y 오프셋", c, ("attack", "name_tag_y_offset"), -500, 500, default=138),
    ], buttons=[minimap_picker, monster_cap, name_cap]))

    # 2. 동선·이동
    pages.append(_page("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋", [
        CheckField("층별 사냥 사용", c, ("floor_hunt", "enabled")),
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
        TextField("현재 사냥터", c, ("hunt_grounds", "active")),
        ComboField("좌표 모드", c, ("coord_mode",), ["off", "on"], default="off"),
    ]))

    # 3. 전투
    pages.append(_page("전투", "공격·버프·물약·펫·줍기", [
        TextField("공격 키", c, ("attack", "key"), default="ctrl"),
        IntField("공격 범위(px)", c, ("attack", "range_px"), 0, 2000, default=350),
        CheckField("공격 전 점프", c, ("attack", "jump_before_attack")),
        CheckField("HP 물약 사용", c, ("recovery", "hp_potion", "enabled")),
        IntField("HP 물약 임계%", c, ("recovery", "hp_potion", "threshold"), 0, 100, default=65),
        TextField("HP 물약 키", c, ("recovery", "hp_potion", "key")),
        CheckField("MP 물약 사용", c, ("recovery", "mp_potion", "enabled")),
        IntField("MP 물약 임계%", c, ("recovery", "mp_potion", "threshold"), 0, 100, default=50),
        TextField("MP 물약 키", c, ("recovery", "mp_potion", "key")),
        CheckField("펫 먹이 사용", c, ("recovery", "pet_food", "enabled")),
    ]))

    # 4. 안전·안티밴
    pages.append(_page("안전·안티밴", "거탐·방지몹·유저감지·자동응답·채널변경·인간화강도", [
        CheckField("거탐 감지", c, ("settings1", "lie_detector", "enabled")),
        CheckField("거탐 알림음", c, ("settings1", "lie_detector", "play_alarm")),
        CheckField("투명도형 자동풀이", c, ("settings1", "transparent_shape", "enabled")),
        CheckField("다른 유저 감지", c, ("settings1", "user_detected", "enabled")),
        CheckField("방지몹 해제", c, ("anti_mob", "enabled")),
        CheckField("레벨 도달 정지", c, ("settings1", "level_stop", "enabled")),
        IntField("정지 레벨", c, ("settings1", "level_stop", "target_level"), 1, 300, default=50),
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
