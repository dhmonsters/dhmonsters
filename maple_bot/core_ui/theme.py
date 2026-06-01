# Linear 디자인 토큰 → PyQt6 QSS/QFont. DESIGN.md(Linear)를 단일 출처로 — 색·폰트·간격·반경·타이포 전부
from __future__ import annotations

# ── 색 (DESIGN.md Linear 1:1) ─────────────────────────────────────
TOKENS = {
    "canvas":          "#010102",   # near-black 배경
    "surface_1":       "#0f1011",   # 차콜 패널 (카드)
    "surface_2":       "#141516",
    "surface_3":       "#18191a",
    "surface_4":       "#191a1b",
    "hairline":        "#23252a",
    "hairline_strong": "#34343a",
    "ink":             "#f7f8f8",   # 본문
    "ink_muted":       "#d0d6e0",
    "ink_subtle":      "#8a8f98",
    "ink_tertiary":    "#62666d",
    "primary":         "#5e6ad2",   # 라벤더 액센트 (포커스/CTA만)
    "primary_hover":   "#828fff",
    "primary_focus":   "#5e69d1",
    "on_primary":      "#ffffff",
    "success":         "#27a644",
}

# ── 간격 (DESIGN.md spacing 토큰, px) ─────────────────────────────
SPACING = {
    "xxs": 4, "xs": 8, "sm": 12, "md": 16,
    "lg": 24, "xl": 32, "xxl": 48, "section": 96,
}

# ── 반경 (DESIGN.md radius) ───────────────────────────────────────
RADIUS = {"sm": 6, "md": 8, "xl": 16}

# ── 타이포 스케일 (DESIGN.md typography: size/weight/tracking) ────
#   음수 트래킹: 큰 글씨일수록 강하게. QFont는 px 자간이라 letterSpacing 그대로 사용.
TYPOGRAPHY = {
    "h1":         {"size": 28, "weight": 600, "tracking": -0.6},   # 봇 UI 스케일(웹 80px→데스크탑 28px)
    "card_title": {"size": 20, "weight": 600, "tracking": -0.4},
    "subhead":    {"size": 16, "weight": 500, "tracking": -0.2},
    "body":       {"size": 13, "weight": 400, "tracking": -0.05},
    "caption":    {"size": 11, "weight": 400, "tracking": 0.0},
}

# ── 폰트 패밀리 (DESIGN.md: Linear Display→Pretendard(한글판 Inter), Mono→JetBrains Mono) ──
#   Inter는 한글 글리프가 없어 □(tofu)로 깨짐 → Latin/한글 모두 커버하는 Pretendard로 통일.
FONT_SANS = '"Pretendard Variable", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif'
FONT_MONO = '"JetBrains Mono", ui-monospace, "Consolas", monospace'
LETTER_SPACING_PX = -0.2   # body 기준 기본 트래킹


def apply_font(app, base_pt: int = 10):
    """번들 Pretendard+JetBrains Mono 런타임 로드(시스템 설치 불필요) + 전역 폰트/트래킹.
    Pretendard는 한글+Latin 모두 포함 → 한글 깨짐 없음. 폴백으로 맑은 고딕도 지정."""
    from pathlib import Path
    from PyQt6.QtGui import QFont, QFontDatabase

    fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    family = "Pretendard Variable"
    for fn, fam in [("PretendardVariable.ttf", "Pretendard"),   # 가변폰트 1개로 전 굵기 커버
                    ("JetBrainsMono-Regular.ttf", "JetBrains Mono")]:
        p = fonts_dir / fn
        if p.exists():
            fid = QFontDatabase.addApplicationFont(str(p))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if fams and fam == "Pretendard":
                family = fams[0]   # 'Pretendard Variable'

    f = QFont(family)
    # 글리프 누락 시 맑은 고딕→Segoe UI 순으로 글자단위 폴백 (한글 보장)
    f.setFamilies([family, "Malgun Gothic", "Segoe UI"])
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setPointSize(base_pt)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, LETTER_SPACING_PX)
    app.setFont(f)
    return family


def build_qss() -> str:
    """Linear 토큰으로 전역 QSS 생성 — surface 사다리·hairline·spacing·radius 반영."""
    t = TOKENS
    s, r = SPACING, RADIUS
    h1, ct, bd = TYPOGRAPHY["h1"], TYPOGRAPHY["card_title"], TYPOGRAPHY["body"]
    return f"""
    QWidget {{
        background-color: {t['canvas']};
        color: {t['ink']};
        font-family: {FONT_SANS};
        font-size: {bd['size']}px;
    }}
    QFrame#card, QWidget#card {{
        background-color: {t['surface_1']};
        border: 1px solid {t['hairline']};
        border-radius: {r['xl']}px;
    }}
    QLabel#h1 {{
        font-size: {h1['size']}px; font-weight: {h1['weight']}; color: {t['ink']};
    }}
    QLabel#cardTitle {{ font-size: {ct['size']}px; font-weight: {ct['weight']}; color: {t['ink']}; }}
    QLabel#subtle {{ color: {t['ink_subtle']}; }}
    QPushButton {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border: 1px solid {t['hairline']};
        border-radius: {r['md']}px;
        padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton:hover {{ border-color: {t['hairline_strong']}; background-color: {t['surface_3']}; }}
    QPushButton:pressed {{ background-color: {t['surface_4']}; }}
    QPushButton#primary {{
        background-color: {t['primary']};
        color: {t['on_primary']};
        border: none;
        border-radius: {r['md']}px;
        font-weight: 600;
        padding: {s['xs']}px {s['md']}px;
    }}
    QPushButton#primary:hover {{ background-color: {t['primary_hover']}; }}
    QPushButton#primary:pressed {{ background-color: {t['primary_focus']}; }}
    QPushButton#nav {{
        background-color: transparent;
        border: none;
        text-align: left;
        padding: {s['sm']}px {s['sm']}px;
        color: {t['ink_subtle']};
        border-radius: {r['sm']}px;
    }}
    QPushButton#nav:hover {{ color: {t['ink_muted']}; background-color: {t['surface_2']}; }}
    QPushButton#nav:checked {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border-left: 2px solid {t['primary']};
    }}
    QListWidget#blockList {{
        background-color: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#blockList::item {{
        background-color: {t['surface_1']};
        border: 1px solid {t['hairline']};
        border-radius: {r['md']}px;
        margin: 2px 0;
    }}
    QListWidget#blockList::item:selected {{
        border: 1px solid {t['primary']};
        background-color: {t['surface_2']};
    }}
    QTextEdit#log {{
        background-color: {t['surface_1']};
        border: 1px solid {t['hairline']};
        border-radius: {r['md']}px;
        color: {t['ink_muted']};
        font-family: {FONT_MONO};
        font-size: {bd['size']}px;
    }}
    """
