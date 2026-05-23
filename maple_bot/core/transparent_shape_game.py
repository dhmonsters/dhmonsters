# 투명 도형 찾기 미니게임 자동 추적 솔버 (3단 폴백 감지 + EMA + 폐루프 마우스 제어)
from __future__ import annotations

import time
import logging
import threading
from typing import Callable, Optional

import numpy as np
import cv2
import win32api

logger = logging.getLogger(__name__)

# ── 타이틀 템플릿 매칭 ────────────────────────────────────────────────
TITLE_TEMPLATE  = "templates/transparent_shape_title.png"
TITLE_THRESHOLD = 0.65

# ── 루프/추적 파라미터 ────────────────────────────────────────────────
FRAME_INTERVAL          = 0.033   # 30fps
EMA_ALPHA               = 0.35
MAX_SPEED               = 30      # px/frame
SPEED_PROPORTION        = 0.4     # 거리의 40%만큼 매 프레임 이동 (P-only)
LOST_FRAMES_MAX         = 8
GAME_END_CHECK_INTERVAL = 0.5

# ── 흰색 도형 감지 (Stage 1) ──────────────────────────────────────────
WHITE_GRAY_THRESH = 200
WHITE_MIN_AREA    = 800
WHITE_MAX_AREA    = 40000
WHITE_KERNEL      = (7, 7)

# ── 프레임 차분 (Stage 2) ─────────────────────────────────────────────
DIFF_THRESHOLD = 20
DIFF_MIN_AREA  = 400


