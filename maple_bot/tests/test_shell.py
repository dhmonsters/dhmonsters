# MainShell — 6카테고리 셸 구조 검증 (offscreen). 도면 4단계 골조
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.shell import MainShell, CATEGORIES
from core_ui.hunt_ground_preset_widget import HuntGroundPresetWidget


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
    assert "#f3f5f2" in shell.styleSheet()


def test_shell_can_shrink_to_compact_width(app):
    shell = MainShell()

    assert shell.minimumWidth() == 760
    assert shell.minimumHeight() == 560


def test_bottom_save_button_is_global_save_and_emits_apply_request(app):
    class Config:
        def __init__(self):
            self.saved = 0

        def save(self):
            self.saved += 1

    config = Config()
    shell = MainShell()
    shell._config = config
    applied = []
    shell.settings_apply_requested.connect(lambda: applied.append(True))

    shell.global_save_button.click()

    assert shell.global_save_button.text() == "전체 설정 저장 및 적용"
    assert config.saved == 1
    assert applied == [True]


def test_hunt_ground_button_is_labeled_as_map_save(app):
    class Config:
        def get(self, *_keys, default=None):
            return default

    widget = HuntGroundPresetWidget(Config())

    assert widget.save_button.text() == "현재 맵 설정 저장"
