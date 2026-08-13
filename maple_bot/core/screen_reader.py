# 화면 캡처 및 템플릿 매칭을 담당하는 ScreenReader 모듈
from __future__ import annotations

import threading

import numpy as np
import cv2
import mss


class ScreenReader:
    """mss 기반 화면 캡처 + cv2 템플릿 매칭 유틸리티.

    mss는 스레드 안전하지 않다 → 스캐너 스레드마다 별도 mss 인스턴스를 둔다
    (thread-local). 한 인스턴스를 여러 스레드에서 grab하면 캡처가 실패한다."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _sct(self):
        """현재 스레드 전용 mss 인스턴스(없으면 생성)."""
        sct = getattr(self._local, "sct", None)
        if sct is None:
            sct = mss.mss()
            self._local.sct = sct
        return sct

    # ── 화면 캡처 ─────────────────────────────────────────────────────
    def capture(self, region: dict | None = None) -> np.ndarray:
        """지정 영역을 캡처해 BGR numpy 배열로 반환.

        Args:
            region: {"left": x, "top": y, "width": w, "height": h}.
                    None이면 기본 모니터 전체 캡처.

        Returns:
            BGR uint8 numpy 배열.
        """
        sct = self._sct()
        if region is None:
            monitor = sct.monitors[0]   # 0 = 전체 가상 데스크톱 (멀티모니터 포함)
        else:
            monitor = {
                "left":   int(region["left"]),
                "top":    int(region["top"]),
                "width":  int(region["width"]),
                "height": int(region["height"]),
            }
        img = sct.grab(monitor)
        return cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)

    # ── 창 위치 ───────────────────────────────────────────────────────
    def get_window_client_origin(self, window_title: str) -> tuple[int, int]:
        """지정 타이틀 창의 클라이언트 영역 좌상단 절대 좌표를 반환.

        창을 찾지 못하면 (0, 0) 반환.
        """
        try:
            import win32gui
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                return (0, 0)
            pt = win32gui.ClientToScreen(hwnd, (0, 0))
            return pt
        except Exception:
            return (0, 0)

    # ── 템플릿 매칭 ───────────────────────────────────────────────────
    # DPI가 다른 PC 호환을 위해 멀티스케일 매칭을 기본으로 사용.
    # 개발 PC(150% DPI)에서 캡처한 템플릿은 100% DPI PC 대비 1.5× 크므로
    # 0.60~1.05 범위의 스케일을 순회해 최고 점수를 반환한다.
    _MATCH_SCALES = [1.0, 0.75, 0.80, 0.85, 0.90, 0.95, 0.67, 0.70, 1.05]

    def _match_multiscale(
        self,
        screenshot: np.ndarray,
        template: np.ndarray,
    ) -> tuple[float, tuple[int, int]]:
        """여러 스케일로 템플릿 매칭을 시도해 (최고점수, 위치) 반환."""
        best_score = 0.0
        best_loc = (0, 0)
        best_size = (template.shape[1], template.shape[0])
        fh, fw = screenshot.shape[:2]
        for scale in self._MATCH_SCALES:
            if scale == 1.0:
                tpl = template
            else:
                nw = max(1, int(template.shape[1] * scale))
                nh = max(1, int(template.shape[0] * scale))
                tpl = cv2.resize(template, (nw, nh), interpolation=cv2.INTER_AREA)
            th, tw = tpl.shape[:2]
            if fw < tw or fh < th:
                continue
            result = cv2.matchTemplate(screenshot, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_size = (tw, th)
        return best_score, (best_loc[0] + best_size[0] // 2, best_loc[1] + best_size[1] // 2)

    def find_template_score(
        self,
        screenshot: np.ndarray,
        template_path: str,
    ) -> float:
        """screenshot에서 template_path 이미지의 최대 매칭 점수(0.0~1.0)를 반환.

        DPI 차이 보정을 위해 멀티스케일 매칭을 수행한다.
        템플릿 로드 실패 시 0.0 반환.
        """
        template = cv2.imread(template_path)
        if template is None:
            return 0.0
        score, _ = self._match_multiscale(screenshot, template)
        return score

    def find_template_match(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.65,
    ) -> tuple[float, tuple[int, int] | None]:
        """한 번의 멀티스케일 탐색으로 점수와 임계값을 통과한 중심을 반환한다."""
        template = cv2.imread(template_path)
        if template is None:
            return 0.0, None
        score, center = self._match_multiscale(screenshot, template)
        return score, center if score >= threshold else None

    def find_template(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.65,
    ) -> tuple[int, int] | None:
        """screenshot에서 template_path 이미지의 중심 좌표를 반환.

        DPI 차이 보정을 위해 멀티스케일 매칭을 수행한다.
        매칭 점수가 threshold 미만이거나 로드 실패 시 None 반환.
        """
        template = cv2.imread(template_path)
        if template is None:
            return None
        score, center = self._match_multiscale(screenshot, template)
        if score >= threshold:
            return center
        return None