class TransparentShapeGame:
    """투명 도형 찾기 미니게임 감지 + 폐루프 추적 마우스 제어기."""

    def __init__(self, screen, input_ctrl, config, stop_event: threading.Event):
        self._screen = screen
        self._input = input_ctrl
        self._config = config
        self._stop = stop_event

        # 게임 창 제목 — bot_loop 가 주입
        self.window_title: str = "MapleStory"

        self._ema_x: Optional[float] = None
        self._ema_y: Optional[float] = None
        self._prev_frame: Optional[np.ndarray] = None
        self._lost_count = 0

    # ── 타이틀 감지 ──────────────────────────────────────────────────
    def detect_title(self, screenshot) -> Optional[tuple]:
        return self._screen.find_template(screenshot, TITLE_TEMPLATE, TITLE_THRESHOLD)

    # ── Board ROI: 게임창 client 원점 + 저장된 offset ────────────────
    def get_board_roi(self) -> Optional[tuple]:
        board_cfg = self._config.get("settings1", "transparent_shape", "board_roi")
        if not board_cfg:
            return None
        try:
            cx = int(board_cfg["client_x"])
            cy = int(board_cfg["client_y"])
            w  = int(board_cfg["w"])
            h  = int(board_cfg["h"])
        except (KeyError, TypeError, ValueError):
            return None
        if w <= 0 or h <= 0:
            return None

        origin = self._screen.get_window_client_origin(self.window_title)
        # (0, 0) 는 창 못 찾음 신호 — None과 동일하게 처리
        if not origin or origin == (0, 0):
            # 창을 못 찾으면 client 좌표를 절대좌표로 간주 (fallback)
            ox, oy = 0, 0
        else:
            ox, oy = origin
        return (ox + cx, oy + cy, w, h)

    # ── 감지 파이프라인 ──────────────────────────────────────────────
    def find_shape_in_board(self, board_img: np.ndarray) -> Optional[tuple]:
        # Stage 1: 흰색 도형 직접 감지
        pos = self._find_white_region(board_img)
        # Stage 2: 흰색이 안 잡히면(투명해짐) 프레임 차분으로 이동 추적
        if pos is None:
            pos = self._find_via_frame_diff(board_img)
        self._prev_frame = board_img.copy()
        return pos

    def _find_white_region(self, img: np.ndarray) -> Optional[tuple]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, WHITE_GRAY_THRESH, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, WHITE_KERNEL)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return self._largest_contour_center(mask, WHITE_MIN_AREA, WHITE_MAX_AREA)

    def _find_via_frame_diff(self, img: np.ndarray) -> Optional[tuple]:
        if self._prev_frame is None or self._prev_frame.shape != img.shape:
            return None
        diff = cv2.absdiff(img, self._prev_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_diff, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)
        return self._largest_contour_center(mask, DIFF_MIN_AREA, WHITE_MAX_AREA)

    @staticmethod
    def _largest_contour_center(mask: np.ndarray, min_area: int, max_area: int) -> Optional[tuple]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [c for c in contours if min_area <= cv2.contourArea(c) <= max_area]
        if not valid:
            return None
        c = max(valid, key=cv2.contourArea)
        m = cv2.moments(c)
        if m["m00"] == 0:
            return None
        return (int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"]))

    # ── EMA 추적 ─────────────────────────────────────────────────────
    def _update_ema(self, abs_x: float, abs_y: float) -> tuple:
        if self._ema_x is None or self._ema_y is None:
            self._ema_x, self._ema_y = float(abs_x), float(abs_y)
        else:
            self._ema_x = EMA_ALPHA * abs_x + (1 - EMA_ALPHA) * self._ema_x
            self._ema_y = EMA_ALPHA * abs_y + (1 - EMA_ALPHA) * self._ema_y
        return self._ema_x, self._ema_y

    # ── 마우스 폐루프 (win32api 직접 호출) ────────────────────────────
    def _move_mouse_toward(self, target_x: float, target_y: float) -> None:
        try:
            cur_x, cur_y = win32api.GetCursorPos()
        except Exception:
            return
        dx = target_x - cur_x
        dy = target_y - cur_y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1.0:
            return
        step = min(dist * SPEED_PROPORTION, MAX_SPEED)
        ratio = step / dist
        new_x = int(round(cur_x + dx * ratio))
        new_y = int(round(cur_y + dy * ratio))
        try:
            win32api.SetCursorPos((new_x, new_y))
        except Exception as exc:
            logger.debug("SetCursorPos 실패: %s", exc)

    # ── 디버그 오버레이 ──────────────────────────────────────────────
    def draw_debug_overlay(self, board_img: np.ndarray, rel_target: Optional[tuple],
                           roi: tuple) -> np.ndarray:
        dbg = board_img.copy()
        bx, by, bw, bh = roi

        # 노란 박스 (board ROI 테두리)
        cv2.rectangle(dbg, (0, 0), (bw - 1, bh - 1), (0, 255, 255), 2)

        # 빨간 십자 (감지된 도형 중심)
        if rel_target is not None:
            cv2.drawMarker(dbg, rel_target, (0, 0, 255), cv2.MARKER_CROSS, 24, 2)

        # 파란 원 (마우스 위치 — board 상대좌표로)
        try:
            mx, my = win32api.GetCursorPos()
            mx_rel, my_rel = mx - bx, my - by
            if 0 <= mx_rel < bw and 0 <= my_rel < bh:
                cv2.circle(dbg, (mx_rel, my_rel), 9, (255, 0, 0), 2)
                # 초록 화살표 (마우스 → 타겟)
                if rel_target is not None:
                    cv2.arrowedLine(dbg, (mx_rel, my_rel), rel_target,
                                    (0, 255, 0), 2, tipLength=0.2)
        except Exception:
            pass

        return dbg

    # ── 메인 폐루프 ──────────────────────────────────────────────────
    def run_follow_loop(self, on_status: Callable[[str], None]) -> None:
        import mss as _mss

        roi = self.get_board_roi()
        if roi is None:
            on_status("⚠ 투명 도형 찾기: 게임판 ROI 미설정 — 설정1 탭에서 캡처 필요")
            return

        bx, by, bw, bh = roi

        # 초기 EMA = board 중심 (도형이 가운데서 시작)
        self._ema_x = bx + bw / 2.0
        self._ema_y = by + bh / 2.0
        self._prev_frame = None
        self._lost_count = 0

        debug_on = bool(self._config.get("settings1", "transparent_shape", "debug_overlay"))
        last_end_check = time.time()
        region = {"left": bx, "top": by, "width": bw, "height": bh}

        # ROI 절대 위치를 로그에 표시 (위치 오류 진단용)
        on_status(f"투명 도형 찾기: 추적 시작 (ROI={bw}×{bh}  위치 X={bx} Y={by})")

        # standalone과 동일하게 독립 mss 인스턴스 사용
        # (ScreenReader의 공유 인스턴스는 스레드 간 혼용 시 오작동 가능)
        with _mss.mss() as sct:
            while not self._stop.is_set():
                loop_start = time.time()

                # 0.5초마다 타이틀 사라졌는지 확인 → 게임 종료
                if loop_start - last_end_check >= GAME_END_CHECK_INTERVAL:
                    shot = self._screen.capture()
                    if self.detect_title(shot) is None:
                        on_status("투명 도형 찾기: 게임 종료 감지")
                        break
                    last_end_check = loop_start

                # 게임판 캡처 — standalone과 동일한 직접 grab
                raw = sct.grab(region)
                board_img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                rel = self.find_shape_in_board(board_img)

                if rel is not None:
                    self._lost_count = 0
                    abs_x = bx + rel[0]
                    abs_y = by + rel[1]
                    sx, sy = self._update_ema(abs_x, abs_y)
                    self._move_mouse_toward(sx, sy)
                else:
                    self._lost_count += 1

                # 디버그 오버레이
                if debug_on:
                    try:
                        dbg = self.draw_debug_overlay(board_img, rel, roi)
                        cv2.imshow("transparent_shape_debug", dbg)
                        cv2.waitKey(1)
                    except Exception as exc:
                        logger.debug("디버그 오버레이 실패: %s", exc)

                # 프레임 throttle (stop_event 즉시 응답)
                elapsed = time.time() - loop_start
                remaining = FRAME_INTERVAL - elapsed
                if remaining > 0:
                    if self._stop.wait(remaining):
                        break
