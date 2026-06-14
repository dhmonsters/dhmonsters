# 투명 도형 ByteTrack 경량 MOT — 2단계 헝가리안 association으로 약검출 타겟 ID 유지 + 배경 공통속도 이상탐지
from __future__ import annotations

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

BT_GATE         = 30     # 예측위치 매칭 게이트 기본(px)
BT_GATE_GROW    = 8      # 미검출 1프레임당 게이트 확장(px)
BT_GATE_MAX     = 280    # 게이트 상한(px)
BT_JUMP_CAP     = 15     # 타겟 점프 상한(직전속도 위 여유, px) — 갈아타기 차단
BT_REL_MIN      = 7.0    # 배경과 다른 속도 임계(px/f) — 흐림 재선택(이상탐지)
BT_BG_REJECT    = 12     # 타겟 매칭 배경동조 거부(px) — 예측보다 배경흐름에 가까우면 데칼
BT_HIGH_THR     = 0.30   # 1단계 high score
BT_LOW_THR      = 0.10   # 2단계 low score 하한(반투명 타겟 0.18이 여기서 ID 유지)
BT_LOST_MAX     = 15     # 타겟 lost coast 유지 한계(프레임)
BT_TRK_MISS_MAX = 10     # 비타겟 트랙 제거 전 허용 미매칭
BT_DECAL_N      = 3      # 배경 계산에 쓸 대표 데칼 수(age 큰 상위 N개 — 전부 불필요)
BT_DECAL_AGE    = 3      # 배경 중앙값에 넣을 데칼 최소 age


class _BTrack:
    __slots__ = ("tid", "x", "y", "vx", "vy", "score", "age", "miss")

    def __init__(self, tid, x, y, score):
        self.tid = tid
        self.x = float(x); self.y = float(y)
        self.vx = 0.0; self.vy = 0.0
        self.score = float(score)
        self.age = 0; self.miss = 0


