# 6 카테고리 설정 페이지 — config 키를 폼 필드로 바인딩. shell이 카테고리별로 호출
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea

from core_ui.theme import SPACING
from core_ui.widgets import CheckField, TextField, IntField, ComboField


def _page(title: str, desc: str, fields: list) -> QWidget:
    """제목 + 설명 + 폼 필드들을 담은 스크롤 페이지."""
    inner = QWidget()
    v = QVBoxLayout(inner)
    v.setContentsMargins(SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"])
    v.setSpacing(SPACING["xs"])

    h = QLabel(title); h.setObjectName("h1")
    sub = QLabel(desc); sub.setObjectName("subtle"); sub.setWordWrap(True)
    v.addWidget(h); v.addWidget(sub)
    v.addSpacing(SPACING["md"])
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

    # 1. 연결·인식
    pages.append(_page("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지", [
        ComboField("사냥 모드", c, ("hunt_mode",), ["key", "coord"]),
        IntField("미니맵 X", c, ("minimap", "region_x"), 0, 4000),
        IntField("미니맵 Y", c, ("minimap", "region_y"), 0, 4000),
        IntField("미니맵 W", c, ("minimap", "width"), 0, 4000),
        IntField("미니맵 H", c, ("minimap", "height"), 0, 4000),
        IntField("색 허용오차", c, ("minimap", "tolerance"), 0, 255, default=30),
        TextField("점프 키", c, ("minimap", "jump_key"), default="alt"),
    ]))

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
