# Linear 디자인 토큰 → PyQt6 QSS 변환. DESIGN.md 를 단일 출처로 한다
from __future__ import annotations

# DESIGN.md(Linear) 토큰 — 색은 DESIGN.md 와 1:1
TOKENS = {
    "canvas":        "#010102",   # near-black 배경
    "surface_1":     "#0f1011",   # 차콜 패널
    "surface_2":     "#141516",
    "surface_3":     "#18191a",
    "hairline":      "#23252a",   # 미세 경계선
    "hairline_strong": "#34343a",
    "ink":           "#f7f8f8",   # 본문 텍스트
    "ink_muted":     "#d0d6e0",
    "ink_subtle":    "#8a8f98",
    "primary":       "#5e6ad2",   # 라벤더 액센트 (포커스/CTA만)
    "primary_hover": "#828fff",
    "on_primary":    "#ffffff",
    "success":       "#27a644",
}

# 간격/반경 — Linear 의 정밀·조밀한 리듬
RADIUS = 8
PAD = 10


def build_qss() -> str:
    """현재 토큰으로 전역 QSS 문자열 생성."""
    t = TOKENS
    return f"""
    QWidget {{
        background-color: {t['canvas']};
        color: {t['ink']};
        font-family: "Segoe UI", "SF Pro Display", sans-serif;
        font-size: 13px;
    }}
    QFrame#card, QWidget#card {{
        background-color: {t['surface_1']};
        border: 1px solid {t['hairline']};
        border-radius: {RADIUS}px;
    }}
    QLabel#h1 {{ font-size: 20px; font-weight: 600; color: {t['ink']}; }}
    QLabel#subtle {{ color: {t['ink_subtle']}; }}
    QPushButton {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border: 1px solid {t['hairline']};
        border-radius: {RADIUS}px;
        padding: {PAD}px 14px;
    }}
    QPushButton:hover {{ border-color: {t['hairline_strong']}; }}
    QPushButton#primary {{
        background-color: {t['primary']};
        color: {t['on_primary']};
        border: none;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{ background-color: {t['primary_hover']}; }}
    QPushButton#nav {{
        background-color: transparent;
        border: none;
        text-align: left;
        padding: {PAD}px 12px;
        color: {t['ink_subtle']};
    }}
    QPushButton#nav:checked {{
        background-color: {t['surface_2']};
        color: {t['ink']};
        border-left: 2px solid {t['primary']};
    }}
    QTextEdit#log {{
        background-color: {t['surface_1']};
        border: 1px solid {t['hairline']};
        border-radius: {RADIUS}px;
        color: {t['ink_muted']};
        font-family: "Consolas", monospace;
        font-size: 12px;
    }}
    """
