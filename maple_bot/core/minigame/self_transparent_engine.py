# SelfTransparentEngine — 자체 ncnn 거탐 엔진을 MinigameSolver 계약으로 노출. secure_loader 우회
# 본체는 어느 엔진인지 모른 채 can_handle/solve 호출 (격리). PlanetV2Engine(서버의존) 대체
from __future__ import annotations

import time
from pathlib import Path

from core.minigame.solver import MinigameSolver, SolveResult


class SelfTransparentEngine(MinigameSolver):
    """투명도형 거탐을 자체 ncnn 모델로 푼다.

    handles: "planet", "transparent" (플래닛맵 투명도형 찾기)
    solve(): board_capture_fn 으로 게임판을 캡처 → 모델로 도형 중심 추적 →
             move_cursor_fn(cx, cy) 로 커서 이동(주입식, Humanizer/입력 경유).
             도형이 사라질 때까지(=풀이 완료) 추적 반복.
    """
    HANDLES = ("planet", "transparent")

    def __init__(self, models_dir: str | Path,
                 board_capture_fn, move_cursor_fn,
                 use_gpu: bool = False, score_thr: float = 0.3,
                 max_sec: float = 30.0, frame_interval: float = 0.033):
        self._models_dir = Path(models_dir)
        self._capture = board_capture_fn      # () -> BGR ndarray (게임판 영역)
        self._move = move_cursor_fn           # (cx, cy) -> None  (커서 이동, 입력계층 경유)
        self._use_gpu = use_gpu
        self._score_thr = score_thr
        self._max_sec = max_sec
        self._interval = frame_interval
        self._det = None   # lazy load

    def _ensure_loaded(self):
        if self._det is None:
            from core.minigame.transparent_yolo import load_default
            self._det = load_default(self._models_dir, use_gpu=self._use_gpu)

    def can_handle(self, minigame_type: str) -> bool:
        return minigame_type in self.HANDLES

    def solve(self, screenshot, ctx: dict | None = None) -> SolveResult:
        """게임판에서 도형을 추적해 커서로 따라간다. 도형이 N프레임 연속 미검출 시 완료."""
        try:
            self._ensure_loaded()
        except Exception as e:
            return SolveResult(success=False, note=f"모델 로드 실패: {e}")

        start = time.time()
        lost = 0
        moved = 0
        LOST_DONE = 8   # 연속 미검출 → 도형 사라짐(풀이 완료)
        while time.time() - start < self._max_sec:
            board = self._capture()
            if board is None:
                break
            center = self._det.detect_center(board, score_thr=self._score_thr)
            if center is None:
                lost += 1
                if lost >= LOST_DONE and moved > 0:
                    return SolveResult(success=True, elapsed=time.time() - start,
                                       note=f"도형 사라짐(추적 {moved}회) → 완료")
            else:
                lost = 0
                self._move(center[0], center[1])
                moved += 1
            time.sleep(self._interval)

        return SolveResult(success=(moved > 0), elapsed=time.time() - start,
                           note=f"타임아웃/종료 (추적 {moved}회)")
