# Claude 전역 PyQt6 테마와 폰트 설정을 정의한다.
from __future__ import annotations

TOKENS = {
    "canvas": "#f4f7f2",
    "surface_1": "#fbfdf9",
    "surface_2": "#ffffff",
    "surface_3": "#eef5ef",
    "surface_4": "#dfeae2",
    "hairline": "#cfdcd2",
    "hairline_strong": "#adc3b4",
    "ink": "#13231b",
    "ink_muted": "#50645a",
    "ink_subtle": "#718177",
    "ink_tertiary": "#8b988f",
    "primary": "#007f72",
    "primary_hover": "#0a988a",
    "primary_focus": "#00685e",
    "on_primary": "#ffffff",
    "accent": "#d86b45",
    "success": "#138a57",
    "danger": "#d13f35",
    "info": "#2f6fb3",
    "char": "#ffd33d",
}

SPACING = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "xxl": 48,
    "section": 96,
}

RADIUS = {"sm": 8, "md": 11, "lg": 14, "xl": 14, "pill": 999}

TYPOGRAPHY = {
    "h1": {"size": 22, "weight": 700, "tracking": -0.3},
    "card_title": {"size": 14, "weight": 600, "tracking": -0.2},
    "subhead": {"size": 13, "weight": 500, "tracking": -0.1},
    "body": {"size": 13, "weight": 400, "tracking": -0.05},
    "caption": {"size": 11, "weight": 400, "tracking": 0.0},
}

FONT_SANS = '"Pretendard Variable", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif'
FONT_MONO = '"JetBrains Mono", "Consolas", monospace'
LETTER_SPACING_PX = -0.2


def apply_font(app, base_pt: int = 10):
    """번들 폰트를 로드하고 전역 기본 폰트를 적용한다."""
    from pathlib import Path
    from PyQt6.QtGui import QFont, QFontDatabase

    fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    family = "Pretendard Variable"
    for fn, fam in [("PretendardVariable.ttf", "Pretendard"), ("JetBrainsMono-Regular.ttf", "JetBrains Mono")]:
        p = fonts_dir / fn
        if p.exists():
            fid = QFontDatabase.addApplicationFont(str(p))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if fams and fam == "Pretendard":
                family = fams[0]

    safe_base_pt = max(9, int(base_pt or 10))
    font = QFont(family)
    font.setFamilies([family, "Malgun Gothic", "Segoe UI"])
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPointSize(safe_base_pt)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, LETTER_SPACING_PX)
    app.setFont(font)
    return family


def build_qss() -> str:
    """Claude 테마 QSS를 생성한다."""
    t = TOKENS
    s = SPACING
    r = RADIUS
    h1 = TYPOGRAPHY["h1"]
    ct = TYPOGRAPHY["card_title"]
    bd = TYPOGRAPHY["body"]
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
    QLabel {{
        background: transparent;
    }}
    QLabel#h1 {{
        font-size: {h1['size']}px;
        font-weight: {h1['weight']};
        color: {t['ink']};
    }}
    QLabel#cardTitle {{
        font-size: {ct['size']}px;
        font-weight: {ct['weight']};
        color: {t['ink']};
    }}
    QLabel#subtle {{
        color: {t['ink_subtle']};
    }}
    QWidget#topnav {{
        background-color: {t['surface_1']};
        border-bottom: 1px solid {t['hairline']};
    }}
    QLabel#logo {{
        font-size: 14px;
        font-weight: 700;
        color: {t['ink']};
    }}
    QPushButton {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border: 1px solid {t['hairline_strong']};
        border-radius: {r['md']}px;
        padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton:hover {{
        background-color: {t['surface_3']};
        border-color: {t['primary']};
    }}
    QPushButton:pressed {{
        background-color: {t['surface_4']};
    }}
    QPushButton#primary, QPushButton#primaryButton, QPushButton#startBtn {{
        background-color: {t['primary']};
        color: {t['on_primary']};
        border: none;
        border-radius: {r['md']}px;
        font-weight: 700;
        padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton#primary:hover, QPushButton#primaryButton:hover, QPushButton#startBtn:hover {{
        background-color: {t['primary_hover']};
    }}
    QPushButton#primary:pressed, QPushButton#primaryButton:pressed, QPushButton#startBtn:pressed {{
        background-color: {t['primary_focus']};
    }}
    QPushButton#stopBtn {{
        background-color: {t['surface_2']};
        color: {t['ink_muted']};
        border: 1px solid {t['hairline_strong']};
        border-radius: {r['md']}px;
        padding: {s['xs']}px {s['md']}px;
    }}
    QWidget#controlbar {{
        background-color: {t['surface_1']};
        border-top: 1px solid {t['hairline']};
    }}
    QPushButton#navtab {{
        background-color: transparent;
        border: none;
        color: {t['ink_muted']};
        border-radius: {r['sm']}px;
        padding: {s['xs']}px {s['sm']}px;
        font-size: 13px;
    }}
    QPushButton#navtab:hover {{
        color: {t['ink']};
        background-color: {t['surface_3']};
    }}
    QPushButton#navtab:checked {{
        color: {t['ink']};
        background-color: {t['surface_2']};
        border-bottom: 2px solid {t['primary']};
        font-weight: 600;
    }}
    QLabel#statusChip {{
        color: {t['success']};
        font-size: 12px;
        background: transparent;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t['surface_3']};
        color: {t['ink']};
        border: 1px solid {t['hairline_strong']};
        border-radius: {r['sm']}px;
        padding: 2px 8px;
        min-height: 22px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {t['primary']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border: 1px solid {t['hairline_strong']};
        selection-background-color: {t['surface_4']};
        border-radius: {r['sm']}px;
    }}
    QCheckBox {{
        color: {t['ink']};
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: {t['surface_4']};
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t['primary']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {t['primary']};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QListWidget#blockList {{
        background-color: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#blockList::item {{
        background-color: {t['surface_2']};
        border: 1px solid {t['hairline']};
        border-radius: {r['md']}px;
        margin: 2px 0;
    }}
    QListWidget#blockList::item:selected {{
        border: 1px solid {t['primary']};
        background-color: {t['surface_3']};
    }}
    QTextEdit#log {{
        background-color: {t['surface_2']};
        border: 1px solid {t['hairline']};
        border-radius: {r['md']}px;
        color: {t['ink_muted']};
        font-family: {FONT_MONO};
        font-size: {bd['size']}px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['surface_4']};
        border-radius: 5px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t['primary']};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
    }}
    QSplitter#vsplit::handle:vertical {{
        background: {t['surface_4']};
        height: 8px;
        margin: 2px 0;
        border-top: 1px solid {t['hairline_strong']};
        border-bottom: 1px solid {t['hairline_strong']};
    }}
    """


