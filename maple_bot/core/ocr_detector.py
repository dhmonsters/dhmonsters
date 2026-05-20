# OCR 기반 화면 텍스트/숫자 감지 — easyocr(영어) 우선, rapidocr 폴백
from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── easyocr 엔진 (숫자 + 영어, 단일 자리 인식에 강함) ───────────────────
_easy_en_reader = None
_easy_en_error = False


def _get_easy_en():
    """easyocr 영어 모드 Reader를 최초 1회 초기화해서 반환한다."""
    global _easy_en_reader, _easy_en_error
    if _easy_en_reader is not None:
        return _easy_en_reader
    if _easy_en_error:
        return None
    try:
        import easyocr
        logger.info("easyocr 영어 모델 로드 중...")
        _easy_en_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        logger.info("easyocr 로드 완료")
        return _easy_en_reader
    except Exception as exc:
        logger.warning("easyocr 초기화 실패: %s", exc)
        _easy_en_error = True
        return None


# ── easyocr 한국어 엔진 (텍스트 감지용) ─────────────────────────────────
_easy_ko_reader = None
_easy_ko_error = False


def _get_easy_ko():
    """easyocr 한국어 Reader를 최초 1회 초기화해서 반환한다."""
    global _easy_ko_reader, _easy_ko_error
    if _easy_ko_reader is not None:
        return _easy_ko_reader
    if _easy_ko_error:
        return None
    try:
        import easyocr
        logger.info("easyocr 한국어 모델 로드 중...")
        _easy_ko_reader = easyocr.Reader(["ko"], gpu=False, verbose=False)
        logger.info("easyocr 한국어 로드 완료")
        return _easy_ko_reader
    except Exception as exc:
        logger.warning("easyocr 한국어 초기화 실패: %s", exc)
        _easy_ko_error = True
        return None


# ── rapidocr 엔진 (폴백용) ───────────────────────────────────────────────
_rapid_engine = None
_rapid_error = False


def _get_rapid():
    """RapidOCR 엔진을 최초 1회 초기화해서 반환한다."""
    global _rapid_engine, _rapid_error
    if _rapid_engine is not None:
        return _rapid_engine
    if _rapid_error:
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_engine = RapidOCR()
        logger.info("RapidOCR 초기화 완료")
        return _rapid_engine
    except Exception as exc:
        logger.warning("RapidOCR 초기화 실패: %s", exc)
        _rapid_error = True
        return None


# ── 전처리 ───────────────────────────────────────────────────────────────

def _prepare_slot(img: np.ndarray) -> np.ndarray:
    """마플스토리 퀵슬롯 이미지에서 숫자 영역만 추출해 OCR용으로 전처리한다.

    체커보드(반투명) 배경 + 흰색 픽셀 폰트를 다음 순서로 처리.
    1. 하단 35% 크롭 — 수량 숫자는 항상 슬롯 하단에 위치
    2. 6배 확대
    3. threshold=200 이진화 + 반전 — 흰 글자 → 검은 글자 (OCR 표준)
    4. 형태학적 Closing — 자릿수 내부 구멍 메우기
    5. 팽창(Dilate) — 획 두껍게
    6. 흰색 패딩 추가
    """
    import cv2
    h, w = img.shape[:2]
    bottom = img[int(h * 0.65):, :]
    big = cv2.resize(bottom, (bottom.shape[1] * 6, bottom.shape[0] * 6),
                     interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    closed = cv2.morphologyEx(t, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    dilated = cv2.dilate(closed, np.ones((3, 3), np.uint8), iterations=1)
    padded = cv2.copyMakeBorder(dilated, 15, 15, 30, 30,
                                 cv2.BORDER_CONSTANT, value=255)
    return cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)


def save_debug_images(img: np.ndarray, folder: str = "debug_ocr") -> None:
    """원본과 전처리 이미지를 folder에 저장한다 (테스트/디버깅용)."""
    import cv2, os
    os.makedirs(folder, exist_ok=True)
    cv2.imwrite(os.path.join(folder, "00_original.png"), img)
    cv2.imwrite(os.path.join(folder, "01_prepared.png"), _prepare_slot(img))
    logger.info("디버그 이미지 저장: %s", folder)


# ── 공개 API ─────────────────────────────────────────────────────────────

def _bright_pixel_ratio(img: np.ndarray, threshold: int = 200) -> float:
    """이미지에서 밝은 픽셀(흰색 글자) 비율을 반환한다."""
    import cv2
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(np.count_nonzero(gray >= threshold)) / gray.size


def read_number(scene: np.ndarray) -> int | None:
    """퀵슬롯 이미지에서 아이템 수량 숫자를 읽어 정수로 반환한다.

    슬롯 전체 이미지(약 70×70px)를 받아:
    1. 하단 35% 크롭 → 6배 확대 → threshold/morphological 전처리
    2. easyocr 영어 모드로 숫자 인식
    3. RapidOCR 폴백
    """
    import re

    prepared = _prepare_slot(scene)

    # 1순위: easyocr 영어 모드
    reader = _get_easy_en()
    if reader is not None:
        try:
            results = reader.readtext(prepared, detail=0, paragraph=False,
                                       allowlist="0123456789")
            text = "".join(results).strip()
            m = re.search(r"\d+", text)
            if m:
                return int(m.group())
        except Exception as exc:
            logger.warning("easyocr 숫자 읽기 실패: %s", exc)

    # 2순위: RapidOCR 폴백
    engine = _get_rapid()
    if engine is not None:
        try:
            result, _ = engine(prepared, use_det=True, use_cls=False, use_rec=True)
            if result:
                text = "".join(r[1] for r in result if r and len(r) > 1)
                m = re.search(r"\d+", text)
                if m:
                    return int(m.group())
            result2, _ = engine(prepared, use_det=False, use_cls=False, use_rec=True)
            if result2:
                text2 = "".join(r[1] for r in result2 if r and len(r) > 1)
                m2 = re.search(r"\d+", text2)
                if m2:
                    return int(m2.group())
        except Exception as exc:
            logger.warning("RapidOCR 숫자 읽기 실패: %s", exc)

    return None


def find_text(scene: np.ndarray, keywords: list[str]) -> bool:
    """이미지에서 키워드 중 하나라도 발견되면 True를 반환한다 (easyocr 한국어 사용).

    scene: BGR numpy 배열 (ScreenReader.capture() 결과)
    keywords: 찾을 문자열 목록
    """
    reader = _get_easy_ko()
    if reader is None:
        return False
    try:
        results = reader.readtext(scene, detail=0, paragraph=False)
        found_text = " ".join(results)
        logger.debug("OCR 결과: %s", found_text)
        return any(kw in found_text for kw in keywords)
    except Exception as exc:
        logger.warning("OCR 텍스트 감지 실패: %s", exc)
        return False


def is_available() -> bool:
    """OCR 사용 가능 여부 (easyocr 또는 rapidocr 중 하나라도 있으면 True)."""
    return _get_easy_en() is not None or _get_rapid() is not None
