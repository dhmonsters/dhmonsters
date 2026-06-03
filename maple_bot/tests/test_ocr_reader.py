# OCR 리더 — ROI 크롭/결과 파싱(가짜 엔진) + 실제 한글 rec 인식(통합) 검증
import numpy as np
import pytest

from core.sensing import ocr_reader


class _FakeEngine:
    """RapidOCR 호출 형식을 흉내: (results, elapse) 반환. results = [[box, text, score], ...]"""
    def __init__(self, results):
        self._results = results
        self.last_img = None

    def __call__(self, img):
        self.last_img = img
        return self._results, 0.0


def test_read_lines_parses_text_and_score(monkeypatch):
    fake = _FakeEngine([[[[0, 0]], "확인", "0.91"], [[[0, 0]], "취소", "0.40"]])
    monkeypatch.setattr(ocr_reader, "_get_engine", lambda: fake)
    scene = np.zeros((20, 60, 3), np.uint8)
    assert ocr_reader.read_lines(scene) == [("확인", 0.91), ("취소", 0.40)]


def test_min_score_filters(monkeypatch):
    fake = _FakeEngine([[[[0, 0]], "확인", "0.91"], [[[0, 0]], "취소", "0.40"]])
    monkeypatch.setattr(ocr_reader, "_get_engine", lambda: fake)
    scene = np.zeros((20, 60, 3), np.uint8)
    assert ocr_reader.read_text(scene, min_score=0.5) == "확인"


def test_roi_crops_before_ocr(monkeypatch):
    fake = _FakeEngine([])
    monkeypatch.setattr(ocr_reader, "_get_engine", lambda: fake)
    scene = np.zeros((100, 100, 3), np.uint8)
    ocr_reader.read_lines(scene, roi=(10, 20, 30, 40))   # left,top,w,h
    assert fake.last_img.shape[:2] == (40, 30)           # height, width


def test_none_and_empty_are_safe(monkeypatch):
    fake = _FakeEngine([])
    monkeypatch.setattr(ocr_reader, "_get_engine", lambda: fake)
    assert ocr_reader.read_text(None) == ""
    assert ocr_reader.read_lines(np.zeros((0, 0, 3), np.uint8)) == []


# ── 실제 엔진 통합: 렌더한 한글을 우리 rec.onnx로 읽어낸다 ──────────────
def _render(text):
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont
    import os
    font_path = "C:/Windows/Fonts/malgun.ttf"
    if not os.path.exists(font_path):
        pytest.skip("malgun.ttf 없음")
    img = Image.new("RGB", (18 * len(text) + 40, 48), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((6, 6), text, font=ImageFont.truetype(font_path, 30), fill=(0, 0, 0))
    return np.array(img)[:, :, ::-1].copy()   # RGB→BGR


def test_real_recognizes_korean():
    pytest.importorskip("rapidocr_onnxruntime")
    for word in ["확인", "취소", "기타"]:
        assert ocr_reader.read_text(_render(word)) == word