class ByteTracker:
    """ByteTrack 경량 MOT — 2단계 헝가리안 association + 배경 공통속도 이상탐지.
    흰색 잠금 타겟에 ID 부여, 모든 후보를 트랙으로 추적, 약검출(반투명 타겟)도
    2단계 매칭으로 ID 유지. 타겟 흐림 시 배경과 다른 속도 트랙으로 ID 승계."""

    def __init__(self):
        self._prev = None
        self._tracks: list[_BTrack] = []
        self._tid = None
        self._next = 0
        self._bgvx = 0.0; self._bgvy = 0.0

    def reset(self):
        self._prev = None; self._tracks = []; self._tid = None
        self._next = 0; self._bgvx = 0.0; self._bgvy = 0.0

    @property
    def locked(self):
        return self._tid is not None

    @property
    def bg_vel(self):
        return (self._bgvx, self._bgvy)

    @property
    def track_count(self):
        return len(self._tracks)

    def _new(self, x, y, score):
        t = _BTrack(self._next, x, y, score)
        self._next += 1
        self._tracks.append(t)
        return t

    def lock(self, x, y):
        """흰색 위치 최근접 트랙을 타겟으로 지정(없으면 생성). 간헐 표시 시 재확정."""
        best, bd = None, BT_GATE * BT_GATE
        for t in self._tracks:
            d = (t.x - x) ** 2 + (t.y - y) ** 2
            if d < bd:
                bd = d; best = t
        if best is None:
            best = self._new(x, y, 1.0)
        self._tid = best.tid

    def nudge(self, x, y):
        """흰색 가시 구간 — 타겟 트랙 위치를 밝기 중심으로 보정."""
        for t in self._tracks:
            if t.tid == self._tid:
                t.x = float(x); t.y = float(y); t.miss = 0
                return

    def _match(self, tracks, dets, bx, by):
        """예측위치 중심거리 헝가리안. 반환: (matches[(ti,di)], 미매칭트랙idx, 미매칭det idx)."""
        if not tracks or not dets:
            return [], list(range(len(tracks))), list(range(len(dets)))
        cost = np.full((len(tracks), len(dets)), 1e6, dtype=np.float64)
        for i, t in enumerate(tracks):
            if t.age > 0:
                px, py = t.x + t.vx, t.y + t.vy
            else:
                px, py = t.x + bx, t.y + by
            gate = min(BT_GATE_MAX, BT_GATE + BT_GATE_GROW * t.miss)
            if t.tid == self._tid:   # 타겟은 점프 상한 게이트로 갈아타기 차단
                spd = (t.vx * t.vx + t.vy * t.vy) ** 0.5
                gate = min(gate, spd + BT_JUMP_CAP)
            g2 = gate * gate
            for j, d in enumerate(dets):
                dd = (d[0] - px) ** 2 + (d[1] - py) ** 2
                if dd <= g2:
                    cost[i, j] = dd ** 0.5
        rows, cols = linear_sum_assignment(cost)
        matches = []
        ut = set(range(len(tracks))); ud = set(range(len(dets)))
        for r, c in zip(rows, cols):
            if cost[r, c] < 1e6:
                matches.append((r, c)); ut.discard(r); ud.discard(c)
        return matches, sorted(ut), sorted(ud)

    def _apply(self, t, d):
        t.vx = t.vx * 0.6 + (d[0] - t.x) * 0.4
        t.vy = t.vy * 0.6 + (d[1] - t.y) * 0.4
        t.x = float(d[0]); t.y = float(d[1]); t.score = float(d[2])
        t.age += 1; t.miss = 0

    def update(self, gray_f32, dets):
        """매 프레임. dets=[(cx,cy,score),...]. 타겟 트랙 위치 (x,y)|None 반환.
        gray_f32=None이면 phaseCorrelate 생략(jsonl 재시뮬용)."""
        # 타겟 직전 상태 보관(배경동조 매칭 검증용)
        _tg0 = next((t for t in self._tracks if t.tid == self._tid), None)
        _tg0_state = (_tg0.x, _tg0.y, _tg0.vx, _tg0.vy) if _tg0 is not None else None

        # 배경 전역 변위(폴백용)
        bx = by = 0.0
        if (gray_f32 is not None and self._prev is not None
                and gray_f32.shape == self._prev.shape):
            (bx, by), _ = cv2.phaseCorrelate(self._prev, gray_f32)
        if gray_f32 is not None:
            self._prev = gray_f32

        high = [d for d in dets if d[2] >= BT_HIGH_THR]
        low = [d for d in dets if BT_LOW_THR <= d[2] < BT_HIGH_THR]

        # 1단계: high score ↔ 전체 트랙
        m1, ut1, ud1 = self._match(self._tracks, high, bx, by)
        for ti, di in m1:
            self._apply(self._tracks[ti], high[di])
        # 2단계: low score ↔ 1단계 미매칭 트랙 (반투명 타겟 ID 유지의 핵심)
        rem = [self._tracks[i] for i in ut1]
        m2, _ut2, _ud2 = self._match(rem, low, bx, by)
        matched_rem = set()
        for ti, di in m2:
            self._apply(rem[ti], low[di]); matched_rem.add(ti)
        # 미매칭 트랙 coast
        for k, t in enumerate(rem):
            if k not in matched_rem:
                if t.age > 0:
                    t.x += t.vx; t.y += t.vy
                else:
                    t.x += bx; t.y += by
                t.miss += 1
                if t.tid == self._tid:   # 타겟 coast 시 속도 감쇠(폭주 방지)
                    t.vx *= 0.9; t.vy *= 0.9
        # 미매칭 high det 새 트랙
        for di in ud1:
            self._new(high[di][0], high[di][1], high[di][2])

        # 배경 공통속도 = 데칼 대표 3개(age 큰=오래 추적돼 안정) 속도 중앙값. 데칼 전부는
        # 불필요(3개로 전체와 동일 정확도, 인게임 확인) — 사용자 설계: 타겟1 + 데칼3 = 4개,
        # 데칼 많으면 상위 3개만. 타겟 위치와 무관한 독립 샘플. 2개 미만이면 phaseCorrelate.
        _decals = sorted(
            (t for t in self._tracks
             if t.tid != self._tid and t.age >= BT_DECAL_AGE and t.miss == 0),
            key=lambda t: -t.age)[:BT_DECAL_N]
        if len(_decals) >= 2:
            self._bgvx = float(np.median([t.vx for t in _decals]))
            self._bgvy = float(np.median([t.vy for t in _decals]))
        else:
            self._bgvx, self._bgvy = bx, by

        # 타겟이 배경동조 데칼을 매칭했으면 취소 → coast (예측보다 배경흐름에 더 가까움).
        # 5초대 회전 배경과 타겟 방향이 겹치는 순간 데칼로 갈아타는 것을 차단(인게임 확인).
        tgt = next((t for t in self._tracks if t.tid == self._tid), None)
        if tgt is not None and tgt.miss == 0 and _tg0_state is not None:
            _px = _tg0_state[0] + _tg0_state[2]
            _py = _tg0_state[1] + _tg0_state[3]
            _bgpx = _tg0_state[0] + self._bgvx
            _bgpy = _tg0_state[1] + self._bgvy
            _dpr = ((tgt.x - _px) ** 2 + (tgt.y - _py) ** 2) ** 0.5
            _dbg = ((tgt.x - _bgpx) ** 2 + (tgt.y - _bgpy) ** 2) ** 0.5
            if _dbg < _dpr and _dbg < BT_BG_REJECT:
                tgt.x, tgt.y = _px, _py     # 예측 복귀(coast)
                tgt.miss = 1
                tgt.vx *= 0.9; tgt.vy *= 0.9

        # 타겟 흐림(lost) → 배경과 다른 속도(이상) 트랙으로 ID 승계
        if tgt is not None and tgt.miss > 0:
            r2 = min(BT_GATE_MAX, BT_GATE + BT_GATE_GROW * tgt.miss)
            pool = [t for t in self._tracks
                    if t.tid != self._tid and t.miss == 0
                    and (t.x - tgt.x) ** 2 + (t.y - tgt.y) ** 2 <= r2 * r2
                    and ((t.vx - self._bgvx) ** 2
                         + (t.vy - self._bgvy) ** 2) ** 0.5 >= BT_REL_MIN]
            if pool:
                best = min(pool, key=lambda t: (t.x - tgt.x) ** 2
                           + (t.y - tgt.y) ** 2 - t.age)
                self._tid = best.tid
                tgt = best

        # 비타겟 트랙 정리
        self._tracks = [t for t in self._tracks
                        if t.miss <= BT_TRK_MISS_MAX or t.tid == self._tid]

        if tgt is not None:
            return (tgt.x, tgt.y) if tgt.miss <= BT_LOST_MAX else None
        return None
