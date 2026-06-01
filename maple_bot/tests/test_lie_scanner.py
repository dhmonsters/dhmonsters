# LieScanner — 거탐(투명도형 타이틀) 출현 감지 → "lie" 이벤트. C MinigameWatcher 방식
import numpy as np
import pytest
from core.sensing.lie_scanner import LieScanner
from core.sensing.event import Event

_RNG = np.random.default_rng(7)


def _textured(seed, size=20):
    return np.random.default_rng(seed).integers(0, 256, (size, size, 3), dtype=np.uint8)


def _scene_with(patch=None, w=300, h=160, x=40, y=20):
    scene = _RNG.integers(0, 60, (h, w, 3), dtype=np.uint8)
    if patch is not None:
        ph, pw = patch.shape[:2]
        scene[y:y+ph, x:x+pw] = patch
    return scene


def test_detects_title_emits_lie_event():
    title = _textured(1)
    scene = _scene_with(title)
    sc = LieScanner(screen_capture=lambda r=None: scene, title_template=title, threshold=0.9)
    ev = sc.scan_once()
    assert ev is not None and ev.type == "lie"


def test_no_title_no_event():
    title = _textured(1)
    scene = _scene_with(None)   # 타이틀 없음
    sc = LieScanner(screen_capture=lambda r=None: scene, title_template=title, threshold=0.9)
    assert sc.scan_once() is None


def test_appear_fires_once_until_disappear():
    """C _on_appear/_on_disappear: 떠있는 동안 이벤트 1회만, 사라졌다 다시 뜨면 또 발행."""
    title = _textured(1)
    present = _scene_with(title)
    absent = _scene_with(None)
    frames = [present, present, present]   # 연속 출현
    i = {"n": 0}
    def cap(r=None):
        f = frames[min(i["n"], len(frames)-1)]; i["n"] += 1; return f
    sc = LieScanner(screen_capture=cap, title_template=title, threshold=0.9)
    e1 = sc.scan_once()   # 첫 출현 → 발행
    e2 = sc.scan_once()   # 계속 떠있음 → 발행 안 함(중복방지)
    assert e1 is not None and e2 is None


def test_redetect_after_gone():
    title = _textured(1)
    present = _scene_with(title); absent = _scene_with(None)
    seq = [present, absent, present]
    i = {"n": 0}
    def cap(r=None):
        f = seq[min(i["n"], len(seq)-1)]; i["n"] += 1; return f
    sc = LieScanner(screen_capture=cap, title_template=title, threshold=0.9)
    e1 = sc.scan_once()   # 출현 → 발행
    e2 = sc.scan_once()   # 사라짐 → None
    e3 = sc.scan_once()   # 재출현 → 다시 발행
    assert e1 is not None and e2 is None and e3 is not None
