# theme — DESIGN.md(Linear) 토큰과 QSS 생성 검증
from core_ui.theme import TOKENS, build_qss


def test_tokens_match_design_md():
    """DESIGN.md(Starbucks) 핵심 토큰이 그대로 반영됐는지."""
    assert TOKENS["canvas"] == "#f2f0eb"     # 크림 캔버스
    assert TOKENS["primary"] == "#00754a"    # Green Accent CTA
    assert TOKENS["surface_1"] == "#ffffff"  # 흰 카드
    assert TOKENS["house_green"] == "#1e3932"  # 딥그린
    assert TOKENS["ink"] == "#1e3932"


def test_build_qss_returns_stylesheet():
    qss = build_qss()
    assert isinstance(qss, str) and len(qss) > 0
    # 캔버스/액센트 색이 QSS에 들어있어야
    assert "#f2f0eb" in qss
    assert "#00754a" in qss


def test_qss_has_widget_rules():
    """주요 위젯 룰 포함."""
    qss = build_qss()
    for sel in ("QWidget", "QPushButton"):
        assert sel in qss


def test_font_stack_has_inter():
    """DESIGN.md 폰트 스택: Inter 우선 + 폴백 체인."""
    from core_ui.theme import FONT_STACK, LETTER_SPACING_PX
    assert "Inter" in FONT_STACK
    assert "Arial" in FONT_STACK          # 최종 폴백
    assert LETTER_SPACING_PX == -0.16     # DESIGN.md 트래킹


def test_apply_font_loads_inter():
    """번들 Inter ttf 런타임 로드 → Inter 패밀리 적용."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from core_ui.theme import apply_font
    app = QApplication.instance() or QApplication([])
    fam = apply_font(app)
    assert fam == "Inter"
    # 자간이 음수(타이트)로 적용됐는지
    assert app.font().letterSpacing() < 0
