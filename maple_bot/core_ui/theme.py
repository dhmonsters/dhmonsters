# 밝은 제어판 디자인 토큰과 PyQt6 공통 스타일을 관리한다.
from __future__ import annotations

# ── 색 (Claude Control Light) ─────────────────────────────────────
TOKENS = {
    "canvas":          "#f3f5f2",   # 앱 배경
    "surface_1":       "#ffffff",   # 내비/컨트롤바/사이드 패널
    "surface_2":       "#ffffff",   # 카드
    "surface_3":       "#edf2ee",   # 입력/선택/호버
    "surface_4":       "#dde6df",   # pressed/strong
    "hairline":        "#d8ded8",
    "hairline_strong": "#becbc2",
    "ink":             "#17211d",   # 본문
    "ink_muted":       "#52635a",
    "ink_subtle":      "#6f7f76",
    "ink_tertiary":    "#8a988f",
    "primary":         "#0f766e",   # 주요 강조/CTA
    "primary_hover":   "#0b625c",
    "primary_focus":   "#094e49",
    "on_primary":      "#ffffff",
    "accent":          "#d97745",   # 보조 강조
    "success":         "#27845f",   # 상태/성공
    "danger":          "#c2413b",   # HP/위험
    "info":            "#356fa3",   # MP
    "char":            "#ffd33d",   # 캐릭터(노란 점)
}

# ── 간격 (px) ─────────────────────────────────────────────────────
SPACING = {
    "xxs": 4, "xs": 8, "sm": 12, "md": 16,
    "lg": 24, "xl": 32, "xxl": 48, "section": 96,
}

# ── 반경 (둥글고 부드럽게) ────────────────────────────────────────
RADIUS = {"sm": 8, "md": 11, "lg": 14, "xl": 14, "pill": 999}

# ── 타이포 ────────────────────────────────────────────────────────
TYPOGRAPHY = {
    "h1":         {"size": 22, "weight": 700, "tracking": -0.3},
    "card_title": {"size": 14, "weight": 600, "tracking": -0.2},
    "subhead":    {"size": 13, "weight": 500, "tracking": -0.1},
    "body":       {"size": 13, "weight": 400, "tracking": -0.05},
    "caption":    {"size": 11, "weight": 400, "tracking": 0.0},
}

# ── 폰트 (Pretendard 유지 — 한글+Latin) ───────────────────────────
FONT_SANS = '"Pretendard Variable", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif'
FONT_MONO = '"JetBrains Mono", ui-monospace, "Consolas", monospace'
LETTER_SPACING_PX = -0.2


def apply_font(app, base_pt: int = 10):
    """번들 Pretendard+JetBrains Mono 런타임 로드(시스템 설치 불필요) + 전역 폰트/트래킹.
    Pretendard는 한글+Latin 모두 포함 → 한글 깨짐 없음. 폴백으로 맑은 고딕도 지정."""
    from pathlib import Path
    from PyQt6.QtGui import QFont, QFontDatabase

    fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    family = "Pretendard Variable"
    for fn, fam in [("PretendardVariable.ttf", "Pretendard"),
                    ("JetBrainsMono-Regular.ttf", "JetBrains Mono")]:
        p = fonts_dir / fn
        if p.exists():
            fid = QFontDatabase.addApplicationFont(str(p))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if fams and fam == "Pretendard":
                family = fams[0]

    safe_pt = base_pt if base_pt > 0 else 10
    f = QFont(family, safe_pt)
    f.setFamilies([family, "Malgun Gothic", "Segoe UI"])
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, LETTER_SPACING_PX)
    app.setFont(f)
    return family


