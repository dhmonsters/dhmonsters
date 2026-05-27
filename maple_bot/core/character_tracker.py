# YOLO 캐릭터 감지 위치를 EMA로 보정하는 트래커
from __future__ import annotations


class CharacterTracker:
    """
    EMA(지수이동평균) 기반 캐릭터 위치 보정.
    - 감지 성공 시: EMA 갱신 후 보정값 반환
    - 감지 실패 시: 이전 EMA 값 반환
    - 연속 max_miss 프레임 실패 시: 리셋 (중앙값 반환)
    """

    def __init__(
        self,
        alpha: float = 0.4,
        max_miss: int = 10,
        default_center: tuple[int, int] = (960, 540),
    ) -> None:
        self._alpha = alpha          # EMA 가중치 (0~1, 클수록 최신값 반영 강함)
        self._max_miss = max_miss    # 연속 미감지 허용 프레임 수
        self._default = default_center
        self._ema_x: float | None = None
        self._ema_y: float | None = None
        self._miss_count: int = 0

    def update(self, detected_center: tuple[int, int] | None) -> tuple[int, int]:
        """
        detected_center: YOLO가 반환한 (cx, cy) 또는 None
        반환: 보정된 캐릭터 위치 (cx, cy)
        """
        if detected_center is not None:
            cx, cy = detected_center
            self._miss_count = 0
            if self._ema_x is None:
                self._ema_x, self._ema_y = float(cx), float(cy)
            else:
                self._ema_x = self._alpha * cx + (1 - self._alpha) * self._ema_x
                self._ema_y = self._alpha * cy + (1 - self._alpha) * self._ema_y
        else:
            self._miss_count += 1
            if self._miss_count >= self._max_miss:
                self.reset()

        if self._ema_x is None:
            return self._default
        return int(self._ema_x), int(self._ema_y)

    def reset(self) -> None:
        """추적 이력 초기화."""
        self._ema_x = None
        self._ema_y = None
        self._miss_count = 0
