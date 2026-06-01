# AntiMobScanner — B 방식(유형별 다중 템플릿) 매크로 방지몹 감지 검증
import numpy as np
import pytest
from core.sensing.antimob_scanner import match_any_template, AntiMobScanner

# 실제 몬스터 템플릿처럼 '텍스처(분산)'가 있는 패치를 만든다.
# 균일색 패치는 TM_CCOEFF_NORMED의 정규화 분모가 0이 되어 모든 위치에서 1.0이 나오므로
# (분산 없는 이미지의 상관계수는 정의 불가) 테스트 픽스처로 부적합하다.
_RNG = np.random.default_rng(42)


def _textured_patch(seed: int, size: int = 14) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)


def _scene_with_patch(patch, x=30, y=20, w=200, h=120):
    """배경(랜덤 노이즈) 위에 patch(작은 이미지)를 (x,y)에 박은 BGR 씬."""
    scene = _RNG.integers(0, 60, size=(h, w, 3), dtype=np.uint8)  # 어두운 노이즈 배경
    ph, pw = patch.shape[:2]
    scene[y:y+ph, x:x+pw] = patch
    return scene


def test_match_any_finds_present_template():
    patch = _textured_patch(seed=1)
    scene = _scene_with_patch(patch, x=40, y=30)
    score, name = match_any_template(scene, {"rich1": patch}, threshold=0.9)
    assert name == "rich1"
    assert score >= 0.9


def test_match_any_returns_none_when_absent():
    patch = _textured_patch(seed=1)
    scene = _RNG.integers(0, 60, size=(120, 200, 3), dtype=np.uint8)  # patch 없는 노이즈
    score, name = match_any_template(scene, {"rich1": patch}, threshold=0.9)
    assert name is None


def test_match_any_picks_best_among_multiple():
    """여러 유형 템플릿 중 실제 존재하는 것을 고른다(B 다중템플릿)."""
    rich = _textured_patch(seed=1)
    lulu = _textured_patch(seed=2)
    scene = _scene_with_patch(lulu, x=50, y=40)
    score, name = match_any_template(scene, {"rich1": rich, "lulu1": lulu}, threshold=0.9)
    assert name == "lulu1"


def test_scanner_respects_enabled_types():
    """config에서 비활성화된 유형은 감지 시도 안 함."""
    lulu = _textured_patch(seed=2)
    scene = _scene_with_patch(lulu, x=50, y=40)

    # lulu 비활성 → 감지 안 됨
    s = AntiMobScanner(
        screen_capture=lambda r=None: scene,
        templates={"lulu": {"lulu1": lulu}, "rich": {}},
        enabled_types={"lulu": False, "rich": True},
        threshold=0.9,
    )
    assert s.scan_once() is None

    # lulu 활성 → 감지됨
    s2 = AntiMobScanner(
        screen_capture=lambda r=None: scene,
        templates={"lulu": {"lulu1": lulu}, "rich": {}},
        enabled_types={"lulu": True, "rich": True},
        threshold=0.9,
    )
    ev = s2.scan_once()
    assert ev is not None and ev.type == "anti_mob"
    assert ev.data["mob_type"] == "lulu"
