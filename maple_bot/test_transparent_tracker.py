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


if __name__ == "__main__":
    test_mask_cursor_removes_pink()
    print("ALL PASS")
