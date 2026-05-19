# OCR 기반 화면 텍스트/숫자 감지 — rapidocr-onnxruntime 우선, easyocr 폴백
from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── rapidocr 엔진 (수량 숫자 읽기용 — onnxruntime 기반, 경량) ───────────
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


# ── easyocr 엔진 (한국어 텍스트 감지용) ─────────────────────────────────
_easy_reader = None
_easy_error = False


def _get_easy():
    """easyocr Reader를 최초 1회 초기화해서 반환한다."""
    global _easy_reader, _easy_error
    if _easy_reader is not None:
        return _easy_reader
    if _easy_error:
        return None
    try:
        import easyocr
        logger.info("easyocr 한국어 모델 로드 중...")
        _easy_reader = easyocr.Reader(["ko"], gpu=False, verbose=False)
        logger.info("easyocr 로드 완료")
        return _easy_reader
    except Exception as exc:
        logger.warning("easyocr 초기화 실패: %s", exc)
        _easy_error = True
        return None


# ── 공용 전처리 ──────────────────────────────────────────────────────────

def _preprocess_slot(img: np.ndarray) -> list:
    """퀵슬롯 이미지를 OCR용으로 전처리한 버전 목록을 반환한다.

    마플스토리 퀵슬롯 아이템 수량은 우하단에 흰색 소형 폰트로 표시된다.
    시도 순서:
    ① 전체 이미지 4배 확대 + 이진화 (threshold 140)
    ② 우하단 절반 크롭 + 4배 확대 + 이진화
    ③ 전체 이미지 4배 확대 + 이진화 (threshold 200, 더 엄격)
    ④ 원본
    """
    import cv2
    h, w = img.shape[:2]

    def _to_thresh(src: np.ndarray, thr: int = 140) -> np.ndarray:
        big = cv2.resize(src, (src.shape[1] * 4, src.shape[0] * 4),
                         interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    crop = img[h // 2:, w // 2:]   # 우하단 절반 (숫자 위치)
    return [
        _to_thresh(img, 140),
        _to_thresh(crop, 140),
        _to_thresh(img, 200),
        img,
    ]


# ── 공개 API ─────────────────────────────────────────────────────────────

def read_number(scene: np.ndarray) -> int | None:
    """퀵슬롯 이미지에서 아이템 수량 숫자를 읽어 정수로 반환한다.

    우선순위: RapidOCR → easyocr → None(실패)
    전처리(우하단 크롭 → 전체 확대 → 원본) 순으로 시도한다.
    """
    import re

    # 1순위: RapidOCR (경량, exe 포함 가능)
    # detection ON → 작은 숫자 박스 찾기 실패 시 detection OFF로 재시도
    engine = _get_rapid()
    if engine is not None:
        try:
            for img in _preprocess_slot(scene):
                # detection + recognition
                result, _ = engine(img, use_det=True, use_cls=False, use_rec=True)
                if result:
                    text = "".join(r[1] for r in result if r and len(r) > 1)
                    m = re.search(r"\d+", text)
                    if m:
                        return int(m.group())
                # detection 없이 recognition만 (단독 소형 숫자 처리)
                result2, _ = engine(img, use_det=False, use_cls=False, use_rec=True)
                if result2:
                    text2 = "".join(r[1] for r in result2 if r and len(r) > 1)
                    m2 = re.search(r"\d+", text2)
                    if m2:
                        return int(m2.group())
        except Exception as exc:
            logger.warning("RapidOCR 숫자 읽기 실패: %s", exc)

    # 2순위: easyocr (한국어 지원, torch 의존 — exe에서는 미포함)
    reader = _get_easy()
    if reader is not None:
        try:
            for img in _preprocess_slot(scene):
                results = reader.readtext(img, detail=0, paragraph=False,
                                          allowlist="0123456789")
                text = "".join(results).strip()
                m = re.search(r"\d+", text)
                if m:
                    return int(m.group())
        except Exception as exc:
            logger.warning("easyocr 숫자 읽기 실패: %s", exc)

    return None


def find_text(scene: np.ndarray, keywords: list[str]) -> bool:
    """이미지에서 키워드 중 하나라도 발견되면 True를 반환한다 (easyocr 한국어 사용).

    scene: BGR numpy 배열 (ScreenReader.capture() 결과)
    keywords: 찾을 문자열 목록
    """
    reader = _get_easy()
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
    """OCR 사용 가능 여부 (rapidocr 또는 easyocr 중 하나라도 있으면 True)."""
    return _get_rapid() is not None or _get_easy() is not None
