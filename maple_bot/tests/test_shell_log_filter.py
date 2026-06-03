# 셸 로그 카테고리 필터 — 켜진 카테고리만 표시, 토글 시 재렌더
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from core_ui.shell import MainShell, LOG_CATEGORIES

_app = QApplication.instance() or QApplication([])


def test_append_and_category_filter():
    s = MainShell()                       # config 없이도 로그 드로어 동작
    s.append_log("때림", "공격")
    s.append_log("버프씀", "버프")
    txt = s.log_view.toPlainText()
    assert "때림" in txt and "버프씀" in txt          # 기본 전부 표시
    # 공격 카테고리 끄기 → 재렌더 시 공격 로그 사라짐
    s._toggle_log_cat("공격")
    txt2 = s.log_view.toPlainText()
    assert "때림" not in txt2 and "버프씀" in txt2
    # 다시 켜기 → 복원
    s._toggle_log_cat("공격")
    assert "때림" in s.log_view.toPlainText()


def test_unknown_category_falls_back_to_system():
    s = MainShell()
    s.append_log("기타", "없는카테고리")
    assert ("시스템", "기타") in s._log_buffer
