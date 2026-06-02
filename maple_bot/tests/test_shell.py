# MainShell — 6카테고리 셸 구조 검증 (offscreen). 도면 4단계 골조
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.shell import MainShell, CATEGORIES


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_six_categories(app):
    shell = MainShell()
    assert len(CATEGORIES) == 6
    # 6개 내비 버튼
    assert len(shell.nav_buttons) == 6
    names = [b.text() for b in shell.nav_buttons]
    assert any("연결" in n for n in names)
    assert any("동선" in n for n in names)
    assert any("안전" in n for n in names)


def test_start_stop_buttons_exist(app):
    shell = MainShell()
    assert shell.btn_start is not None
    assert shell.btn_stop is not None


def test_category_switch_changes_page(app):
    shell = MainShell()
    # 초기 페이지 인덱스 0
    assert shell.stack.currentIndex() == 0
    # 3번째 카테고리 클릭 → 스택 전환
    shell.nav_buttons[2].click()
    assert shell.stack.currentIndex() == 2


def test_log_dock_exists(app):
    shell = MainShell()
    assert shell.log_view is not None
    # 로그 추가 동작
    shell.append_log("테스트 메시지")
    assert "테스트 메시지" in shell.log_view.toPlainText()


def test_qss_applied(app):
    shell = MainShell()
    # 스타일시트가 셸에 적용됐는지 (Discord Night 배경색 포함)
    assert "#1a1b1e" in shell.styleSheet()
