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