def build_qss() -> str:
    """Discord Night 토큰으로 전역 QSS — 다크+네온, 둥근 카드, 호버/클릭 마이크로인터랙션.
    (PyQt QSS는 box-shadow/transition 미지원 → 글로우는 색/테두리로 근사, 상태별 즉각 피드백.)"""
    t = TOKENS
    s, r = SPACING, RADIUS
    h1, ct, bd = TYPOGRAPHY["h1"], TYPOGRAPHY["card_title"], TYPOGRAPHY["body"]
    grad = f"qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t['primary']}, stop:1 {t['primary_hover']})"
    return f"""
    QWidget {{
        background-color: {t['canvas']};
        color: {t['ink']};
        font-family: {FONT_SANS};
        font-size: {bd['size']}px;
    }}
    QFrame#card, QWidget#card {{
        background-color: {t['surface_2']};
        border: 1px solid {t['hairline']};
        border-radius: {r['lg']}px;
    }}
    QLabel {{ background: transparent; }}
    QLabel#h1 {{ font-size: {h1['size']}px; font-weight: {h1['weight']}; color: {t['ink']}; }}
    QLabel#cardTitle {{ font-size: {ct['size']}px; font-weight: {ct['weight']}; color: {t['ink']}; }}
    QLabel#subtle {{ color: {t['ink_subtle']}; }}

    /* 기본 버튼 */
    QPushButton {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border: 1px solid {t['hairline_strong']};
        border-radius: {r['md']}px;
        padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton:hover {{ background-color: {t['surface_3']}; border-color: {t['primary']}; }}
    QPushButton:pressed {{ background-color: {t['surface_4']}; }}

    /* CTA(블러플 그라데이션) */
    QPushButton#primary, QPushButton#startBtn {{
        background: {grad};
        color: {t['on_primary']};
        border: none;
        border-radius: {r['md']}px;
        font-weight: 700;
        padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton#primary:hover, QPushButton#startBtn:hover {{ background-color: {t['primary_hover']}; }}
    QPushButton#primary:pressed, QPushButton#startBtn:pressed {{ background-color: {t['primary_focus']}; }}
    QPushButton#stopBtn {{
        background-color: {t['surface_2']}; color: {t['ink_muted']};
        border: 1px solid {t['hairline_strong']}; border-radius: {r['md']}px; padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton#stopBtn:hover {{ background-color: {t['surface_3']}; color: {t['ink']}; }}

    /* 상단 내비 */
    QWidget#topnav {{ background-color: {t['surface_1']}; border-bottom: 1px solid {t['hairline']}; }}
    QLabel#logo {{ font-size: 14px; font-weight: 700; color: {t['ink']}; }}
    QPushButton#navtab {{
        background-color: transparent; border: none; color: {t['ink_muted']};
        border-radius: {r['sm']}px; padding: {s['xs']}px {s['sm']}px; font-size: 13px;
    }}
    QPushButton#navtab:hover {{ color: {t['ink']}; background-color: {t['surface_2']}; }}
    QPushButton#navtab:checked {{
        color: {t['ink']}; background-color: {t['surface_3']};
        border-bottom: 2px solid {t['primary']}; font-weight: 600;
    }}
    QLabel#statusChip {{ color: {t['success']}; font-size: 12px; background: transparent; }}

    /* 하단 컨트롤바 */
    QWidget#controlbar {{ background-color: {t['surface_1']}; border-top: 1px solid {t['hairline']}; }}

    /* 좌측 nav (레거시 호환) */
    QPushButton#nav {{
        background-color: transparent; border: none; text-align: left;
        padding: {s['sm']}px; color: {t['ink_subtle']}; border-radius: {r['sm']}px;
    }}
    QPushButton#nav:hover {{ color: {t['ink_muted']}; background-color: {t['surface_2']}; }}
    QPushButton#nav:checked {{ background-color: {t['surface_3']}; color: {t['ink']}; border-left: 2px solid {t['primary']}; }}

    /* 입력 위젯 (둥근·포커스 강조, 글자 안 잘리게 min-height) */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t['surface_3']}; color: {t['ink']};
        border: 1px solid {t['hairline_strong']}; border-radius: {r['sm']}px;
        padding: 2px 8px; min-height: 22px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {t['primary']}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox::down-arrow {{
        width: 0; height: 0; margin-right: 6px;
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-top: 5px solid {t['ink_muted']};
    }}
    /* 스핀박스 업다운 — 깔끔한 삼각 화살표 */
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border; subcontrol-position: top right; width: 16px;
        background: {t['surface_4']}; border-top-right-radius: {r['sm']}px; border: none;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border; subcontrol-position: bottom right; width: 16px;
        background: {t['surface_4']}; border-bottom-right-radius: {r['sm']}px; border: none;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {t['primary']}; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        width: 0; height: 0;
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-bottom: 5px solid {t['ink_muted']};
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        width: 0; height: 0;
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-top: 5px solid {t['ink_muted']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['surface_2']}; color: {t['ink']};
        border: 1px solid {t['hairline_strong']}; selection-background-color: {t['primary']};
        border-radius: {r['sm']}px;
    }}
    QCheckBox {{ color: {t['ink']}; }}

    /* 슬라이더(임계값 바) — 둥근 트랙 + 네온 핸들 */
    QSlider::groove:horizontal {{ height: 6px; background: {t['surface_4']}; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {t['primary']}; border-radius: 3px; }}
    QSlider::handle:horizontal {{
        background: {t['ink']}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {t['primary_hover']}; }}

    /* 블록 리스트 카드 */
    QListWidget#blockList {{ background-color: transparent; border: none; outline: none; }}
    QListWidget#blockList::item {{
        background-color: {t['surface_2']}; border: 1px solid {t['hairline']};
        border-radius: {r['md']}px; margin: 2px 0;
    }}
    QListWidget#blockList::item:selected {{ border: 1px solid {t['primary']}; background-color: {t['surface_3']}; }}

    QTextEdit#log {{
        background-color: {t['surface_1']}; border: 1px solid {t['hairline']};
        border-radius: {r['md']}px; color: {t['ink_muted']};
        font-family: {FONT_MONO}; font-size: {bd['size']}px;
    }}

    /* 스크롤바 (얇고 둥글게) */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t['surface_4']}; border-radius: 5px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['primary']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    /* 세로 스플리터 핸들 — 로그창 크기조절용(잡기 쉽게 보이는 그립) */
    QSplitter#vsplit::handle:vertical {{
        background: {t['surface_3']}; height: 8px; margin: 2px 0;
        border-top: 1px solid {t['hairline_strong']}; border-bottom: 1px solid {t['hairline_strong']};
    }}
    QSplitter#vsplit::handle:vertical:hover {{ background: {t['primary']}; }}
    QFrame#huntGroundPresetCard {{
        background-color: {t['surface_2']}; border: 1px solid {t['hairline_strong']};
        border-radius: {r['lg']}px;
    }}
    QLabel#presetTitle {{ color: {t['ink']}; font-size: 16px; font-weight: 700; }}
    QLabel#presetDescription {{ color: {t['ink_muted']}; }}
    QLabel#presetStatus {{ color: {t['primary']}; font-weight: 600; }}
    QPushButton#primaryButton {{
        background-color: {t['primary']}; color: {t['on_primary']}; border: none;
        border-radius: {r['md']}px; padding: {s['xs']}px {s['md']}px; font-weight: 700;
    }}
    QPushButton#primaryButton:hover {{ background-color: {t['primary_hover']}; }}
    """
