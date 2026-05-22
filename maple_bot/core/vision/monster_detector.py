# 게임 화면에서 몬스터 이름표 템플릿 매칭으로 위치를 감지하는 모듈
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# NMS 중복 제거 거리 임계값 (픽셀)
_NMS_DIST = 30

# 기본 템플릿 매칭 임계값
_DEFAULT_THRESHOLD = 0.75


class MonsterDetector:
    """FrameBuffer의 game_screen ROI에서 monsters/ 폴더 템플릿을 순회하며 위치를 감지.

    기존 Detector.find_monsters()를 재사용하므로 중복 구현 없음.
    감지 결과는 game_screen 기준 픽셀 좌표 목록으로 반환한다.

    Args:
        config:       ConfigManager 인스턴스 (threshold 설정 참조).
        frame_buffer: FrameBuffer 인스턴스 (game_screen ROI 소스).
        detector:     기존 Detector 인스턴스 (find_monsters() 재사용).
    """

    def __init__(self, config, frame_buffer=None, detector=None) -> None:
        self._config = config
        self._frame_buffer = frame_buffer
        self._detector = detector

    # ── 공개 API ──────────────────────────────────────────────────────────
    def detect(
        self, game_frame: "np.ndarray | None" = None
    ) -> list[tuple[int, int]]:
        """게임 화면에서 몬스터 위치 목록을 반환한다.

        Args:
            game_frame: BGR 게임 화면 이미지. None이면 frame_buffer에서 읽는다.

        Returns:
            game_screen 기준 (x, y) 픽셀 좌표 목록. 감지 실패 또는 템플릿 없으면 [].
        """
        if self._detector is None:
            return []

        # 프레임 확보 (캐시 우선)
        frame = game_frame
        if frame is None and self._frame_buffer is not None:
            frame = self._frame_buffer.get_roi("game_screen")
        if frame is None:
            return []

        threshold = self._get_threshold()
        templates = []
        try:
            folder = (
                (self._config.get("attack", "monster_folder") or "").strip()
                or "monsters"
            )
            # list_monster_templates는 static 메서드 — 인스턴스 또는 클래스 경유 모두 동작
            templates = self._detector.list_monster_templates(folder)
        except Exception:
            pass

        if not templates:
            return []

        # 모든 템플릿에서 위치 수집
        raw: list[tuple[int, int]] = []
        for tpl_path in templates:
            try:
                positions = self._detector.find_monsters(frame, tpl_path, threshold)
                raw.extend(positions)
            except Exception:
                pass

        return self._nms(raw)

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────
    def _get_threshold(self) -> float:
        """config에서 monster_threshold를 읽는다. 없으면 기본값 사용."""
        try:
            v = self._config.get("vision", "monster_threshold")
            if v is not None:
                return float(v)
        except Exception:
            pass
        return _DEFAULT_THRESHOLD

    @staticmethod
    def _nms(positions: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """거리 기반 NMS — 서로 _NMS_DIST px 이내인 포인트는 하나만 남긴다."""
        if not positions:
            return []
        kept: list[tuple[int, int]] = []
        for px, py in positions:
            duplicate = False
            for kx, ky in kept:
                if abs(px - kx) < _NMS_DIST and abs(py - ky) < _NMS_DIST:
                    duplicate = True
                    break
            if not duplicate:
                kept.append((px, py))
        return kept
