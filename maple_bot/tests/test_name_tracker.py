# 닉네임 템플릿 추적기 — 사냥영역에서 닉네임 위치(중심) 매칭 검증
import numpy as np

from core.sensing.name_tracker import NameTracker


def _scene_with_template():
    # 좌반 흰/우반 검정 패턴(변별력 있는) 템플릿을 (60,40) 위치에 심음
    tpl = np.zeros((10, 20, 3), np.uint8)
    tpl[:, :10] = 255
    scene = np.zeros((100, 120, 3), np.uint8)
    scene[40:50, 60:80] = tpl
    return scene, tpl


def test_finds_nickname_center():
    scene, tpl = _scene_with_template()
    nt = NameTracker(tpl, threshold=0.7)
    pos = nt.find(scene)
    assert pos is not None
    assert abs(pos[0] - 70) <= 2 and abs(pos[1] - 45) <= 2   # 중심(70,45) 근처
    assert nt.last == pos                                   # 마지막 위치 저장


def test_none_when_no_template_or_scene():
    assert NameTracker(None).find(np.zeros((10, 10, 3), np.uint8)) is None
    scene, tpl = _scene_with_template()
    assert NameTracker(tpl).find(None) is None


def test_last_kept_when_not_found():
    scene, tpl = _scene_with_template()
    nt = NameTracker(tpl, threshold=0.7)
    nt.find(scene)                       # 한 번 찾음
    blank = np.zeros((100, 120, 3), np.uint8)
    nt.find(blank)                       # 빈 화면 → 못 찾음
    assert nt.last is not None           # 마지막 위치는 유지
