# 몬스터 위치를 프레임 간 추적해 스킬 이펙트/가림 시에도 박스를 일시 유지한다
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class MonsterTrack:
    """추적 중인 몬스터 하나의 상태."""
    x:      int
    y:      int
    missed: int   = 0    # 연속 미감지 프레임 수
    conf:   float = 1.0  # 신뢰도 (미감지 시 감쇠)


class MonsterTracker:
    """MonsterDetector가 반환하는 (x, y) 목록을 프레임 간 안정적으로 추적한다.

    동작 원리.
        1. 새 감지 결과와 기존 track을 거리 기반으로 매칭한다.
        2. 매칭된 track은 좌표를 갱신하고 missed=0 으로 초기화한다.
        3. 매칭 실패 track은 missed를 증가시키고, MAX_MISSED 초과 시 삭제한다.
        4. 매칭 실패 감지는 신규 track으로 추가한다.

    이를 통해 순간적인 이펙트/가림이 있어도 박스가 바로 사라지지 않는다.
    """

    MAX_MISSED: int   = 8    # 이 이상 연속 미감지 시 track 삭제
    MATCH_DIST: int   = 40   # 매칭 거리 임계값 (픽셀)
    CONF_DECAY: float = 0.85 # 미감지 시 신뢰도 감쇠 비율

    def __init__(self) -> None:
        self._tracks: list[MonsterTrack] = []

    # ── 공개 API ──────────────────────────────────────────────────────────

    def update(self, detections: list[tuple[int, int]]) -> list[dict]:
        """감지 결과를 반영해 추적 목록을 갱신하고 현재 track 목록을 반환한다.

        Args:
            detections: game_screen 기준 (x, y) 좌표 목록.

        Returns:
            [{"x": …, "y": …, "conf": …}, …] — 현재 유효한 track 목록.
        """
        matched_track_idxs:     set[int] = set()
        matched_detection_idxs: set[int] = set()

        # ── 기존 track ↔ detection 거리 매칭 ──────────────────────────
        for ti, track in enumerate(self._tracks):
            best_dist = self.MATCH_DIST + 1
            best_di   = -1
            for di, (dx, dy) in enumerate(detections):
                if di in matched_detection_idxs:
                    continue
                dist = math.hypot(track.x - dx, track.y - dy)
                if dist < best_dist:
                    best_dist = dist
                    best_di   = di

            if best_di >= 0:
                # 매칭 성공 — 위치 갱신
                dx, dy = detections[best_di]
                track.x      = dx
                track.y      = dy
                track.missed = 0
                track.conf   = 1.0
                matched_track_idxs.add(ti)
                matched_detection_idxs.add(best_di)

        # ── 미매칭 track 처리 (missed 증가 / 삭제) ────────────────────
        alive: list[MonsterTrack] = []
        for ti, track in enumerate(self._tracks):
            if ti not in matched_track_idxs:
                track.missed += 1
                track.conf   *= self.CONF_DECAY
                if track.missed <= self.MAX_MISSED:
                    alive.append(track)
            else:
                alive.append(track)
        self._tracks = alive

        # ── 미매칭 detection → 신규 track ────────────────────────────
        for di, (dx, dy) in enumerate(detections):
            if di not in matched_detection_idxs:
                self._tracks.append(MonsterTrack(x=dx, y=dy))

        return [{"x": t.x, "y": t.y, "conf": t.conf} for t in self._tracks]

    def clear(self) -> None:
        """모든 track을 초기화한다."""
        self._tracks.clear()

    @property
    def track_count(self) -> int:
        return len(self._tracks)


