# Starbucks 디자인 토큰 → PyQt6 QSS 변환. DESIGN.md(starbucks) 를 단일 출처로 한다
from __future__ import annotations

# DESIGN.md(Starbucks) 토큰 — 따뜻한 크림 캔버스 + 4단계 그린
TOKENS = {
    "canvas":        "#f2f0eb",   # 따뜻한 크림 (café 종이/벽 질감)
    "surface_1":     "#ffffff",   # 카드/모달 흰 표면
    "surface_2":     "#edebe9",   # 세라믹 오프화이트 (존 구분)
    "surface_3":     "#f9f9f9",   # 쿨그레이 유틸리티
    "hairline":      "#e0ddd6",   # 크림톤 경계선
    "hairline_strong": "#cba258", # 골드 (Rewards 강조)
    "ink":           "#1e3932",   # House Green = 딥 텍스트
    "ink_muted":     "#33433d",   # Rewards 슬레이트 그린
    "ink_subtle":    "rgba(0,0,0,0.58)",  # 메타 텍스트
    "primary":       "#00754a",   # Green Accent = 주 CTA
    "primary_hover": "#006241",   # Starbucks Green
    "on_primary":    "#ffffff",
    "house_green":   "#1e3932",   # 사이드바/피처밴드 딥그린
    "success":       "#006241",
}

# 간격/반경 — Starbucks: 카드 12px 라운드, 버튼은 풀-pill(50px)
RADIUS = 12
PILL = 22
PAD = 10


def build_qss() -> str:
    """현재 토큰으로 전역 QSS 문자열 생성 (Starbucks 톤)."""
    t = TOKENS
    return f"""
    QWidget {{
        background-color: {t['canvas']};
        color: {t['ink']};
        font-family: "Segoe UI", "SoDoSans", sans-serif;
        font-size: 13px;
    }}
    QFrame#card, QWidget#card {{
        background-color: {t['surface_1']};
        border: 1px solid {t['hairline']};
        border-radius: {RADIUS}px;
    }}
    QLabel#h1 {{ font-size: 20px; font-weight: 700; color: {t['primary_hover']}; }}
    QLabel#subtle {{ color: {t['ink_subtle']}; }}
    QPushButton {{
        background-color: {t['surface_1']};
        color: {t['ink']};
        border: 1px solid {t['hairline']};
        border-radius: {PILL}px;
        padding: {PAD}px 18px;
    }}
    QPushButton:hover {{ border-color: {t['primary']}; }}
    QPushButton#primary {{
        background-color: {t['primary']};
        color: {t['on_primary']};
        border: none;
        border-radius: {PILL}px;
        font-weight: 700;
    }}
    QPushButton#primary:hover {{ background-color: {t['primary_hover']}; }}
    QPushButton#nav {{
        background-color: transparent;
        border: none;
        text-align: left;
        padding: {PAD}px 12px;
        color: rgba(255,255,255,0.70);
        border-radius: 0px;
    }}
    QPushButton#nav:checked {{
        background-color: {t['primary']};
        color: {t['on_primary']};
        border-left: 3px solid {t['hairline_strong']};
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
