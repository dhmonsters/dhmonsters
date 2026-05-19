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

def _scale_slot(img: np.ndarray) -> np.ndarray:
    """슬롯 이미지를 4배 확대한다. easyocr은 원본 컬러 이미지가 가장 잘 동작한다."""
    import cv2
    h, w = img.shape[:2]
    return cv2.resize(img, (w * 4, h * 4), interpolation=cv2.INTER_CUBIC)


def save_debug_images(img: np.ndarray, folder: str = "debug_ocr") -> None:
    """원본과 4배 확대 이미지를 folder에 저장한다 (테스트/디버깅용)."""
    import cv2, os
    os.makedirs(folder, exist_ok=True)
    cv2.imwrite(os.path.join(folder, "00_original.png"), img)
    cv2.imwrite(os.path.join(folder, "01_scaled4x.png"), _scale_slot(img))
    logger.info("디버그 이미지 저장: %s", folder)


# ── 공개 API ─────────────────────────────────────────────────────────────

def _bright_pixel_ratio(img: np.ndarray, threshold: int = 200) -> float:
    """이미지에서 밝은 픽셀(흰색 글자) 비율을 반환한다."""
    import cv2
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(np.count_nonzero(gray >= threshold)) / gray.size


def read_number(scene: np.ndarray, zero_bright_threshold: float = 0.04) -> int | None:
    """퀵슬롯 이미지에서 아이템 수량 숫자를 읽어 정수로 반환한다.

    슬롯 전체 이미지(약 32×32px)를 4배 확대해서 easyocr(영어)로 인식.
    OCR 실패 시: 밝은 픽셀 비율이 zero_bright_threshold 이하면 0 반환
    (슬롯에 '0' 표시 또는 빈 슬롯 → 밝은 픽셀 극히 적음).
    우선순위: easyocr(영어) → RapidOCR → 밝기 기반 0 감지 → None
    """
    import re

    scaled = _scale_slot(scene)

    # 1순위: easyocr 영어 모드 (단일 자리 숫자에 강함)
    reader = _get_easy_en()
    if reader is not None:
        try:
            results = reader.readtext(scaled, detail=0, paragraph=False,
                                       allowlist="0123456789")
            text = "".join(results).strip()
            m = re.search(r"\d+", text)
            if m:
                return int(m.group())
        except Exception as exc:
            logger.warning("easyocr 숫자 읽기 실패: %s", exc)

    # 2순위: RapidOCR (easyocr 없을 때 폴백)
    engine = _get_rapid()
    if engine is not None:
        try:
            result, _ = engine(scaled, use_det=True, use_cls=False, use_rec=True)
            if result:
                text = "".join(r[1] for r in result if r and len(r) > 1)
                m = re.search(r"\d+", text)
                if m:
                    return int(m.group())
            result2, _ = engine(scaled, use_det=False, use_cls=False, use_rec=True)
            if result2:
                text2 = "".join(r[1] for r in result2 if r and len(r) > 1)
                m2 = re.search(r"\d+", text2)
                if m2:
                    return int(m2.group())
        except Exception as exc:
            logger.warning("RapidOCR 숫자 읽기 실패: %s", exc)

    # 3순위: 밝기 기반 0 감지 (OCR이 '0'이나 '1' 같은 단일 자리를 못 읽을 때)
    # 슬롯에 숫자가 없거나 '0' 표시: 흰 픽셀이 극히 적음
    ratio = _bright_pixel_ratio(scaled)
    logger.debug("밝기 비율: %.3f (임계값: %.3f)", ratio, zero_bright_threshold)
    if ratio <= zero_bright_threshold:
        logger.info("밝기 기반 0 감지 (비율=%.3f)", ratio)
        return 0

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
