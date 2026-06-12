# 배경과 '같이' 움직이는 후보를 걸러내고 혼자 특이하게 움직이는 타겟을 고르는 모션 분별기
"""
전제(실측): 배경 데칼들은 전역 평행이동(phaseCorrelate 일치 0.997)으로 일제히 움직이고,
타겟만 배경 대비 상대속도 median 2.27px/frame로 '혼자 특이하게' 움직인다.

메커니즘 (사용자 4단계 설계):
  1) 매 프레임 phaseCorrelate로 배경 전역 변위 측정
  2) YOLO 후보들을 짧은 트랙으로 연계 (예상 위치 = 직전 위치 + 배경 변위)
  3) 트랙별 특이성 누적: |후보 변위 − 배경 변위| — 데칼은 ≈0, 타겟만 쌓임
  4) 직전 타겟 근처(연속성 게이트) 트랙 중 특이성+YOLO점수 최고를 채택

동조(타겟이 잠깐 배경과 같은 방향)·겹침 순간엔 롤링 누적이 버텨주고,
위치 게이트가 먼 데칼로 갈아타는 것을 막는다.
"""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np

MATCH_R = 25          # 트랙-후보 연계 반경(px) — 배경 보상 후 예상 위치 기준
MATCH_R_GROW = 3.0    # 미매칭 1프레임당 재매칭 반경 확장(px) — 공백 중 타겟 상대이동 보상
TRACK_MISS_MAX = 12   # 이 프레임 수 연속 미매칭 시 트랙 제거 (검출 공백 견디기)
UNIQ_CLIP = 8.0       # 프레임당 특이성 상한(px) — 검출 흔들림 스파이크 억제
UNIQ_WIN = 20         # 특이성 롤링 윈도우(프레임) — 오랜 과거 희석
SCORE_W = 6.0         # 선택 점수에서 YOLO score 가중 (uniq 누적과 단위 맞춤)
UNIQ_MIN = 6.0        # 약한 후보 채택 최소 특이성 — 배경과 같이 움직이는 데칼(≈0) 거부
UNIQ_MIN_OBS = 3      # 특이성 판정 최소 관측 프레임 (신규 트랙 유예)


class _Track:
    __slots__ = ("x", "y", "uniq", "miss", "score", "matched")

    def __init__(self, x, y, score):
        self.x = float(x)
        self.y = float(y)
        self.uniq = deque(maxlen=UNIQ_WIN)   # 프레임별 특이성
        self.miss = 0
        self.score = float(score)            # 최근 YOLO score
        self.matched = True                  # 이번 프레임 실측 매칭 여부

    def uniq_sum(self):
        return float(sum(self.uniq))


class MotionDiscriminator:
    """YOLO 다중 후보 + 배경 모션으로 '혼자 움직이는' 타겟 트랙을 고른다."""

    def __init__(self):
        self._prev = None        # 직전 프레임 gray float32
        self._tracks: list[_Track] = []

    def reset(self):
        self._prev = None
        self._tracks = []

    @property
    def track_count(self):
        return len(self._tracks)

    def update(self, gray_f32, cands, last_target=None, gate=120.0):
        """프레임당 1회. cands=[(cx,cy,score,...), ...] (YOLO detect_all).
        반환: 채택 트랙 (cx, cy, uniq누적) | None.
        last_target이 None이거나 (0,0)이면 게이트 없이 특이성 최고 트랙."""
        # 1) 배경 전역 변위
        bx = by = 0.0
        if self._prev is not None and gray_f32.shape == self._prev.shape:
            (bx, by), _ = cv2.phaseCorrelate(self._prev, gray_f32)
        self._prev = gray_f32

        # 2) 트랙-후보 연계 (탐욕 최근접) — 예상 위치 = 직전 위치 + 배경 변위
        for t in self._tracks:
            t.matched = False
        free = list(cands)
        # 안정 트랙(특이성 큰 것) 우선 매칭 — 타겟 트랙이 데칼에 후보를 뺏기지 않게
        for t in sorted(self._tracks, key=lambda t: -t.uniq_sum()):
            px, py = t.x + bx, t.y + by
            best = None
            r = MATCH_R + MATCH_R_GROW * t.miss   # 공백이 길수록 넓게 재매칭
            best_d2 = r * r
            for c in free:
                d2 = (c[0] - px) ** 2 + (c[1] - py) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best = c
            if best is not None:
                free.remove(best)
                dx_, dy_ = best[0] - t.x, best[1] - t.y
                # 3) 특이성 = 후보 변위가 배경 변위와 다른 정도
                t.uniq.append(min(UNIQ_CLIP, float(np.hypot(dx_ - bx, dy_ - by))))
                t.x, t.y = float(best[0]), float(best[1])
                t.score = float(best[2])
                t.miss = 0
                t.matched = True
            else:
                # 미매칭 — 배경과 같이 흘러간다고 가정하고 위치만 이류(재매칭 대비)
                t.x, t.y = px, py
                t.miss += 1
        self._tracks = [t for t in self._tracks if t.miss <= TRACK_MISS_MAX]
        for c in free:
            self._tracks.append(_Track(c[0], c[1], c[2]))

        # 4) 선택 — 연속성 게이트 내, 이번 프레임 실측 매칭된 트랙만.
        #    핵심 거부 규칙(추적 확립 후): score 강약 불문 "혼자 움직인다"가 증명된 트랙만.
        #    배경 데칼은 배경과 같이 흘러 특이성이 영원히 ≈0 → 강한 가짜라도 영구 거부.
        #    (신규 트랙은 UNIQ_MIN_OBS 프레임 관측 필요 — 타겟은 ~2.3px/f씩 쌓여 금방 통과.
        #     트랙이 검출 공백을 이류로 견디므로 짧은 끊김에 이력이 리셋되지 않는다)
        established = last_target is not None and last_target != (0, 0)
        pool = []
        for t in self._tracks:
            if not t.matched:
                continue
            if established and not (len(t.uniq) >= UNIQ_MIN_OBS
                                    and t.uniq_sum() >= UNIQ_MIN):
                continue   # 배경 동조 트랙(데칼) 거부 — 특이성 미증명
            pool.append(t)
        if established:
            g2 = gate * gate
            pool = [t for t in pool
                    if (t.x - last_target[0]) ** 2 + (t.y - last_target[1]) ** 2 <= g2]
        if not pool:
            return None
        best = max(pool, key=lambda t: t.uniq_sum() + SCORE_W * t.score)
        return (best.x, best.y, best.uniq_sum())
