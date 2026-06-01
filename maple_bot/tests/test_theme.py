# theme — DESIGN.md(Linear) 토큰과 QSS 생성 검증
from core_ui.theme import TOKENS, build_qss


def test_tokens_match_design_md():
    """DESIGN.md(Linear) 핵심 토큰이 그대로 반영됐는지."""
    assert TOKENS["canvas"] == "#010102"     # near-black 캔버스
    assert TOKENS["primary"] == "#5e6ad2"    # 라벤더 액센트
    assert TOKENS["surface_1"] == "#0f1011"  # 차콜 패널
    assert TOKENS["hairline"] == "#23252a"
    assert TOKENS["ink"] == "#f7f8f8"


def test_build_qss_returns_stylesheet():
    qss = build_qss()
    assert isinstance(qss, str) and len(qss) > 0
    # 캔버스/액센트 색이 QSS에 들어있어야
    assert "#010102" in qss
    assert "#5e6ad2" in qss


def test_design_tokens_present():
    """DESIGN.md spacing/radius/typography 토큰이 정의됐는지."""
    from core_ui.theme import SPACING, RADIUS, TYPOGRAPHY
    assert SPACING["md"] == 16 and SPACING["lg"] == 24   # DESIGN.md spacing
    assert RADIUS["md"] == 8 and RADIUS["xl"] == 16       # DESIGN.md radius
    assert TYPOGRAPHY["h1"]["tracking"] < 0               # 음수 트래킹


def test_qss_has_widget_rules():
    """주요 위젯 룰 포함."""
    qss = build_qss()
    for sel in ("QWidget", "QPushButton"):
        assert sel in qss


def test_font_stack_has_inter():
    """DESIGN.md 폰트 스택: Inter(Linear Display 대체) sans + JetBrains Mono."""
    from core_ui.theme import FONT_SANS, FONT_MONO, LETTER_SPACING_PX
    assert "Inter" in FONT_SANS
    assert "JetBrains Mono" in FONT_MONO   # Linear Mono 대체
    assert LETTER_SPACING_PX < 0           # DESIGN.md 음수 트래킹


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
