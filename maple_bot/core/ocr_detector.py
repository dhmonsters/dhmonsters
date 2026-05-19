# OCR 기반 화면 텍스트 감지 — easyocr 사용 (한국어 지원)
from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)

# easyocr Reader는 생성 비용이 크므로 한 번만 만들어서 재사용
_reader = None
_reader_error = False   # 초기화 실패했으면 다시 시도하지 않음


def _get_reader():
    """easyocr Reader를 최초 1회 초기화해서 반환한다."""
    global _reader, _reader_error
    if _reader is not None:
        return _reader
    if _reader_error:
        return None
    try:
        import easyocr
        logger.info("easyocr 한국어 모델 로드 중... (첫 실행 시 다운로드 발생)")
        _reader = easyocr.Reader(["ko"], gpu=False, verbose=False)
        logger.info("easyocr 로드 완료")
        return _reader
    except Exception as exc:
        logger.warning("easyocr 초기화 실패: %s", exc)
        _reader_error = True
        return None


def find_text(scene: np.ndarray, keywords: list[str]) -> bool:
    """이미지에서 키워드 중 하나라도 발견되면 True를 반환한다.

    scene: BGR numpy 배열 (ScreenReader.capture() 결과)
    keywords: 찾을 한국어 문자열 목록
    """
    reader = _get_reader()
    if reader is None:
        return False

    try:
        results = reader.readtext(scene, detail=0, paragraph=False)
        found_text = " ".join(results)
        logger.debug("OCR 결과: %s", found_text)
        return any(kw in found_text for kw in keywords)
    except Exception as exc:
        logger.warning("OCR 실패: %s", exc)
        return False


def _preprocess_slot(img: np.ndarray) -> list:
    """퀵슬롯 이미지를 OCR에 적합한 여러 버전으로 전처리해 반환한다.

    마플스토리 퀵슬롯의 아이템 수량은 우하단 모서리에 흰색 소형 폰트로 표시되므로
    ① 우하단 1/2 영역 크롭 + 4배 확대 + 이진화
    ② 전체 이미지 4배 확대 + 이진화
    ③ 원본 이미지
    세 가지를 순서대로 시도한다.
    """
    import cv2
    h, w = img.shape[:2]

    def _to_thresh(src):
        big = cv2.resize(src, (src.shape[1] * 4, src.shape[0] * 4),
                         interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    # 우하단 절반 크롭 (수량 숫자가 있는 위치)
    crop = img[h // 2:, w // 2:]
    return [_to_thresh(crop), _to_thresh(img), img]


def read_number(scene: np.ndarray) -> int | None:
    """이미지에서 숫자를 읽어 정수로 반환한다. 인식 실패 시 None 반환.

    MapleStory 퀵슬롯 아이템 수량 판독에 사용.
    우하단 크롭 → 전체 이진화 → 원본 순으로 시도한다.
    """
    reader = _get_reader()
    if reader is None:
        return None
    try:
        import re
        for img in _preprocess_slot(scene):
            results = reader.readtext(img, detail=0, paragraph=False,
                                      allowlist="0123456789")
            text = "".join(results).strip()
            m = re.search(r"\d+", text)
            if m:
                return int(m.group())
        return None
    except Exception as exc:
        logger.warning("OCR(숫자) 실패: %s", exc)
        return None


def is_available() -> bool:
    """easyocr 사용 가능 여부 확인."""
    return _get_reader() is not None
