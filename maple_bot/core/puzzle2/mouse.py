# Puzzle2 추적 좌표를 Interception 커널 입력과 화면 커서 보정에 연결한다.
from __future__ import annotations

from collections.abc import Callable
from typing import Any


DriverLoader = Callable[[], Any]
CursorObserver = Callable[[], tuple[float, float] | None]


def detect_pink_cursor(frame_bgr: Any) -> tuple[float, float] | None:
    try:
        import cv2
        import numpy as np

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(
            hsv,
            np.array([140, 80, 80]),
            np.array([175, 255, 255]),
        )
        contours, _hierarchy = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 15:
            return None
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return None
        return (
            float(moments["m10"] / moments["m00"]),
            float(moments["m01"] / moments["m00"]),
        )
    except Exception:
        return None


class GameCursorObserver:
    def __init__(self, vendor_backend: Any, quest_roi: tuple[int, int, int, int]) -> None:
        self._backend = vendor_backend
        self._quest_roi = tuple(int(value) for value in quest_roi)
        self._capture: Any = None
        self._hwnd: int | None = None

    def __call__(self) -> tuple[float, float] | None:
        try:
            window = self._backend.find_game_window()
            if window is None:
                return None
            hwnd = int(window.hwnd)
            if self._capture is None or hwnd != self._hwnd:
                self.close()
                self._capture = self._backend.ScreenCapture(hwnd)
                self._hwnd = hwnd
            frame, _rect = self._capture.grab_client()
            client = self._backend.client_rect(hwnd)
            if not client:
                return None
            x, y, width, height = self._quest_roi
            roi = frame[y : y + height, x : x + width]
            if roi.shape[:2] != (height, width):
                return None
            cursor = detect_pink_cursor(roi)
            if cursor is None:
                return None
            return (
                float(client["x"] + x) + cursor[0],
                float(client["y"] + y) + cursor[1],
            )
        except Exception:
            return None

    def close(self) -> None:
        if self._capture is not None:
            try:
                self._capture.close()
            except Exception:
                pass
        self._capture = None
        self._hwnd = None


class InterceptionMouseController:
    def __init__(
        self,
        *,
        driver_loader: DriverLoader | None = None,
        cursor_observer: CursorObserver | None = None,
        offset_alpha: float = 0.5,
        offset_limit: float = 120.0,
    ) -> None:
        self._driver_loader = driver_loader or _load_interception_driver
        self._cursor_observer = cursor_observer or (lambda: None)
        self._driver: Any = None
        self._offset_alpha = float(offset_alpha)
        self._offset_limit = float(offset_limit)
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._last_target: tuple[float, float] | None = None

    @property
    def offset(self) -> tuple[float, float]:
        return self._offset_x, self._offset_y

    def begin_puzzle(self) -> None:
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._last_target = None

    def move(self, target_x: float, target_y: float, *, learn_offset: bool) -> bool:
        driver = self._require_driver()
        target = (float(target_x), float(target_y))
        if learn_offset and self._last_target is not None:
            observed = self._cursor_observer()
            if observed is not None:
                self._offset_x += (
                    self._last_target[0] - float(observed[0])
                ) * self._offset_alpha
                self._offset_y += (
                    self._last_target[1] - float(observed[1])
                ) * self._offset_alpha
                self._offset_x = _clamp(self._offset_x, self._offset_limit)
                self._offset_y = _clamp(self._offset_y, self._offset_limit)
        driver.move_to(
            int(round(target[0] + self._offset_x)),
            int(round(target[1] + self._offset_y)),
        )
        if learn_offset:
            self._last_target = target
        return True

    def click(self, target_x: float, target_y: float) -> bool:
        driver = self._require_driver()
        driver.click(
            int(round(float(target_x) + self._offset_x)),
            int(round(float(target_y) + self._offset_y)),
        )
        return True

    def close(self) -> None:
        close = getattr(self._cursor_observer, "close", None)
        if callable(close):
            close()

    def _require_driver(self) -> Any:
        if self._driver is None:
            driver = self._driver_loader()
            if str(getattr(driver, "name", "")) != "interception":
                raise RuntimeError("Interception 커널 마우스만 사용할 수 있습니다")
            if not callable(getattr(driver, "move_to", None)):
                raise RuntimeError("Interception move_to()를 찾지 못했습니다")
            if not callable(getattr(driver, "click", None)):
                raise RuntimeError("Interception click()을 찾지 못했습니다")
            self._driver = driver
        return self._driver


def _load_interception_driver() -> Any:
    from core.humanize.backend import select_backend

    selected = select_backend()
    kernel = getattr(selected, "_ic", None)
    if kernel is None:
        raise RuntimeError("Interception 커널 모듈을 찾지 못했습니다")
    return _SelectedInterceptionDriver(kernel)


class _SelectedInterceptionDriver:
    name = "interception"

    def __init__(self, kernel: Any) -> None:
        self._kernel = kernel

    def move_to(self, x: int, y: int) -> None:
        self._kernel.move_to(int(x), int(y))

    def click(self, x: int, y: int) -> None:
        self._kernel.click(int(x), int(y))


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))
