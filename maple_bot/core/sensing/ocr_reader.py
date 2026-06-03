# 고정 위치(ROI) 한국어 텍스트를 det 없이 rec-only(RapidOCR + 커스텀 rec.onnx)로 읽는 OCR 리더 — 기타창/확인창 등 위치가 정해진 글자 인식용
from __future__ import annotations

import os
import sys
import threading

import numpy as np

# 박스 위치 탐색(det)은 우리 기존 파이프라인이 담당하고, 여기선 좌표가 정해진 ROI를
# 잘라 글자만 읽는다(rec-only). 사전은 rec.onnx에 'character' 메타로 임베딩돼 있음
# (tools/embed_ocr_dict.py 참고) — 별도 keys 파일 지정이 필요 없다.

_engine = None
_lock = threading.Lock()


def _project_root() -> str:
    """프로젝트 루트(설치 시 exe 폴더, 개발 시 maple_bot 폴더)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _rec_model_path() -> str:
    return os.path.join(_project_root(), "assets", "ocr", "rec.onnx")


def _get_engine():
    """rec-only RapidOCR 엔진(지연 로딩 싱글톤). det/cls는 끈다."""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from rapidocr_onnxruntime import RapidOCR
                _engine = RapidOCR(
                    rec_model_path=_rec_model_path(),
                    use_text_det=False,
                    use_angle_cls=False,
                )
    return _engine


def _crop(scene: np.ndarray, roi: tuple[int, int, int, int] | None) -> np.ndarray | None:
    """roi=(left, top, width, height)로 자른다. roi 없으면 전체."""
    if roi is None:
        return scene
    left, top, width, height = roi
    return scene[top:top + height, left:left + width]


def read_lines(scene: np.ndarray | None,
               roi: tuple[int, int, int, int] | None = None,
               min_score: float = 0.0) -> list[tuple[str, float]]:
    """ROI(없으면 전체)에서 (텍스트, 신뢰도) 목록. det를 끈 rec-only라 보통 한 줄을 통째로 읽는다."""
    if scene is None:
        return []
    img = _crop(scene, roi)
    if img is None or img.size == 0:
        return []
    out, _elapse = _get_engine()(img)
    result: list[tuple[str, float]] = []
    for item in out or []:           # item = [box, text, score]
        text, score = item[1], float(item[2])
        if score >= min_score:
            result.append((text, score))
    return result


def read_text(scene: np.ndarray | None,
              roi: tuple[int, int, int, int] | None = None,
              min_score: float = 0.0) -> str:
    """ROI 텍스트를 한 문자열로(여러 조각이면 공백으로 이어붙임)."""
    return " ".join(t for t, _ in read_lines(scene, roi, min_score)).strip()
