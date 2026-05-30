# 투명 도형 추적기 순수 함수 단위 테스트 (pytest 불필요, 직접 실행)
import numpy as np
import cv2
import importlib.util, os

spec = importlib.util.spec_from_file_location(
    "tst", os.path.join(os.path.dirname(__file__), "transparent_shape_standalone.py"))
tst = importlib.util.module_from_spec(spec)
# PyQt6 import 부작용 없이 함수만 쓰기 위해 모듈 로드
spec.loader.exec_module(tst)


def test_mask_cursor_removes_pink():
    # 회색 배경에 분홍 커서 블록을 그림
    img = np.full((100, 100, 3), 120, np.uint8)            # BGR 회색
    cv2.circle(img, (50, 50), 12, (200, 0, 200), -1)        # 분홍(자홍) 원
    out = tst.mask_cursor(img)
    # 커서 중심부가 더 이상 고채도 분홍이 아니어야 함
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[50, 50]
    assert s < tst.CURSOR_SAT_MIN, f"분홍 채도 남음 s={s}"
    print("test_mask_cursor_removes_pink: PASS")


def _make_structured_patch():
    # 어두운 베이스에 밝은 사각형(도형 테두리 구조 모사) — NCC가 의미를 갖도록
    patch = np.full((64, 64, 3), 90, np.uint8)
    cv2.rectangle(patch, (16, 16), (48, 48), (230, 230, 230), -1)
    return patch


def test_match_template_local_finds_patch():
    # 200x200 배경(90)에 구조화 패치를 (120,80) 중심에 끼워넣음
    img = np.full((200, 200, 3), 90, np.uint8)
    patch = _make_structured_patch()
    cx, cy = 120, 80
    img[cy-32:cy+32, cx-32:cx+32] = patch
    # 예측 위치를 약간 어긋나게 줘도 윈도우 안에서 찾아야 함
    res = tst.match_template_local(img, patch, (110, 70), tst.SEARCH_MARGIN)
    assert res is not None, "매칭 실패"
    fx, fy, score = res
    assert abs(fx - cx) <= 3 and abs(fy - cy) <= 3, f"위치 오차 ({fx},{fy})"
    assert score >= tst.MATCH_THRESH, f"점수 낮음 {score}"
    print("test_match_template_local_finds_patch: PASS")


def test_match_template_local_rejects_noise():
    img = np.random.randint(0, 60, (200, 200, 3), np.uint8)  # 어두운 노이즈(패치 부재)
    patch = _make_structured_patch()                         # 구조화 패치
    res = tst.match_template_local(img, patch, (100, 100), tst.SEARCH_MARGIN)
    assert res is None or res[2] < tst.MATCH_THRESH, "노이즈 오검출"
    print("test_match_template_local_rejects_noise: PASS")


if __name__ == "__main__":
    test_mask_cursor_removes_pink()
    test_match_template_local_finds_patch()
    test_match_template_local_rejects_noise()
    print("ALL PASS")
