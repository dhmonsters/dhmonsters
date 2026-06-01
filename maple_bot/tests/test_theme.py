# theme — DESIGN.md(Linear) 토큰과 QSS 생성 검증
from core_ui.theme import TOKENS, build_qss


def test_tokens_match_design_md():
    """DESIGN.md 핵심 토큰이 그대로 반영됐는지."""
    assert TOKENS["canvas"] == "#010102"
    assert TOKENS["primary"] == "#5e6ad2"
    assert TOKENS["surface_1"] == "#0f1011"
    assert TOKENS["hairline"] == "#23252a"
    assert TOKENS["ink"] == "#f7f8f8"


def test_build_qss_returns_stylesheet():
    qss = build_qss()
    assert isinstance(qss, str) and len(qss) > 0
    # 캔버스/액센트 색이 QSS에 들어있어야
    assert "#010102" in qss
    assert "#5e6ad2" in qss


def test_qss_has_widget_rules():
    """주요 위젯 룰 포함."""
    qss = build_qss()
    for sel in ("QWidget", "QPushButton"):
        assert sel in qss
